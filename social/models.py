"""
Posts, comments, likes and follows. Deferred features (feed UI) build on these;
`follows` also powers the post-trip "follow your trip-mates" retention prompt.
Shares, media and messaging are future work and not modelled yet.
"""
from django.conf import settings
from django.db import models
from django.db.models import F, Q


class ContentStatus(models.TextChoices):
    PUBLISHED = "published", "Published"
    HIDDEN = "hidden", "Hidden"


class Post(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts"
    )
    group = models.ForeignKey(
        "communities.CampingGroup", null=True, blank=True,
        on_delete=models.CASCADE, related_name="posts",
    )
    trip = models.ForeignKey(  # trip recap posts
        "trips.Trip", null=True, blank=True, on_delete=models.SET_NULL, related_name="posts"
    )
    location = models.ForeignKey(
        "locations.Location", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="posts",
    )
    content_text = models.TextField()
    status = models.CharField(
        max_length=10, choices=ContentStatus.choices, default=ContentStatus.PUBLISHED
    )
    like_count = models.PositiveIntegerField(default=0)
    comment_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "posts"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"])]

    def __str__(self):
        return f"Post {self.pk} by {self.user}"


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments"
    )
    parent_comment = models.ForeignKey(  # NULL = top-level
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


class Like(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="likes"
    )
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "likes"
        constraints = [models.UniqueConstraint(fields=["user", "post"], name="likes_unique")]


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
