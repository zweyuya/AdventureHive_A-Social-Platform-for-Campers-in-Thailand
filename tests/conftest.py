"""Shared fixtures. Tests run against PostgreSQL with all migrations (incl. triggers)."""
from datetime import timedelta
from itertools import count

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Profile, User
from locations.models import Location, LocationStatus
from trips.models import Trip, TripStatus

_seq = count(1)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def make_user(db):
    def _make(email=None, password="Camp1ng!Pass", **extra):
        email = email or f"user{next(_seq)}@example.com"
        user = User.objects.create_user(email=email, password=password, **extra)
        Profile.objects.create(user=user, display_name=email.split("@")[0])
        return user

    return _make


@pytest.fixture
def user(make_user):
    return make_user()


@pytest.fixture
def location(db):
    return Location.objects.create(
        name="Pha Taem Campground",
        province="Ubon Ratchathani",
        latitude=15.40,
        longitude=105.50,
        category="campground",
        status=LocationStatus.PUBLISHED,
    )


@pytest.fixture
def make_trip(db, make_user, location):
    def _make(organizer=None, capacity=2, status=TripStatus.PUBLISHED, days_from_now=7, **extra):
        start = timezone.now() + timedelta(days=days_from_now)
        return Trip.objects.create(
            organizer=organizer or make_user(),
            location=extra.pop("loc", location),
            title="Weekend at Pha Taem",
            start_datetime=start,
            end_datetime=start + timedelta(days=2),
            participant_capacity=capacity,
            status=status,
            **extra,
        )

    return _make


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    """Throttle counters live in the cache; reset them so tests stay independent."""
    from django.core.cache import cache

    cache.clear()


@pytest.fixture
def login(api_client):
    """Log a user in through the real endpoint (cookies land on the client)."""

    def _login(user, password="Camp1ng!Pass", client=None):
        c = client or api_client
        res = c.post("/api/auth/login/", {"email": user.email, "password": password}, format="json")
        assert res.status_code == 200, res.content
        return c

    return _login
