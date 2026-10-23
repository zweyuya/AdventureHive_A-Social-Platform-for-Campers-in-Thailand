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


class Review(models.Model):
    location = models.ForeignKey(
        "locations.Location", on_delete=models.CASCADE, related_name="reviews"
    )
    trip = models.ForeignKey("trips.Trip", on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews"
    )
    rating = models.PositiveSmallIntegerField()
    review_text = models.TextField(blank=True)
    status = models.CharField(
        max_length=10, choices=ReviewStatus.choices, default=ReviewStatus.PUBLISHED
    )
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
        ]

    def __str__(self):
        return f"{self.rating}★ {self.location} by {self.user}"
