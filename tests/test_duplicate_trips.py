"""
Duplicate trips by the same organizer.

Rule A: an organizer cannot have two ACTIVE trips (draft / published / full) with
        the same title, ignoring capitals and spaces at the ends. Completed and
        cancelled trips free the title again.
Rule B: an organizer cannot have two ACTIVE trips whose dates overlap.
Other organizers are never blocked.

Each rule is checked twice: by the API (friendly 400 message) and by PostgreSQL
(partial unique index + exclusion constraint), which also stops two requests
that arrive at the same moment.
"""
import threading
from datetime import timedelta
from unittest import mock

import pytest
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from trips import services
from trips.models import Trip, TripStatus


def _trip(organizer, location, title="Khao Yai", days=10, length=2, status=TripStatus.PUBLISHED):
    start = timezone.now() + timedelta(days=days)
    return Trip.objects.create(organizer=organizer, location=location, title=title,
                               start_datetime=start, end_datetime=start + timedelta(days=length),
                               participant_capacity=4, status=status)


def _db_rejects(**kwargs):
    with pytest.raises(IntegrityError) as exc, transaction.atomic():
        _trip(**kwargs)
    return str(exc.value)


def _payload(location, title="Khao Yai", days=10, length=2):
    start = timezone.now() + timedelta(days=days)
    return {"location_id": location.pk, "title": title, "start_datetime": start.isoformat(),
            "end_datetime": (start + timedelta(days=length)).isoformat(),
            "participant_capacity": 4}


# ---- database level: rule A (same title) -------------------------------------------
@pytest.mark.django_db
@pytest.mark.parametrize("title", ["Khao Yai", "khao yai", "  KHAO YAI  "])
def test_db_blocks_same_title_for_same_organizer(user, location, title):
    _trip(user, location, "Khao Yai", days=10)
    msg = _db_rejects(organizer=user, location=location, title=title, days=40)
    assert "trips_unique_active_title_per_organizer" in msg


@pytest.mark.django_db
@pytest.mark.parametrize("old_status", [TripStatus.COMPLETED, TripStatus.CANCELLED])
def test_db_allows_title_again_after_old_trip_is_completed_or_cancelled(user, location, old_status):
    _trip(user, location, "Khao Yai", days=10, status=old_status)
    _trip(user, location, "Khao Yai", days=40)  # no error


@pytest.mark.django_db
def test_db_allows_same_title_and_dates_for_another_organizer(make_user, location):
    _trip(make_user(), location, "Khao Yai", days=10)
    _trip(make_user(), location, "Khao Yai", days=10)  # no error


# ---- database level: rule B (overlapping dates) ------------------------------------
@pytest.mark.django_db
def test_db_blocks_overlapping_dates_for_same_organizer(user, location):
    _trip(user, location, "Khao Yai", days=10, length=2)
    msg = _db_rejects(organizer=user, location=location, title="Doi Inthanon", days=11)
    assert "trips_no_overlap_per_organizer" in msg


@pytest.mark.django_db
def test_db_allows_back_to_back_trips(user, location):
    first = _trip(user, location, "Khao Yai", days=10, length=2)
    Trip.objects.create(organizer=user, location=location, title="Doi Inthanon",
                        start_datetime=first.end_datetime,  # starts exactly when the first ends
                        end_datetime=first.end_datetime + timedelta(days=1), participant_capacity=4)


@pytest.mark.django_db
def test_db_ignores_cancelled_trips_for_overlap(user, location):
    _trip(user, location, "Khao Yai", days=10, status=TripStatus.CANCELLED)
    _trip(user, location, "Doi Inthanon", days=10)  # no error


# ---- API level ---------------------------------------------------------------------
@pytest.mark.django_db
def test_api_explains_duplicate_title(user, location, login):
    client = login(user)
    assert client.post("/api/trips/", _payload(location, days=10), format="json").status_code == 201
    res = client.post("/api/trips/", _payload(location, " khao  yai ", days=40), format="json")
    assert res.status_code == 400
    assert "already have an active trip called 'Khao Yai'" in res.json()["title"][0]


@pytest.mark.django_db
def test_api_explains_overlapping_dates(user, location, login):
    client = login(user)
    client.post("/api/trips/", _payload(location, "Khao Yai", days=10), format="json")
    res = client.post("/api/trips/", _payload(location, "Doi Inthanon", days=11), format="json")
    assert res.status_code == 400
    assert "overlap your trip 'Khao Yai'" in res.json()["start_datetime"][0]


@pytest.mark.django_db
def test_api_cleans_extra_spaces_in_title(user, location, login):
    client = login(user)
    res = client.post("/api/trips/", _payload(location, "  Khao   Yai  "), format="json")
    assert res.json()["title"] == "Khao Yai"


@pytest.mark.django_db
def test_api_blocks_renaming_into_a_clash_but_allows_editing_own_trip(user, location, login):
    client = login(user)
    client.post("/api/trips/", _payload(location, "Khao Yai", days=10), format="json")
    other = client.post("/api/trips/", _payload(location, "Doi Inthanon", days=40),
                        format="json").json()
    res = client.patch(f"/api/trips/{other['id']}/", {"title": "KHAO YAI"}, format="json")
    assert res.status_code == 400 and "title" in res.json()
    # keeping its own title / changing other fields is fine (the trip does not clash with itself)
    res = client.patch(f"/api/trips/{other['id']}/", {"title": "Doi Inthanon",
                                                       "participant_capacity": 6}, format="json")
    assert res.status_code == 200


@pytest.mark.django_db
def test_api_allows_same_title_for_another_organizer(make_user, location, login, api_client):
    from rest_framework.test import APIClient
    a, b = make_user(), make_user()
    assert login(a).post("/api/trips/", _payload(location), format="json").status_code == 201
    assert login(b, client=APIClient()).post("/api/trips/", _payload(location),
                                             format="json").status_code == 201


@pytest.mark.django_db
def test_db_error_becomes_a_400_not_a_500(user, location, login):
    """If the app check is skipped (e.g. two requests at once), the DB still says no,
    and the API turns that into a normal 400 message."""
    client = login(user)
    client.post("/api/trips/", _payload(location, days=10), format="json")
    with mock.patch("trips.serializers.duplicate_trip_error", return_value=None):
        res = client.post("/api/trips/", _payload(location, days=40), format="json")
    assert res.status_code == 400
    assert "already have an active trip with this title" in str(res.json()["title"])


@pytest.mark.django_db
def test_organizer_name_is_on_trip_cards(user, location, api_client):
    trip = _trip(user, location)
    card = api_client.get("/api/trips/").json()["results"][0]
    assert card["id"] == trip.pk and card["organizer"]["display_name"]


# ---- two requests at the same moment -----------------------------------------------
@pytest.mark.django_db(transaction=True)
def test_double_click_create_makes_only_one_trip(user, location):
    """Five threads (separate connections, like five clicks on 'Create') insert the
    same trip at the same instant. PostgreSQL lets exactly one through."""
    barrier = threading.Barrier(5)
    results = []

    def worker():
        try:
            barrier.wait()
            with services.duplicate_guard():
                _trip(user, location, "Khao Yai", days=10)
            results.append("created")
        except services.TripError:
            results.append("rejected")
        finally:
            connection.close()

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["created"] + ["rejected"] * 4
    assert Trip.objects.filter(organizer=user, title="Khao Yai").count() == 1
