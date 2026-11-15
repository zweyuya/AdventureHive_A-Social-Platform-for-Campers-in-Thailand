from django.db.models import Exists, OuterRef, Subquery
from rest_framework import serializers

from core.people import person

from trips.models import Trip, TripParticipant

from .models import ReportReason, Review, ReviewStatus


class ReviewSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    trip = serializers.SerializerMethodField()
    campsite_id = serializers.IntegerField(source="location_id", read_only=True)
    campsite_name = serializers.CharField(source="location.name", read_only=True)
    campsite_image = serializers.SerializerMethodField()
    verified_attendee = serializers.SerializerMethodField(
        help_text="Always true: only attended participants can review.")
    verification = serializers.SerializerMethodField(
        help_text="'check_in' = checked in with the trip code and confirmed by the organizer; "
                  "'organizer_only' = confirmed by the organizer without a check-in.")
    counts_in_rating = serializers.SerializerMethodField(
        help_text="False for a person's older reviews of the same campsite: only their newest "
                  "review counts toward the rating.")

    class Meta:
        model = Review
        fields = ["id", "campsite_id", "campsite_name", "campsite_image", "rating", "organizer_rating",
                  "review_text", "author", "trip", "verified_attendee", "verification",
                  "counts_in_rating", "status", "created_at", "edited_at"]
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        # Private to the author, so organizers can't find out who rated them low.
        if not (request and request.user.is_authenticated and request.user.pk == instance.user_id):
            data.pop("organizer_rating")
        return data

    def get_campsite_image(self, obj) -> str | None:
        return obj.location.cover_image.url if obj.location.cover_image else None

    def get_author(self, obj) -> dict:
        return person(obj.user)

    def get_trip(self, obj) -> dict:
        return {"id": obj.trip_id, "title": obj.trip.title,
                "start_datetime": obj.trip.start_datetime}

    def get_verified_attendee(self, obj) -> bool:
        return True

    def get_verification(self, obj) -> str | None:
        if hasattr(obj, "verification"):  # annotated by with_badges()
            return obj.verification or None
        return TripParticipant.objects.filter(trip_id=obj.trip_id, user_id=obj.user_id) \
            .values_list("verification_method", flat=True).first() or None

    def get_counts_in_rating(self, obj) -> bool:
        if obj.status != ReviewStatus.PUBLISHED:
            return False
        superseded = obj.superseded if hasattr(obj, "superseded") else _newer(obj).exists()
        return not superseded


def _newer(review):
    return Review.objects.filter(location_id=review.location_id, user_id=review.user_id,
                                 status=ReviewStatus.PUBLISHED, created_at__gt=review.created_at)


def with_badges(qs):
    """Annotate a review queryset with what ReviewSerializer needs, in one query."""
    return qs.annotate(
        verification=Subquery(TripParticipant.objects.filter(
            trip_id=OuterRef("trip_id"), user_id=OuterRef("user_id")
        ).values("verification_method")[:1]),
        superseded=Exists(Review.objects.filter(
            location_id=OuterRef("location_id"), user_id=OuterRef("user_id"),
            status=ReviewStatus.PUBLISHED, created_at__gt=OuterRef("created_at"))),
    )


class ReviewReportSerializer(serializers.Serializer):
    reason = serializers.ChoiceField(choices=ReportReason.choices)
    details = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class ReviewCreateSerializer(serializers.Serializer):
    trip_id = serializers.PrimaryKeyRelatedField(queryset=Trip.objects.all(), source="trip")
    rating = serializers.IntegerField(min_value=1, max_value=5)
    organizer_rating = serializers.IntegerField(
        min_value=1, max_value=5, required=False, allow_null=True,
        help_text="Optional: how was the organizer? Only you see it; it counts in their average.")
    review_text = serializers.CharField(required=False, allow_blank=True, max_length=5000)


class ReviewUpdateSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5, required=False)
    organizer_rating = serializers.IntegerField(min_value=1, max_value=5, required=False,
                                                allow_null=True)
    review_text = serializers.CharField(required=False, allow_blank=True, max_length=5000)
