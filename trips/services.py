"""
Trip rules: status lifecycle, RSVP, waitlist, completion and attendance.

Concurrency: every operation that changes seats locks the trip row first
(SELECT ... FOR UPDATE inside transaction.atomic). Two people trying to take
the last seat at the same moment are therefore processed one after the other:
the first gets 'confirmed', the second sees the trip full and is waitlisted.
The CHECK (confirmed_count <= participant_capacity) constraint is a second
safety net that makes overbooking impossible even if this code had a bug.

Status lifecycle:
    draft ──publish──▶ published ◀──▶ full        (automatic, by seat count)
      │                    │            │
      └──────cancel────────┴────────────┴──▶ cancelled
                           └──end passes (scheduled command)──▶ completed
"""
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import F, Max
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from core.models import ExperienceLevel
from notifications.models import NotificationType, ReferenceType
from notifications.services import notify

from .models import ParticipantStatus as PS
from .models import Trip, TripParticipant, TripStatus

ATTENDANCE_WINDOW = timedelta(days=7)

ALLOWED_TRANSITIONS = {
    TripStatus.DRAFT: {TripStatus.PUBLISHED, TripStatus.CANCELLED},
    TripStatus.PUBLISHED: {TripStatus.FULL, TripStatus.CANCELLED, TripStatus.COMPLETED},
    TripStatus.FULL: {TripStatus.PUBLISHED, TripStatus.CANCELLED, TripStatus.COMPLETED},
    TripStatus.CANCELLED: set(),
    TripStatus.COMPLETED: set(),
}
OPEN_STATUSES = (TripStatus.PUBLISHED, TripStatus.FULL)
ACTIVE_PARTICIPANT = (PS.CONFIRMED, PS.WAITLISTED)


class TripError(ValidationError):
    """A rule violation (HTTP 400) with a human-readable message."""


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def transition(trip: Trip, new_status: str) -> None:
    if new_status == trip.status:
        return
    if new_status not in ALLOWED_TRANSITIONS[trip.status]:
        raise TripError(f"A {trip.status} trip cannot become {new_status}.")
    trip.status = new_status


def _lock(trip) -> Trip:
    return Trip.objects.select_for_update().get(pk=trip.pk)


def _sync_full(trip: Trip) -> None:
    """published ⇄ full follows the seat count automatically."""
    if trip.status in OPEN_STATUSES:
        transition(trip, TripStatus.FULL if trip.confirmed_count >= trip.participant_capacity
                   else TripStatus.PUBLISHED)


def _save_seats(trip: Trip) -> None:
    trip.save(update_fields=["confirmed_count", "status", "updated_at"])


def _promote_waitlist(trip: Trip) -> list[TripParticipant]:
    """Fill free seats from the front of the waitlist. Caller holds the trip lock."""
    promoted = []
    while trip.confirmed_count < trip.participant_capacity:
        nxt = (TripParticipant.objects.select_for_update()
               .filter(trip=trip, status=PS.WAITLISTED).order_by("waitlist_position").first())
        if nxt is None:
            break
        position = nxt.waitlist_position
        nxt.status, nxt.waitlist_position = PS.CONFIRMED, None
        nxt.save()
        _close_gap(trip, position)
        trip.confirmed_count += 1
        promoted.append(nxt)
    return promoted


def _close_gap(trip: Trip, position: int) -> None:
    """Everyone behind `position` moves up one place (positions stay 1..n)."""
    TripParticipant.objects.filter(
        trip=trip, status=PS.WAITLISTED, waitlist_position__gt=position
    ).update(waitlist_position=F("waitlist_position") - 1)


def _notify_promoted(trip: Trip, promoted) -> None:
    for p in promoted:
        notify(p.user, NotificationType.WAITLIST_PROMOTED, ReferenceType.TRIP, trip.pk)


def _check_group_access(trip: Trip, user) -> None:
    group = trip.group
    if group and group.privacy_type == "private" and not group.memberships.filter(
        user=user, status="active"
    ).exists():
        raise TripError("This trip is only open to members of its private group.")


# --------------------------------------------------------------------------
# Organizer actions
# --------------------------------------------------------------------------
@transaction.atomic
def publish(trip: Trip) -> Trip:
    trip = _lock(trip)
    if trip.start_datetime <= timezone.now():
        raise TripError("A trip that has already started cannot be published.")
    transition(trip, TripStatus.PUBLISHED)
    _sync_full(trip)
    trip.save(update_fields=["status", "updated_at"])
    return trip


@transaction.atomic
def update_trip(trip: Trip, data: dict) -> Trip:
    """Organizer edits. Capacity changes re-balance seats; key changes notify people."""
    trip = _lock(trip)
    if trip.status not in (TripStatus.DRAFT, *OPEN_STATUSES):
        raise TripError(f"A {trip.status} trip cannot be edited.")
    new_capacity = data.get("participant_capacity", trip.participant_capacity)
    if new_capacity < trip.confirmed_count:
        raise TripError({"participant_capacity":
                         f"{trip.confirmed_count} people are already confirmed; capacity "
                         f"cannot be lower than that."})
    important = {"start_datetime", "end_datetime", "location", "meeting_point_name",
                 "meeting_latitude", "meeting_longitude"}
    changed_important = any(k in important and getattr(trip, k) != v for k, v in data.items())

    for field, value in data.items():
        setattr(trip, field, value)
    promoted = _promote_waitlist(trip) if trip.status in OPEN_STATUSES else []
    _sync_full(trip)
    trip.save()

    _notify_promoted(trip, promoted)
    if changed_important and trip.status in OPEN_STATUSES:
        for p in trip.participants.filter(status__in=ACTIVE_PARTICIPANT).select_related("user"):
            notify(p.user, NotificationType.TRIP_UPDATED, ReferenceType.TRIP, trip.pk,
                   actor=trip.organizer)
    return trip


@transaction.atomic
def cancel_trip(trip: Trip, actor) -> Trip:
    """Trips are never hard-deleted; cancelling keeps the history."""
    trip = _lock(trip)
    if trip.status == TripStatus.CANCELLED:
        raise TripError("This trip is already cancelled.")
    transition(trip, TripStatus.CANCELLED)
    trip.save(update_fields=["status", "updated_at"])
    for p in trip.participants.filter(status__in=ACTIVE_PARTICIPANT).select_related("user"):
        notify(p.user, NotificationType.TRIP_CANCELLED, ReferenceType.TRIP, trip.pk, actor=actor)
    return trip


# --------------------------------------------------------------------------
# RSVP
# --------------------------------------------------------------------------
@transaction.atomic
def rsvp(trip: Trip, user) -> TripParticipant:
    trip = _lock(trip)  # serialises concurrent RSVPs for this trip
    if trip.status not in OPEN_STATUSES:
        raise TripError(f"You cannot join a {trip.status} trip.")
    if trip.start_datetime <= timezone.now():
        raise TripError("This trip has already started.")
    if trip.organizer_id == user.pk:
        raise TripError("You are the organizer of this trip.")
    _check_group_access(trip, user)
    level = user.profile.camping_experience_level
    if ExperienceLevel.rank(level) < ExperienceLevel.rank(trip.min_experience_level):
        raise TripError(f"This trip requires at least '{trip.min_experience_level}' experience "
                        f"(your profile says '{level}').")

    existing = TripParticipant.objects.select_for_update().filter(trip=trip, user=user).first()
    if existing and existing.status in ACTIVE_PARTICIPANT:
        raise TripError(f"You have already joined this trip ({existing.status}).")

    if trip.confirmed_count < trip.participant_capacity:
        status, position = PS.CONFIRMED, None
        trip.confirmed_count += 1
    else:
        top = trip.participants.filter(status=PS.WAITLISTED).aggregate(m=Max("waitlist_position"))
        status, position = PS.WAITLISTED, (top["m"] or 0) + 1

    if existing:  # re-joining after a cancellation: reuse the row (UNIQUE trip+user)
        existing.status, existing.waitlist_position = status, position
        existing.attendance_marked_by = existing.attendance_marked_at = None
        existing.save()
        participant = existing
    else:
        participant = TripParticipant.objects.create(
            trip=trip, user=user, status=status, waitlist_position=position)

    _sync_full(trip)
    _save_seats(trip)
    notify(user, NotificationType.RSVP_CONFIRMED if status == PS.CONFIRMED
           else NotificationType.RSVP_WAITLISTED, ReferenceType.TRIP, trip.pk)
    return participant


@transaction.atomic
def cancel_rsvp(trip: Trip, user) -> TripParticipant:
    trip = _lock(trip)
    if trip.status not in OPEN_STATUSES:
        raise TripError(f"RSVPs cannot be changed on a {trip.status} trip.")
    participant = TripParticipant.objects.select_for_update().filter(
        trip=trip, user=user, status__in=ACTIVE_PARTICIPANT).first()
    if participant is None:
        raise TripError("You have not joined this trip.")

    promoted = []
    if participant.status == PS.CONFIRMED:
        participant.status = PS.CANCELLED
        participant.save()
        trip.confirmed_count -= 1
        promoted = _promote_waitlist(trip)  # the freed seat goes to waitlist #1
    else:
        position = participant.waitlist_position
        participant.status, participant.waitlist_position = PS.CANCELLED, None
        participant.save()
        _close_gap(trip, position)

    _sync_full(trip)
    _save_seats(trip)
    _notify_promoted(trip, promoted)
    return participant


# --------------------------------------------------------------------------
# After the trip
# --------------------------------------------------------------------------
def complete_finished_trips(now=None) -> dict:
    """
    Run on a schedule (management command `complete_trips`). Idempotent.
    - published/full trips whose end has passed → completed
      * confirmed participants stay 'confirmed' until the organizer records attendance
      * anyone still waitlisted is moved to 'cancelled'
    - drafts whose end has passed → cancelled (they never happened)
    """
    now = now or timezone.now()
    completed = 0
    for trip_id in Trip.objects.filter(status__in=OPEN_STATUSES, end_datetime__lt=now) \
            .values_list("id", flat=True):
        with transaction.atomic():
            trip = Trip.objects.select_for_update().get(pk=trip_id)
            if trip.status not in OPEN_STATUSES:
                continue  # changed meanwhile
            transition(trip, TripStatus.COMPLETED)
            trip.save(update_fields=["status", "updated_at"])
            trip.participants.filter(status=PS.WAITLISTED).update(
                status=PS.CANCELLED, waitlist_position=None)
            notify(trip.organizer, NotificationType.TRIP_REMINDER, ReferenceType.TRIP, trip.pk)
            completed += 1
    stale_drafts = Trip.objects.filter(status=TripStatus.DRAFT, end_datetime__lt=now) \
        .update(status=TripStatus.CANCELLED, updated_at=now)
    return {"completed": completed, "cancelled_drafts": stale_drafts}


@transaction.atomic
def mark_attendance(trip: Trip, organizer, records: list[dict]) -> list[TripParticipant]:
    """
    The organizer records who actually came. Only 'attended' participants can
    later review the campsite (enforced again by the database trigger).
    records = [{"user_id": 5, "status": "attended" | "no_show"}, ...]
    """
    trip = _lock(trip)
    now = timezone.now()
    if trip.status != TripStatus.COMPLETED:
        raise TripError("Attendance can be recorded once the trip is completed.")
    if now > trip.end_datetime + ATTENDANCE_WINDOW:
        raise TripError(f"Attendance must be recorded within {ATTENDANCE_WINDOW.days} days "
                        f"after the trip ends.")

    wanted = {r["user_id"]: r["status"] for r in records}
    participants = list(TripParticipant.objects.select_for_update().select_related("user").filter(
        trip=trip, user_id__in=wanted, status__in=[PS.CONFIRMED, PS.ATTENDED, PS.NO_SHOW]))
    missing = set(wanted) - {p.user_id for p in participants}
    if missing:
        raise TripError({"records": f"Not confirmed participants of this trip: {sorted(missing)}"})

    newly_attended = []
    for p in participants:
        new_status = wanted[p.user_id]
        if p.status != PS.ATTENDED and new_status == PS.ATTENDED:
            newly_attended.append(p)
        p.status = new_status
        p.attendance_marked_by = organizer
        p.attendance_marked_at = now
        try:
            with transaction.atomic():
                p.save()
        except IntegrityError as exc:  # review-gate trigger
            raise TripError({"records": f"User {p.user_id} has already reviewed this trip, so "
                                        f"their attendance cannot be changed."}) from exc
    for p in newly_attended:
        notify(p.user, NotificationType.REVIEW_UNLOCKED, ReferenceType.TRIP, trip.pk,
               actor=organizer)
    return participants


# --------------------------------------------------------------------------
# Account deletion
# --------------------------------------------------------------------------
def withdraw_user(user) -> None:
    """Called when an account is deleted: free their seats and cancel their upcoming trips."""
    for p in TripParticipant.objects.filter(user=user, status__in=ACTIVE_PARTICIPANT,
                                            trip__status__in=OPEN_STATUSES).select_related("trip"):
        cancel_rsvp(p.trip, user)
    for trip in Trip.objects.filter(organizer=user,
                                    status__in=[TripStatus.DRAFT, *OPEN_STATUSES]):
        cancel_trip(trip, user)
