"""
Layer 4 — RSVP & waitlist rules (written from the requirements first).

Covers the professor's "database reliability" comment:
  - capacity can never be exceeded (also under concurrent requests — see test_layer4_concurrency)
  - waitlist positions stay consistent (1..n, no gaps, no duplicates)
"""
import pytest
from rest_framework.test import APIClient

from communities.models import CampingGroup, GroupMember
from notifications.models import Notification
from trips.models import ParticipantStatus as PS
from trips.models import Trip, TripParticipant, TripStatus


@pytest.fixture
def people(make_user, login):
    """Five logged-in members, each with their own client."""
    out = []
    for _ in range(5):
        u = make_user()
        out.append((u, login(u, client=APIClient())))
    return out


def _rsvp(client, trip):
    return client.post(f"/api/trips/{trip.pk}/rsvp/")


def _leave(client, trip):
    return client.delete(f"/api/trips/{trip.pk}/rsvp/")


def _waitlist(trip):
    return list(TripParticipant.objects.filter(trip=trip, status=PS.WAITLISTED)
                .order_by("waitlist_position").values_list("user_id", "waitlist_position"))


# ---------------- Joining ------------------------------------------------------

@pytest.mark.django_db
def test_rsvp_below_capacity_is_confirmed(make_trip, people):
    trip = make_trip(capacity=2)
    user, client = people[0]
    res = _rsvp(client, trip)
    assert res.status_code == 201 and res.json()["status"] == "confirmed"
    trip.refresh_from_db()
    assert trip.confirmed_count == 1 and trip.status == TripStatus.PUBLISHED
    assert Notification.objects.filter(recipient=user, type="rsvp_confirmed").exists()


@pytest.mark.django_db
def test_capacity_full_next_rsvp_is_waitlisted_and_trip_becomes_full(make_trip, people):
    trip = make_trip(capacity=2)
    for _, c in people[:2]:
        assert _rsvp(c, trip).json()["status"] == "confirmed"
    trip.refresh_from_db()
    assert trip.status == TripStatus.FULL and trip.confirmed_count == 2

    third, fourth = people[2], people[3]
    r3, r4 = _rsvp(third[1], trip).json(), _rsvp(fourth[1], trip).json()
    assert (r3["status"], r3["waitlist_position"]) == ("waitlisted", 1)
    assert (r4["status"], r4["waitlist_position"]) == ("waitlisted", 2)
    trip.refresh_from_db()
    assert trip.confirmed_count == 2  # never above capacity
    assert Notification.objects.filter(recipient=third[0], type="rsvp_waitlisted").exists()


@pytest.mark.django_db
def test_duplicate_rsvp_rejected(make_trip, people):
    trip = make_trip(capacity=1)
    (_, a), (_, b) = people[:2]
    _rsvp(a, trip)
    _rsvp(b, trip)  # waitlisted
    for client in (a, b):
        res = _rsvp(client, trip)
        assert res.status_code == 400 and "already joined" in str(res.json())
    assert TripParticipant.objects.filter(trip=trip).count() == 2
    trip.refresh_from_db()
    assert trip.confirmed_count == 1


# ---------------- Cancelling & promotion ---------------------------------------

@pytest.mark.django_db
def test_cancel_then_promote_first_waitlisted_and_renumber(make_trip, people):
    trip = make_trip(capacity=1)
    (a, ca), (b, cb), (c, cc), (d, cd) = people[:4]
    for client in (ca, cb, cc, cd):
        _rsvp(client, trip)
    assert _waitlist(trip) == [(b.pk, 1), (c.pk, 2), (d.pk, 3)]

    res = _leave(ca, trip)
    assert res.status_code == 200 and res.json()["status"] == "cancelled"

    assert TripParticipant.objects.get(trip=trip, user=b).status == PS.CONFIRMED
    assert _waitlist(trip) == [(c.pk, 1), (d.pk, 2)]  # no gaps
    trip.refresh_from_db()
    assert trip.confirmed_count == 1 and trip.status == TripStatus.FULL
    assert Notification.objects.filter(recipient=b, type="waitlist_promoted").exists()


@pytest.mark.django_db
def test_cancel_with_empty_waitlist_reopens_trip(make_trip, people):
    trip = make_trip(capacity=1)
    _, client = people[0]
    _rsvp(client, trip)
    trip.refresh_from_db()
    assert trip.status == TripStatus.FULL
    _leave(client, trip)
    trip.refresh_from_db()
    assert trip.confirmed_count == 0 and trip.status == TripStatus.PUBLISHED


@pytest.mark.django_db
def test_leaving_the_waitlist_closes_the_gap(make_trip, people):
    trip = make_trip(capacity=1)
    (a, ca), (b, cb), (c, cc), (d, cd) = people[:4]
    for client in (ca, cb, cc, cd):
        _rsvp(client, trip)
    _leave(cc, trip)  # #2 on the waitlist leaves
    assert _waitlist(trip) == [(b.pk, 1), (d.pk, 2)]
    trip.refresh_from_db()
    assert trip.confirmed_count == 1


@pytest.mark.django_db
def test_rejoin_after_cancel_reuses_row_and_goes_to_back_of_waitlist(make_trip, people):
    trip = make_trip(capacity=1)
    (a, ca), (b, cb), (c, cc) = people[:3]
    _rsvp(ca, trip)
    _rsvp(cb, trip)
    _leave(cb, trip)
    _rsvp(cc, trip)            # c is now waitlist #1
    res = _rsvp(cb, trip)      # b re-joins
    assert res.status_code == 201
    assert res.json()["status"] == "waitlisted" and res.json()["waitlist_position"] == 2
    assert TripParticipant.objects.filter(trip=trip, user=b).count() == 1


@pytest.mark.django_db
def test_cannot_leave_a_trip_you_did_not_join(make_trip, people):
    trip = make_trip()
    assert _leave(people[0][1], trip).status_code == 400


@pytest.mark.django_db
def test_raising_capacity_promotes_waitlist(make_trip, people, login):
    trip = make_trip(capacity=1)
    (a, ca), (b, cb), (c, cc) = people[:3]
    for client in (ca, cb, cc):
        _rsvp(client, trip)
    organizer = login(trip.organizer, client=APIClient())
    res = organizer.patch(f"/api/trips/{trip.pk}/", {"participant_capacity": 2}, format="json")
    assert res.status_code == 200
    assert TripParticipant.objects.get(trip=trip, user=b).status == PS.CONFIRMED
    assert _waitlist(trip) == [(c.pk, 1)]
    trip.refresh_from_db()
    assert trip.confirmed_count == 2 and trip.status == TripStatus.FULL


@pytest.mark.django_db
def test_capacity_cannot_drop_below_confirmed(make_trip, people, login):
    trip = make_trip(capacity=3)
    for _, c in people[:2]:
        _rsvp(c, trip)
    organizer = login(trip.organizer, client=APIClient())
    res = organizer.patch(f"/api/trips/{trip.pk}/", {"participant_capacity": 1}, format="json")
    assert res.status_code == 400 and "participant_capacity" in res.json()


# ---------------- Eligibility -----------------------------------------------------

@pytest.mark.django_db
def test_experience_level_below_minimum_rejected(make_trip, people):
    trip = make_trip(min_experience_level="advanced")
    user, client = people[0]
    res = _rsvp(client, trip)
    assert res.status_code == 400 and "experience" in str(res.json())
    user.profile.camping_experience_level = "expert"
    user.profile.save()
    assert _rsvp(client, trip).status_code == 201


@pytest.mark.django_db
def test_organizer_cannot_rsvp_own_trip(make_trip, login):
    trip = make_trip()
    client = login(trip.organizer, client=APIClient())
    assert _rsvp(client, trip).status_code == 400


@pytest.mark.django_db
@pytest.mark.parametrize("status", [TripStatus.CANCELLED, TripStatus.COMPLETED])
def test_cannot_rsvp_closed_trips(make_trip, people, status):
    trip = make_trip(status=status)
    assert _rsvp(people[0][1], trip).status_code == 400


@pytest.mark.django_db
def test_cannot_rsvp_draft_trip(make_trip, people):
    trip = make_trip(status=TripStatus.DRAFT)
    assert _rsvp(people[0][1], trip).status_code == 404  # drafts are invisible


@pytest.mark.django_db
def test_cannot_rsvp_trip_that_already_started(make_trip, people):
    trip = make_trip(days_from_now=-1)  # started yesterday, ends tomorrow
    assert _rsvp(people[0][1], trip).status_code == 400


@pytest.mark.django_db
def test_anonymous_cannot_rsvp(make_trip, api_client):
    assert api_client.post(f"/api/trips/{make_trip().pk}/rsvp/").status_code == 401


@pytest.mark.django_db
def test_private_group_trip_hidden_from_non_members(make_trip, people):
    (member, cm), (outsider, co) = people[:2]
    group = CampingGroup.objects.create(name="Secret Hikers", privacy_type="private",
                                        created_by=member)
    GroupMember.objects.create(group=group, user=member, role_in_group="admin")
    trip = make_trip(group=group)
    assert co.get(f"/api/trips/{trip.pk}/").status_code == 404
    assert _rsvp(co, trip).status_code == 404
    assert APIClient().get(f"/api/trips/{trip.pk}/").status_code == 404
    assert _rsvp(cm, trip).status_code == 201


@pytest.mark.django_db
def test_rsvp_is_rate_limited(make_trip, people, monkeypatch):
    """RSVP flooding protection: the 'rsvp' throttle scope (10/min in settings)."""
    from rest_framework.throttling import ScopedRateThrottle
    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES",
                        {**ScopedRateThrottle.THROTTLE_RATES, "rsvp": "3/min"})
    trip = make_trip(capacity=10)
    _, client = people[0]
    codes = [_rsvp(client, trip).status_code, _leave(client, trip).status_code,
             _rsvp(client, trip).status_code, _leave(client, trip).status_code]
    assert codes == [201, 200, 201, 429]


@pytest.mark.django_db
def test_trip_row_count_matches_confirmed_count(make_trip, people):
    """Invariant: confirmed_count always equals the number of confirmed rows."""
    trip = make_trip(capacity=2)
    clients = [c for _, c in people]
    for c in clients:
        _rsvp(c, trip)
    _leave(clients[0], trip)
    _leave(clients[3], trip)
    _rsvp(clients[0], trip)
    trip = Trip.objects.get(pk=trip.pk)
    assert trip.confirmed_count == trip.participants.filter(status=PS.CONFIRMED).count() == 2
    positions = [p for _, p in _waitlist(trip)]
    assert positions == list(range(1, len(positions) + 1))
