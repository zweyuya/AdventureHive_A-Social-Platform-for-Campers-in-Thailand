"""
Find campsites whose map pin is outside Thailand, and optionally remove them.

    python manage.py remove_foreign_campsites            # report only, changes nothing
    python manage.py remove_foreign_campsites --delete   # remove them

Uses the same border check as the API (core/provinces.py), so it catches pins in
Laos, Cambodia, Myanmar or Malaysia that the old rectangle check let through.

With --delete:
  - no trips at the campsite  -> deleted (its revisions, reviews and Q&A links go too)
  - trips use the campsite    -> can't be deleted without breaking those trips, so it
                                 is archived with a note: hidden from the public list and
                                 map, still visible to admins.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.provinces import check_pin
from locations.models import Location, LocationStatus

NOTE = "Removed: the map pin is outside Thailand ({where})."


class Command(BaseCommand):
    help = "List (and with --delete, remove) campsites whose pin is outside Thailand."

    def add_arguments(self, parser):
        parser.add_argument("--delete", action="store_true",
                            help="Delete them (or archive them if trips use them).")

    @transaction.atomic
    def handle(self, *args, **options):
        foreign = []
        for loc in Location.objects.order_by("id"):
            pin = check_pin(float(loc.latitude), float(loc.longitude))
            if not pin.in_thailand:
                foreign.append((loc, pin.country or "not in Thailand"))

        total = Location.objects.count()
        if not foreign:
            self.stdout.write(self.style.SUCCESS(f"All {total} campsites are inside Thailand."))
            return

        self.stdout.write(f"{len(foreign)} of {total} campsites are outside Thailand:")
        for loc, where in foreign:
            trips = loc.trips.count()
            self.stdout.write(f"  #{loc.pk} '{loc.name}' [{loc.status}] pin {loc.latitude}, "
                              f"{loc.longitude} -> {where}; {trips} trip(s)")
            if not options["delete"]:
                continue
            if trips:
                Location.objects.filter(pk=loc.pk).update(
                    status=LocationStatus.ARCHIVED, moderation_note=NOTE.format(where=where),
                    reviewed_at=timezone.now())
                self.stdout.write(self.style.WARNING("      -> archived (hidden): trips use it"))
            else:
                loc.delete()
                self.stdout.write(self.style.SUCCESS("      -> deleted"))

        if not options["delete"]:
            self.stdout.write("Nothing changed. Run again with --delete to remove them.")
