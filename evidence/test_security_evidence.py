"""
Readable security evidence for the report (run on a real PostgreSQL test database).

    pytest evidence/test_security_evidence.py -k authorization -s
    pytest evidence/test_security_evidence.py -k csrf -s

Each test calls the live API and prints a table you can screenshot. It also FAILS if
anything differs from the design, so the printout can't drift from the code.

The authorization table reuses MATRIX and the setup from
tests/test_authorization_matrix.py, so the report and the test suite measure the same thing.
"""
import os

import pytest
from django.core.cache import cache
from django.db import transaction
from rest_framework.test import APIClient

from tests.test_authorization_matrix import MATRIX, ROLES, _call, _client, world  # noqa: F401

# ANSI colours (Windows Terminal, PowerShell 7 and macOS/Linux terminals show them)
_COLOUR = os.environ.get("NO_COLOR") is None
GREEN, RED, BOLD, RESET = ("\033[92m", "\033[91m", "\033[1m", "\033[0m") if _COLOUR else ("",) * 4

LABELS = {"anon": "Visitor", "member": "Member", "participant": "Participant",
          "organizer": "Organizer", "admin": "Admin"}


def _cell(code: int) -> str:
    return "allowed" if code == 200 else str(code)


def _paint(text: str, width: int) -> str:
    colour = GREEN if text == "allowed" else RED
    return f"{colour}{text:>{width}}{RESET}"


@pytest.mark.django_db
def test_authorization_table(world, login):
    """Every role x every action, measured live from the API."""
    first, col = 44, 12
    print("\n" + BOLD + "Action (measured live from the API)".ljust(first)
          + "".join(LABELS[r].rjust(col) for r in ROLES) + RESET)
    print("-" * (first + col * len(ROLES)))

    # One login per role (the login endpoint is rate-limited to 10/min).
    clients = {role: _client(world, role, login) for role in ROLES}
    differences, checked = [], 0
    for action, expected_row in MATRIX.items():
        cells = []
        for role, expected in zip(ROLES, expected_row):
            # Each cell runs in a savepoint that is rolled back, so one call can't
            # change the result of the next (e.g. the organizer cancelling the trip).
            with transaction.atomic():
                got = _call(clients[role], action, world).status_code
                transaction.set_rollback(True)
            cache.clear()  # reset other rate-limit counters between cells
            checked += 1
            if got != expected:
                differences.append(f"{role} -> {action}: expected {expected}, got {got}")
            cells.append(_paint(_cell(got), col))
        print(action.ljust(first) + "".join(cells))

    summary = GREEN if not differences else RED
    print(f"\nCells checked: {checked}    {summary}Different from the design table: "
          f"{len(differences)}{RESET}")
    for line in differences:
        print("  " + line)
    assert not differences


@pytest.mark.django_db
def test_csrf_protection(make_trip, make_user):
    """A forged request carries the login cookie but not the CSRF header -> blocked."""
    member = make_user()
    trip = make_trip(capacity=4)
    browser = APIClient(enforce_csrf_checks=True)  # behaves like a real browser
    res = browser.post("/api/auth/login/",
                       {"email": member.email, "password": "Camp1ng!Pass"}, format="json")
    assert res.status_code == 200
    cookie = res.cookies["ah_access"]
    httponly, samesite = bool(cookie["httponly"]), cookie["samesite"]

    print("\n" + BOLD + "Login cookie flags:" + RESET)
    print(f"  ah_access   {GREEN}HttpOnly={httponly}{RESET}   {GREEN}SameSite={samesite}{RESET}"
          "   (JavaScript cannot read it)")
    assert httponly and samesite == "Strict"
    assert "access" not in res.json()  # the token is never in the response body

    url = f"/api/trips/{trip.pk}/rsvp/"
    print(f"\n1) POST {url}  with the login cookie, WITHOUT X-CSRFToken")
    forged = browser.post(url)
    detail = forged.json().get("detail", "")
    print(f"   -> {RED}{forged.status_code}{RESET}  {detail}")
    assert forged.status_code == 403 and "CSRF" in detail

    print("2) Same request WITH the X-CSRFToken header from our own page")
    token = browser.cookies["csrftoken"].value
    ok = browser.post(url, HTTP_X_CSRFTOKEN=token)
    print(f"   -> {GREEN}{ok.status_code}{RESET}  status: {ok.json().get('status')}")
    assert ok.status_code == 201 and ok.json()["status"] == "confirmed"
