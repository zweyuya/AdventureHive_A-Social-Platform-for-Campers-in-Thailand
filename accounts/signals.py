from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile, User


@receiver(post_save, sender=User)
def ensure_profile(sender, instance, created, raw=False, **kwargs):
    """Every user has a profile — including superusers made with createsuperuser."""
    if created and not raw:
        Profile.objects.get_or_create(
            user=instance, defaults={"display_name": instance.email.split("@")[0][:100]}
        )
