"""
Layer 4 — scheduled completion, organizer-recorded attendance, and the link to
review credibility (professor's comment: "how is attendance verified?").
"""
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from notifications.models import Notification
from reviews.models import Review
from trips import services
from trips.models import ParticipantStatus as PS
from trips.models import Trip, TripParticipant, TripStatus


@pytest.fixture
def finished_trip(make_trip, make_user):
    """A published trip with 2 confirmed + 1 waitlisted, that ended an hour ago."""
    trip = make_trip(capacity=2)
    people = [make_user() for _ in range(3)]
    for p in people:
        services.rsvp(trip, p)
    now = timezone.now()
    Trip.objects.filter(pk=trip.pk).update(start_datetime=now - timedelta(days=2),
                                           end_datetime=now - timedelta(hours=1))
    trip.refresh_from_db()
    return trip, people


# ---------------- complete_trips command -----------------------------------------

@pytest.mark.django_db
def test_complete_trips_command(finished_trip, make_trip):
    trip, (a, b, waiter) = finished_trip
    future = make_trip()
    stale_draft = make_trip(status=TripStatus.DRAFT, days_from_now=-10)

    call_command("complete_trips")

    trip.refresh_from_db()
    assert trip.status == TripStatus.COMPLETED
    # Confirmed people stay confirmed until the organizer records attendance
    assert set(trip.participants.filter(status=PS.CONFIRMED).values_list("user_id", flat=True)) \
        == {a.pk, b.pk}
    w = TripParticipant.objects.get(trip=trip, user=waiter)
    assert w.status == PS.CANCELLED and w.waitlist_position is None
    assert Trip.objects.get(pk=future.pk).status == TripStatus.PUBLISHED
    assert Trip.objects.get(pk=stale_draft.pk).status == TripStatus.CANCELLED
    assert Notification.objects.filter(recipient=trip.organizer, type="trip_reminder").exists()


@pytest.mark.django_db
def test_complete_trips_is_idempotent(finished_trip):
    trip, _ = finished_trip
    assert services.complete_finished_trips() == {"completed": 1, "cancelled_drafts": 0}
    assert services.complete_finished_trips() == {"completed": 0, "cancelled_drafts": 0}


# ---------------- Attendance -------------------------------------------------------

def _mark(client, trip, records):
    return client.post(f"/api/trips/{trip.pk}/attendance/", {"records": records}, format="json")


@pytest.mark.django_db
def test_organizer_marks_attendance(finished_trip, login):
    trip, (a, b, _) = finished_trip
    services.complete_finished_trips()
    client = login(trip.organizer, client=APIClient())
    res = _mark(client, trip, [{"user_id": a.pk, "status": "attended"},
                               {"user_id": b.pk, "status": "no_show"}])
    assert res.status_code == 200, res.content
    pa = TripParticipant.objects.get(trip=trip, user=a)
    assert pa.status == PS.ATTENDED and pa.attendance_marked_by == trip.organizer
    assert TripParticipant.objects.get(trip=trip, user=b).status == PS.NO_SHOW
    assert Notification.objects.filter(recipient=a, type="review_unlocked").exists()
    assert not Notification.objects.filter(recipient=b, type="review_unlocked").exists()


@pytest.mark.django_db
def test_attendance_only_after_completion(make_trip, make_user, login):
    trip = make_trip()
    u = make_user()
    services.rsvp(trip, u)
    client = login(trip.organizer, client=APIClient())
    res = _mark(client, trip, [{"user_id": u.pk, "status": "attended"}])
    assert res.status_code == 400 and "completed" in str(res.json())


@pytest.mark.django_db
def test_attendance_window_closes_after_7_days(finished_trip, login):
    trip, (a, _, _) = finished_trip
    services.complete_finished_trips()
    Trip.objects.filter(pk=trip.pk).update(end_datetime=timezone.now() - timedelta(days=8),
                                           start_datetime=timezone.now() - timedelta(days=9))
    client = login(trip.organizer, client=APIClient())
    res = _mark(client, trip, [{"user_id": a.pk, "status": "attended"}])
    assert res.status_code == 400 and "7 days" in str(res.json())


@pytest.mark.django_db
def test_only_organizer_marks_attendance(finished_trip, login):
    trip, (a, _, _) = finished_trip
    services.complete_finished_trips()
    client = login(a, client=APIClient())  # a participant tries to mark themselves
    assert _mark(client, trip, [{"user_id": a.pk, "status": "attended"}]).status_code == 403


@pytest.mark.django_db
def test_cannot_mark_people_who_were_not_confirmed(finished_trip, make_user, login):
    trip, (_, _, waiter) = finished_trip
    services.complete_finished_trips()
    stranger = make_user()
    client = login(trip.organizer, client=APIClient())
    for uid in (waiter.pk, stranger.pk):  # waitlisted (now cancelled) / never joined
        res = _mark(client, trip, [{"user_id": uid, "status": "attended"}])
        assert res.status_code == 400 and "Not confirmed" in str(res.json())


@pytest.mark.django_db
def test_attendance_is_all_or_nothing(finished_trip, make_user, login):
    trip, (a, _, _) = finished_trip
    services.complete_finished_trips()
    client = login(trip.organizer, client=APIClient())
    res = _mark(client, trip, [{"user_id": a.pk, "status": "attended"},
                               {"user_id": make_user().pk, "status": "attended"}])
    assert res.status_code == 400
    assert TripParticipant.objects.get(trip=trip, user=a).status == PS.CONFIRMED


# ---------------- Link to reviews -------------------------------------------------

@pytest.mark.django_db
def test_only_attended_participants_can_review(finished_trip, login):
    trip, (a, b, _) = finished_trip
    services.complete_finished_trips()
    services.mark_attendance(trip, trip.organizer, [{"user_id": a.pk, "status": "attended"},
                                                    {"user_id": b.pk, "status": "no_show"}])
    Review.objects.create(trip=trip, user=a, location=trip.location, rating=5)
    with pytest.raises(IntegrityError), transaction.atomic():
        Review.objects.create(trip=trip, user=b, location=trip.location, rating=1)


@pytest.mark.django_db
def test_attendance_of_reviewer_cannot_be_revoked(finished_trip, login):
    trip, (a, _, _) = finished_trip
    services.complete_finished_trips()
    services.mark_attendance(trip, trip.organizer, [{"user_id": a.pk, "status": "attended"}])
    Review.objects.create(trip=trip, user=a, location=trip.location, rating=5)
    client = login(trip.organizer, client=APIClient())
    res = _mark(client, trip, [{"user_id": a.pk, "status": "no_show"}])
    assert res.status_code == 400 and "already reviewed" in str(res.json())


# ---------------- Account deletion frees seats --------------------------------------

@pytest.mark.django_db
def test_deleting_account_frees_seat_and_cancels_organised_trips(make_trip, make_user):
    from accounts.services import delete_account
    trip = make_trip(capacity=1)
    leaver, waiter = make_user(), make_user()
    services.rsvp(trip, leaver)
    services.rsvp(trip, waiter)
    own_trip = make_trip(organizer=leaver)

    delete_account(leaver)

    assert TripParticipant.objects.get(trip=trip, user=waiter).status == PS.CONFIRMED
    assert Trip.objects.get(pk=own_trip.pk).status == TripStatus.CANCELLED
