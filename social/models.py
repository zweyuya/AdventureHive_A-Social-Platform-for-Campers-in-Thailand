"""
Group and trip posts, comments and reactions (the newsfeed).

Every post belongs to exactly ONE place — a group or a trip — which decides who
can see it and who moderates it:
  * group post  → visible to everyone (public group) or active members (private group);
                  moderated by the group's admins / co-admins.
  * trip post   → visible to the trip's organizer and confirmed/attended participants;
                  moderated by the organizer.
In PRIVATE groups, posts by ordinary members start as `pending_review` and need
approval from a group admin or co-admin. There is no global public feed (future work).
"""
from django.conf import settings
from django.db import models
from django.db.models import F, Q


class PostStatus(models.TextChoices):
    PENDING_REVIEW = "pending_review", "Waiting for approval"
    PUBLISHED = "published", "Published"
    REJECTED = "rejected", "Rejected"
    HIDDEN = "hidden", "Hidden by a moderator"


class ContentStatus(models.TextChoices):
    PUBLISHED = "published", "Published"
    HIDDEN = "hidden", "Hidden"


class ReactionType(models.TextChoices):
    LIKE = "like", "👍 Like"
    LOVE = "love", "❤️ Love"
    HAHA = "haha", "😂 Haha"
    WOW = "wow", "😮 Wow"
    SAD = "sad", "😢 Sad"


class Post(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts"
    )
    group = models.ForeignKey(
        "communities.CampingGroup", null=True, blank=True,
        on_delete=models.CASCADE, related_name="posts",
    )
    trip = models.ForeignKey(  # trip recap / trip discussion
        "trips.Trip", null=True, blank=True, on_delete=models.CASCADE, related_name="posts"
    )
    location = models.ForeignKey(  # optional "where was this?" tag
        "locations.Location", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="posts",
    )
    content_text = models.TextField()
    # Re-encoded on upload (max 1600 px, metadata incl. GPS removed)
    image = models.ImageField(upload_to="posts/", blank=True)
    status = models.CharField(
        max_length=20, choices=PostStatus.choices, default=PostStatus.PUBLISHED
    )
    moderation_note = models.TextField(blank=True)  # reason shown to the author on rejection
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reaction_count = models.PositiveIntegerField(default=0)
    comment_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "posts"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["group", "status", "-created_at"]),
            models.Index(fields=["trip", "status", "-created_at"]),
            models.Index(fields=["user", "-created_at"]),
        ]
        constraints = [
            # A post lives in exactly one place.
            models.CheckConstraint(
                name="posts_exactly_one_place",
                condition=(Q(group__isnull=False) & Q(trip__isnull=True))
                | (Q(group__isnull=True) & Q(trip__isnull=False)),
            ),
            models.CheckConstraint(
                name="posts_rejected_has_note",
                condition=~Q(status=PostStatus.REJECTED) | ~Q(moderation_note=""),
            ),
        ]

    def __str__(self):
        return f"Post {self.pk} by {self.user}"


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments"
    )
    parent_comment = models.ForeignKey(  # NULL = top-level; replies are one level deep
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies"
    )
    content_text = models.TextField()
    status = models.CharField(
        max_length=10, choices=ContentStatus.choices, default=ContentStatus.PUBLISHED
    )
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "comments"
        ordering = ["created_at"]
        indexes = [models.Index(fields=["post", "created_at"])]


class Reaction(models.Model):
    """One reaction per person per post; changing it updates the type."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reactions"
    )
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="reactions")
    type = models.CharField(max_length=10, choices=ReactionType.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reactions"
        constraints = [
            models.UniqueConstraint(fields=["user", "post"], name="reactions_one_per_user_post"),
        ]


class Follow(models.Model):
    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="following"
    )
    followee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="followers"
    )
    followed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "follows"
        constraints = [
            models.UniqueConstraint(fields=["follower", "followee"], name="follows_unique"),
            models.CheckConstraint(
                name="follows_not_self", condition=~Q(follower=F("followee"))
            ),
        ]
