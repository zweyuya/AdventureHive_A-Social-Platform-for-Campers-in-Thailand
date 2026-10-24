from django.contrib.auth import password_validation
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from core.models import ExperienceLevel

from .models import EmergencyContact, InterestTag, Profile, User


class InterestTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterestTag
        fields = ["id", "tag_name"]


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=255)
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    display_name = serializers.CharField(max_length=100)
    camping_experience_level = serializers.ChoiceField(
        choices=ExperienceLevel.choices, default=ExperienceLevel.BEGINNER
    )
    interest_tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=InterestTag.objects.all(), many=True, required=False, source="interest_tags"
    )
    pdpa_consent = serializers.BooleanField(
        write_only=True, help_text="Must be true (Thai PDPA consent)."
    )

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_pdpa_consent(self, value):
        if value is not True:
            raise serializers.ValidationError(
                "You must agree to the collection and use of your personal data (PDPA)."
            )
        return value

    def validate(self, attrs):
        # Run Django's password validators with the user's own data, so
        # passwords similar to the email/display name are rejected.
        candidate = User(email=attrs["email"])
        try:
            password_validation.validate_password(attrs["password"], user=candidate)
        except Exception as exc:  # django ValidationError → DRF error
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs

    @transaction.atomic
    def create(self, validated):
        tags = validated.pop("interest_tags", [])
        user = User.objects.create_user(
            email=validated["email"],
            password=validated["password"],
            pdpa_consent_at=timezone.now(),
        )
        profile = Profile.objects.create(
            user=user,
            display_name=validated["display_name"],
            camping_experience_level=validated["camping_experience_level"],
        )
        profile.interest_tags.set(tags)
        return user


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------
class PublicProfileSerializer(serializers.ModelSerializer):
    """What anyone may see. No email, phone, birth date or gender."""

    id = serializers.IntegerField(source="user_id", read_only=True)
    interest_tags = InterestTagSerializer(many=True, read_only=True)
    member_since = serializers.DateTimeField(source="user.created_at", read_only=True)

    class Meta:
        model = Profile
        fields = [
            "id", "display_name", "bio", "city",
            "camping_experience_level", "interest_tags", "member_since",
        ]


class PrivateProfileSerializer(serializers.ModelSerializer):
    """
    The owner's own view and edit form.
    email, status and pdpa_consent_at are read-only.
    """

    id = serializers.IntegerField(source="user_id", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    status = serializers.CharField(source="user.status", read_only=True)
    pdpa_consent_at = serializers.DateTimeField(source="user.pdpa_consent_at", read_only=True)
    phone = serializers.CharField(
        source="user.phone", required=False, allow_blank=True, allow_null=True, max_length=30
    )
    interest_tags = InterestTagSerializer(many=True, read_only=True)
    interest_tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=InterestTag.objects.all(), many=True, required=False,
        write_only=True, source="interest_tags",
    )

    class Meta:
        model = Profile
        fields = [
            "id", "email", "status", "pdpa_consent_at", "phone",
            "display_name", "bio", "date_of_birth", "gender", "city",
            "camping_experience_level", "interest_tags", "interest_tag_ids",
        ]

    def validate_phone(self, value):
        value = value or None
        if value and User.objects.filter(phone=value).exclude(pk=self.instance.user_id).exists():
            raise serializers.ValidationError("This phone number is already in use.")
        return value

    @transaction.atomic
    def update(self, profile, validated):
        user_data = validated.pop("user", {})
        tags = validated.pop("interest_tags", None)
        if "phone" in user_data:
            profile.user.phone = user_data["phone"]
            profile.user.save(update_fields=["phone"])
        for field, value in validated.items():
            setattr(profile, field, value)
        profile.save()
        if tags is not None:
            profile.interest_tags.set(tags)
        return profile


# ---------------------------------------------------------------------------
# Emergency contact (owner only, encrypted at rest)
# ---------------------------------------------------------------------------
class EmergencyContactSerializer(serializers.ModelSerializer):
    name = serializers.CharField(max_length=100)
    phone = serializers.CharField(max_length=30)

    class Meta:
        model = EmergencyContact
        fields = ["name", "phone", "relationship", "updated_at"]
        read_only_fields = ["updated_at"]


# ---------------------------------------------------------------------------
# Account deletion
# ---------------------------------------------------------------------------
class AccountDeleteSerializer(serializers.Serializer):
    password = serializers.CharField(
        write_only=True, style={"input_type": "password"},
        help_text="Current password, to confirm deletion.",
    )
