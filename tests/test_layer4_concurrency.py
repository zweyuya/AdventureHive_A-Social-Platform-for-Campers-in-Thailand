"""
Concurrency: many people press "Join" for the last seat at the same instant.

Each thread uses its own database connection and its own transaction, exactly
like separate web requests. A barrier releases them all at once. Without the
row lock (SELECT ... FOR UPDATE) several of them could read "1 seat left" and
all be confirmed; with it, exactly one wins and the rest are waitlisted.
"""
import threading

import pytest
from django.db import connection

from trips import services
from trips.models import ParticipantStatus as PS
from trips.models import Trip, TripParticipant


def _race(trip, users):
    return _run_together([(services.rsvp, trip, u) for u in users])


def _run_together(jobs):
    """jobs = [(service_fn, trip, user), ...] — all released at the same instant."""
    barrier = threading.Barrier(len(jobs))
    errors = []

    def worker(fn, trip, user):
        try:
            barrier.wait()
            fn(Trip.objects.get(pk=trip.pk), user)
        except Exception as exc:  # pragma: no cover - surfaced by the assertion below
            errors.append(repr(exc))
        finally:
            connection.close()  # each thread has its own DB connection

    threads = [threading.Thread(target=worker, args=job) for job in jobs]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return errors


@pytest.mark.django_db(transaction=True)
def test_twenty_people_race_for_the_last_seat(make_trip, make_user):
    trip = make_trip(capacity=1)
    users = [make_user() for _ in range(20)]

    errors = _race(trip, users)

    assert errors == []
    trip.refresh_from_db()
    statuses = list(TripParticipant.objects.filter(trip=trip).values_list("status", flat=True))
    assert statuses.count(PS.CONFIRMED) == 1          # never overbooked
    assert statuses.count(PS.WAITLISTED) == 19
    assert trip.confirmed_count == 1
    positions = sorted(TripParticipant.objects.filter(trip=trip, status=PS.WAITLISTED)
                       .values_list("waitlist_position", flat=True))
    assert positions == list(range(1, 20))            # 1..19, no duplicates, no gaps


@pytest.mark.django_db(transaction=True)
def test_ten_people_race_for_three_seats(make_trip, make_user):
    trip = make_trip(capacity=3)
    errors = _race(trip, [make_user() for _ in range(10)])
    assert errors == []
    trip.refresh_from_db()
    assert trip.confirmed_count == 3 == trip.participants.filter(status=PS.CONFIRMED).count()
    assert trip.participants.filter(status=PS.WAITLISTED).count() == 7
    assert trip.status == "full"


@pytest.mark.django_db(transaction=True)
def test_cancel_racing_new_rsvps_gives_seat_to_waitlist_not_newcomers(make_trip, make_user):
    """
    A full trip with a waitlist: one confirmed person cancels at the same instant
    as several newcomers press "Join". Whatever order the lock grants, the freed
    seat must go to waitlist #1 — newcomers can never jump the queue.
    """
    trip = make_trip(capacity=3)
    confirmed = [make_user() for _ in range(3)]
    first_waiting, second_waiting = make_user(), make_user()
    for u in [*confirmed, first_waiting, second_waiting]:
        services.rsvp(Trip.objects.get(pk=trip.pk), u)

    newcomers = [make_user() for _ in range(8)]
    leaver = confirmed[0]
    errors = _run_together([(services.cancel_rsvp, trip, leaver),
                            *[(services.rsvp, trip, u) for u in newcomers]])

    assert errors == []
    trip.refresh_from_db()
    status_of = dict(TripParticipant.objects.filter(trip=trip).values_list("user_id", "status"))
    assert status_of[leaver.pk] == PS.CANCELLED
    assert status_of[first_waiting.pk] == PS.CONFIRMED       # the freed seat went to #1
    assert all(status_of[u.pk] == PS.WAITLISTED for u in newcomers)  # nobody jumped the queue
    assert trip.confirmed_count == 3 == trip.participants.filter(status=PS.CONFIRMED).count()
    assert trip.status == "full"

    waitlist = list(TripParticipant.objects.filter(trip=trip, status=PS.WAITLISTED)
                    .order_by("waitlist_position").values_list("user_id", "waitlist_position"))
    assert [pos for _, pos in waitlist] == list(range(1, 10))   # 1..9, no duplicates, no gaps
    assert waitlist[0][0] == second_waiting.pk                  # earlier waiter stays ahead
