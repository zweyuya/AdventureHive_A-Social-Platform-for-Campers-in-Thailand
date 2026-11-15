"""
Straight-line distance from the meeting point to the campsite, on the trip page.

It is shown only to people who may see the meeting point (the organizer and confirmed or
attended participants). Together with the public campsite pin, the distance would narrow
down where the private meeting point is, so it is hidden from everyone else.
"""
from math import pi

import pytest
from rest_framework.test import APIClient

from core.provinces import distance_km
from trips import services


@pytest.mark.unit
def test_haversine_one_degree_of_latitude():
    """One degree along a meridian is 6371 * pi / 180 = 111.19 km on our sphere."""
    assert distance_km(14.0, 100.0, 15.0, 100.0) == pytest.approx(6371 * pi / 180, abs=1e-9)


@pytest.mark.unit
def test_haversine_is_symmetric_and_zero_for_the_same_point():
    assert distance_km(14.44, 101.37, 14.43, 101.38) == pytest.approx(distance_km(14.43, 101.38, 14.44, 101.37))
    assert distance_km(14.44, 101.37, 14.44, 101.37) == 0


@pytest.fixture
def trip(make_trip, location):
    # 0.1 degrees south of the campsite, same longitude: 11.1 km in a straight line
    return make_trip(capacity=1, meeting_point_name="Park gate",
                     meeting_latitude=location.latitude - 0.1, meeting_longitude=location.longitude)


def _distance(client, trip):
    return client.get(f"/api/trips/{trip.pk}/").json()["meeting_distance_km"]


@pytest.mark.django_db
def test_organizer_sees_the_distance_rounded(trip, login):
    assert _distance(login(trip.organizer), trip) == 11.1


@pytest.mark.django_db
def test_confirmed_participant_sees_the_distance(trip, make_user, login):
    person = make_user()
    services.rsvp(trip, person)
    assert _distance(login(person), trip) == 11.1


@pytest.mark.django_db
def test_distance_is_hidden_with_the_meeting_point(trip, make_user, login, api_client):
    services.rsvp(trip, make_user())             # takes the only seat
    waiting = make_user()
    services.rsvp(trip, waiting)                 # waitlisted
    for client in (api_client, login(make_user(), client=APIClient()), login(waiting, client=APIClient())):
        data = client.get(f"/api/trips/{trip.pk}/").json()
        assert data["meeting_point_hidden"] is True
        assert data["meeting_latitude"] is None and data["meeting_distance_km"] is None


@pytest.mark.django_db
def test_no_meeting_point_means_no_distance(make_trip, login):
    trip = make_trip()
    assert _distance(login(trip.organizer), trip) is None


@pytest.mark.django_db
def test_distance_is_not_in_the_public_trip_list(trip, api_client):
    row = api_client.get("/api/trips/").json()["results"][0]
    assert "meeting_distance_km" not in row
