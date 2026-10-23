from django.core.management.base import BaseCommand

from accounts.models import InterestTag

TAGS = [
    "car camping", "backpacking", "family camping", "van life", "glamping",
    "hiking", "stargazing", "photography", "birdwatching", "waterfalls",
    "mountains", "beach camping", "fishing", "cooking outdoors", "solo camping",
]


class Command(BaseCommand):
    help = "Create the interest tags users pick at registration (idempotent)."

    def handle(self, *args, **options):
        created = sum(InterestTag.objects.get_or_create(tag_name=t)[1] for t in TAGS)
        self.stdout.write(self.style.SUCCESS(f"{created} new tags, {len(TAGS)} total."))
