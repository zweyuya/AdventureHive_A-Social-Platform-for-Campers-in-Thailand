from django.db.models import Count
from rest_framework import serializers

from .models import Authority, Location, LocationRevision
from .services import EDITABLE_FIELDS, check_pin_and_province


class AuthoritySerializer(serializers.ModelSerializer):
    class Meta:
        model = Authority
        fields = ["id", "name", "authority_type", "phone", "email",
                  "website_url", "booking_url", "description"]


def image_url(location) -> str | None:
    """Site-relative URL (/media/...) so it works behind any proxy or domain."""
    return location.cover_image.url if location.cover_image else None


class CampsiteListSerializer(serializers.ModelSerializer):
    cover_image = serializers.SerializerMethodField()

    class Meta:
        model = Location
        fields = ["id", "name", "province", "category", "latitude", "longitude",
                  "avg_rating", "review_count", "has_water_source", "has_restrooms",
                  "fire_pit_allowed", "permit_status", "cover_image", "cover_image_credit"]

    def get_cover_image(self, obj) -> str | None:
        return image_url(obj)


class CampsiteDetailSerializer(serializers.ModelSerializer):
    authority = AuthoritySerializer(read_only=True)
    cover_image = serializers.SerializerMethodField()
    rating_breakdown = serializers.SerializerMethodField(
        help_text='Reviews per star, e.g. {"5": 16, "4": 5, "3": 1, "2": 0, "1": 1}. Counts the '
                  "same reviews as avg_rating / review_count (published, newest per person).")

    def get_cover_image(self, obj) -> str | None:
        return image_url(obj)

    def get_rating_breakdown(self, obj) -> dict[str, int]:
        from reviews.services import counted_reviews  # local import: reviews depends on locations
        counts = dict(counted_reviews(obj.pk).order_by().values_list("rating")
                      .annotate(n=Count("id")))  # order_by(): keep GROUP BY on rating only
        return {str(star): counts.get(star, 0) for star in range(5, 0, -1)}

    class Meta:
        model = Location
        fields = [
            "id", "name", "province", "category", "description",
            "latitude", "longitude", "terrain_type", "elevation_m",
            "has_water_source", "has_restrooms", "fire_pit_allowed", "site_capacity",
            "authority", "permit_status", "permit_details", "permit_booking_url",
            "rules", "permit_info_source", "permit_info_verified_at",
            "avg_rating", "review_count", "rating_breakdown", "status", "moderation_note",
            "current_version", "created_at", "updated_at",
            "cover_image", "cover_image_credit",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        user = self.context["request"].user
        is_owner_or_staff = user.is_authenticated and (
            user.is_staff or instance.created_by_id == user.pk
        )
        if not is_owner_or_staff:  # moderation details are private
            data.pop("moderation_note")
        return data


class CampsiteWriteSerializer(serializers.ModelSerializer):
    """Used by members to create a draft, and to edit it while draft/rejected."""

    authority_id = serializers.PrimaryKeyRelatedField(
        queryset=Authority.objects.all(), source="authority",
        required=False, allow_null=True,
    )

    class Meta:
        model = Location
        fields = [f for f in EDITABLE_FIELDS if f != "authority_id"] + ["authority_id"]
        # Blank province = fill it in from the map pin.
        extra_kwargs = {"province": {"required": False, "allow_blank": True}}

    def validate(self, attrs):
        return check_pin_and_province(attrs, self.instance)


class PinCheckSerializer(serializers.Serializer):
    """What the suggest-a-campsite form shows under the map after a click."""

    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    in_thailand = serializers.BooleanField()
    country = serializers.CharField(allow_null=True)
    province = serializers.CharField(allow_null=True)
    provinces = serializers.ListField(child=serializers.CharField(),
                                      help_text="Provinces that may be chosen for this pin.")
    nearby = serializers.ListField(child=serializers.DictField(),
                                   help_text="Published campsites within 1 km.")


class SuggestEditSerializer(serializers.Serializer):
    """Any subset of the editable fields + a short summary of the change."""

    edit_summary = serializers.CharField(max_length=300)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # get_fields() returns fresh (unbound) copies of the write serializer's fields.
        for name, field in CampsiteWriteSerializer().get_fields().items():
            field.required = False
            self.fields[name] = field

    def to_internal_value(self, data):
        values = super().to_internal_value(data)
        if "authority" in values:
            authority = values.pop("authority")
            values["authority_id"] = authority.pk if authority else None
        return values


class RejectSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=2000,
                                 help_text="Reason shown to the submitter (required).")


class RevisionSerializer(serializers.ModelSerializer):
    edited_by = serializers.SerializerMethodField()
    campsite_id = serializers.IntegerField(source="location_id", read_only=True)

    class Meta:
        model = LocationRevision
        fields = ["id", "campsite_id", "version_no", "status", "edit_summary",
                  "edited_by", "review_note", "snapshot", "created_at"]

    def get_edited_by(self, obj) -> str:
        if obj.edited_by_id is None:
            return "System import"
        profile = getattr(obj.edited_by, "profile", None)
        return profile.display_name if profile else "Unknown"
