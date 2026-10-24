from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from .models import EmergencyContact, User, UserStatus


def blacklist_all_tokens(user: User) -> None:
    """Invalidate every refresh token the user holds (all devices)."""
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)


@transaction.atomic
def delete_account(user: User) -> None:
    """
    PDPA account deletion = anonymisation.

    Personal data is erased (email, phone, password, profile details, interest
    tags, emergency contact). The user row is kept as an anonymous "Deleted
    user" so trips they organised and reviews they wrote stay consistent for
    other people (and campsite ratings do not silently change).

    Their active RSVPs are cancelled (waitlisted people are promoted into the
    freed seats) and upcoming trips they organise are cancelled with notices.
    They leave all groups; a sole group admin is succeeded by the longest-standing
    co-admin (or member).
    """
    from communities.services import withdraw_user as leave_groups  # local imports
    from trips.services import withdraw_user as leave_trips          # avoid cycles

    leave_trips(user)
    leave_groups(user)
    user = User.objects.select_for_update().get(pk=user.pk)
    now = timezone.now()

    EmergencyContact.objects.filter(user=user).delete()

    user.email = f"deleted-{user.pk}@deleted.invalid"
    user.phone = None
    user.set_unusable_password()
    user.status = UserStatus.DELETED
    user.deleted_at = now
    user.is_staff = False
    user.is_superuser = False
    user.save()

    profile = getattr(user, "profile", None)
    if profile is not None:
        profile.display_name = "Deleted user"
        profile.bio = ""
        profile.date_of_birth = None
        profile.gender = ""
        profile.city = ""
        profile.save()
        profile.interest_tags.clear()

    blacklist_all_tokens(user)
