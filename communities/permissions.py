"""
Group-level permissions. They read group_members.role_in_group for the
requesting user — a different system from Django's platform roles.
"""
from rest_framework.permissions import BasePermission

from .models import GroupMember, GroupMemberRole, GroupMemberStatus


def _role(group, user):
    if not user.is_authenticated:
        return None
    return GroupMember.objects.filter(group=group, user=user, status=GroupMemberStatus.ACTIVE) \
        .values_list("role_in_group", flat=True).first()


class IsGroupAdmin(BasePermission):
    message = "Only group admins can do this."

    def has_object_permission(self, request, view, obj):
        return _role(obj, request.user) == GroupMemberRole.ADMIN


class IsGroupModerator(BasePermission):
    """Admins and co-admins."""

    message = "Only group admins or co-admins can do this."

    def has_object_permission(self, request, view, obj):
        return _role(obj, request.user) in (GroupMemberRole.ADMIN, GroupMemberRole.CO_ADMIN)
