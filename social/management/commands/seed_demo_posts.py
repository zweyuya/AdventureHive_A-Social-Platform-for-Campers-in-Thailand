"""Demo newsfeed: group and trip posts, reactions, comments and one post awaiting approval."""
import uuid
from datetime import timedelta

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from communities import services as groups
from communities.models import CampingGroup, GroupMember
from social import services as feed
from social.models import Post
from trips.models import Trip

DOMAIN = "demo.adventurehive.test"


def _photo(location):
    """Reuse a campsite's cover photo for a demo post, if it has one."""
    if not (location and location.cover_image):
        return None
    try:
        with location.cover_image.open("rb") as f:
            return ContentFile(f.read(), name=f"{uuid.uuid4().hex}.jpg")
    except (FileNotFoundError, OSError):
        return None


class Command(BaseCommand):
    help = "Create demo posts in groups and trips (idempotent; needs seed_demo first)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true",
                            help="Delete existing demo posts first, then recreate them.")

    @transaction.atomic
    def handle(self, *args, **options):
        u = {x.profile.display_name: x for x in
             User.objects.filter(email__endswith=f"@{DOMAIN}").select_related("profile")}
        if "Nok" not in u:
            self.stdout.write("Run seed_demo first.")
            return
        demo_posts = Post.objects.filter(user__in=u.values())
        if options.get("reset"):
            for p in demo_posts.exclude(image=""):
                p.image.delete(save=False)
            demo_posts.delete()
            from notifications.models import Notification, ReferenceType
            Notification.objects.filter(recipient__in=u.values(), reference_type=ReferenceType.POST).delete()
        if demo_posts.exists():
            self.stdout.write("Demo posts already exist — nothing to do.")
            return

        g = {x.name: x for x in CampingGroup.objects.filter(created_by__in=u.values())}
        khaoyai, bkk, river = g["Khao Yai Campers"], g["Bangkok Car Campers"], g["Kanchanaburi River Crew"]
        for name in ("Jee", "Beam"):  # give the private group a few more members
            if not GroupMember.objects.filter(group=river, user=u[name], status="active").exists():
                groups.add_member(river, u["Tono"], u[name])
        past = Trip.objects.get(title="Pha Taem Sunrise Trip", organizer=u["Ploy"])
        river_trip = Trip.objects.get(title="Kanchanaburi River Camp", organizer=u["Tono"])

        now = timezone.now()
        made = []

        def post(user, hours_ago, text, **where):
            p = feed.create_post(user, content_text=text, **where)
            Post.objects.filter(pk=p.pk).update(created_at=now - timedelta(hours=hours_ago))
            made.append(p)
            return p

        # Khao Yai Campers (public)
        p1 = post(u["Ploy"], 30, "Morning fog at Lam Ta Khong today — totally worth the 5am alarm. "
                                 "Campground was quiet, restrooms clean. 🏕️",
                  group=khaoyai, image=_photo(_loc("Lam Ta Khong Campground")))
        for name, kind in (("Nok", "love"), ("Mint", "wow"), ("June", "like"), ("Palm", "love")):
            feed.react(p1, u[name], kind)
        c = feed.add_comment(p1, u["June"], "Beautiful! Did you need to book a spot in advance?")
        feed.add_comment(p1, u["Ploy"], "Weekdays no, but weekends book through the DNP site.", parent_id=c.pk)
        feed.add_comment(p1, u["Nok"], "Adding this to our next trip list.")

        p2 = post(u["Palm"], 8, "Anyone have a spare 2-person tent to lend for next weekend? "
                                "Mine has a broken pole 😢", group=khaoyai)
        feed.react(p2, u["Jee"], "sad")
        feed.add_comment(p2, u["Mint"], "I have one — message me and I'll bring it to the meet-up.")

        # Bangkok Car Campers (public)
        p3 = post(u["Beam"], 50, "Tip: the Shell station on Highway 2 before Pak Chong has the last cheap ice. "
                                 "Fill your cooler there.", group=bkk)
        for name, kind in (("Ploy", "like"), ("Tono", "haha")):
            feed.react(p3, u[name], kind)

        # Kanchanaburi River Crew (private): admin post live, member post waits for approval
        p4 = post(u["Tono"], 20, "Water level at the river spot is good this month. "
                                 "Planning another trip after the Erawan one — ideas welcome.", group=river)
        feed.react(p4, u["Nok"], "like")
        feed.react(p4, u["Jee"], "love")
        feed.add_comment(p4, u["Beam"], "Sai Yok Noi next?")
        post(u["Jee"], 3, "Found a quieter bend about 2 km upstream — shared the pin with Tono.", group=river)
        river_pending = post(u["Nok"], 1, "Can we bring kayaks on the next river trip? "
                                          "I can borrow two from my cousin.", group=river)
        jee_post = Post.objects.filter(user=u["Jee"], group=river).first()
        feed.review_post(jee_post, u["Tono"], approve=True)

        # Trip posts (members only)
        p5 = post(u["Ploy"], 70, "Thanks everyone for coming! Sunrise photo from the cliff 🌅 "
                                 "Reviews for Pha Taem are now open for those who attended.",
                  trip=past, image=_photo(past.location))
        for name, kind in (("Nok", "love"), ("Mint", "love"), ("Tono", "wow")):
            feed.react(p5, u[name], kind)
        feed.add_comment(p5, u["Mint"], "Best sunrise I've seen in Thailand.")
        post(u["Jee"], 12, "Who's driving from Bangkok? I can share fuel costs.", trip=river_trip)

        self.stdout.write(self.style.SUCCESS(
            f"Created {len(made)} demo posts. Nok's post in the private Kanchanaburi River Crew "
            f"(#{river_pending.pk}) is waiting for approval — log in as tono@{DOMAIN} to approve it."))


def _loc(name):
    from locations.models import Location
    return Location.objects.filter(name=name).first()
