"""
Trip-verified campsite reviews.

Credibility is enforced in three places:
  1. API: IsAttendedParticipant permission + serializer validation (Layer 5).
  2. DB:  UNIQUE (trip, user) — one review per person per trip.
  3. DB:  trigger reviews_enforce_attended (migration 0002) — rejects any review
          unless the author is 'attended' on a 'completed' trip, is not the
          trip's organizer, and the review's location matches the trip's.
"""
from django.conf import settings
from django.db import models
from django.db.models import Q


class ReviewStatus(models.TextChoices):
    PUBLISHED = "published", "Published"
    HIDDEN = "hidden", "Hidden"  # hidden by a moderator after a report


class HiddenReason(models.TextChoices):
    NONE = "", "—"
    MODERATOR = "moderator", "Hidden by a moderator"
    TRIP_FLAGGED = "trip_flagged", "Trip flagged as suspicious"


class Review(models.Model):
    location = models.ForeignKey(
        "locations.Location", on_delete=models.CASCADE, related_name="reviews"
    )
    trip = models.ForeignKey("trips.Trip", on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews"
    )
    rating = models.PositiveSmallIntegerField()
    # Optional: how good the trip's organizer was (the rating above is for the campsite).
    # Only the author sees it; the organizer only sees the average (organizer_stats).
    organizer_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    review_text = models.TextField(blank=True)
    status = models.CharField(
        max_length=10, choices=ReviewStatus.choices, default=ReviewStatus.PUBLISHED
    )
    # Why it is hidden, so un-flagging a trip restores only the reviews the flag hid.
    hidden_reason = models.CharField(max_length=20, choices=HiddenReason.choices, blank=True,
                                     default=HiddenReason.NONE)
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)  # versioning: current + "edited" marker

    class Meta:
        db_table = "reviews"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["location", "status"])]
        constraints = [
            models.UniqueConstraint(fields=["trip", "user"], name="reviews_one_per_trip_user"),
            models.CheckConstraint(
                name="reviews_rating_1_to_5", condition=Q(rating__gte=1, rating__lte=5)
            ),
            models.CheckConstraint(
                name="reviews_organizer_rating_1_to_5",
                condition=Q(organizer_rating__isnull=True)
                | Q(organizer_rating__gte=1, organizer_rating__lte=5),
            ),
        ]

    def __str__(self):
        return f"{self.rating}★ {self.location} by {self.user}"


class ReportReason(models.TextChoices):
    FAKE = "fake", "Looks fake / reviewer wasn't there"
    MISLEADING = "misleading", "Wrong or misleading information"
    OFFENSIVE = "offensive", "Offensive or abusive"
    SPAM = "spam", "Spam or advertising"
    OTHER = "other", "Other"


class ReportStatus(models.TextChoices):
    OPEN = "open", "Open"
    ACTIONED = "actioned", "Review hidden"
    DISMISSED = "dismissed", "Dismissed"


class ReviewReport(models.Model):
    """A member reports a review; a moderator hides the review or dismisses the report."""

    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="reports")
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="review_reports"
    )
    reason = models.CharField(max_length=20, choices=ReportReason.choices)
    details = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=ReportStatus.choices,
                              default=ReportStatus.OPEN)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "review_reports"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]
        constraints = [
            # One report per person per review (no report-spamming).
            models.UniqueConstraint(fields=["review", "reporter"], name="review_reports_once"),
        ]

    def __str__(self):
        return f"Report on review {self.review_id} ({self.get_reason_display()})"
