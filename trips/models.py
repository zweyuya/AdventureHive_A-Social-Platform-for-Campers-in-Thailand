import secrets

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.db.models.constraints import Deferrable

from core.geo import in_thailand_q, validate_th_latitude, validate_th_longitude
from core.models import ExperienceLevel, TimeStampedModel


class ActivityType(models.TextChoices):
    CAMPING = "camping", "Camping"


class DifficultyLevel(models.TextChoices):
    EASY = "easy", "Easy"
    MODERATE = "moderate", "Moderate"
    DIFFICULT = "difficult", "Difficult"
    STRENUOUS = "strenuous", "Strenuous"


class TripStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"
    FULL = "full", "Full"
    CANCELLED = "cancelled", "Cancelled"
    COMPLETED = "completed", "Completed"


class EquipmentProvider(models.TextChoices):
    ORGANIZER = "organizer", "Organizer"
    PARTICIPANT = "participant", "Participant"


class ParticipantStatus(models.TextChoices):
    CONFIRMED = "confirmed", "Confirmed"
    WAITLISTED = "waitlisted", "Waitlisted"
    CANCELLED = "cancelled", "Cancelled"
    ATTENDED = "attended", "Attended"   # set by the organizer after the trip
    NO_SHOW = "no_show", "No-show"      # set by the organizer after the trip


class VerificationMethod(models.TextChoices):
    """How an 'attended' record was verified (shown on the review as a badge)."""

    CHECK_IN = "check_in", "Checked in with the trip code"
    ORGANIZER_ONLY = "organizer_only", "Confirmed by the organizer only"


class FlagStatus(models.TextChoices):
    """Admin review of trips whose attendance looks suspicious."""

    NONE = "", "Not flagged"
    NEEDS_REVIEW = "needs_review", "Needs admin review"  # set automatically (many overrides)
    REVIEWS_HIDDEN = "reviews_hidden", "Suspicious: reviews hidden"  # set by an admin
    CLEARED = "cleared", "Checked by admin: OK"


def new_checkin_salt():
    return secrets.token_hex(8)


class Trip(TimeStampedModel):
    activity_type = models.CharField(
        max_length=20, choices=ActivityType.choices, default=ActivityType.CAMPING
    )
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="organized_trips"
    )
    group = models.ForeignKey(
        "communities.CampingGroup", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="trips",
    )
    location = models.ForeignKey(
        "locations.Location", on_delete=models.PROTECT, related_name="trips"
    )

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()

    # Meeting point — precise coordinates are shown only to confirmed participants.
    meeting_point_name = models.CharField(max_length=200, blank=True)
    meeting_latitude = models.FloatField(null=True, blank=True, validators=[validate_th_latitude])
    meeting_longitude = models.FloatField(null=True, blank=True, validators=[validate_th_longitude])

    status = models.CharField(max_length=20, choices=TripStatus.choices, default=TripStatus.DRAFT)
    difficulty = models.CharField(
        max_length=20, choices=DifficultyLevel.choices, default=DifficultyLevel.MODERATE
    )
    distance_km = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    estimated_duration_hours = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    participant_capacity = models.PositiveIntegerField()
    min_experience_level = models.CharField(
        max_length=20, choices=ExperienceLevel.choices, default=ExperienceLevel.BEGINNER
    )
    safety_notes = models.TextField(blank=True)

    # Denormalised count of confirmed participants. Updated inside the RSVP
    # transaction; the CHECK below makes overbooking impossible at the DB level
    # even if application code has a bug.
    confirmed_count = models.PositiveIntegerField(default=0)

    # Check-in code: derived from this salt + SECRET_KEY (see services.checkin_code),
    # so the code itself is never stored. A new salt = a new code.
    checkin_salt = models.CharField(max_length=32, default=new_checkin_salt, editable=False)

    # Suspicious-attendance review (rule: too many attended without check-in).
    flag_status = models.CharField(max_length=20, choices=FlagStatus.choices, blank=True,
                                   default=FlagStatus.NONE)
    flag_note = models.TextField(blank=True)
    flagged_at = models.DateTimeField(null=True, blank=True)

    # Set when the trip's PRIVATE group is deleted: the trip then has no group to
    # decide who may see it, so only its organizer and participants still can.
    members_only = models.BooleanField(default=False)

    class Meta:
        db_table = "trips"
        ordering = ["start_datetime"]
        indexes = [
            models.Index(fields=["status", "start_datetime"]),
            models.Index(fields=["location", "status"]),
            models.Index(fields=["organizer"]),
        ]
        constraints = [
            models.CheckConstraint(
                name="trips_end_after_start", condition=Q(end_datetime__gt=F("start_datetime"))
            ),
            models.CheckConstraint(
                name="trips_capacity_positive", condition=Q(participant_capacity__gt=0)
            ),
            models.CheckConstraint(
                name="trips_confirmed_within_capacity",
                condition=Q(confirmed_count__gte=0)
                & Q(confirmed_count__lte=F("participant_capacity")),
            ),
            models.CheckConstraint(
                name="trips_meeting_coords_pair",
                condition=Q(meeting_latitude__isnull=True, meeting_longitude__isnull=True)
                | (
                    Q(meeting_latitude__isnull=False, meeting_longitude__isnull=False)
                    & in_thailand_q("meeting_latitude", "meeting_longitude")
                ),
            ),
        ]

    def __str__(self):
        return self.title

    @property
    def spots_left(self):
        return self.participant_capacity - self.confirmed_count


class TripEquipmentItem(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="equipment_items")
    item_name = models.CharField(max_length=150)
    required = models.BooleanField(default=True)
    provided_by = models.CharField(max_length=20, choices=EquipmentProvider.choices)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "trip_equipment_items"
        ordering = ["trip", "item_name"]

    def __str__(self):
        return self.item_name


class TripParticipant(models.Model):
    """
    No default status on purpose: the RSVP code must decide confirmed vs
    waitlisted explicitly (the schema's 'waitlisted' default is not relied on).
    """

    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="trip_participations"
    )
    status = models.CharField(max_length=20, choices=ParticipantStatus.choices)
    waitlist_position = models.PositiveIntegerField(null=True, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    status_changed_at = models.DateTimeField(auto_now=True)

    # Review credibility: who marked attendance and when.
    attendance_marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    attendance_marked_at = models.DateTimeField(null=True, blank=True)

    # Two-sided attendance: the participant checks in with the organizer's code,
    # the organizer confirms. Without a check-in the organizer must give a reason.
    checked_in_at = models.DateTimeField(null=True, blank=True)
    verification_method = models.CharField(max_length=20, choices=VerificationMethod.choices,
                                           blank=True, default="")
    override_reason = models.TextField(blank=True)

    # Opt-in: let the organizer read my (encrypted) emergency contact, only around
    # the trip dates. Off by default; the participant can turn it off any time.
    share_emergency_contact = models.BooleanField(default=False)

    class Meta:
        db_table = "trip_participants"
        ordering = ["trip", "waitlist_position", "joined_at"]
        indexes = [models.Index(fields=["trip", "status"])]
        constraints = [
            # One row per (trip, user): duplicate RSVPs are impossible.
            models.UniqueConstraint(fields=["trip", "user"], name="trip_participants_unique"),
            # Waitlist positions are unique per trip. DEFERRED so a promotion can
            # shift everyone up one place inside a single transaction.
            models.UniqueConstraint(
                fields=["trip", "waitlist_position"],
                name="trip_participants_unique_waitlist_pos",
                deferrable=Deferrable.DEFERRED,
            ),
            # Waitlisted rows must have a position >= 1; nobody else may have one.
            models.CheckConstraint(
                name="trip_participants_waitlist_position_consistent",
                condition=(
                    Q(status=ParticipantStatus.WAITLISTED)
                    & Q(waitlist_position__isnull=False)
                    & Q(waitlist_position__gte=1)
                )
                | (~Q(status=ParticipantStatus.WAITLISTED) & Q(waitlist_position__isnull=True)),
            ),
            # attended / no_show can only exist once attendance has been recorded.
            models.CheckConstraint(
                name="trip_participants_attendance_recorded",
                condition=~Q(status__in=[ParticipantStatus.ATTENDED, ParticipantStatus.NO_SHOW])
                | Q(attendance_marked_at__isnull=False),
            ),
            # Every 'attended' row says how it was verified; nobody else has a method.
            models.CheckConstraint(
                name="trip_participants_attended_has_verification",
                condition=(Q(status=ParticipantStatus.ATTENDED) & ~Q(verification_method=""))
                | (~Q(status=ParticipantStatus.ATTENDED) & Q(verification_method="")),
            ),
            # 'check_in' needs a real check-in; 'organizer_only' needs a written reason.
            models.CheckConstraint(
                name="trip_participants_verification_evidence",
                condition=(~Q(verification_method=VerificationMethod.CHECK_IN)
                           | Q(checked_in_at__isnull=False))
                & (~Q(verification_method=VerificationMethod.ORGANIZER_ONLY)
                   | ~Q(override_reason="")),
            ),
        ]

    def __str__(self):
        return f"{self.user} → {self.trip} ({self.status})"


class EmergencyContactAccess(models.Model):
    """Audit log: every time an organizer opened a participant's shared emergency contact."""

    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="emergency_accesses")
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    participant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+"
    )
    accessed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "emergency_contact_accesses"
        ordering = ["-accessed_at"]
        indexes = [models.Index(fields=["trip", "participant"])]

    def __str__(self):
        return f"Trip {self.trip_id}: organizer {self.organizer_id} viewed user {self.participant_id}"
