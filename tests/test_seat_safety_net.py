"""
Second safety net against overbooking, and no hard user deletion in the admin.

The trigger counts the real 'confirmed' rows at COMMIT, so overbooking is rejected
by PostgreSQL even when the stored counter is wrong or a code path forgot the row lock.
The admin has no delete: the cascade would remove RSVP rows without freeing the seat
or promoting the waitlist. Accounts go through the delete_account service instead.
"""
import threading
from unittest import mock

import pytest
from django.db import IntegrityError, OperationalError, connection, transaction
from django.test import Client

from accounts.models import UserStatus
from trips import services
from trips.models import ParticipantStatus as PS
from trips.models import Trip, TripParticipant


def _confirmed(trip):
    return TripParticipant.objects.filter(trip=trip, status=PS.CONFIRMED).count()


def _insert(trip, user, status=PS.CONFIRMED, position=None):
    """Writes a row directly: no lock, no counter update (the bug the trigger must catch)."""
    return TripParticipant.objects.create(trip=trip, user=user, status=status,
                                          waitlist_position=position)


def _rejected_at_commit(fn):
    """Runs fn and the deferred checks; returns the database's error message."""
    with pytest.raises(IntegrityError) as exc, transaction.atomic():
        fn()
        connection.check_constraints()
    return str(exc.value)


# ---- the trigger -------------------------------------------------------------------
@pytest.mark.django_db
def test_db_rejects_overbooking_even_when_the_counter_is_wrong(make_trip, make_user):
    trip = make_trip(capacity=1)
    a, b = make_user(), make_user()

    def overbook():
        _insert(trip, a)
        _insert(trip, b)

    msg = _rejected_at_commit(overbook)
    assert "seat_rule" in msg and "2 confirmed participants but only 1 seats" in msg
    trip.refresh_from_db()
    assert trip.confirmed_count == 0  # the stored counter never noticed: the old CHECK passes


@pytest.mark.django_db
def test_db_allows_exactly_full_and_ignores_the_waitlist(make_trip, make_user):
    trip = make_trip(capacity=1)
    _insert(trip, make_user())
    _insert(trip, make_user(), PS.WAITLISTED, 1)
    connection.check_constraints()  # no error
    assert _confirmed(trip) == 1


@pytest.mark.django_db
def test_db_rejects_promoting_a_waitlisted_row_into_a_full_trip(make_trip, make_user):
    trip = make_trip(capacity=1)
    _insert(trip, make_user())
    waiting = _insert(trip, make_user(), PS.WAITLISTED, 1)

    def promote():
        TripParticipant.objects.filter(pk=waiting.pk).update(status=PS.CONFIRMED,
                                                             waitlist_position=None)

    assert "seat_rule" in _rejected_at_commit(promote)


@pytest.mark.django_db
def test_db_rejects_lowering_capacity_below_the_real_rows(make_trip, make_user):
    trip = make_trip(capacity=2)
    _insert(trip, make_user())
    _insert(trip, make_user())

    def lower():
        Trip.objects.filter(pk=trip.pk).update(participant_capacity=1)

    assert "seat_rule" in _rejected_at_commit(lower)


@pytest.mark.django_db(transaction=True)
def test_db_rejects_at_a_real_commit_and_saves_nothing(make_trip, make_user):
    trip = make_trip(capacity=1)
    a, b = make_user(), make_user()
    with pytest.raises(IntegrityError, match="seat_rule"), transaction.atomic():
        _insert(trip, a)
        _insert(trip, b)
    assert TripParticipant.objects.filter(trip=trip).count() == 0


# ---- normal flows must keep working ------------------------------------------------
@pytest.mark.django_db(transaction=True)
def test_raising_capacity_still_promotes_the_waitlist(make_trip, make_user):
    """Promotion happens before the new capacity is saved: only a deferred check allows it."""
    trip = make_trip(capacity=1)
    first, second = make_user(), make_user()
    services.rsvp(trip, first)
    services.rsvp(Trip.objects.get(pk=trip.pk), second)
    services.update_trip(Trip.objects.get(pk=trip.pk), {"participant_capacity": 2})
    assert TripParticipant.objects.get(trip=trip, user=second).status == PS.CONFIRMED
    assert _confirmed(trip) == 2


@pytest.mark.django_db(transaction=True)
def test_cancelling_still_promotes_the_waitlist(make_trip, make_user):
    trip = make_trip(capacity=1)
    first, second = make_user(), make_user()
    services.rsvp(trip, first)
    services.rsvp(Trip.objects.get(pk=trip.pk), second)
    services.cancel_rsvp(Trip.objects.get(pk=trip.pk), first)
    assert TripParticipant.objects.get(trip=trip, user=second).status == PS.CONFIRMED
    assert _confirmed(trip) == 1


# ---- a code path forgets the row lock ----------------------------------------------
@pytest.mark.django_db(transaction=True)
def test_race_without_the_row_lock_still_cannot_overbook(make_trip, make_user):
    """Without the lock this race confirms 14-18 people for one seat. Now PostgreSQL
    lets one through. Refused requests get a database error, not a seat."""
    trip = make_trip(capacity=1)
    users = [make_user() for _ in range(20)]
    barrier = threading.Barrier(len(users))
    unexpected = []

    def worker(user):
        try:
            barrier.wait()
            services.rsvp(Trip.objects.get(pk=trip.pk), user)
        except (IntegrityError, OperationalError):
            pass  # refused: the safety net, the waitlist constraint, or a deadlock on it
        except Exception as exc:  # pragma: no cover - surfaced by the assertion below
            unexpected.append(repr(exc))
        finally:
            connection.close()

    with mock.patch.object(services, "_lock", lambda t: Trip.objects.get(pk=t.pk)):
        threads = [threading.Thread(target=worker, args=(u,)) for u in users]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    assert unexpected == []
    assert _confirmed(trip) == 1


# ---- admin: no hard delete ---------------------------------------------------------
@pytest.fixture
def admin_client(db, make_user):
    admin = make_user(is_staff=True, is_superuser=True)
    client = Client()
    client.force_login(admin)
    client.admin = admin
    return client


@pytest.mark.django_db
def test_admin_has_no_delete_for_users(admin_client, make_user):
    target = make_user()
    page = admin_client.get(f"/admin/accounts/user/{target.pk}/change/").content.decode()
    assert "deletelink" not in page
    assert admin_client.get(f"/admin/accounts/user/{target.pk}/delete/").status_code == 403

    changelist = admin_client.get("/admin/accounts/user/").content.decode()
    assert 'value="delete_selected"' not in changelist
    assert 'value="delete_accounts"' in changelist

    admin_client.post("/admin/accounts/user/", {"action": "delete_selected",
                                                "_selected_action": [target.pk], "post": "yes"})
    assert type(target).objects.filter(pk=target.pk).exists()


def _run_action(client, target, **extra):
    return client.post("/admin/accounts/user/", {"action": "delete_accounts",
                                                 "_selected_action": [target.pk], **extra})


@pytest.mark.django_db
def test_admin_action_asks_first_and_changes_nothing(admin_client, make_user):
    target = make_user()
    res = _run_action(admin_client, target)
    assert res.status_code == 200 and b"cannot be undone" in res.content
    target.refresh_from_db()
    assert target.status == UserStatus.ACTIVE


@pytest.mark.django_db
def test_admin_action_frees_the_seat_and_promotes_the_waitlist(admin_client, make_trip, make_user):
    trip = make_trip(capacity=1)
    leaving, waiting = make_user(), make_user()
    services.rsvp(trip, leaving)
    services.rsvp(Trip.objects.get(pk=trip.pk), waiting)

    assert _run_action(admin_client, leaving, apply="1").status_code == 302

    leaving.refresh_from_db()
    assert leaving.status == UserStatus.DELETED and leaving.email.endswith("@deleted.invalid")
    assert TripParticipant.objects.get(trip=trip, user=waiting).status == PS.CONFIRMED
    trip.refresh_from_db()
    assert trip.confirmed_count == _confirmed(trip) == 1


@pytest.mark.django_db
def test_admin_cannot_delete_their_own_account_with_the_action(admin_client):
    _run_action(admin_client, admin_client.admin, apply="1")
    admin_client.admin.refresh_from_db()
    assert admin_client.admin.status == UserStatus.ACTIVE


@pytest.mark.django_db
def test_hard_delete_is_the_bug_the_admin_change_prevents(make_trip, make_user):
    """The ORM cascade (what the admin's delete did): the row goes, nothing else is updated."""
    trip = make_trip(capacity=1)
    leaving, waiting = make_user(), make_user()
    services.rsvp(trip, leaving)
    services.rsvp(Trip.objects.get(pk=trip.pk), waiting)
    leaving.delete()
    trip.refresh_from_db()
    assert trip.confirmed_count == 1 and _confirmed(trip) == 0
    assert TripParticipant.objects.get(trip=trip, user=waiting).status == PS.WAITLISTED
