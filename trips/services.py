"""
Trip rules: status lifecycle, RSVP, waitlist, completion and attendance.

Concurrency: every operation that changes seats locks the trip row first
(SELECT ... FOR UPDATE inside transaction.atomic). Two people trying to take
the last seat at the same moment are therefore processed one after the other:
the first gets 'confirmed', the second sees the trip full and is waitlisted.
The CHECK (confirmed_count <= participant_capacity) guards the stored counter,
and a deferred trigger (migration 0006) counts the real confirmed rows at COMMIT,
so overbooking is rejected even if a code path forgot the lock.

Status lifecycle:
    draft ──publish──▶ published ◀──▶ full        (automatic, by seat count)
      │                    │            │
      └──────cancel────────┴────────────┴──▶ cancelled
                           └──end passes (scheduled command)──▶ completed
"""
import hashlib
import hmac
from contextlib import contextmanager
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Max, Q
from django.db.models.functions import Lower, Trim
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import EmergencyContact
from core.models import ExperienceLevel
from notifications.models import NotificationType, ReferenceType
from notifications.services import notify, notify_admins

from .models import ParticipantStatus as PS
from .models import (
    ACTIVE_TRIP_STATUSES,
    AppealStatus,
    AttendanceAppeal,
    EmergencyContactAccess,
    FlagStatus,
    Trip,
    TripParticipant,
    TripStatus,
    VerificationMethod,
)

ATTENDANCE_WINDOW = timedelta(days=7)
CHECKIN_OPENS_BEFORE = timedelta(hours=2)
CHECKIN_CLOSES_AFTER = timedelta(hours=24)
EMERGENCY_MARGIN = timedelta(days=1)  # shared contacts readable 1 day before → 1 day after
OVERRIDE_FLAG_SHARE = 0.5  # flag when more than half of the attendees did not check in
OVERRIDE_FLAG_COUNT = 3    # ... or when this many did, however large the trip is
APPEAL_WINDOW = timedelta(days=14)  # a no-show can appeal until this long after the trip ends
PRIORITY_WINDOW = timedelta(hours=48)  # a repeated trip: past attendees may join first
RECAP_AFTER = timedelta(days=2)        # remind attendees to share a recap this long after the end
RECAP_UNTIL = timedelta(days=14)       # ...but never for trips older than this (first run, old data)

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
# Duplicate trips (same rules as the two DB constraints on trips)
# --------------------------------------------------------------------------
DUPLICATE_TITLE = "You already have an active trip called '{}'. Use a different title, or cancel that trip first."
OVERLAPPING_DATES = ("These dates overlap your trip '{}' ({}). An organizer can only lead "
                     "one trip at a time.")


def _short_date(dt) -> str:
    local = timezone.localtime(dt)  # "%-d" is not supported on Windows
    return f"{local.day} {local:%b %Y}"


def duplicate_trip_error(organizer, title, start, end, exclude_pk=None) -> dict | None:
    """Friendly message when the organizer already has an active trip with this title
    (ignoring capitals and outer spaces) or one whose dates overlap. None if OK."""
    active = Trip.objects.filter(organizer=organizer, status__in=ACTIVE_TRIP_STATUSES)
    if exclude_pk:
        active = active.exclude(pk=exclude_pk)
    same = active.annotate(t=Lower(Trim("title"))).filter(t=title.strip().lower()).first()
    if same:  # conflicting_trip_id lets the form link to the trip that's in the way
        return {"title": DUPLICATE_TITLE.format(same.title), "conflicting_trip_id": same.pk}
    overlap = active.filter(start_datetime__lt=end, end_datetime__gt=start).first()
    if overlap:
        when = f"{_short_date(overlap.start_datetime)} – {_short_date(overlap.end_datetime)}"
        return {"start_datetime": OVERLAPPING_DATES.format(overlap.title, when),
                "conflicting_trip_id": overlap.pk}
    return None


@contextmanager
def duplicate_guard():
    """Turns a DB constraint violation (two requests at the same moment that both
    passed duplicate_trip_error) into the same HTTP 400 instead of a 500."""
    try:
        with transaction.atomic():
            yield
    except IntegrityError as exc:
        if "trips_unique_active_title_per_organizer" in str(exc):
            raise TripError({"title": "You already have an active trip with this title."}) from exc
        if "trips_no_overlap_per_organizer" in str(exc):
            raise TripError({"start_datetime": "You already have an active trip at this time."}) from exc
        raise


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
    invited = []
    if trip.repeat_of_id and trip.priority_until is None:
        trip.priority_until = timezone.now() + PRIORITY_WINDOW
        invited = list(past_attendees(trip))
    trip.save(update_fields=["status", "priority_until", "updated_at"])
    for person in invited:
        notify(person, NotificationType.TRIP_REPEATED, ReferenceType.TRIP, trip.pk, actor=trip.organizer)
    return trip


def past_attendees(trip: Trip):
    """People who attended the trip this one repeats (they are invited and may join first)."""
    from accounts.models import User  # local import: accounts depends on trips
    if not trip.repeat_of_id:
        return User.objects.none()
    return User.objects.filter(trip_participations__trip_id=trip.repeat_of_id,
                               trip_participations__status=PS.ATTENDED).exclude(pk=trip.organizer_id)


def in_priority_window(trip: Trip, now=None) -> bool:
    return bool(trip.priority_until and (now or timezone.now()) < trip.priority_until)


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
    with duplicate_guard():
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
    if in_priority_window(trip) and not past_attendees(trip).filter(pk=user.pk).exists():
        raise TripError(f"People who came on the previous trip can join first, until "
                        f"{timezone.localtime(trip.priority_until):%d %b %H:%M}. Try again after that.")
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
        existing.checked_in_at, existing.verification_method, existing.override_reason = None, "", ""
        existing.share_emergency_contact = False
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
    return {"completed": completed, "cancelled_drafts": stale_drafts,
            "recap_reminders": send_recap_reminders(now)}


def send_recap_reminders(now=None) -> int:
    """
    Two days after a trip, invite the people who were there to share a recap in the
    trip posts. Once per trip; skips people who already posted there. Returns how many
    people were reminded.

    It waits until the organizer has recorded attendance (or the 7 days to do so are
    over): before that nobody counts as 'attended', and the reminder would miss everyone.
    """
    from social.models import Post  # local import: social depends on trips
    now = now or timezone.now()
    sent = 0
    due = (Trip.objects.filter(status=TripStatus.COMPLETED, recap_reminder_sent_at__isnull=True,
                               end_datetime__lte=now - RECAP_AFTER, end_datetime__gte=now - RECAP_UNTIL)
           .annotate(unmarked=Count("participants", filter=Q(participants__status=PS.CONFIRMED)))
           .filter(Q(unmarked=0) | Q(end_datetime__lte=now - ATTENDANCE_WINDOW))
           .values_list("id", flat=True))
    for trip_id in due:
        with transaction.atomic():
            trip = Trip.objects.select_for_update().get(pk=trip_id)
            if trip.recap_reminder_sent_at:
                continue  # another run got here first
            posted = set(Post.objects.filter(trip=trip).values_list("user_id", flat=True))
            people = {p.user for p in trip.participants.filter(status=PS.ATTENDED).select_related("user")}
            people.add(trip.organizer)
            for person in people:
                if person.pk not in posted and person.is_active:
                    notify(person, NotificationType.RECAP_REMINDER, ReferenceType.TRIP, trip.pk)
                    sent += 1
            trip.recap_reminder_sent_at = now
            trip.save(update_fields=["recap_reminder_sent_at", "updated_at"])
    return sent


# --------------------------------------------------------------------------
# Check-in (participant side of attendance)
# --------------------------------------------------------------------------
def checkin_code(trip: Trip) -> str:
    """
    The trip's 6-digit check-in code. Derived from SECRET_KEY + the trip's salt,
    never stored, so reading the database does not reveal it.
    """
    msg = f"trip-checkin:{trip.pk}:{trip.checkin_salt}".encode()
    digest = hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()
    return f"{int(digest, 16) % 1_000_000:06d}"


def checkin_window(trip: Trip) -> tuple:
    """Open from 2 h before the start (meeting point, usually has signal) until
    24 h after the end (for people who had no signal at the campsite)."""
    return trip.start_datetime - CHECKIN_OPENS_BEFORE, trip.end_datetime + CHECKIN_CLOSES_AFTER


def checkin_is_open(trip: Trip, now=None) -> bool:
    opens, closes = checkin_window(trip)
    now = now or timezone.now()
    return trip.status in (*OPEN_STATUSES, TripStatus.COMPLETED) and opens <= now <= closes


@transaction.atomic
def check_in(trip: Trip, user, code: str) -> TripParticipant:
    """A confirmed participant enters the organizer's code. Records checked_in_at."""
    trip = _lock(trip)
    if not checkin_is_open(trip):
        opens, closes = checkin_window(trip)
        raise TripError(f"Check-in is open from {timezone.localtime(opens):%d %b %H:%M} "
                        f"until {timezone.localtime(closes):%d %b %H:%M}.")
    participant = TripParticipant.objects.select_for_update().filter(
        trip=trip, user=user, status__in=[PS.CONFIRMED, PS.ATTENDED, PS.NO_SHOW]).first()
    if participant is None:
        raise TripError("Only confirmed participants can check in.")
    if not hmac.compare_digest(str(code).strip(), checkin_code(trip)):
        raise TripError({"code": "That code is not right. Ask the organizer for the trip code."})
    if participant.checked_in_at is None:
        participant.checked_in_at = timezone.now()
        if participant.verification_method == VerificationMethod.ORGANIZER_ONLY:
            # Already confirmed by the organizer: the late check-in upgrades the proof.
            participant.verification_method = VerificationMethod.CHECK_IN
        participant.save()
    return participant


# --------------------------------------------------------------------------
# Attendance (organizer side) and the suspicious-trip flag
# --------------------------------------------------------------------------
@transaction.atomic
def mark_attendance(trip: Trip, organizer, records: list[dict]) -> list[TripParticipant]:
    """
    The organizer records who actually came. Only 'attended' participants can
    later review the campsite (enforced again by the database trigger).
    records = [{"user_id": 5, "status": "attended" | "no_show", "reason": "..."}, ...]

    Attended needs both sides: a participant who checked in is verified by
    'check_in'. Someone who did not check in (e.g. forgot, no signal) can still
    be marked attended, but only with a written reason ('organizer_only'); the
    review then shows the weaker badge, and a trip where most attendees (or 3 or
    more of them) have no check-in is flagged for an admin. An admin's decision on
    an appeal stands: the organizer cannot turn that person back into a no-show.
    """
    trip = _lock(trip)
    now = timezone.now()
    if trip.status != TripStatus.COMPLETED:
        raise TripError("Attendance can be recorded once the trip is completed.")
    if now > trip.end_datetime + ATTENDANCE_WINDOW:
        raise TripError(f"Attendance must be recorded within {ATTENDANCE_WINDOW.days} days "
                        f"after the trip ends.")

    wanted = {r["user_id"]: r for r in records}
    participants = list(TripParticipant.objects.select_for_update().select_related("user").filter(
        trip=trip, user_id__in=wanted, status__in=[PS.CONFIRMED, PS.ATTENDED, PS.NO_SHOW]))
    missing = set(wanted) - {p.user_id for p in participants}
    if missing:
        raise TripError({"records": f"Not confirmed participants of this trip: {sorted(missing)}"})

    decided = set(AttendanceAppeal.objects.filter(
        participant__in=participants, status=AppealStatus.APPROVED,
    ).values_list("participant__user_id", flat=True))
    overruled = sorted(u for u in decided if wanted[u]["status"] != PS.ATTENDED)
    if overruled:
        raise TripError({"records": f"An admin approved the appeal of these people, so they "
                                    f"stay attended: {overruled}"})
    participants = [p for p in participants if p.user_id not in decided]

    no_reason = [p.user_id for p in participants
                 if wanted[p.user_id]["status"] == PS.ATTENDED and p.checked_in_at is None
                 and not (wanted[p.user_id].get("reason") or "").strip()]
    if no_reason:
        raise TripError({"records": f"These people did not check in, so give a reason to mark "
                                    f"them attended: {sorted(no_reason)}"})

    newly_attended = []
    for p in participants:
        record = wanted[p.user_id]
        new_status = record["status"]
        if p.status != PS.ATTENDED and new_status == PS.ATTENDED:
            newly_attended.append(p)
        p.status = new_status
        if new_status == PS.ATTENDED and p.checked_in_at:
            p.verification_method, p.override_reason = VerificationMethod.CHECK_IN, ""
        elif new_status == PS.ATTENDED:
            p.verification_method = VerificationMethod.ORGANIZER_ONLY
            p.override_reason = record["reason"].strip()[:500]
        else:
            p.verification_method, p.override_reason = "", ""
        p.attendance_marked_by = organizer
        p.attendance_marked_at = now
        try:
            with transaction.atomic():
                p.save()
        except IntegrityError as exc:  # review-gate trigger
            raise TripError({"records": f"User {p.user_id} has already reviewed this trip, so "
                                        f"their attendance cannot be changed."}) from exc
    # The organizer corrected their own mistake: nothing is left for an admin to decide.
    AttendanceAppeal.objects.filter(participant__in=newly_attended, status=AppealStatus.OPEN).update(
        status=AppealStatus.APPROVED, decided_by=organizer, decided_at=now,
        decision_note="The organizer corrected the attendance.")
    _flag_if_suspicious(trip, now)
    for p in newly_attended:
        notify(p.user, NotificationType.REVIEW_UNLOCKED, ReferenceType.TRIP, trip.pk,
               actor=organizer)
    return participants


def _flag_if_suspicious(trip: Trip, now) -> None:
    """More than half of the attendees, or 3 or more, without a check-in → an admin should look."""
    if trip.flag_status != FlagStatus.NONE:
        return  # already flagged or already checked by an admin
    attended = trip.participants.filter(status=PS.ATTENDED)
    total = attended.count()
    overrides = attended.filter(verification_method=VerificationMethod.ORGANIZER_ONLY).count()
    if total and (overrides / total > OVERRIDE_FLAG_SHARE or overrides >= OVERRIDE_FLAG_COUNT):
        trip.flag_status = FlagStatus.NEEDS_REVIEW
        trip.flag_note = (f"{overrides} of {total} attendees were marked attended without "
                          f"checking in.")
        trip.flagged_at = now
        trip.save(update_fields=["flag_status", "flag_note", "flagged_at", "updated_at"])
        notify_admins(NotificationType.TRIP_FLAGGED, ReferenceType.TRIP, trip.pk,
                      exclude=[trip.organizer_id])


# --------------------------------------------------------------------------
# No-show appeals: the participant asks, an admin decides
# --------------------------------------------------------------------------
def appeal_is_open(trip: Trip, now=None) -> bool:
    return (now or timezone.now()) <= trip.end_datetime + APPEAL_WINDOW


@transaction.atomic
def submit_appeal(trip: Trip, user, reason: str) -> AttendanceAppeal:
    trip = _lock(trip)
    participant = TripParticipant.objects.select_for_update().filter(trip=trip, user=user).first()
    if participant is None or participant.status != PS.NO_SHOW:
        raise TripError("Only people marked as a no-show on this trip can appeal.")
    if not appeal_is_open(trip):
        raise TripError(f"Appeals close {APPEAL_WINDOW.days} days after the trip ends.")
    if AttendanceAppeal.objects.filter(participant=participant).exists():
        raise TripError("You have already appealed this no-show.")
    appeal = AttendanceAppeal.objects.create(participant=participant, reason=reason.strip()[:2000])
    notify_admins(NotificationType.APPEAL_SUBMITTED, ReferenceType.TRIP, trip.pk, actor=user,
                  exclude=[user.pk, trip.organizer_id])
    notify(trip.organizer, NotificationType.APPEAL_ON_MY_TRIP, ReferenceType.TRIP, trip.pk, actor=user)
    return appeal


@transaction.atomic
def decide_appeal(appeal: AttendanceAppeal, admin, approve: bool, note: str = "") -> AttendanceAppeal:
    """Approving makes the person attended, so they can review. Refusing needs a note."""
    trip = _lock(appeal.participant.trip)
    appeal = AttendanceAppeal.objects.select_for_update().get(pk=appeal.pk)
    participant = TripParticipant.objects.select_for_update().select_related("user").get(
        pk=appeal.participant_id)
    if appeal.status != AppealStatus.OPEN:
        raise TripError("This appeal has already been decided.")
    if admin.pk in (trip.organizer_id, participant.user_id):
        raise TripError("You are involved in this trip, so another admin must decide.")
    note = note.strip()
    if not approve and not note:
        raise TripError("Say why the appeal is not approved.")

    now = timezone.now()
    if approve:
        participant.status = PS.ATTENDED
        participant.attendance_marked_by = admin
        participant.attendance_marked_at = now
        if participant.checked_in_at:  # the check-in proves it; the normal badge is correct
            participant.verification_method, participant.override_reason = VerificationMethod.CHECK_IN, ""
        else:
            participant.verification_method = VerificationMethod.ADMIN_APPEAL
            participant.override_reason = (note or "Approved on appeal by an admin.")[:500]
        participant.save()
    appeal.status = AppealStatus.APPROVED if approve else AppealStatus.REJECTED
    appeal.decided_by, appeal.decided_at, appeal.decision_note = admin, now, note
    appeal.save()
    notify(participant.user, NotificationType.APPEAL_APPROVED if approve
           else NotificationType.APPEAL_REJECTED, ReferenceType.TRIP, trip.pk)
    return appeal


# --------------------------------------------------------------------------
# Emergency contacts: opt-in sharing with the organizer, around the trip only
# --------------------------------------------------------------------------
def emergency_window(trip: Trip) -> tuple:
    """The organizer can read shared contacts from 1 day before the start to 1 day after the end."""
    return trip.start_datetime - EMERGENCY_MARGIN, trip.end_datetime + EMERGENCY_MARGIN


def emergency_window_is_open(trip: Trip, now=None) -> bool:
    opens, closes = emergency_window(trip)
    now = now or timezone.now()
    return trip.status != TripStatus.CANCELLED and opens <= now <= closes


@transaction.atomic
def set_emergency_sharing(trip: Trip, user, share: bool) -> TripParticipant:
    """A confirmed participant turns sharing of their emergency contact on or off."""
    participant = TripParticipant.objects.select_for_update().filter(
        trip=trip, user=user, status__in=[PS.CONFIRMED, PS.ATTENDED]).first()
    if participant is None:
        raise TripError("Only confirmed participants can share an emergency contact.")
    if share and not EmergencyContact.objects.filter(user=user).exists():
        raise TripError("Add an emergency contact to your profile first.")
    participant.share_emergency_contact = share
    participant.save(update_fields=["share_emergency_contact", "status_changed_at"])
    return participant


@transaction.atomic
def read_emergency_contacts(trip: Trip, organizer) -> list[dict]:
    """
    The organizer reads the contacts participants chose to share — only inside the
    emergency window. Every read is logged, and each participant is told (once
    per trip) that the organizer opened their contact.
    """
    if trip.organizer_id != organizer.pk:
        raise TripError("Only the trip organizer can see shared emergency contacts.")
    if not emergency_window_is_open(trip):
        opens, closes = emergency_window(trip)
        raise TripError(f"Shared emergency contacts can be opened from "
                        f"{timezone.localtime(opens):%d %b %H:%M} until "
                        f"{timezone.localtime(closes):%d %b %H:%M}.")
    rows = (TripParticipant.objects
            .filter(trip=trip, share_emergency_contact=True, status__in=[PS.CONFIRMED, PS.ATTENDED],
                    user__emergency_contact__isnull=False)
            .select_related("user__emergency_contact", "user__profile"))
    result = []
    for p in rows:
        contact = p.user.emergency_contact
        first_view = not EmergencyContactAccess.objects.filter(trip=trip, participant=p.user).exists()
        EmergencyContactAccess.objects.create(trip=trip, organizer=organizer, participant=p.user)
        if first_view:
            notify(p.user, NotificationType.EMERGENCY_CONTACT_VIEWED, ReferenceType.TRIP, trip.pk,
                   actor=organizer)
        result.append({"user_id": p.user_id, "display_name": p.user.profile.display_name,
                       "name": contact.name, "phone": contact.phone,
                       "relationship": contact.relationship})
    return result


# --------------------------------------------------------------------------
# Account deletion
# --------------------------------------------------------------------------
def withdraw_user(user) -> None:
    """Called when an account is deleted: free their seats and cancel their upcoming trips.
    Their appeals go too: the written reason is personal data."""
    AttendanceAppeal.objects.filter(participant__user=user).delete()
    for p in TripParticipant.objects.filter(user=user, status__in=ACTIVE_PARTICIPANT,
                                            trip__status__in=OPEN_STATUSES).select_related("trip"):
        cancel_rsvp(p.trip, user)
    for trip in Trip.objects.filter(organizer=user,
                                    status__in=[TripStatus.DRAFT, *OPEN_STATUSES]):
        cancel_trip(trip, user)
