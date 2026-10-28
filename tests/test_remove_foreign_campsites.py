"""remove_foreign_campsites: finds pins outside Thailand; deletes or archives them."""
import io

import pytest
from django.core.management import call_command

from locations.models import Location, LocationStatus


def _run(*args):
    out = io.StringIO()
    call_command("remove_foreign_campsites", *args, stdout=out)
    return out.getvalue()


def _site(name, lat, lng, status=LocationStatus.PUBLISHED):
    # Siem Reap / Luang Prabang are inside the old rectangle CHECK, so the DB accepts them
    return Location.objects.create(name=name, province="Sa Kaeo", latitude=lat, longitude=lng,
                                   category="campground", status=status)


@pytest.mark.django_db
def test_report_only_by_default_and_seed_campsites_all_pass():
    call_command("seed_campsites", stdout=io.StringIO())
    assert "All 15 campsites are inside Thailand." in _run()
    cambodia = _site("Khao tai", 13.36, 103.86, LocationStatus.PENDING_REVIEW)
    out = _run()
    assert "'Khao tai'" in out and "Cambodia" in out and "Nothing changed" in out
    assert Location.objects.filter(pk=cambodia.pk).exists()


@pytest.mark.django_db
def test_delete_removes_foreign_sites_and_archives_ones_with_trips(make_trip, location):
    cambodia = _site("Khao tai", 13.36, 103.86)
    laos = _site("Luang Prabang riverside", 19.88, 102.13)
    trip = make_trip()
    trip.location = laos
    trip.save(update_fields=["location"])

    out = _run("--delete")

    assert not Location.objects.filter(pk=cambodia.pk).exists()
    laos.refresh_from_db()
    assert laos.status == LocationStatus.ARCHIVED and "outside Thailand" in laos.moderation_note
    assert Location.objects.get(pk=location.pk).status == LocationStatus.PUBLISHED  # Thai one kept
    assert "deleted" in out and "archived" in out
    assert "All" not in _run()  # archived one is still reported, nothing else
