"""
Security round (professor's comment: authorization and access to sensitive information).

A. Deleting a private group must not make its trips public.
B. Emergency contacts: opt-in sharing with the organizer, only around the trip,
   every read logged and the participant notified.
"""
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import EmergencyContact, User
from communities import services as groups
from notifications.models import Notification
from trips import services
from trips.models import EmergencyContactAccess, Trip, TripStatus


# ---------------- A. Private group deletion ----------------------------------------

@pytest.fixture
def private_group_trips(make_user, make_trip):
    admin, member, stranger = make_user(), make_user(), make_user()
    group = groups.create_group(admin, {"name": "Secret campers", "privacy_type": "private",
                                        "category": "general"})
    groups.add_member(group, admin, member)
    upcoming = make_trip(organizer=admin, group=group, capacity=4)
    past = make_trip(organizer=admin, group=group, capacity=4)
    services.rsvp(upcoming, member)
    services.rsvp(past, member)
    now = timezone.now()
    Trip.objects.filter(pk=past.pk).update(start_datetime=now - timedelta(days=5),
                                           end_datetime=now - timedelta(days=3))
    services.complete_finished_trips()
    return group, admin, member, stranger, upcoming, past


@pytest.mark.django_db
def test_deleting_a_private_group_does_not_make_its_trips_public(private_group_trips, login,
                                                                 api_client):
    group, admin, member, stranger, upcoming, past = private_group_trips
    stranger_client = login(stranger, client=APIClient())
    for trip in (upcoming, past):  # before: hidden from outsiders
        assert stranger_client.get(f"/api/trips/{trip.pk}/").status_code == 404

    groups.delete_group(group, admin)

    upcoming.refresh_from_db()
    past.refresh_from_db()
    assert upcoming.status == TripStatus.CANCELLED          # upcoming trips are cancelled…
    assert Notification.objects.filter(recipient=member, type="trip_cancelled").exists()
    assert upcoming.members_only and past.members_only      # …and all become members-only
    for trip in (upcoming, past):                            # after: still hidden from outsiders
        assert stranger_client.get(f"/api/trips/{trip.pk}/").status_code == 404
        assert api_client.get(f"/api/trips/{trip.pk}/").status_code == 404
        # …but the organizer and the people who joined keep their history
        assert login(member, client=APIClient()).get(f"/api/trips/{trip.pk}/").status_code == 200
        assert login(admin, client=APIClient()).get(f"/api/trips/{trip.pk}/").status_code == 200
    listed = {t["id"] for t in stranger_client.get("/api/trips/?status=completed").json()["results"]}
    assert past.pk not in listed


@pytest.mark.django_db
def test_deleting_a_public_group_keeps_its_trips_public(make_user, make_trip, api_client):
    admin = make_user()
    group = groups.create_group(admin, {"name": "Open campers", "privacy_type": "public",
                                        "category": "general"})
    trip = make_trip(organizer=admin, group=group)
    groups.delete_group(group, admin)
    trip.refresh_from_db()
    assert trip.status == TripStatus.PUBLISHED and not trip.members_only
    assert api_client.get(f"/api/trips/{trip.pk}/").status_code == 200


# ---------------- B. Emergency contact sharing --------------------------------------

@pytest.fixture
def running_trip(make_trip, make_user):
    """A trip happening right now (inside the emergency window) with 2 confirmed people."""
    trip = make_trip(capacity=3)
    sharer, private = make_user(), make_user()
    for u in (sharer, private):
        services.rsvp(trip, u)
        EmergencyContact.objects.create(user=u, name=f"Mum of {u.pk}", phone="+66811111111",
                                        relationship="mother")
    now = timezone.now()
    Trip.objects.filter(pk=trip.pk).update(start_datetime=now - timedelta(hours=3),
                                           end_datetime=now + timedelta(days=1))
    trip.refresh_from_db()
    return trip, sharer, private


def _contacts(client, trip):
    return client.get(f"/api/trips/{trip.pk}/emergency-contacts/")


@pytest.mark.django_db
def test_organizer_sees_only_contacts_that_were_shared(running_trip, login):
    trip, sharer, private = running_trip
    sharer_client = login(sharer, client=APIClient())
    assert sharer_client.post(f"/api/trips/{trip.pk}/emergency-sharing/").status_code == 200

    rows = _contacts(login(trip.organizer, client=APIClient()), trip).json()
    assert [r["user_id"] for r in rows] == [sharer.pk]       # the private one is not there
    assert rows[0]["name"] == f"Mum of {sharer.pk}" and rows[0]["phone"] == "+66811111111"


@pytest.mark.django_db
def test_every_read_is_logged_and_the_participant_is_told_once(running_trip, login):
    trip, sharer, _ = running_trip
    services.set_emergency_sharing(trip, sharer, share=True)
    organizer = login(trip.organizer, client=APIClient())
    _contacts(organizer, trip)
    _contacts(organizer, trip)
    assert EmergencyContactAccess.objects.filter(trip=trip, participant=sharer).count() == 2
    told = Notification.objects.filter(recipient=sharer, type="emergency_contact_viewed")
    assert told.count() == 1  # one notification per trip, not per click


@pytest.mark.django_db
def test_stop_sharing_hides_the_contact_again(running_trip, login):
    trip, sharer, _ = running_trip
    client = login(sharer, client=APIClient())
    client.post(f"/api/trips/{trip.pk}/emergency-sharing/")
    assert client.delete(f"/api/trips/{trip.pk}/emergency-sharing/").status_code == 200
    assert _contacts(login(trip.organizer, client=APIClient()), trip).json() == []


@pytest.mark.django_db
def test_contacts_only_open_around_the_trip(make_trip, make_user, login):
    trip, user = make_trip(days_from_now=10), make_user()
    services.rsvp(trip, user)
    EmergencyContact.objects.create(user=user, name="Dad", phone="+66822222222",
                                    relationship="father")
    services.set_emergency_sharing(trip, user, share=True)   # sharing early is fine…
    res = _contacts(login(trip.organizer, client=APIClient()), trip)
    assert res.status_code == 400 and "can be opened from" in str(res.json())  # …reading is not
    assert not EmergencyContactAccess.objects.exists()

    now = timezone.now()  # long after the trip: closed again
    Trip.objects.filter(pk=trip.pk).update(start_datetime=now - timedelta(days=5),
                                           end_datetime=now - timedelta(days=3))
    assert _contacts(login(trip.organizer, client=APIClient()), trip).status_code == 400


@pytest.mark.django_db
def test_admins_and_other_participants_cannot_read_shared_contacts(running_trip, login):
    trip, sharer, private = running_trip
    services.set_emergency_sharing(trip, sharer, share=True)
    admin = User.objects.create_superuser(email="mod@example.com", password="Adm1n-Pass!")
    assert _contacts(login(admin, password="Adm1n-Pass!", client=APIClient()), trip).status_code == 403
    assert _contacts(login(private, client=APIClient()), trip).status_code == 403


@pytest.mark.django_db
def test_sharing_needs_a_contact_and_a_confirmed_seat(make_trip, make_user, login):
    trip = make_trip(capacity=1)
    no_contact, waiting = make_user(), make_user()
    services.rsvp(trip, no_contact)
    services.rsvp(trip, waiting)
    EmergencyContact.objects.create(user=waiting, name="X", phone="+66833333333",
                                    relationship="friend")
    res = login(no_contact, client=APIClient()).post(f"/api/trips/{trip.pk}/emergency-sharing/")
    assert res.status_code == 400 and "Add an emergency contact" in str(res.json())
    res = login(waiting, client=APIClient()).post(f"/api/trips/{trip.pk}/emergency-sharing/")
    assert res.status_code == 400 and "Only confirmed" in str(res.json())


@pytest.mark.django_db
def test_rejoining_a_trip_resets_sharing(running_trip):
    trip, sharer, _ = running_trip
    Trip.objects.filter(pk=trip.pk).update(start_datetime=timezone.now() + timedelta(days=2),
                                           end_datetime=timezone.now() + timedelta(days=3))
    trip.refresh_from_db()
    services.set_emergency_sharing(trip, sharer, share=True)
    services.cancel_rsvp(trip, sharer)
    services.rsvp(trip, sharer)
    assert not trip.participants.get(user=sharer).share_emergency_contact  # must opt in again
