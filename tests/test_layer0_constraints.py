"""Database constraints that back up the professor's reliability comments."""
from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from locations.models import Location, LocationRevision, LocationStatus, RevisionStatus
from social.models import Follow
from trips.models import ParticipantStatus as PS
from trips.models import Trip, TripParticipant


def _violates(fn):
    with pytest.raises(IntegrityError), transaction.atomic():
        fn()


# ---------------- Trips -----------------------------------------------------

@pytest.mark.django_db
def test_trip_end_must_be_after_start(make_trip):
    trip = make_trip()
    trip.end_datetime = trip.start_datetime - timedelta(hours=1)
    _violates(trip.save)


@pytest.mark.django_db
def test_trip_capacity_must_be_positive(make_trip):
    _violates(lambda: make_trip(capacity=0))


@pytest.mark.django_db
def test_db_rejects_overbooking_even_if_code_is_wrong(make_trip):
    trip = make_trip(capacity=2)
    Trip.objects.filter(pk=trip.pk).update(confirmed_count=2)  # full: OK
    _violates(lambda: Trip.objects.filter(pk=trip.pk).update(confirmed_count=F("confirmed_count") + 1))


@pytest.mark.django_db
def test_meeting_point_must_be_in_thailand_and_paired(make_trip):
    _violates(lambda: make_trip(meeting_latitude=14.0))  # longitude missing
    _violates(lambda: make_trip(meeting_latitude=35.6, meeting_longitude=139.7))  # Tokyo


# ---------------- Participants / waitlist -----------------------------------

@pytest.mark.django_db
def test_duplicate_rsvp_rejected(make_trip, user):
    trip = make_trip()
    TripParticipant.objects.create(trip=trip, user=user, status=PS.CONFIRMED)
    _violates(lambda: TripParticipant.objects.create(trip=trip, user=user, status=PS.CONFIRMED))


@pytest.mark.django_db
def test_waitlisted_needs_position_and_others_must_not_have_one(make_trip, user, make_user):
    trip = make_trip()
    _violates(lambda: TripParticipant.objects.create(trip=trip, user=user, status=PS.WAITLISTED))
    _violates(lambda: TripParticipant.objects.create(
        trip=trip, user=make_user(), status=PS.CONFIRMED, waitlist_position=1))


@pytest.mark.django_db
def test_waitlist_positions_unique_but_renumbering_works_in_one_transaction(make_trip, make_user):
    trip = make_trip(capacity=1)
    w = [TripParticipant.objects.create(trip=trip, user=make_user(), status=PS.WAITLISTED,
                                        waitlist_position=i) for i in (1, 2, 3)]
    # Same position twice is rejected (checked at commit because it is DEFERRED).
    with pytest.raises(IntegrityError), transaction.atomic():
        TripParticipant.objects.create(trip=trip, user=make_user(), status=PS.WAITLISTED,
                                       waitlist_position=2)
        # deferred constraint fires when the savepoint is released
        from django.db import connection
        with connection.cursor() as c:
            c.execute("SET CONSTRAINTS ALL IMMEDIATE")

    # Promotion: #1 leaves the waitlist, everyone else moves up — one transaction.
    with transaction.atomic():
        TripParticipant.objects.filter(pk=w[0].pk).update(status=PS.CONFIRMED, waitlist_position=None)
        TripParticipant.objects.filter(trip=trip, waitlist_position__gt=1).update(
            waitlist_position=F("waitlist_position") - 1)
    positions = list(TripParticipant.objects.filter(trip=trip, status=PS.WAITLISTED)
                     .order_by("waitlist_position").values_list("waitlist_position", flat=True))
    assert positions == [1, 2]


@pytest.mark.django_db
def test_attended_requires_attendance_record(make_trip, user):
    trip = make_trip()
    _violates(lambda: TripParticipant.objects.create(trip=trip, user=user, status=PS.ATTENDED))
    TripParticipant.objects.create(trip=trip, user=user, status=PS.ATTENDED,
                                   attendance_marked_at=timezone.now())


# ---------------- Locations / content workflow ------------------------------

@pytest.mark.django_db
def test_location_outside_thailand_rejected():
    _violates(lambda: Location.objects.create(name="X", province="?", latitude=48.8, longitude=2.3))


@pytest.mark.django_db
def test_rejected_submission_needs_a_note(location):
    location.status = LocationStatus.REJECTED
    _violates(location.save)
    location.moderation_note = "Permit info is wrong; please cite the DNP page."
    location.save()


@pytest.mark.django_db
def test_published_queryset_hides_unapproved(location):
    Location.objects.create(name="Pending", province="Chiang Mai", latitude=18.8,
                            longitude=98.9, status=LocationStatus.PENDING_REVIEW)
    assert list(Location.objects.published()) == [location]


@pytest.mark.django_db
def test_only_approved_revisions_have_version_numbers(location, user):
    _violates(lambda: LocationRevision.objects.create(
        location=location, snapshot={}, edited_by=user, status=RevisionStatus.PENDING, version_no=1))
    LocationRevision.objects.create(location=location, snapshot={}, edited_by=user,
                                    status=RevisionStatus.APPROVED, version_no=1)
    _violates(lambda: LocationRevision.objects.create(
        location=location, snapshot={}, edited_by=user, status=RevisionStatus.APPROVED, version_no=1))


# ---------------- Social ------------------------------------------------------

@pytest.mark.django_db
def test_cannot_follow_yourself(user):
    _violates(lambda: Follow.objects.create(follower=user, followee=user))
