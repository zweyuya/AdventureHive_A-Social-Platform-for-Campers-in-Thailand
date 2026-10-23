"""The trip-verified review gate is enforced by PostgreSQL, not only by the API."""
import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from locations.models import Location, LocationStatus
from reviews.models import Review
from trips.models import ParticipantStatus as PS
from trips.models import TripParticipant, TripStatus


def _participant(trip, user, status):
    marked = timezone.now() if status in (PS.ATTENDED, PS.NO_SHOW) else None
    return TripParticipant.objects.create(trip=trip, user=user, status=status,
                                          attendance_marked_at=marked)


def _rejected(**kwargs):
    with pytest.raises(IntegrityError, match="review_gate"), transaction.atomic():
        Review.objects.create(rating=5, **kwargs)


@pytest.mark.django_db
def test_attended_participant_of_completed_trip_can_review(make_trip, user):
    trip = make_trip(status=TripStatus.COMPLETED)
    _participant(trip, user, PS.ATTENDED)
    Review.objects.create(trip=trip, user=user, location=trip.location, rating=4)


@pytest.mark.django_db
@pytest.mark.parametrize("status", [PS.CONFIRMED, PS.NO_SHOW, PS.CANCELLED])
def test_non_attended_participant_cannot_review(make_trip, user, status):
    trip = make_trip(status=TripStatus.COMPLETED)
    _participant(trip, user, status)
    _rejected(trip=trip, user=user, location=trip.location)


@pytest.mark.django_db
def test_stranger_cannot_review(make_trip, user):
    trip = make_trip(status=TripStatus.COMPLETED)
    _rejected(trip=trip, user=user, location=trip.location)


@pytest.mark.django_db
def test_cannot_review_trip_that_is_not_completed(make_trip, user):
    trip = make_trip(status=TripStatus.PUBLISHED)
    _participant(trip, user, PS.ATTENDED)
    _rejected(trip=trip, user=user, location=trip.location)


@pytest.mark.django_db
def test_organizer_cannot_review_own_trip(make_trip, user):
    trip = make_trip(organizer=user, status=TripStatus.COMPLETED)
    _participant(trip, user, PS.ATTENDED)
    _rejected(trip=trip, user=user, location=trip.location)


@pytest.mark.django_db
def test_review_location_must_match_trip_location(make_trip, user):
    other = Location.objects.create(name="Doi Inthanon", province="Chiang Mai",
                                    latitude=18.59, longitude=98.49,
                                    status=LocationStatus.PUBLISHED)
    trip = make_trip(status=TripStatus.COMPLETED)
    _participant(trip, user, PS.ATTENDED)
    _rejected(trip=trip, user=user, location=other)


@pytest.mark.django_db
def test_one_review_per_trip_per_user(make_trip, user):
    trip = make_trip(status=TripStatus.COMPLETED)
    _participant(trip, user, PS.ATTENDED)
    Review.objects.create(trip=trip, user=user, location=trip.location, rating=4)
    with pytest.raises(IntegrityError), transaction.atomic():
        Review.objects.create(trip=trip, user=user, location=trip.location, rating=1)


@pytest.mark.django_db
def test_rating_must_be_1_to_5(make_trip, user):
    trip = make_trip(status=TripStatus.COMPLETED)
    _participant(trip, user, PS.ATTENDED)
    with pytest.raises(IntegrityError), transaction.atomic():
        Review.objects.create(trip=trip, user=user, location=trip.location, rating=6)


@pytest.mark.django_db
def test_reviewer_attendance_cannot_be_revoked_while_review_exists(make_trip, user):
    trip = make_trip(status=TripStatus.COMPLETED)
    p = _participant(trip, user, PS.ATTENDED)
    Review.objects.create(trip=trip, user=user, location=trip.location, rating=4)
    p.status = PS.NO_SHOW
    with pytest.raises(IntegrityError, match="review_gate"), transaction.atomic():
        p.save()
