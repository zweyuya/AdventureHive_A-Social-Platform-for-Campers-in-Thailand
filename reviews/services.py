"""
Trip-verified reviews.

Who may review (checked here with clear messages, and again by the database
trigger `reviews_enforce_attended`, so no code path can bypass it):
  * the trip is completed
  * the organizer recorded the reviewer as ATTENDED
  * the reviewer is not the trip's organizer
  * one review per person per trip
  * within REVIEW_WINDOW after the trip ended
The campsite is always taken from the trip, so a review can't be attached to a
different campsite. Ratings are recalculated in the same transaction.
"""
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import IntegrityError, transaction
from django.db.models import Avg, Count
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from locations.models import Location
from trips.models import ParticipantStatus as PS
from trips.models import TripParticipant, TripStatus

from .models import Review, ReviewStatus

REVIEW_WINDOW = timedelta(days=30)


class ReviewError(ValidationError):
    """A review rule was broken (HTTP 400)."""


def recalculate_rating(location_id: int) -> Location:
    """avg_rating / review_count from PUBLISHED reviews only. Caller is inside a transaction."""
    location = Location.objects.select_for_update().get(pk=location_id)
    agg = Review.objects.filter(location_id=location_id, status=ReviewStatus.PUBLISHED) \
        .aggregate(avg=Avg("rating"), n=Count("id"))
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
    attended = TripParticipant.objects.filter(trip=trip, user=user, status=PS.ATTENDED).exists()
    if not attended:
        return "Only participants the organizer marked as attended can review this trip."
    if Review.objects.filter(trip=trip, user=user).exists():
        return "You have already reviewed this trip."
    if timezone.now() > trip.end_datetime + REVIEW_WINDOW:
        return f"Reviews must be written within {REVIEW_WINDOW.days} days after the trip."
    return None


@transaction.atomic
def create_review(user, trip, rating: int, review_text: str = "") -> Review:
    Location.objects.select_for_update().get(pk=trip.location_id)  # serialise rating updates
    reason = review_eligibility(trip, user)
    if reason:
        raise ReviewError(reason)
    try:
        with transaction.atomic():
            review = Review.objects.create(trip=trip, user=user, location_id=trip.location_id,
                                           rating=rating, review_text=review_text)
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
    for field in ("rating", "review_text"):
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
def set_review_status(review: Review, status: str) -> Review:
    """Moderators hide / restore a review; ratings follow."""
    review = Review.objects.select_for_update().get(pk=review.pk)
    review.status = status
    review.save(update_fields=["status"])
    recalculate_rating(review.location_id)
    return review
