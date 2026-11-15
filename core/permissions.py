from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsOwner(BasePermission):
    """
    Object belongs to the requesting user (obj.user, or obj itself for User).
    No exception for staff: used for emergency contacts, which nobody but the
    owner may read — including admins.
    """

    message = "Only the owner can access this resource."

    def has_object_permission(self, request, view, obj):
        owner_id = getattr(obj, "user_id", None) or getattr(obj, "pk", None)
        return request.user.is_authenticated and owner_id == request.user.pk


class IsSelfOrReadOnly(BasePermission):
    """Anyone may read a public profile; only the user may edit their own."""

    message = "You can only edit your own profile."

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        # obj may be a Profile (owner = obj.user_id) or a User (owner = obj.pk).
        owner_id = getattr(obj, "user_id", None) or obj.pk
        return request.user.is_authenticated and owner_id == request.user.pk


def can_moderate_campsites(user) -> bool:
    return user.is_authenticated and (user.is_staff or user.is_moderator)


class CanModerateCampsites(BasePermission):
    """
    Platform admins and campsite moderators. A moderator cannot decide their own
    submission. Admins can, because a small site may have only one admin.
    """

    message = "Only campsite moderators can do this."

    def has_permission(self, request, view):
        return can_moderate_campsites(request.user)

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        if obj.created_by_id == request.user.pk:
            self.message = "You submitted this campsite, so another moderator must decide."
            return False
        return True
