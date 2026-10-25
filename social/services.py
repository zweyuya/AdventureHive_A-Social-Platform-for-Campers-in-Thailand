"""
Newsfeed rules: who can see, post, approve, react and comment.

Places and audiences
  group post — public group: anyone can read; active members can post/comment/react.
               private group: active members only. Ordinary members' posts need
               approval by a group admin/co-admin; moderators' own posts go live.
  trip post  — organizer + confirmed/attended participants read, post, comment, react
               (cancelled trips are read-only).
Moderators of a place: group admins/co-admins, or the trip organizer. Platform staff
can moderate everything.

Counts (reaction_count, comment_count) are changed only here, in a transaction.
"""
from django.db import transaction
from django.db.models import Count, F, Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from communities.models import GroupMember, GroupMemberRole, GroupMemberStatus, PrivacyType
from notifications.models import NotificationType as NT
from notifications.models import ReferenceType as RT
from notifications.services import notify
from trips.models import ParticipantStatus, Trip, TripStatus

from .models import Comment, ContentStatus, Post, PostStatus, Reaction

TRIP_MEMBER_STATUSES = (ParticipantStatus.CONFIRMED, ParticipantStatus.ATTENDED)
MODERATOR_ROLES = (GroupMemberRole.ADMIN, GroupMemberRole.CO_ADMIN)


class SocialError(ValidationError):
    """A newsfeed rule was broken (HTTP 400)."""


# --------------------------------------------------------------------------
# Membership helpers
# --------------------------------------------------------------------------
def group_role(group, user):
    if not user.is_authenticated:
        return None
    return GroupMember.objects.filter(group=group, user=user, status=GroupMemberStatus.ACTIVE) \
        .values_list("role_in_group", flat=True).first()


def is_trip_member(trip, user) -> bool:
    if not user.is_authenticated:
        return False
    return trip.organizer_id == user.pk or trip.participants.filter(
        user=user, status__in=TRIP_MEMBER_STATUSES).exists()


def can_moderate_place(user, *, group=None, trip=None) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    if group is not None:
        return group_role(group, user) in MODERATOR_ROLES
    return trip is not None and trip.organizer_id == user.pk


def can_moderate(user, post: Post) -> bool:
    return can_moderate_place(user, group=post.group, trip=post.trip)


def can_participate(user, *, group=None, trip=None) -> bool:
    """May this user post / comment / react in this group or on this trip?"""
    if group is not None:
        return group_role(group, user) is not None
    if trip is not None:
        return trip.status != TripStatus.CANCELLED and is_trip_member(trip, user)
    return False


def visible_posts(user, qs=None):
    """Published posts the user may read, plus their own posts and posts they moderate."""
    qs = qs if qs is not None else Post.objects.all()
    if user.is_authenticated and user.is_staff:
        return qs
    my_groups = GroupMember.objects.filter(status=GroupMemberStatus.ACTIVE)
    readable = Q(status=PostStatus.PUBLISHED) & (
        Q(group__privacy_type=PrivacyType.PUBLIC)
        | (Q(group__isnull=False) & Q(group__in=my_groups.filter(user_id=getattr(user, "pk", None))
                                      .values("group")))
        | (Q(trip__isnull=False) & (Q(trip__organizer_id=getattr(user, "pk", None))
                                    | Q(trip__participants__user_id=getattr(user, "pk", None),
                                        trip__participants__status__in=TRIP_MEMBER_STATUSES)))
    )
    if not user.is_authenticated:
        return qs.filter(status=PostStatus.PUBLISHED, group__privacy_type=PrivacyType.PUBLIC)
    moderated = Q(group__in=my_groups.filter(user=user, role_in_group__in=MODERATOR_ROLES)
                  .values("group")) | Q(trip__organizer=user)
    return qs.filter(readable | Q(user=user) | moderated).distinct()


def feed_for(user, qs=None):
    """Home feed: published posts from my groups and my trips (newest first),
    plus my own posts that are waiting for approval or were not approved."""
    qs = qs if qs is not None else Post.objects.all()
    groups = GroupMember.objects.filter(user=user, status=GroupMemberStatus.ACTIVE).values("group")
    trips = Q(trip__organizer=user) | Q(trip__participants__user=user,
                                        trip__participants__status__in=TRIP_MEMBER_STATUSES)
    return qs.filter((Q(status=PostStatus.PUBLISHED) & (Q(group__in=groups) | trips))
                     | Q(user=user)).distinct()


# --------------------------------------------------------------------------
# Posts
# --------------------------------------------------------------------------
def _notify_moderators_of_pending(post):
    mods = GroupMember.objects.filter(group=post.group, status=GroupMemberStatus.ACTIVE,
                                      role_in_group__in=MODERATOR_ROLES).select_related("user")
    for m in mods:
        if m.user_id != post.user_id:
            notify(m.user, NT.POST_PENDING, RT.POST, post.pk, actor=post.user)


def _initial_status(user, group) -> str:
    """Private-group posts by ordinary members wait for approval."""
    if group is not None and group.privacy_type == PrivacyType.PRIVATE \
            and group_role(group, user) not in MODERATOR_ROLES:
        return PostStatus.PENDING_REVIEW
    return PostStatus.PUBLISHED


@transaction.atomic
def create_post(user, *, content_text: str, group=None, trip=None, image=None, location=None) -> Post:
    if (group is None) == (trip is None):
        raise SocialError("Choose either a group or a trip to post in.")
    if not content_text.strip() and image is None:
        raise SocialError({"content_text": "Write something or add a photo."})
    if not can_participate(user, group=group, trip=trip):
        raise PermissionDenied("Only members of this group can post here." if group
                               else "Only the organizer and people going on this trip can post here.")
    post = Post(user=user, group=group, trip=trip, location=location,
                content_text=content_text.strip(), status=_initial_status(user, group))
    if image is not None:
        post.image.save(image.name, image, save=False)
    post.save()
    if post.status == PostStatus.PENDING_REVIEW:
        _notify_moderators_of_pending(post)
    return post


@transaction.atomic
def edit_post(post: Post, user, content_text: str) -> Post:
    post = Post.objects.select_for_update(of=("self",)).select_related("group").get(pk=post.pk)
    if post.user_id != user.pk:
        raise PermissionDenied("Only the author can edit this post.")
    if post.status == PostStatus.HIDDEN:
        raise SocialError("A hidden post cannot be edited.")
    post.content_text = content_text.strip()
    post.edited_at = timezone.now()
    # Edited private-group posts are re-checked, so an approved post can't be swapped out.
    new_status = _initial_status(user, post.group)
    resubmitted = new_status == PostStatus.PENDING_REVIEW and post.status != PostStatus.PENDING_REVIEW
    if post.status in (PostStatus.PUBLISHED, PostStatus.REJECTED, PostStatus.PENDING_REVIEW):
        post.status = new_status
    if post.status == PostStatus.PENDING_REVIEW:
        post.moderation_note = ""
    post.save()
    if resubmitted:
        _notify_moderators_of_pending(post)
    return post


@transaction.atomic
def review_post(post: Post, moderator, approve: bool, note: str = "") -> Post:
    post = Post.objects.select_for_update(of=("self",)).select_related("group").get(pk=post.pk)
    if post.group is None or not can_moderate(moderator, post):
        raise PermissionDenied("Only this group's admins and co-admins can review posts.")
    if post.status != PostStatus.PENDING_REVIEW:
        raise SocialError("This post isn't waiting for approval.")
    if not approve and not note.strip():
        raise SocialError({"note": "Tell the author why the post wasn't approved."})
    post.status = PostStatus.PUBLISHED if approve else PostStatus.REJECTED
    post.moderation_note = "" if approve else note.strip()
    post.reviewed_by, post.reviewed_at = moderator, timezone.now()
    post.save()
    notify(post.user, NT.POST_APPROVED if approve else NT.POST_REJECTED, RT.POST, post.pk,
           actor=moderator)
    return post


@transaction.atomic
def set_post_hidden(post: Post, moderator, hidden: bool) -> Post:
    post = Post.objects.select_for_update().get(pk=post.pk)
    if not can_moderate(moderator, post):
        raise PermissionDenied("Only moderators of this group or trip can do this.")
    if hidden:
        post.status = PostStatus.HIDDEN
    elif post.status == PostStatus.HIDDEN:
        post.status = PostStatus.PUBLISHED
    post.save(update_fields=["status"])
    return post


@transaction.atomic
def delete_post(post: Post, user) -> None:
    if post.user_id != user.pk and not can_moderate(user, post):
        raise PermissionDenied("Only the author or a moderator can delete this post.")
    if post.image:
        post.image.delete(save=False)
    post.delete()


# --------------------------------------------------------------------------
# Reactions
# --------------------------------------------------------------------------
def _require_interactive(post: Post, user):
    if post.status != PostStatus.PUBLISHED:
        raise SocialError("You can only react to or comment on published posts.")
    if not can_participate(user, group=post.group, trip=post.trip):
        raise PermissionDenied("Join this group (or trip) to react and comment.")


@transaction.atomic
def react(post: Post, user, reaction_type: str) -> Reaction:
    post = Post.objects.select_for_update(of=("self",)).select_related("group", "trip").get(pk=post.pk)
    _require_interactive(post, user)
    reaction, created = Reaction.objects.update_or_create(
        user=user, post=post, defaults={"type": reaction_type})
    if created:
        Post.objects.filter(pk=post.pk).update(reaction_count=F("reaction_count") + 1)
        if post.user_id != user.pk:
            notify(post.user, NT.REACTION, RT.POST, post.pk, actor=user)
    return reaction


@transaction.atomic
def unreact(post: Post, user) -> None:
    post = Post.objects.select_for_update().get(pk=post.pk)
    deleted, _ = Reaction.objects.filter(user=user, post=post).delete()
    if deleted:
        Post.objects.filter(pk=post.pk).update(reaction_count=F("reaction_count") - 1)


def reaction_summaries(post_ids, user) -> tuple[dict, dict]:
    """({post_id: {type: count}}, {post_id: my_type}) for a page of posts — two queries."""
    summary: dict = {}
    for row in Reaction.objects.filter(post_id__in=post_ids).values("post_id", "type") \
            .annotate(n=Count("id")):
        summary.setdefault(row["post_id"], {})[row["type"]] = row["n"]
    mine = {}
    if user.is_authenticated:
        mine = dict(Reaction.objects.filter(post_id__in=post_ids, user=user)
                    .values_list("post_id", "type"))
    return summary, mine


# --------------------------------------------------------------------------
# Comments
# --------------------------------------------------------------------------
@transaction.atomic
def add_comment(post: Post, user, text: str, parent_id: int | None = None) -> Comment:
    post = Post.objects.select_for_update(of=("self",)).select_related("group", "trip").get(pk=post.pk)
    _require_interactive(post, user)
    if not text.strip():
        raise SocialError({"content_text": "Write a comment."})
    parent = None
    if parent_id:
        parent = Comment.objects.filter(pk=parent_id, post=post,
                                        status=ContentStatus.PUBLISHED).first()
        if parent is None:
            raise SocialError({"parent_comment_id": "That comment doesn't exist on this post."})
        parent = parent.parent_comment or parent  # keep replies one level deep
    comment = Comment.objects.create(post=post, user=user, content_text=text.strip(),
                                     parent_comment=parent)
    Post.objects.filter(pk=post.pk).update(comment_count=F("comment_count") + 1)
    if post.user_id != user.pk:
        notify(post.user, NT.COMMENT, RT.POST, post.pk, actor=user)
    if parent and parent.user_id not in (user.pk, post.user_id):
        notify(parent.user, NT.REPLY, RT.POST, post.pk, actor=user)
    return comment


def _recount_comments(post_id):
    n = Comment.objects.filter(post_id=post_id, status=ContentStatus.PUBLISHED).count()
    Post.objects.filter(pk=post_id).update(comment_count=n)


@transaction.atomic
def delete_comment(comment: Comment, user) -> None:
    post = comment.post
    if comment.user_id != user.pk and not can_moderate(user, post):
        raise PermissionDenied("Only the author or a moderator can delete this comment.")
    comment.delete()  # replies go with it
    _recount_comments(post.pk)


@transaction.atomic
def set_comment_hidden(comment: Comment, moderator, hidden: bool) -> Comment:
    if not can_moderate(moderator, comment.post):
        raise PermissionDenied("Only moderators of this group or trip can do this.")
    comment.status = ContentStatus.HIDDEN if hidden else ContentStatus.PUBLISHED
    comment.save(update_fields=["status"])
    _recount_comments(comment.post_id)
    return comment


# --------------------------------------------------------------------------
# Account deletion (PDPA)
# --------------------------------------------------------------------------
def withdraw_user(user) -> None:
    """Delete the user's posts (and photos), comments and reactions; fix counts elsewhere."""
    affected = set(Comment.objects.filter(user=user).values_list("post_id", flat=True))
    affected |= set(Reaction.objects.filter(user=user).values_list("post_id", flat=True))
    for post in Post.objects.filter(user=user):
        if post.image:
            post.image.delete(save=False)
    Post.objects.filter(user=user).delete()
    Comment.objects.filter(user=user).delete()
    Reaction.objects.filter(user=user).delete()
    for post_id in Post.objects.filter(pk__in=affected).values_list("pk", flat=True):
        _recount_comments(post_id)
        Post.objects.filter(pk=post_id).update(
            reaction_count=Reaction.objects.filter(post_id=post_id).count())
