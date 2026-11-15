"""
Trip-verified reviews.

Who may review (checked here with clear messages, and again by the database
trigger `reviews_enforce_attended`, so no code path can bypass it):
  * the trip is completed
  * the organizer recorded the reviewer as ATTENDED
  * the reviewer is not the trip's organizer
  * one review per person per trip
  * within REVIEW_WINDOW after the trip ended
  * the trip has not been flagged as suspicious by an admin
The campsite is always taken from the trip, so a review can't be attached to a
different campsite. Ratings are recalculated in the same transaction and count
only each person's newest review of a campsite.
"""
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, F, Q, Subquery
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from locations.models import Location
from notifications.models import NotificationType, ReferenceType
from notifications.services import notify_admins
from trips.models import ParticipantStatus as PS
from trips.models import FlagStatus, Trip, TripParticipant, TripStatus

from .models import HiddenReason, Review, ReviewReport, ReviewStatus, ReportStatus

REVIEW_WINDOW = timedelta(days=30)
REPORT_ESCALATION = 3  # this many open reports: top of the moderation queue, admins notified


class ReviewError(ValidationError):
    """A review rule was broken (HTTP 400)."""


def counted_reviews(location_id: int):
    """
    The reviews that count toward a campsite's rating: published, and only the
    newest one per person (someone who camped there five times counts once).
    """
    latest_ids = Review.objects.filter(location_id=location_id, status=ReviewStatus.PUBLISHED) \
        .order_by("user_id", "-created_at").distinct("user_id").values("id")
    return Review.objects.filter(id__in=Subquery(latest_ids))


def recalculate_rating(location_id: int) -> Location:
    """avg_rating / review_count from counted reviews only. Caller is inside a transaction."""
    location = Location.objects.select_for_update().get(pk=location_id)
    agg = counted_reviews(location_id).aggregate(avg=Avg("rating"), n=Count("id"))
    location.review_count = agg["n"]
    location.avg_rating = (
        Decimal(agg["avg"]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if agg["n"] else None
    )
    location.save(update_fields=["avg_rating", "review_count", "updated_at"])
    return location


def review_eligibility(trip, user) -> str | None:
    """None if the user may review this trip now, otherwise the reason why not."""
    if trip.status != TripStatus.COMPLETED:
        return "You can review a trip once it is completed."
    if trip.organizer_id == user.pk:
        return "Organizers cannot review their own trip."
    if trip.flag_status == FlagStatus.REVIEWS_HIDDEN:
        return "Reviews are closed for this trip after a moderator check."
    attended = TripParticipant.objects.filter(trip=trip, user=user, status=PS.ATTENDED).exists()
    if not attended:
        return "Only participants the organizer marked as attended can review this trip."
    if Review.objects.filter(trip=trip, user=user).exists():
        return "You have already reviewed this trip."
    if timezone.now() > trip.end_datetime + REVIEW_WINDOW:
        return f"Reviews must be written within {REVIEW_WINDOW.days} days after the trip."
    return None


@transaction.atomic
def create_review(user, trip, rating: int, review_text: str = "",
                  organizer_rating: int | None = None) -> Review:
    Location.objects.select_for_update().get(pk=trip.location_id)  # serialise rating updates
    reason = review_eligibility(trip, user)
    if reason:
        raise ReviewError(reason)
    try:
        with transaction.atomic():
            review = Review.objects.create(trip=trip, user=user, location_id=trip.location_id,
                                           rating=rating, review_text=review_text,
                                           organizer_rating=organizer_rating)
    except IntegrityError as exc:  # trigger / unique constraint as last line of defence
        raise ReviewError("This review is not allowed.") from exc
    recalculate_rating(trip.location_id)
    return review


@transaction.atomic
def update_review(review: Review, data: dict) -> Review:
    review = Review.objects.select_for_update().select_related("trip").get(pk=review.pk)
    if review.status == ReviewStatus.HIDDEN:
        raise ReviewError("A hidden review cannot be edited.")
    if timezone.now() > review.trip.end_datetime + REVIEW_WINDOW:
        raise ReviewError(f"Reviews can only be edited within {REVIEW_WINDOW.days} days "
                          f"after the trip.")
    for field in ("rating", "review_text", "organizer_rating"):
        if field in data:
            setattr(review, field, data[field])
    review.edited_at = timezone.now()
    review.save()
    recalculate_rating(review.location_id)
    return review


@transaction.atomic
def delete_review(review: Review) -> None:
    location_id = review.location_id
    review.delete()
    recalculate_rating(location_id)


@transaction.atomic
def set_review_status(review: Review, status: str, reason: str = HiddenReason.MODERATOR) -> Review:
    """Moderators hide / restore a review; ratings follow."""
    review = Review.objects.select_for_update().get(pk=review.pk)
    review.status = status
    review.hidden_reason = reason if status == ReviewStatus.HIDDEN else HiddenReason.NONE
    review.save(update_fields=["status", "hidden_reason"])
    recalculate_rating(review.location_id)
    return review


# --------------------------------------------------------------------------
# Reports (members flag a review, a moderator decides)
# --------------------------------------------------------------------------
@transaction.atomic
def report_review(review: Review, user, reason: str, details: str = "") -> ReviewReport:
    review = Review.objects.select_for_update().get(pk=review.pk)  # so only one report is the third
    if review.user_id == user.pk:
        raise ReviewError("You cannot report your own review.")
    if review.status != ReviewStatus.PUBLISHED:
        raise ReviewError("This review is already hidden.")
    report, created = ReviewReport.objects.get_or_create(
        review=review, reporter=user, defaults={"reason": reason, "details": details[:2000]})
    if not created:
        raise ReviewError("You have already reported this review.")
    if review.reports.filter(status=ReportStatus.OPEN).count() == REPORT_ESCALATION:
        notify_admins(NotificationType.REVIEW_ESCALATED, ReferenceType.REVIEW, review.pk)
    return report


@transaction.atomic
def resolve_reports(review: Review, moderator, hide: bool) -> int:
    """Close all open reports on a review: hide it (actioned) or keep it (dismissed)."""
    if hide:
        set_review_status(review, ReviewStatus.HIDDEN, HiddenReason.MODERATOR)
    return review.reports.filter(status=ReportStatus.OPEN).update(
        status=ReportStatus.ACTIONED if hide else ReportStatus.DISMISSED,
        resolved_by=moderator, resolved_at=timezone.now())


# --------------------------------------------------------------------------
# Suspicious trips (admin)
# --------------------------------------------------------------------------
@transaction.atomic
def flag_trip_hide_reviews(trip, moderator, note: str = "") -> int:
    """Admin decides a trip looks fake: hide all its reviews and block new ones."""
    trip = Trip.objects.select_for_update().get(pk=trip.pk)
    trip.flag_status = FlagStatus.REVIEWS_HIDDEN
    trip.flag_note = note or trip.flag_note or "Flagged by a moderator."
    trip.flagged_at = timezone.now()
    trip.save(update_fields=["flag_status", "flag_note", "flagged_at", "updated_at"])
    hidden = 0
    for review in trip.reviews.filter(status=ReviewStatus.PUBLISHED):
        set_review_status(review, ReviewStatus.HIDDEN, HiddenReason.TRIP_FLAGGED)
        hidden += 1
    return hidden


@transaction.atomic
def clear_trip_flag(trip, moderator) -> int:
    """Admin checked the trip and it is fine: restore the reviews the flag had hidden."""
    trip = Trip.objects.select_for_update().get(pk=trip.pk)
    trip.flag_status = FlagStatus.CLEARED
    trip.save(update_fields=["flag_status", "updated_at"])
    restored = 0
    for review in trip.reviews.filter(hidden_reason=HiddenReason.TRIP_FLAGGED):
        set_review_status(review, ReviewStatus.PUBLISHED)
        restored += 1
    return restored


# --------------------------------------------------------------------------
# Organizer stats (shown on the trip page and the organizer's profile)
# --------------------------------------------------------------------------
MIN_ATTENDEES = 2           # a trip with fewer people at it does not count
MIN_ORGANIZER_RATERS = 3    # no average is shown until this many different people rated


def counted_trips(organizer):
    """
    Trips that count toward an organizer's record. Hard to fake on purpose:
    completed (not planned or cancelled), not flagged as suspicious by the system or an
    admin, at least 2 attendees, and at least half of them checked in with the trip code
    (so the organizer's word alone is not enough).
    """
    attended = Q(participants__status=PS.ATTENDED)
    return (Trip.objects.filter(organizer=organizer, status=TripStatus.COMPLETED)
            .exclude(flag_status__in=[FlagStatus.NEEDS_REVIEW, FlagStatus.REVIEWS_HIDDEN])
            .annotate(n_attended=Count("participants", filter=attended),
                      n_checked_in=Count("participants",
                                         filter=attended & Q(participants__checked_in_at__isnull=False)))
            .filter(n_attended__gte=MIN_ATTENDEES, n_checked_in__gte=F("n_attended") / 2.0))


def organizer_stats(organizer) -> dict:
    trips = counted_trips(organizer)
    trip_ids = list(trips.values_list("pk", flat=True))
    campers = (TripParticipant.objects.filter(trip_id__in=trip_ids, status=PS.ATTENDED)
               .values("user_id").distinct().count())
    # Each person counts once: their newest organizer rating for this organizer.
    newest = (Review.objects.filter(trip_id__in=trip_ids, status=ReviewStatus.PUBLISHED,
                                    organizer_rating__isnull=False)
              .order_by("user_id", "-created_at").distinct("user_id").values("id"))
    rated = Review.objects.filter(id__in=Subquery(newest)).aggregate(
        avg=Avg("organizer_rating"), n=Count("id"))
    shown = rated["n"] >= MIN_ORGANIZER_RATERS
    return {
        "trips_run": len(trip_ids),
        "campers": campers,
        # Cancelled after people had joined (cancelling an empty draft is not held against anyone).
        "cancelled": Trip.objects.filter(organizer=organizer, status=TripStatus.CANCELLED,
                                         participants__isnull=False).distinct().count(),
        "rating": round(float(rated["avg"]), 1) if shown else None,
        "rating_count": rated["n"],
        "min_ratings": MIN_ORGANIZER_RATERS,
    }
