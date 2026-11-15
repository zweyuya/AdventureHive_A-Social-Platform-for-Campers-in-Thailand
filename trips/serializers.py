from django.utils import timezone
from rest_framework import serializers

from accounts.models import EmergencyContact
from core.people import avatar_url, display_name as _display_name, person
from core.provinces import check_pin, distance_km

from communities.models import CampingGroup
from locations.models import Location

from .models import ParticipantStatus as PS
from .models import AttendanceAppeal, Trip, TripEquipmentItem, TripParticipant, TripStatus
from .services import (
    APPEAL_WINDOW,
    ATTENDANCE_WINDOW,
    appeal_is_open,
    checkin_is_open,
    checkin_window,
    emergency_window,
    duplicate_guard,
    duplicate_trip_error,
    emergency_window_is_open,
    in_priority_window,
    past_attendees,
    update_trip,
)


class _MiniLocation(serializers.ModelSerializer):
    cover_image = serializers.SerializerMethodField()

    class Meta:
        model = Location
        fields = ["id", "name", "province", "latitude", "longitude", "cover_image"]

    def get_cover_image(self, obj) -> str | None:
        return obj.cover_image.url if obj.cover_image else None


class _MyStatusMixin(serializers.Serializer):
    """The requesting user's own RSVP status (context['my_rsvps'] = {trip_id: (status, pos)})."""

    my_status = serializers.SerializerMethodField()
    my_waitlist_position = serializers.SerializerMethodField()

    def _mine(self, obj):
        return self.context.get("my_rsvps", {}).get(obj.pk, (None, None))

    def get_my_status(self, obj) -> str | None:
        return self._mine(obj)[0]

    def get_my_waitlist_position(self, obj) -> int | None:
        return self._mine(obj)[1]


class TripListSerializer(_MyStatusMixin, serializers.ModelSerializer):
    location = _MiniLocation(read_only=True)
    organizer = serializers.SerializerMethodField()
    spots_left = serializers.IntegerField(read_only=True)

    class Meta:
        model = Trip
        fields = ["id", "title", "status", "start_datetime", "end_datetime", "difficulty",
                  "min_experience_level", "participant_capacity", "confirmed_count",
                  "spots_left", "location", "organizer", "group",
                  "my_status", "my_waitlist_position"]

    def get_organizer(self, obj) -> dict:
        return person(obj.organizer)


class EquipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TripEquipmentItem
        fields = ["id", "item_name", "required", "provided_by", "notes"]


class TripDetailSerializer(TripListSerializer):
    equipment_items = EquipmentSerializer(many=True, read_only=True)
    waitlist_count = serializers.SerializerMethodField()
    can_review = serializers.SerializerMethodField(
        help_text="True when the current user may write a review for this trip now.")
    checkin = serializers.SerializerMethodField(
        help_text="Check-in window, and when the current user checked in (null if not).")
    emergency = serializers.SerializerMethodField(
        help_text="Emergency-contact sharing: the window the organizer can read shared "
                  "contacts in, and whether the current user shares theirs.")

    appeal = serializers.SerializerMethodField(
        help_text="The current user's no-show appeal: whether they can appeal, or its outcome. "
                  "Null if none of this applies to them.")
    organizer_stats = serializers.SerializerMethodField(
        help_text="The organizer's record: trips run, campers, cancellations and rating. Only "
                  "trips that are hard to fake count (see reviews.services.counted_trips).")
    priority = serializers.SerializerMethodField(
        help_text="A repeated trip: until `until`, only people who attended the previous trip "
                  "(`repeat_of`) may join. Null when there is no such window.")
    meeting_distance_km = serializers.SerializerMethodField(
        help_text="Straight-line (great-circle) distance from the meeting point to the campsite, "
                  "in km. Null when there is no meeting point, or when it is hidden from this user.")

    class Meta(TripListSerializer.Meta):
        fields = TripListSerializer.Meta.fields + [
            "activity_type", "description", "distance_km", "estimated_duration_hours",
            "safety_notes", "meeting_point_name", "meeting_latitude", "meeting_longitude",
            "equipment_items", "waitlist_count", "can_review", "checkin", "emergency", "appeal",
            "meeting_distance_km", "organizer_stats", "priority", "created_at",
            "updated_at",
        ]

    def get_checkin(self, obj) -> dict:
        opens, closes = checkin_window(obj)
        user = self.context["request"].user
        mine = None
        if user.is_authenticated:
            mine = obj.participants.filter(user=user).values_list("checked_in_at", flat=True).first()
        return {"opens_at": opens, "closes_at": closes, "is_open": checkin_is_open(obj),
                "my_checked_in_at": mine}

    def get_emergency(self, obj) -> dict:
        opens, closes = emergency_window(obj)
        user = self.context["request"].user
        sharing = has_contact = False
        if user.is_authenticated:
            sharing = obj.participants.filter(user=user, share_emergency_contact=True).exists()
            has_contact = EmergencyContact.objects.filter(user=user).exists()
        return {"opens_at": opens, "closes_at": closes, "is_open": emergency_window_is_open(obj),
                "i_share": sharing, "i_have_contact": has_contact}

    def get_priority(self, obj) -> dict | None:
        if not in_priority_window(obj):
            return None
        user = self.context["request"].user
        return {
            "until": obj.priority_until,
            "repeat_of": {"id": obj.repeat_of_id, "title": obj.repeat_of.title},
            "i_am_invited": user.is_authenticated and past_attendees(obj).filter(pk=user.pk).exists(),
        }

    def get_organizer_stats(self, obj) -> dict:
        from reviews.services import organizer_stats  # local import: reviews depends on trips
        return organizer_stats(obj.organizer)

    def get_meeting_distance_km(self, obj) -> float | None:
        if obj.meeting_latitude is None or obj.meeting_longitude is None:
            return None
        return round(distance_km(obj.meeting_latitude, obj.meeting_longitude,
                                 obj.location.latitude, obj.location.longitude), 1)

    def get_appeal(self, obj) -> dict | None:
        user = self.context["request"].user
        if not user.is_authenticated:
            return None
        mine = obj.participants.filter(user=user).select_related("appeal").first()
        appeal = getattr(mine, "appeal", None)
        if mine is None or (mine.status != PS.NO_SHOW and appeal is None):
            return None
        return {
            "can_appeal": appeal is None and appeal_is_open(obj),
            "closes_at": obj.end_datetime + APPEAL_WINDOW,
            "status": appeal.status if appeal else None,
            "reason": appeal.reason if appeal else None,
            "decision_note": appeal.decision_note if appeal else None,
        }

    def get_waitlist_count(self, obj) -> int:
        return obj.participants.filter(status=PS.WAITLISTED).count()

    def get_can_review(self, obj) -> bool:
        from reviews.services import REVIEW_WINDOW  # local import: reviews depends on trips
        return (
            obj.status == TripStatus.COMPLETED
            and self._mine(obj)[0] == PS.ATTENDED
            and obj.organizer_id != self.context["request"].user.pk
            and obj.pk not in self.context.get("my_reviewed", set())
            and timezone.now() <= obj.end_datetime + REVIEW_WINDOW
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        user = self.context["request"].user
        can_see_meeting_point = user.is_authenticated and (
            instance.organizer_id == user.pk or data["my_status"] in (PS.CONFIRMED, PS.ATTENDED)
        )
        if not can_see_meeting_point:  # exact meeting point is private to the group
            # The distance goes too: with the public campsite pin it would narrow down the spot.
            for key in ("meeting_point_name", "meeting_latitude", "meeting_longitude",
                        "meeting_distance_km"):
                data[key] = None
            data["meeting_point_hidden"] = True
        return data


class TripWriteSerializer(serializers.ModelSerializer):
    location_id = serializers.PrimaryKeyRelatedField(
        queryset=Location.objects.published(), source="location",
        help_text="A published campsite.",
        error_messages={"does_not_exist": "Trips can only be organised at campsites a moderator "
                                          "has checked. This one isn't verified yet."},
    )
    repeat_of_id = serializers.PrimaryKeyRelatedField(
        queryset=Trip.objects.all(), source="repeat_of", required=False, allow_null=True,
        help_text="'Repeat this trip': your own earlier, completed trip. Its attendees are "
                  "invited when this one is published, and may join first for 48 hours.",
    )
    group_id = serializers.PrimaryKeyRelatedField(
        queryset=CampingGroup.objects.all(), source="group", required=False, allow_null=True,
    )

    class Meta:
        model = Trip
        fields = ["location_id", "group_id", "title", "description", "start_datetime",
                  "end_datetime", "meeting_point_name", "meeting_latitude", "meeting_longitude",
                  "difficulty", "distance_km", "estimated_duration_hours",
                  "participant_capacity", "min_experience_level", "safety_notes", "repeat_of_id"]

    def validate_title(self, value):
        return " ".join(value.split())  # "Khao  Yai " -> "Khao Yai"

    def validate_participant_capacity(self, value):
        if value < 1:
            raise serializers.ValidationError("Capacity must be at least 1.")
        return value

    def validate(self, attrs):
        inst = self.instance
        start = attrs.get("start_datetime", inst.start_datetime if inst else None)
        end = attrs.get("end_datetime", inst.end_datetime if inst else None)
        if start and end and end <= start:
            raise serializers.ValidationError({"end_datetime": "Must be after the start."})
        if "start_datetime" in attrs and attrs["start_datetime"] <= timezone.now():
            raise serializers.ValidationError({"start_datetime": "Must be in the future."})

        lat = attrs.get("meeting_latitude", inst.meeting_latitude if inst else None)
        lng = attrs.get("meeting_longitude", inst.meeting_longitude if inst else None)
        if (lat is None) != (lng is None):
            raise serializers.ValidationError(
                {"meeting_latitude": "Give both meeting latitude and longitude, or neither."})
        moved = "meeting_latitude" in attrs or "meeting_longitude" in attrs
        if moved and lat is not None and not (pin := check_pin(lat, lng)).in_thailand:
            where = f"in {pin.country}" if pin.country else "outside Thailand"
            raise serializers.ValidationError(
                {"meeting_latitude": f"This meeting point is {where}. It must be inside Thailand."})

        group = attrs.get("group")
        user = self.context["request"].user
        if group and not group.memberships.filter(user=user, status="active").exists():
            raise serializers.ValidationError({"group_id": "You are not a member of this group."})
        if inst and inst.status in (TripStatus.CANCELLED, TripStatus.COMPLETED):
            raise serializers.ValidationError(f"A {inst.status} trip cannot be edited.")

        if "repeat_of" in attrs:
            original = attrs["repeat_of"]
            if inst is not None and original != inst.repeat_of:
                raise serializers.ValidationError({"repeat_of_id": "This can only be set when the trip is created."})
            if original and (original.organizer_id != user.pk or original.status != TripStatus.COMPLETED):
                raise serializers.ValidationError(
                    {"repeat_of_id": "You can only repeat a completed trip that you organised."})

        title = attrs.get("title", inst.title if inst else "")
        organizer = inst.organizer if inst else user
        if error := duplicate_trip_error(organizer, title, start, end, inst.pk if inst else None):
            raise serializers.ValidationError(error)
        return attrs

    def create(self, validated_data):
        with duplicate_guard():
            return super().create(validated_data)

    def update(self, instance, validated_data):
        return update_trip(instance, validated_data)


class AppealSerializer(serializers.ModelSerializer):
    reason = serializers.CharField(max_length=2000)

    class Meta:
        model = AttendanceAppeal
        fields = ["reason", "status", "decision_note", "created_at"]
        read_only_fields = ["status", "decision_note", "created_at"]


class OrganisedTripSerializer(TripListSerializer):
    """A trip on the organizer's dashboard, with what needs their attention."""

    waitlist_count = serializers.IntegerField(read_only=True)
    needs_attendance = serializers.SerializerMethodField(
        help_text="Completed, attendance not fully recorded, and still within the 7 days to do it.")
    attendance_due = serializers.SerializerMethodField()
    open_appeals = serializers.IntegerField(read_only=True)

    class Meta(TripListSerializer.Meta):
        fields = TripListSerializer.Meta.fields + [
            "waitlist_count", "needs_attendance", "attendance_due", "open_appeals", "flag_status",
            "repeat_of"]

    def get_attendance_due(self, obj):
        return obj.end_datetime + ATTENDANCE_WINDOW if obj.status == TripStatus.COMPLETED else None

    def get_needs_attendance(self, obj) -> bool:
        return (obj.status == TripStatus.COMPLETED and obj.n_unmarked > 0
                and timezone.now() <= obj.end_datetime + ATTENDANCE_WINDOW)


class ParticipantSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(read_only=True)
    display_name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
    camping_experience_level = serializers.CharField(
        source="user.profile.camping_experience_level", read_only=True)

    class Meta:
        model = TripParticipant
        fields = ["user_id", "display_name", "avatar", "camping_experience_level", "status",
                  "waitlist_position", "joined_at", "attendance_marked_at", "checked_in_at",
                  "verification_method", "override_reason"]

    def get_display_name(self, obj) -> str:
        return _display_name(obj.user)

    def get_avatar(self, obj) -> str | None:
        return avatar_url(obj.user)


class RsvpResultSerializer(serializers.ModelSerializer):
    trip_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = TripParticipant
        fields = ["trip_id", "status", "waitlist_position", "joined_at"]


class _AttendanceRecord(serializers.Serializer):
    user_id = serializers.IntegerField()
    status = serializers.ChoiceField(choices=[PS.ATTENDED, PS.NO_SHOW])
    reason = serializers.CharField(
        required=False, allow_blank=True, max_length=500,
        help_text="Required to mark someone attended who did not check in.")


class CheckInSerializer(serializers.Serializer):
    code = serializers.RegexField(r"^\s*\d{6}\s*$", error_messages={"invalid": "Enter the 6-digit code."})


class CheckInCodeSerializer(serializers.Serializer):
    """Organizer only: the code to show participants, and when it works."""

    code = serializers.CharField()
    opens_at = serializers.DateTimeField()
    closes_at = serializers.DateTimeField()
    is_open = serializers.BooleanField()


class AttendanceSerializer(serializers.Serializer):
    records = _AttendanceRecord(many=True, allow_empty=False)

    def validate_records(self, records):
        ids = [r["user_id"] for r in records]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("Each user may appear only once.")
        return records


class SharedEmergencyContactSerializer(serializers.Serializer):
    """Organizer only, inside the emergency window: what a participant chose to share."""

    user_id = serializers.IntegerField()
    display_name = serializers.CharField()
    name = serializers.CharField()
    phone = serializers.CharField()
    relationship = serializers.CharField()
