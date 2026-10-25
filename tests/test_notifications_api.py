"""Notifications API (bell icon) and the public recent-reviews feed."""
import pytest
from rest_framework.test import APIClient

from trips import services


@pytest.mark.django_db
def test_notifications_list_messages_links_and_mark_read(make_trip, make_user, login):
    trip = make_trip(capacity=1)
    a, b = make_user(), make_user()
    services.rsvp(trip, a)
    services.rsvp(trip, b)          # waitlisted
    services.cancel_rsvp(trip, a)   # b promoted

    client = login(b, client=APIClient())
    body = client.get("/api/notifications/").json()
    assert body["unread_count"] == 2
    latest = body["results"][0]
    assert latest["type"] == "waitlist_promoted"
    assert trip.title in latest["message"]
    assert latest["link"] == f"/trips/{trip.pk}"

    assert client.post("/api/notifications/read-all/").json() == {"marked": 2}
    assert client.get("/api/notifications/").json()["unread_count"] == 0


@pytest.mark.django_db
def test_notifications_are_private(make_trip, make_user, login, api_client):
    trip = make_trip()
    services.rsvp(trip, make_user())
    other = login(make_user(), client=APIClient())
    assert other.get("/api/notifications/").json()["results"] == []
    assert api_client.get("/api/notifications/").status_code == 401


@pytest.mark.django_db
def test_recent_reviews_feed_is_public(api_client):
    res = api_client.get("/api/reviews/")
    assert res.status_code == 200 and res.json()["count"] == 0


@pytest.mark.django_db
def test_seed_demo_runs_and_is_idempotent(api_client):
    from django.core.management import call_command
    call_command("seed_demo")
    call_command("seed_demo")
    assert api_client.get("/api/trips/").json()["count"] == 3
    assert api_client.get("/api/reviews/").json()["count"] == 2
    assert api_client.get("/api/groups/").json()["count"] == 4
