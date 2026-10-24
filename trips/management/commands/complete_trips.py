"""
Mark finished trips as completed. Schedule it, e.g. every 15 minutes with cron:

    */15 * * * * cd /path/to/adventurehive && .venv/bin/python manage.py complete_trips

Safe to run any number of times.
"""
from django.core.management.base import BaseCommand

from trips.services import complete_finished_trips


class Command(BaseCommand):
    help = "Complete trips whose end time has passed; cancel stale drafts. Idempotent."

    def handle(self, *args, **options):
        result = complete_finished_trips()
        self.stdout.write(self.style.SUCCESS(
            f"{result['completed']} trip(s) completed, "
            f"{result['cancelled_drafts']} stale draft(s) cancelled."
        ))
