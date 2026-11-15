"""
Fresh trip for a live check-in + attendance demo (run it on presentation day).

    python manage.py demo_checkin_trip

Creates a trip organised by Ploy at Lam Ta Khong that ended 2 hours ago, with
Nok, Beam and June confirmed. Check-in is still open (until 24 h after the end)
and attendance is not recorded yet. Needs the demo users (seed_demo).

Running it again first deletes the previous demo trip(s) (same title, organised
by the demo Ploy) together with their reviews, and recalculates the campsite rating.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from locations.models import Location
from reviews.services import recalculate_rating
from trips import services
from trips.models import Trip, TripStatus

DOMAIN = "demo.adventurehive.test"
TITLE = "Khao Yai Overnight (just finished)"


def delete_old_demo_trips() -> int:
    """Only trips with exactly this title by the demo Ploy; their reviews cascade with them."""
    old = Trip.objects.filter(organizer__email=f"ploy@{DOMAIN}", title=TITLE)
    sites = set(old.values_list("location_id", flat=True))
    count = old.count()
    old.delete()
    for site_id in sites:
        recalculate_rating(site_id)
    return count


def create_checkin_demo_trip() -> Trip:
    people = {name: User.objects.filter(email=f"{name.lower()}@{DOMAIN}").first()
              for name in ("Ploy", "Nok", "Beam", "June")}
    if not all(people.values()):
        raise CommandError("Demo users not found. Run: python manage.py seed_demo")
    site = Location.objects.published().get(name="Lam Ta Khong Campground")
    now = timezone.now()
    trip = Trip.objects.create(
        organizer=people["Ploy"], location=site, title=TITLE,
        # created far in the future (so it never overlaps Ploy's real trips),
        # then moved into the past below
        status=TripStatus.DRAFT, start_datetime=now + timedelta(days=365),
        end_datetime=now + timedelta(days=366), participant_capacity=4,
        meeting_point_name="Khao Yai Visitor Center", meeting_latitude=14.44,
        meeting_longitude=101.37, description="Demo trip for check-in and attendance.")
    services.publish(trip)
    for name in ("Nok", "Beam", "June"):
        services.rsvp(Trip.objects.get(pk=trip.pk), people[name])
    Trip.objects.filter(pk=trip.pk).update(start_datetime=now - timedelta(days=1),
                                           end_datetime=now - timedelta(hours=2))
    services.complete_finished_trips()
    return Trip.objects.get(pk=trip.pk)


class Command(BaseCommand):
    help = "Create a trip that just ended, for a live check-in + attendance demo."

    @transaction.atomic
    def handle(self, *args, **options):
        removed = delete_old_demo_trips()
        trip = create_checkin_demo_trip()
        if removed:
            self.stdout.write(f"Removed {removed} old demo trip(s) and their reviews.")
        self.stdout.write(self.style.SUCCESS(
            f"Trip #{trip.pk} '{trip.title}' — check-in code {services.checkin_code(trip)}\n"
            f"Open http://localhost:5173/trips/{trip.pk}\n"
            f"  1. Log in as nok@{DOMAIN} (password DemoCamp123!) and enter the code\n"
            f"  2. Log in as ploy@{DOMAIN}: Record attendance (Nok pre-ticked; Beam needs a "
            f"reason; June no-show)\n"
            f"  3. Log in as nok again: Write a review → badge 'Verified attendee · checked in'"))
