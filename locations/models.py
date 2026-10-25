from django.conf import settings
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.geo import in_thailand_q, validate_th_latitude, validate_th_longitude
from core.models import TimeStampedModel


class AuthorityType(models.TextChoices):
    NATIONAL_PARK = "national_park", "National park (DNP)"
    FOREST_PARK = "forest_park", "Forest park"
    LOCAL_GOVERNMENT = "local_government", "Local government"
    PRIVATE_OWNER = "private_owner", "Private owner"
    OTHER = "other", "Other"


class LocationCategory(models.TextChoices):
    CAMPSITE = "campsite", "Campsite"
    CAMPGROUND = "campground", "Campground"
    BACKCOUNTRY = "backcountry", "Backcountry"
    OTHER = "other", "Other"


class PermitStatus(models.TextChoices):
    REQUIRED = "required", "Required"
    NOT_REQUIRED = "not_required", "Not required"
    UNKNOWN = "unknown", "Unknown"  # default until someone verifies it


class LocationStatus(models.TextChoices):
    """Content-management workflow for user-submitted campsites."""

    DRAFT = "draft", "Draft"
    PENDING_REVIEW = "pending_review", "Pending review"
    PUBLISHED = "published", "Published"
    REJECTED = "rejected", "Rejected"
    ARCHIVED = "archived", "Archived"


MAX_IMAGE_BYTES = 5 * 1024 * 1024


def validate_image_size(file):
    if file.size > MAX_IMAGE_BYTES:
        raise ValidationError("The photo must be 5 MB or smaller.")


def campsite_image_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower()
    return f"campsites/{instance.pk or 'new'}-{uuid4().hex[:8]}.{ext}"


class Authority(models.Model):
    """Who manages the site and issues permits (e.g. a DNP park office)."""

    name = models.CharField(max_length=200)
    authority_type = models.CharField(max_length=30, choices=AuthorityType.choices)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(max_length=255, blank=True)
    website_url = models.URLField(blank=True)
    booking_url = models.URLField(blank=True)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "authorities"
        verbose_name_plural = "authorities"
        ordering = ["name"]

    def __str__(self):
        return self.name


class LocationQuerySet(models.QuerySet):
    def published(self):
        """The ONLY queryset public endpoints and the map may use."""
        return self.filter(status=LocationStatus.PUBLISHED)


class Location(TimeStampedModel):
    """Schema table `locations` (campsites), plus province and workflow fields."""

    name = models.CharField(max_length=200)
    province = models.CharField(max_length=100)
    latitude = models.FloatField(validators=[validate_th_latitude])
    longitude = models.FloatField(validators=[validate_th_longitude])
    category = models.CharField(
        max_length=20, choices=LocationCategory.choices, default=LocationCategory.OTHER
    )
    description = models.TextField(blank=True)

    terrain_type = models.CharField(max_length=100, blank=True)
    elevation_m = models.FloatField(null=True, blank=True)
    has_water_source = models.BooleanField(default=False)
    has_restrooms = models.BooleanField(default=False)
    fire_pit_allowed = models.BooleanField(default=False)
    site_capacity = models.PositiveIntegerField(null=True, blank=True)

    # Permit information
    authority = models.ForeignKey(
        Authority, null=True, blank=True, on_delete=models.SET_NULL, related_name="locations"
    )
    permit_status = models.CharField(
        max_length=20, choices=PermitStatus.choices, default=PermitStatus.UNKNOWN
    )
    permit_details = models.TextField(blank=True)
    permit_booking_url = models.URLField(blank=True)
    rules = models.TextField(blank=True)
    permit_info_source = models.CharField(max_length=200, blank=True)
    permit_info_verified_at = models.DateTimeField(null=True, blank=True)

    # Aggregates, maintained when reviews change
    avg_rating = models.DecimalField(
        max_digits=3, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    review_count = models.PositiveIntegerField(default=0)

    # Cover photo, uploaded by moderators in the admin. The credit is shown under
    # the photo (e.g. "Photo: Jane Doe, CC BY-SA 4.0 via Wikimedia Commons").
    cover_image = models.ImageField(
        upload_to=campsite_image_path, blank=True,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"]), validate_image_size],
        help_text="JPEG, PNG or WebP, max 5 MB. Landscape photos look best.",
    )
    cover_image_credit = models.CharField(
        max_length=300, blank=True,
        help_text="Who took the photo and its licence / source. Required if you use someone else's photo.",
    )

    # Future work (semantic search). Kept as JSON until pgvector is adopted.
    embedding = models.JSONField(null=True, blank=True)

    # Content-management workflow
    status = models.CharField(
        max_length=20, choices=LocationStatus.choices, default=LocationStatus.DRAFT
    )
    created_by = models.ForeignKey(  # NULL = imported by the system (seed data)
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="submitted_locations",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="reviewed_locations",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    moderation_note = models.TextField(blank=True)  # rejection reason shown to the submitter
    current_version = models.PositiveIntegerField(default=0)  # 0 = never published

    objects = LocationQuerySet.as_manager()

    class Meta:
        db_table = "locations"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["status", "province"]),
            models.Index(fields=["status", "category"]),
        ]
        constraints = [
            models.CheckConstraint(
                name="locations_coords_in_thailand",
                condition=in_thailand_q("latitude", "longitude"),
            ),
            models.CheckConstraint(
                name="locations_avg_rating_range",
                condition=Q(avg_rating__isnull=True) | Q(avg_rating__gte=1, avg_rating__lte=5),
            ),
            models.CheckConstraint(
                name="locations_rejected_has_note",
                condition=~Q(status=LocationStatus.REJECTED) | ~Q(moderation_note=""),
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.province})"


class RevisionStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class LocationRevision(models.Model):
    """
    Full version history for campsites (permit info and rules are safety-critical
    and edited by many people). Each approved revision gets the next version_no;
    pending or rejected suggestions have version_no = NULL.
    """

    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="revisions")
    version_no = models.PositiveIntegerField(null=True, blank=True)
    snapshot = models.JSONField()  # copy of every editable field at this version
    edit_summary = models.CharField(max_length=300, blank=True)
    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="location_revisions",
    )
    status = models.CharField(
        max_length=20, choices=RevisionStatus.choices, default=RevisionStatus.PENDING
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="reviewed_location_revisions",
    )
    review_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "location_revisions"
        ordering = ["location", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["location", "version_no"], name="location_revisions_unique_version"
            ),
            # Only approved revisions carry a version number.
            models.CheckConstraint(
                name="location_revisions_version_iff_approved",
                condition=(Q(status=RevisionStatus.APPROVED) & Q(version_no__isnull=False))
                | (~Q(status=RevisionStatus.APPROVED) & Q(version_no__isnull=True)),
            ),
        ]

    def __str__(self):
        return f"{self.location} v{self.version_no or '?'} ({self.status})"
