"""
Tidy the demo accounts before a presentation.

    python manage.py tidy_demo_accounts --dry-run   # preview, changes nothing
    python manage.py tidy_demo_accounts

1. Gives the 8 demo users (…@demo.adventurehive.test) full Thai names, e.g. "Nok"
   becomes "Nok Srisuk". Logins, passwords, trips, reviews and photos are unchanged.
2. Removes the old test accounts (mali@example.com, nok@example.com):
   - no content of their own  -> deleted completely
   - they organised trips, wrote reviews, posts, ... -> anonymised with the normal
     PDPA account deletion, so other people's trips and ratings stay consistent.

Safe to re-run.
"""
from django.contrib.admin.models import LogEntry
from django.core.management.base import BaseCommand
from django.db import models, transaction
from django.db.models.deletion import Collector, ProtectedError

from accounts.models import EmergencyContact, Profile, User
from accounts.services import delete_account
from core.management.commands.seed_demo import FULL_NAMES

OLD_TEST_ACCOUNTS = ["mali@example.com", "nok@example.com"]

# Rows that belong only to the account itself; deleting them affects nobody else.
_OWN_ROWS = {User, Profile, EmergencyContact, LogEntry, Profile.interest_tags.through}


def _owns_shared_content(user) -> bool:
    """True if deleting the user would remove or orphan content other people see."""
    from notifications.models import Notification
    from rest_framework_simplejwt.token_blacklist.models import (BlacklistedToken,
                                                                 OutstandingToken)
    own = _OWN_ROWS | {Notification, OutstandingToken, BlacklistedToken}
    collector = Collector(using="default")
    try:
        collector.collect([user])
    except ProtectedError:      # e.g. organised a trip or created a group
        return True
    # anything cascaded besides their own rows (RSVPs, reviews, posts, answers, ...)
    if any(objs and model not in own for model, objs in collector.data.items()):
        return True
    # SET_NULL relations (campsites they submitted, edits they made, ...) would
    # silently lose their author
    for rel in User._meta.related_objects:
        if rel.on_delete is models.SET_NULL and \
                rel.related_model._base_manager.filter(**{rel.field.name: user}).exists():
            return True
    return False


class Command(BaseCommand):
    help = "Give demo users full Thai names and remove leftover test accounts."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Show what would change without saving anything.")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        with transaction.atomic():
            self._rename()
            self._remove_old()
            if dry:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("Dry run: nothing was saved."))
            else:
                self.stdout.write(self.style.SUCCESS("Done."))

    def _rename(self):
        for email, full_name in FULL_NAMES.items():
            profile = Profile.objects.filter(user__email=email).first()
            if profile is None:
                self.stdout.write(f"  skip   {email} (not found — run seed_demo)")
            elif profile.display_name == full_name:
                self.stdout.write(f"  ok     {email} already '{full_name}'")
            else:
                self.stdout.write(f"  rename {email}: '{profile.display_name}' -> '{full_name}'")
                profile.display_name = full_name
                profile.save(update_fields=["display_name"])

    def _remove_old(self):
        for email in OLD_TEST_ACCOUNTS:
            user = User.objects.filter(email=email).first()
            if user is None:
                self.stdout.write(f"  gone   {email} (already removed)")
            elif user.is_staff or user.is_superuser:
                self.stdout.write(self.style.WARNING(f"  keep   {email} is staff — not touched"))
            elif _owns_shared_content(user):
                delete_account(user)
                self.stdout.write(f"  anonymised {email} (had trips/reviews/posts; "
                                  f"now 'Deleted user', login disabled)")
            else:
                user.delete()
                self.stdout.write(f"  deleted {email}")
