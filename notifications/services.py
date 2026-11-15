from accounts.models import User, UserStatus

from .models import Notification


def notify(recipient, type, reference_type, reference_id, actor=None):
    """Create an in-app notification (shown when the user next loads the app)."""
    if recipient is None:
        return None
    return Notification.objects.create(
        recipient=recipient, actor=actor, type=type,
        reference_type=reference_type, reference_id=reference_id,
    )


def notify_admins(type, reference_type, reference_id, actor=None, exclude=()):
    """Every active staff user, except those in `exclude` (e.g. the people involved)."""
    admins = User.objects.filter(is_staff=True, status=UserStatus.ACTIVE).exclude(pk__in=exclude)
    return Notification.objects.bulk_create([
        Notification(recipient=admin, actor=actor, type=type,
                     reference_type=reference_type, reference_id=reference_id)
        for admin in admins
    ])
