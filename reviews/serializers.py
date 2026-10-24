from rest_framework import serializers

from trips.models import Trip

from .models import Review


def _display_name(user) -> str:
    profile = getattr(user, "profile", None)
    return profile.display_name if profile else "Unknown"


class ReviewSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    trip = serializers.SerializerMethodField()
    campsite_id = serializers.IntegerField(source="location_id", read_only=True)
    verified_attendee = serializers.SerializerMethodField(
        help_text="Always true: only attended participants can review.")

    class Meta:
        model = Review
        fields = ["id", "campsite_id", "rating", "review_text", "author", "trip",
                  "verified_attendee", "status", "created_at", "edited_at"]
        read_only_fields = fields

    def get_author(self, obj) -> dict:
        return {"id": obj.user_id, "display_name": _display_name(obj.user)}

    def get_trip(self, obj) -> dict:
        return {"id": obj.trip_id, "title": obj.trip.title,
                "start_datetime": obj.trip.start_datetime}

    def get_verified_attendee(self, obj) -> bool:
        return True


class ReviewCreateSerializer(serializers.Serializer):
    trip_id = serializers.PrimaryKeyRelatedField(queryset=Trip.objects.all(), source="trip")
    rating = serializers.IntegerField(min_value=1, max_value=5)
    review_text = serializers.CharField(required=False, allow_blank=True, max_length=5000)


class ReviewUpdateSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5, required=False)
    review_text = serializers.CharField(required=False, allow_blank=True, max_length=5000)
