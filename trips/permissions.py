from rest_framework.permissions import BasePermission


class IsOrganizer(BasePermission):
    """Only the trip's organizer. Admins are NOT included (participant privacy)."""

    message = "Only the trip organizer can do this."

    def has_object_permission(self, request, view, obj):
        return request.user.is_authenticated and obj.organizer_id == request.user.pk


class IsOrganizerOrStaff(BasePermission):
    """Organizer, or platform staff (for moderation: cancelling a trip)."""

    message = "Only the trip organizer or a moderator can do this."

    def has_object_permission(self, request, view, obj):
        user = request.user
        return user.is_authenticated and (obj.organizer_id == user.pk or user.is_staff)
