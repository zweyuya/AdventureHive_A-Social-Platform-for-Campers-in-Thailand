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
