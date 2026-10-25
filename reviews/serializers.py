from rest_framework import serializers

from core.people import person

from trips.models import Trip

from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    trip = serializers.SerializerMethodField()
    campsite_id = serializers.IntegerField(source="location_id", read_only=True)
    campsite_name = serializers.CharField(source="location.name", read_only=True)
    campsite_image = serializers.SerializerMethodField()
    verified_attendee = serializers.SerializerMethodField(
        help_text="Always true: only attended participants can review.")

    class Meta:
        model = Review
        fields = ["id", "campsite_id", "campsite_name", "campsite_image", "rating", "review_text", "author", "trip",
                  "verified_attendee", "status", "created_at", "edited_at"]
        read_only_fields = fields

    def get_campsite_image(self, obj) -> str | None:
        return obj.location.cover_image.url if obj.location.cover_image else None

    def get_author(self, obj) -> dict:
        return person(obj.user)

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
