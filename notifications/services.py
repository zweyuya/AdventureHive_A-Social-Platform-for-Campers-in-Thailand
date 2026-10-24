from .models import Notification


def notify(recipient, type, reference_type, reference_id, actor=None):
    """Create an in-app notification (shown when the user next loads the app)."""
    if recipient is None:
        return None
    return Notification.objects.create(
        recipient=recipient, actor=actor, type=type,
        reference_type=reference_type, reference_id=reference_id,
    )
