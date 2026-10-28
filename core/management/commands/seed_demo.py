"""
Demo data for screenshots and the progress presentation.

    python manage.py seed_campsites   # first
    python manage.py seed_demo

Creates clearly fake accounts (@demo.adventurehive.test, password: DemoCamp123!),
groups, upcoming trips with RSVPs and a waitlist, one completed trip with attendance
and verified reviews (both badge types), one trip that ended 2 hours ago for a live
check-in + attendance demo, and a few Q&A threads. Everything goes through the same
service functions as the API, so all business rules still apply.
Safe to re-run: it does nothing if the demo users already exist.
"""
from datetime import timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import InterestTag, User
from communities import services as groups
from locations.models import Location
from qa import services as qa
from qa.models import Question
from reviews import services as reviews
from trips import services as trips
from trips.management.commands.demo_checkin_trip import create_checkin_demo_trip
from trips.models import Trip, TripEquipmentItem, TripParticipant, TripStatus

PASSWORD = "DemoCamp123!"
DOMAIN = "demo.adventurehive.test"
PEOPLE = [  # nickname (login: <nickname>@DOMAIN), surname, experience level
    ("Nok", "Srisuk", "intermediate"), ("Ploy", "Chaiyaporn", "advanced"),
    ("Mint", "Rattanakul", "intermediate"), ("Palm", "Wongsawat", "beginner"),
    ("Tono", "Phromsuwan", "advanced"), ("June", "Thongdee", "beginner"),
    ("Jee", "Saetang", "intermediate"), ("Beam", "Boonmee", "expert"),
]
FULL_NAMES = {f"{nick.lower()}@{DOMAIN}": f"{nick} {surname}" for nick, surname, _ in PEOPLE}


class Command(BaseCommand):
    help = "Create demo users, groups, trips, reviews and Q&A (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        if User.objects.filter(email=f"nok@{DOMAIN}").exists():
            self.stdout.write("Demo data already exists — nothing to do.")
            return
        if not Location.objects.published().exists():
            call_command("seed_campsites")
        call_command("seed_interest_tags")

        tags = list(InterestTag.objects.all())
        u = {}
        for i, (name, surname, level) in enumerate(PEOPLE):
            user = User.objects.create_user(email=f"{name.lower()}@{DOMAIN}", password=PASSWORD,
                                            pdpa_consent_at=timezone.now())
            user.profile.display_name = f"{name} {surname}"
            user.profile.camping_experience_level = level
            user.profile.city = ["Bangkok", "Chiang Mai", "Khon Kaen", "Phuket"][i % 4]
            user.profile.save()
            user.profile.interest_tags.set(tags[i % len(tags): i % len(tags) + 3])
            u[name] = user

        site = {loc.name: loc for loc in Location.objects.published()}
        khao_yai = site["Lam Ta Khong Campground"]
        kanchanaburi = site["Erawan Waterfall Campground"]
        inthanon = site["Doi Inthanon Park HQ Campground"]
        pha_taem = site["Pha Taem Campground"]

        # ---- groups -----------------------------------------------------------------
        g_khaoyai = groups.create_group(u["Nok"], {
            "name": "Khao Yai Campers", "category": "general",
            "description": "Weekend trips to Khao Yai National Park."})
        g_bkk = groups.create_group(u["Ploy"], {
            "name": "Bangkok Car Campers", "category": "car_camping",
            "description": "Drive out of the city, pitch a tent, come back Sunday."})
        g_family = groups.create_group(u["Mint"], {
            "name": "Family Camping Thailand", "category": "family_camping",
            "description": "Kid-friendly campsites with restrooms and easy access."})
        g_river = groups.create_group(u["Tono"], {
            "name": "Kanchanaburi River Crew", "category": "general", "privacy_type": "private",
            "description": "Invite-only riverside trips."})
        for name in ("Ploy", "Mint", "Palm", "June", "Jee"):
            groups.join(g_khaoyai, u[name])
        for name in ("Nok", "Tono", "Beam"):
            groups.join(g_bkk, u[name])
        for name in ("Palm", "June"):
            groups.join(g_family, u[name])
        groups.add_member(g_river, u["Tono"], u["Nok"])
        groups.change_role(g_khaoyai, u["Nok"], u["Ploy"].pk, "co_admin")

        now = timezone.now()

        def make_trip(organizer, location, title, days, capacity, **extra):
            start = timezone.localtime(now + timedelta(days=days)).replace(
                hour=8, minute=0, second=0, microsecond=0)  # 08:00 Bangkok time
            trip = Trip.objects.create(
                organizer=organizer, location=location, title=title, status=TripStatus.DRAFT,
                start_datetime=start, end_datetime=start + timedelta(days=2),
                participant_capacity=capacity, **extra)
            trips.publish(trip)
            return Trip.objects.get(pk=trip.pk)

        # ---- upcoming trips ------------------------------------------------------------
        t1 = make_trip(u["Nok"], khao_yai, "Khao Yai Weekend Camp", 12, 6, group=g_khaoyai,
                       difficulty="moderate", distance_km=12.5, estimated_duration_hours=6,
                       meeting_point_name="Khao Yai Visitor Center",
                       meeting_latitude=14.44, meeting_longitude=101.37,
                       description="A relaxing weekend at Khao Yai: good company, stargazing "
                                   "and a chance to disconnect. Suitable for beginners.",
                       safety_notes="Watch for wildlife at dusk; bring rain gear.")
        TripEquipmentItem.objects.create(trip=t1, item_name="Tent (4-person)",
                                         provided_by="participant", notes="2-person or bigger")
        TripEquipmentItem.objects.create(trip=t1, item_name="Cooking stove",
                                         provided_by="organizer", notes="Shared")
        for name in ("Ploy", "Mint", "Palm", "June"):
            trips.rsvp(t1, u[name])

        t2 = make_trip(u["Tono"], kanchanaburi, "Kanchanaburi River Camp", 20, 2,
                       difficulty="easy", description="Riverside camping near Erawan falls.")
        for name in ("Jee", "Beam", "Palm"):   # capacity 2 → Palm waitlisted
            trips.rsvp(t2, u[name])

        t3 = make_trip(u["Mint"], inthanon, "Doi Inthanon Stargazing Camp", 30, 10,
                       difficulty="moderate", min_experience_level="intermediate",
                       description="Cold, clear skies at Thailand's highest peak.")
        for name in ("Nok", "Tono", "Beam"):
            trips.rsvp(t3, u[name])

        # ---- a completed trip with attendance and verified reviews -------------------
        past = make_trip(u["Ploy"], pha_taem, "Pha Taem Sunrise Trip", 5, 5,
                         description="Cliff-top sunrise over the Mekong.")
        for name in ("Nok", "Mint", "Tono", "Jee"):
            trips.rsvp(past, u[name])
        Trip.objects.filter(pk=past.pk).update(start_datetime=now - timedelta(days=6),
                                               end_datetime=now - timedelta(days=4))
        trips.complete_finished_trips()
        past.refresh_from_db()
        # Nok and Mint checked in with the trip code; Tono's phone died, so Ploy
        # confirms him with a reason (shows the weaker "Confirmed by organizer" badge).
        TripParticipant.objects.filter(trip=past, user__in=[u["Nok"], u["Mint"]]).update(
            checked_in_at=past.start_datetime + timedelta(minutes=20))
        trips.mark_attendance(past, u["Ploy"], [
            {"user_id": u["Nok"].pk, "status": "attended"},
            {"user_id": u["Mint"].pk, "status": "attended"},
            {"user_id": u["Tono"].pk, "status": "attended",
             "reason": "His phone battery died; he camped with us both nights."},
            {"user_id": u["Jee"].pk, "status": "no_show"},
        ])
        reviews.create_review(u["Nok"], past, 5, "Incredible sunrise and a very well organised trip.")
        reviews.create_review(u["Mint"], past, 4, "Clean restrooms, a bit windy at night.")
        reviews.create_review(u["Tono"], past, 4, "Great cliff views. Bring a power bank!")

        # ---- a trip that ended 2 hours ago: live check-in + attendance demo -------------
        # (re-create a fresh one on presentation day: python manage.py demo_checkin_trip)
        create_checkin_demo_trip()

        # ---- Q&A -------------------------------------------------------------------------
        q1 = Question.objects.create(author=u["June"], location=khao_yai,
                                     title="Is there drinking water at the campground?",
                                     body="Planning a trip in December with my family.")
        a1 = qa.post_answer(q1, u["Nok"], "Yes, there are taps near the restrooms. "
                                          "Bring a bottle to refill.")
        qa.accept_answer(q1, u["June"], a1)
        q2 = Question.objects.create(author=u["Palm"], location=inthanon,
                                     title="How cold does it get in January?",
                                     body="Do I need a winter sleeping bag?")
        qa.post_answer(q2, u["Beam"], "It can drop to around 5°C at night. "
                                      "A warm sleeping bag is a must.")
        Question.objects.create(author=u["Jee"], location=pha_taem,
                                title="Are campfires allowed?", body="Thinking of a BBQ.")

        call_command("seed_demo_posts", stdout=self.stdout)

        self.stdout.write(self.style.SUCCESS(
            f"Demo data created. Log in as nok@{DOMAIN} (or ploy, mint, palm, tono, june, "
            f"jee, beam) with password {PASSWORD}"))
