"""
Organizer rating and record.

Campers can rate the organizer (optional, 1-5) when they review a trip's campsite. The
organizer's record counts only trips that are hard to fake: completed, not flagged, at
least 2 attendees, and at least half of them checked in with the trip code. No average
is shown until 3 different people have rated, each person counts once, and nobody but
the author can see an individual organizer rating.
"""
from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from reviews import services as reviews
from reviews.models import Review, ReviewStatus
from trips import services
from trips.models import FlagStatus, Trip, TripStatus


def _finished(make_trip, organizer, people, checked_in, **extra):
    """A completed trip: everyone in `people` attended; only `checked_in` used the code."""
    trip = make_trip(organizer=organizer, capacity=max(len(people), 1), **extra)
    for p in people:
        services.rsvp(Trip.objects.get(pk=trip.pk), p)
    now = timezone.now()
    Trip.objects.filter(pk=trip.pk).update(start_datetime=now - timedelta(days=1, hours=1),
                                           end_datetime=now - timedelta(hours=1))
    services.complete_finished_trips()
    trip.refresh_from_db()
    for p in checked_in:
        services.check_in(trip, p, services.checkin_code(trip))
    if people:
        services.mark_attendance(trip, organizer, [
            {"user_id": p.pk, "status": "attended", "reason": "Was there"} for p in people])
    trip.refresh_from_db()
    return trip


@pytest.fixture
def organizer(make_user):
    return make_user()


@pytest.fixture
def campers(make_user):
    return [make_user() for _ in range(4)]


def stats(user):
    return reviews.organizer_stats(user)


# ---- the rating itself ---------------------------------------------------------------
@pytest.mark.django_db
def test_organizer_rating_is_optional(make_trip, organizer, campers):
    trip = _finished(make_trip, organizer, campers[:2], campers[:2])
    review = reviews.create_review(campers[0], trip, 4, "Nice")
    assert review.organizer_rating is None


@pytest.mark.django_db
def test_database_only_allows_1_to_5(make_trip, organizer, campers):
    trip = _finished(make_trip, organizer, campers[:2], campers[:2])
    review = reviews.create_review(campers[0], trip, 4, "Nice", 5)
    for bad in (0, 6):
        with pytest.raises(IntegrityError, match="organizer_rating_1_to_5"), transaction.atomic():
            Review.objects.filter(pk=review.pk).update(organizer_rating=bad)


@pytest.mark.django_db
def test_rate_the_organizer_through_the_api(make_trip, organizer, campers, login):
    trip = _finished(make_trip, organizer, campers[:2], campers[:2])
    client = login(campers[0])
    bad = client.post("/api/reviews/", {"trip_id": trip.pk, "rating": 4, "organizer_rating": 6}, format="json")
    assert bad.status_code == 400 and "organizer_rating" in bad.json()
    res = client.post("/api/reviews/", {"trip_id": trip.pk, "rating": 4, "organizer_rating": 5}, format="json")
    assert res.status_code == 201 and res.json()["organizer_rating"] == 5
    edited = client.patch(f"/api/reviews/{res.json()['id']}/", {"organizer_rating": 3}, format="json")
    assert edited.json()["organizer_rating"] == 3


@pytest.mark.django_db
def test_only_the_author_sees_an_organizer_rating(make_trip, organizer, campers, login, api_client):
    trip = _finished(make_trip, organizer, campers[:2], campers[:2])
    review = reviews.create_review(campers[0], trip, 4, "Nice", 2)
    as_organizer = login(organizer, client=APIClient())
    for client in (api_client, as_organizer):
        assert "organizer_rating" not in client.get(f"/api/reviews/{review.pk}/").json()
        listed = client.get(f"/api/campsites/{trip.location_id}/reviews/").json()["results"][0]
        assert "organizer_rating" not in listed
    mine = login(campers[0], client=APIClient()).get("/api/reviews/mine/").json()[0]
    assert mine["organizer_rating"] == 2


@pytest.mark.django_db
def test_the_organizer_cannot_rate_themselves(make_trip, organizer, campers):
    trip = _finished(make_trip, organizer, campers[:2], campers[:2])
    with pytest.raises(Exception, match="(?i)organizer"):
        reviews.create_review(organizer, trip, 5, "I was great", 5)


# ---- which trips count (anti-faking) -------------------------------------------------
@pytest.mark.django_db
def test_a_real_trip_counts(make_trip, organizer, campers):
    _finished(make_trip, organizer, campers[:2], campers[:2])
    s = stats(organizer)
    assert s["trips_run"] == 1 and s["campers"] == 2


@pytest.mark.django_db
def test_planned_and_draft_trips_do_not_count(make_trip, organizer):
    make_trip(organizer=organizer)
    make_trip(organizer=organizer, status=TripStatus.DRAFT)
    assert stats(organizer)["trips_run"] == 0


@pytest.mark.django_db
def test_a_trip_with_only_one_attendee_does_not_count(make_trip, organizer, campers):
    _finished(make_trip, organizer, campers[:1], campers[:1])
    assert stats(organizer)["trips_run"] == 0


@pytest.mark.django_db
def test_a_trip_where_most_attendees_did_not_check_in_does_not_count(make_trip, organizer, campers):
    trip = _finished(make_trip, organizer, campers[:3], campers[:1])  # 1 of 3 checked in
    assert trip.flag_status == FlagStatus.NEEDS_REVIEW               # also flagged automatically
    Trip.objects.filter(pk=trip.pk).update(flag_status=FlagStatus.CLEARED)  # even if an admin clears it
    assert stats(organizer)["trips_run"] == 0


@pytest.mark.django_db
def test_exactly_half_checked_in_counts(make_trip, organizer, campers):
    _finished(make_trip, organizer, campers[:2], campers[:1])  # 1 of 2 = half
    assert stats(organizer)["trips_run"] == 1


@pytest.mark.django_db
@pytest.mark.parametrize("flag", [FlagStatus.NEEDS_REVIEW, FlagStatus.REVIEWS_HIDDEN])
def test_a_flagged_trip_does_not_count(make_trip, organizer, campers, flag):
    trip = _finished(make_trip, organizer, campers[:2], campers[:2])
    Trip.objects.filter(pk=trip.pk).update(flag_status=flag)
    assert stats(organizer)["trips_run"] == 0


@pytest.mark.django_db
def test_a_trip_cleared_by_an_admin_counts(make_trip, organizer, campers):
    trip = _finished(make_trip, organizer, campers[:2], campers[:2])
    Trip.objects.filter(pk=trip.pk).update(flag_status=FlagStatus.CLEARED)
    assert stats(organizer)["trips_run"] == 1


@pytest.mark.django_db
def test_the_same_people_again_are_counted_once(make_trip, organizer, campers):
    for _ in range(3):
        _finished(make_trip, organizer, campers[:2], campers[:2])
    s = stats(organizer)
    assert s["trips_run"] == 3 and s["campers"] == 2


@pytest.mark.django_db
def test_cancellations_count_only_when_people_had_joined(make_trip, organizer, make_user):
    joined = make_trip(organizer=organizer)
    services.rsvp(joined, make_user())
    services.cancel_trip(Trip.objects.get(pk=joined.pk), organizer)
    empty = make_trip(organizer=organizer, status=TripStatus.DRAFT)
    services.cancel_trip(empty, organizer)
    assert stats(organizer)["cancelled"] == 1


# ---- the average ---------------------------------------------------------------------
@pytest.mark.django_db
def test_no_average_until_three_people_rated(make_trip, organizer, campers):
    trip = _finished(make_trip, organizer, campers[:3], campers[:3])
    reviews.create_review(campers[0], trip, 4, "", 5)
    reviews.create_review(campers[1], trip, 4, "", 4)
    s = stats(organizer)
    assert s["rating"] is None and s["rating_count"] == 2 and s["min_ratings"] == 3
    reviews.create_review(campers[2], trip, 4, "", 5)
    s = stats(organizer)
    assert s["rating"] == 4.7 and s["rating_count"] == 3


@pytest.mark.django_db
def test_each_person_counts_once_with_their_newest_rating(make_trip, organizer, campers):
    first = _finished(make_trip, organizer, campers[:3], campers[:3])
    for c in campers[:3]:
        reviews.create_review(c, first, 4, "", 1)
    second = _finished(make_trip, organizer, campers[:2], campers[:2])
    reviews.create_review(campers[0], second, 4, "", 5)  # changed their mind on a later trip
    s = stats(organizer)
    assert s["rating_count"] == 3 and s["rating"] == pytest.approx((5 + 1 + 1) / 3, abs=0.05)


@pytest.mark.django_db
def test_ratings_from_trips_that_do_not_count_are_ignored(make_trip, organizer, campers):
    good = _finished(make_trip, organizer, campers[:3], campers[:3])
    for c in campers[:3]:
        reviews.create_review(c, good, 4, "", 2)
    weak = _finished(make_trip, organizer, campers[:3], campers[:1])  # flagged, mostly no check-in
    Trip.objects.filter(pk=weak.pk).update(flag_status=FlagStatus.CLEARED)
    for c in campers[:3]:
        reviews.create_review(c, weak, 4, "", 5)
    assert stats(organizer)["rating"] == 2.0


@pytest.mark.django_db
def test_hidden_reviews_and_reviews_without_an_organizer_rating_are_ignored(make_trip, organizer, campers):
    trip = _finished(make_trip, organizer, campers[:4], campers[:4])
    for c in campers[:3]:
        reviews.create_review(c, trip, 4, "", 4)
    hidden = reviews.create_review(campers[3], trip, 4, "", 1)
    Review.objects.filter(pk=hidden.pk).update(status=ReviewStatus.HIDDEN)
    assert stats(organizer)["rating"] == 4.0 and stats(organizer)["rating_count"] == 3


# ---- where it is shown ---------------------------------------------------------------
@pytest.mark.django_db
def test_shown_on_the_trip_page_and_both_profiles(make_trip, organizer, campers, login, api_client):
    trip = _finished(make_trip, organizer, campers[:2], campers[:2])
    assert api_client.get(f"/api/trips/{trip.pk}/").json()["organizer_stats"]["trips_run"] == 1
    assert api_client.get(f"/api/users/{organizer.pk}/").json()["organizer"]["trips_run"] == 1
    assert login(organizer).get("/api/users/me/").json()["organizer"]["campers"] == 2


@pytest.mark.django_db
def test_demo_data_gives_ploy_a_visible_rating():
    from django.core.management import call_command
    from accounts.models import User
    call_command("seed_campsites")
    call_command("seed_demo")
    s = stats(User.objects.get(email="ploy@demo.adventurehive.test"))
    assert s["trips_run"] == 1 and s["campers"] == 3
    assert s["rating"] == 4.7 and s["rating_count"] == 3
