from django.conf import settings
from django.db import models


class NotificationType(models.TextChoices):
    # Trips
    RSVP_CONFIRMED = "rsvp_confirmed", "RSVP confirmed"
    RSVP_WAITLISTED = "rsvp_waitlisted", "Added to waitlist"
    WAITLIST_PROMOTED = "waitlist_promoted", "Promoted from waitlist"
    TRIP_CANCELLED = "trip_cancelled", "Trip cancelled"
    TRIP_UPDATED = "trip_updated", "Trip date or place changed"
    TRIP_REMINDER = "trip_reminder", "Trip reminder"
    REVIEW_UNLOCKED = "review_unlocked", "You can now review this campsite"
    # Content workflow
    SUBMISSION_APPROVED = "submission_approved", "Campsite submission approved"
    SUBMISSION_REJECTED = "submission_rejected", "Campsite submission rejected"
    ANSWER_POSTED = "answer_posted", "New answer to your question"
    # Social
    FOLLOW = "follow", "New follower"
    LIKE = "like", "Post liked"            # kept for compatibility; reactions use REACTION
    REACTION = "reaction", "Reaction to your post"
    COMMENT = "comment", "New comment"
    REPLY = "reply", "Reply to your comment"
    GROUP_POST = "group_post", "New post in your group"
    POST_PENDING = "post_pending", "Post waiting for your approval"
    POST_APPROVED = "post_approved", "Your post was approved"
    POST_REJECTED = "post_rejected", "Your post was not approved"


class ReferenceType(models.TextChoices):
    TRIP = "trip", "Trip"
    LOCATION = "location", "Location"
    QUESTION = "question", "Question"
    ANSWER = "answer", "Answer"
    POST = "post", "Post"
    COMMENT = "comment", "Comment"
    USER = "user", "User"
    GROUP = "group", "Group"


class Notification(models.Model):
    """In-app notifications, loaded on login / page load (no real-time push in the MVP)."""

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    actor = models.ForeignKey(  # NULL = system-generated
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    type = models.CharField(max_length=30, choices=NotificationType.choices)
    reference_type = models.CharField(max_length=20, choices=ReferenceType.choices)
    reference_id = models.PositiveBigIntegerField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "is_read", "-created_at"])]

    def __str__(self):
        return f"{self.type} → {self.recipient}"
