"""
Community groups: membership and in-group roles.

Roles (group_members.role_in_group — separate from Django's platform roles):
  admin     edit/delete the group, change roles, add/remove/ban members
  co_admin  moderation: add members, remove ordinary members
  member    takes part

Membership status: active · inactive (left) · removed · banned
member_count = number of ACTIVE members. It is changed only here, inside a
transaction with the group row locked, so it can't drift.
"""
from django.db import transaction
from django.db.models import F
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import CampingGroup, GroupMember, GroupMemberRole, GroupMemberStatus, PrivacyType

ROLE = GroupMemberRole
STATUS = GroupMemberStatus
MODERATOR_ROLES = (ROLE.ADMIN, ROLE.CO_ADMIN)


class GroupError(ValidationError):
    """A membership rule was broken (HTTP 400)."""


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _lock(group) -> CampingGroup:
    return CampingGroup.objects.select_for_update().get(pk=group.pk)


def _count(group, delta: int) -> None:
    CampingGroup.objects.filter(pk=group.pk).update(member_count=F("member_count") + delta)


def active_membership(group, user) -> GroupMember | None:
    if not user.is_authenticated:
        return None
    return GroupMember.objects.filter(group=group, user=user, status=STATUS.ACTIVE).first()


def _require_role(group, user, roles, action: str) -> GroupMember:
    m = active_membership(group, user)
    if m is None or m.role_in_group not in roles:
        raise PermissionDenied(f"Only group {' or '.join(r.replace('_', '-') for r in roles)}s "
                               f"can {action}.")
    return m


def _active_admin_count(group) -> int:
    return GroupMember.objects.filter(group=group, status=STATUS.ACTIVE,
                                      role_in_group=ROLE.ADMIN).count()


def _target(group, user_id) -> GroupMember:
    m = GroupMember.objects.select_for_update().filter(group=group, user_id=user_id).first()
    if m is None:
        raise GroupError("That user is not in this group.")
    return m


# --------------------------------------------------------------------------
# Group lifecycle
# --------------------------------------------------------------------------
@transaction.atomic
def create_group(user, data: dict) -> CampingGroup:
    group = CampingGroup.objects.create(created_by=user, member_count=1, **data)
    GroupMember.objects.create(group=group, user=user, role_in_group=ROLE.ADMIN,
                               status=STATUS.ACTIVE)
    return group


@transaction.atomic
def update_group(group, user, data: dict) -> CampingGroup:
    group = _lock(group)
    _require_role(group, user, (ROLE.ADMIN,), "edit the group")
    for field, value in data.items():
        setattr(group, field, value)
    group.save()
    return group


@transaction.atomic
def delete_group(group, user) -> None:
    group = _lock(group)
    _require_role(group, user, (ROLE.ADMIN,), "delete the group")
    group.delete()  # trips keep existing (group set to NULL)


# --------------------------------------------------------------------------
# Joining and leaving
# --------------------------------------------------------------------------
@transaction.atomic
def join(group, user) -> GroupMember:
    group = _lock(group)
    m = GroupMember.objects.select_for_update().filter(group=group, user=user).first()
    if m and m.status == STATUS.ACTIVE:
        raise GroupError("You are already a member of this group.")
    if m and m.status in (STATUS.BANNED, STATUS.REMOVED):
        raise GroupError(f"You were {m.status} from this group and cannot rejoin by yourself.")
    if group.privacy_type == PrivacyType.PRIVATE:
        raise GroupError("This is a private group. Ask a group admin to add you.")
    if m:  # left earlier → reactivate the same row (UNIQUE group+user)
        m.status, m.role_in_group = STATUS.ACTIVE, ROLE.MEMBER
        m.save()
    else:
        m = GroupMember.objects.create(group=group, user=user, role_in_group=ROLE.MEMBER,
                                       status=STATUS.ACTIVE)
    _count(group, +1)
    return m


@transaction.atomic
def leave(group, user) -> GroupMember:
    group = _lock(group)
    m = GroupMember.objects.select_for_update().filter(
        group=group, user=user, status=STATUS.ACTIVE).first()
    if m is None:
        raise GroupError("You are not a member of this group.")
    if m.role_in_group == ROLE.ADMIN and _active_admin_count(group) == 1:
        raise GroupError("You are the only admin. Make another member admin first, "
                         "or delete the group.")
    m.status = STATUS.INACTIVE
    m.save()
    _count(group, -1)
    return m


# --------------------------------------------------------------------------
# Moderation
# --------------------------------------------------------------------------
@transaction.atomic
def add_member(group, actor, user) -> GroupMember:
    """Admins and co-admins add people (the only way into a private group)."""
    group = _lock(group)
    actor_m = _require_role(group, actor, MODERATOR_ROLES, "add members")
    m = GroupMember.objects.select_for_update().filter(group=group, user=user).first()
    if m and m.status == STATUS.ACTIVE:
        raise GroupError("That user is already a member.")
    if m and m.status == STATUS.BANNED and actor_m.role_in_group != ROLE.ADMIN:
        raise PermissionDenied("Only a group admin can re-admit a banned user.")
    if m:
        m.status, m.role_in_group = STATUS.ACTIVE, ROLE.MEMBER
        m.save()
    else:
        m = GroupMember.objects.create(group=group, user=user, role_in_group=ROLE.MEMBER,
                                       status=STATUS.ACTIVE)
    _count(group, +1)
    return m


@transaction.atomic
def remove_member(group, actor, user_id: int, ban: bool = False) -> GroupMember:
    group = _lock(group)
    needed = (ROLE.ADMIN,) if ban else MODERATOR_ROLES
    actor_m = _require_role(group, actor, needed, "ban members" if ban else "remove members")
    if user_id == actor.pk:
        raise GroupError("Use 'leave' to leave the group yourself.")
    m = _target(group, user_id)
    if actor_m.role_in_group == ROLE.CO_ADMIN and m.role_in_group != ROLE.MEMBER:
        raise PermissionDenied("Co-admins can only remove ordinary members.")
    new_status = STATUS.BANNED if ban else STATUS.REMOVED
    if m.status == new_status:
        raise GroupError(f"That user is already {new_status}.")
    was_active = m.status == STATUS.ACTIVE
    if not ban and not was_active:
        raise GroupError("That user is not an active member.")
    m.status, m.role_in_group = new_status, ROLE.MEMBER
    m.save()
    if was_active:
        _count(group, -1)
    return m


@transaction.atomic
def change_role(group, actor, user_id: int, role: str) -> GroupMember:
    group = _lock(group)
    _require_role(group, actor, (ROLE.ADMIN,), "change roles")
    m = _target(group, user_id)
    if m.status != STATUS.ACTIVE:
        raise GroupError("Only active members can be given a role.")
    if m.role_in_group == ROLE.ADMIN and role != ROLE.ADMIN and _active_admin_count(group) == 1:
        raise GroupError("A group must keep at least one admin.")
    m.role_in_group = role
    m.save()
    return m


# --------------------------------------------------------------------------
# Account deletion
# --------------------------------------------------------------------------
def withdraw_user(user) -> None:
    """
    Deleted account: leave every group. If they were the only admin of a group
    that still has members, the longest-standing member becomes admin.
    """
    for m in GroupMember.objects.filter(user=user, status=STATUS.ACTIVE).select_related("group"):
        with transaction.atomic():
            group = _lock(m.group)
            if m.role_in_group == ROLE.ADMIN and _active_admin_count(group) == 1:
                others = (GroupMember.objects.select_for_update()
                          .filter(group=group, status=STATUS.ACTIVE).exclude(user=user)
                          .order_by("joined_at"))
                # Prefer the longest-standing co-admin, otherwise the longest-standing member.
                successor = others.filter(role_in_group=ROLE.CO_ADMIN).first() or others.first()
                if successor:
                    successor.role_in_group = ROLE.ADMIN
                    successor.save()
            GroupMember.objects.filter(pk=m.pk).update(status=STATUS.INACTIVE)
            _count(group, -1)
