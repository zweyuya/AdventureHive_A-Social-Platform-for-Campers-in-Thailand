from django.utils import timezone
from rest_framework import serializers

from communities.models import CampingGroup
from locations.models import Location

from .models import ParticipantStatus as PS
from .models import Trip, TripEquipmentItem, TripParticipant, TripStatus
from .services import update_trip


class _MiniLocation(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ["id", "name", "province", "latitude", "longitude"]


def _display_name(user) -> str:
    profile = getattr(user, "profile", None)
    return profile.display_name if profile else "Unknown"


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
        return {"id": obj.organizer_id, "display_name": _display_name(obj.organizer)}


class EquipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TripEquipmentItem
        fields = ["id", "item_name", "required", "provided_by", "notes"]


class TripDetailSerializer(TripListSerializer):
    equipment_items = EquipmentSerializer(many=True, read_only=True)
    waitlist_count = serializers.SerializerMethodField()
    can_review = serializers.SerializerMethodField(
        help_text="True when the current user may write a review for this trip now.")

    class Meta(TripListSerializer.Meta):
        fields = TripListSerializer.Meta.fields + [
            "activity_type", "description", "distance_km", "estimated_duration_hours",
            "safety_notes", "meeting_point_name", "meeting_latitude", "meeting_longitude",
            "equipment_items", "waitlist_count", "can_review", "created_at", "updated_at",
        ]

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
            for key in ("meeting_point_name", "meeting_latitude", "meeting_longitude"):
                data[key] = None
            data["meeting_point_hidden"] = True
        return data


class TripWriteSerializer(serializers.ModelSerializer):
    location_id = serializers.PrimaryKeyRelatedField(
        queryset=Location.objects.published(), source="location",
        help_text="A published campsite.",
    )
    group_id = serializers.PrimaryKeyRelatedField(
        queryset=CampingGroup.objects.all(), source="group", required=False, allow_null=True,
    )

    class Meta:
        model = Trip
        fields = ["location_id", "group_id", "title", "description", "start_datetime",
                  "end_datetime", "meeting_point_name", "meeting_latitude", "meeting_longitude",
                  "difficulty", "distance_km", "estimated_duration_hours",
                  "participant_capacity", "min_experience_level", "safety_notes"]

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

        group = attrs.get("group")
        user = self.context["request"].user
        if group and not group.memberships.filter(user=user, status="active").exists():
            raise serializers.ValidationError({"group_id": "You are not a member of this group."})
        if inst and inst.status in (TripStatus.CANCELLED, TripStatus.COMPLETED):
            raise serializers.ValidationError(f"A {inst.status} trip cannot be edited.")
        return attrs

    def update(self, instance, validated_data):
        return update_trip(instance, validated_data)


class ParticipantSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(read_only=True)
    display_name = serializers.SerializerMethodField()
    camping_experience_level = serializers.CharField(
        source="user.profile.camping_experience_level", read_only=True)

    class Meta:
        model = TripParticipant
        fields = ["user_id", "display_name", "camping_experience_level", "status",
                  "waitlist_position", "joined_at", "attendance_marked_at"]

    def get_display_name(self, obj) -> str:
        return _display_name(obj.user)


class RsvpResultSerializer(serializers.ModelSerializer):
    trip_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = TripParticipant
        fields = ["trip_id", "status", "waitlist_position", "joined_at"]


class _AttendanceRecord(serializers.Serializer):
    user_id = serializers.IntegerField()
    status = serializers.ChoiceField(choices=[PS.ATTENDED, PS.NO_SHOW])


class AttendanceSerializer(serializers.Serializer):
    records = _AttendanceRecord(many=True, allow_empty=False)

    def validate_records(self, records):
        ids = [r["user_id"] for r in records]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("Each user may appear only once.")
        return records
