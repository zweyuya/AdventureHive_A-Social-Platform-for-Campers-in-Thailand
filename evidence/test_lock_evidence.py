"""
Readable evidence that the trip row lock prevents overbooking.

    pytest evidence/test_lock_evidence.py -s

20 users press "Join" at the same instant on a trip with 1 seat, 5 rounds per mode.
Each user is a separate thread with its own database connection and transaction,
like separate web requests. The rounds run twice:

  WITH row lock     - the real code: services._lock() uses SELECT ... FOR UPDATE
  WITHOUT row lock  - the same code with the lock replaced by a plain SELECT,
                      to show what the lock is protecting against

The test FAILS if any WITH-lock round is wrong. WITHOUT-lock results are only
reported (race outcomes vary from run to run), never hidden or adjusted.
"""
import os
import threading

import pytest
from django.db import connection

from trips import services
from trips.models import ParticipantStatus as PS
from trips.models import Trip, TripParticipant

ROUNDS, PEOPLE, SEATS = 5, 20, 1
_COLOUR = os.environ.get("NO_COLOR") is None
GREEN, RED, BOLD, RESET = ("\033[92m", "\033[91m", "\033[1m", "\033[0m") if _COLOUR else ("",) * 4


def _race(trip, users):
    """Release every user at the same instant; return the errors they hit."""
    barrier = threading.Barrier(len(users))
    errors = []

    def worker(user):
        try:
            barrier.wait()
            services.rsvp(Trip.objects.get(pk=trip.pk), user)
        except Exception as exc:
            errors.append(type(exc).__name__)
        finally:
            connection.close()  # each thread has its own connection

    threads = [threading.Thread(target=worker, args=(u,)) for u in users]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return errors


def _round(make_trip, users):
    trip = make_trip(capacity=SEATS)
    errors = _race(trip, users)
    trip.refresh_from_db()
    rows = list(TripParticipant.objects.filter(trip=trip).values_list("status", flat=True))
    confirmed, waitlisted = rows.count(PS.CONFIRMED), rows.count(PS.WAITLISTED)
    correct = (confirmed == SEATS and waitlisted == PEOPLE - SEATS and not errors
               and trip.confirmed_count == SEATS)
    if correct:
        verdict = f"{GREEN}correct{RESET}"
    elif confirmed > SEATS:
        verdict = f"{RED}OVERBOOKED{RESET}"
    else:
        verdict = f"{RED}INCONSISTENT{RESET}"
    return confirmed, waitlisted, len(errors), trip.confirmed_count, correct, verdict


@pytest.mark.django_db(transaction=True)
def test_row_lock_prevents_overbooking(make_trip, make_user, monkeypatch):
    users = [make_user() for _ in range(PEOPLE)]  # reused across rounds (new trip each time)

    print(f"\n{PEOPLE} users press 'Join' at the same instant on a trip with {SEATS} seat "
          f"({ROUNDS} rounds each)\n")
    print(BOLD + f"{'Mode':<20}{'Round':>6}{'Confirmed':>11}{'Waitlisted':>12}{'Errors':>8}"
          f"{'confirmed_count':>17}   Result" + RESET)
    print("-" * 92)

    def run(mode):
        results = []
        for n in range(1, ROUNDS + 1):
            c, w, e, cc, ok, verdict = _round(make_trip, users)
            results.append(ok)
            print(f"{mode:<20}{n:>6}{c:>11}{w:>12}{e:>8}{cc:>17}   {verdict}")
        return results

    with_lock = run("WITH row lock")
    print()
    # Same code, but the lock becomes a plain read (what the code would be without it).
    monkeypatch.setattr(services, "_lock", lambda trip: Trip.objects.get(pk=trip.pk))
    without_lock = run("WITHOUT row lock")

    print(f"\nWITH lock: {GREEN if all(with_lock) else RED}{sum(with_lock)}/{ROUNDS} correct{RESET}"
          f"    WITHOUT lock: {sum(without_lock)}/{ROUNDS} correct")
    assert all(with_lock), "the row lock failed to prevent a double booking"
