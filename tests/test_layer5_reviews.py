"""
Layer 5 — trip-verified reviews (professor's "review credibility" comment).

A review can only be written by someone the organizer marked as ATTENDED on a
COMPLETED trip, once, within 30 days. Ratings update in the same transaction.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from locations.models import Location, LocationStatus
from reviews.models import Review
from trips import services as trip_services
from trips.models import Trip


@pytest.fixture
def completed_trip(make_trip, make_user):
    """Completed trip: a, b attended · c no-show · d was confirmed but never marked."""
    trip = make_trip(capacity=4)
    a, b, c, d = (make_user() for _ in range(4))
    for u in (a, b, c, d):
        trip_services.rsvp(trip, u)
    now = timezone.now()
    Trip.objects.filter(pk=trip.pk).update(start_datetime=now - timedelta(days=3),
                                           end_datetime=now - timedelta(days=1))
    trip.refresh_from_db()
    trip_services.complete_finished_trips()
    trip_services.mark_attendance(trip, trip.organizer, [
        {"user_id": a.pk, "status": "attended"},
        {"user_id": b.pk, "status": "attended"},
        {"user_id": c.pk, "status": "no_show"},
    ])
    trip.refresh_from_db()
    return trip, {"a": a, "b": b, "no_show": c, "unmarked": d}


def _post(client, trip, rating=5, text="Great site", **extra):
    return client.post("/api/reviews/", {"trip_id": trip.pk, "rating": rating,
                                         "review_text": text, **extra}, format="json")


# ---------------- Writing a review ------------------------------------------------

@pytest.mark.django_db
def test_attended_participant_reviews_and_rating_updates(completed_trip, login, api_client):
    trip, u = completed_trip
    client = login(u["a"], client=APIClient())
    res = _post(client, trip, rating=4)
    assert res.status_code == 201, res.content
    body = res.json()
    assert body["verified_attendee"] is True and body["campsite_id"] == trip.location_id

    loc = Location.objects.get(pk=trip.location_id)
    assert loc.avg_rating == Decimal("4.00") and loc.review_count == 1

    _post(login(u["b"], client=APIClient()), trip, rating=5)
    loc.refresh_from_db()
    assert loc.avg_rating == Decimal("4.50") and loc.review_count == 2

    listing = api_client.get(f"/api/campsites/{trip.location_id}/reviews/").json()
    assert listing["count"] == 2
    assert {r["author"]["id"] for r in listing["results"]} == {u["a"].pk, u["b"].pk}


@pytest.mark.django_db
@pytest.mark.parametrize("who, message", [
    ("no_show", "marked as attended"),
    ("unmarked", "marked as attended"),
])
def test_non_attended_participants_cannot_review(completed_trip, login, who, message):
    trip, u = completed_trip
    res = _post(login(u[who], client=APIClient()), trip)
    assert res.status_code == 400 and message in str(res.json())
    assert not Review.objects.exists()


@pytest.mark.django_db
def test_stranger_cannot_review(completed_trip, make_user, login):
    trip, _ = completed_trip
    res = _post(login(make_user(), client=APIClient()), trip)
    assert res.status_code == 400


@pytest.mark.django_db
def test_organizer_cannot_review_own_trip(completed_trip, login):
    trip, _ = completed_trip
    res = _post(login(trip.organizer, client=APIClient()), trip)
    assert res.status_code == 400 and "Organizers" in str(res.json())


@pytest.mark.django_db
def test_cannot_review_before_trip_is_completed(make_trip, make_user, login):
    trip = make_trip()
    u = make_user()
    trip_services.rsvp(trip, u)
    res = _post(login(u, client=APIClient()), trip)
    assert res.status_code == 400 and "completed" in str(res.json())


@pytest.mark.django_db
def test_one_review_per_trip(completed_trip, login):
    trip, u = completed_trip
    client = login(u["a"], client=APIClient())
    assert _post(client, trip).status_code == 201
    res = _post(client, trip, rating=1)
    assert res.status_code == 400 and "already reviewed" in str(res.json())
    assert Review.objects.count() == 1


@pytest.mark.django_db
def test_review_window_closes_after_30_days(completed_trip, login):
    trip, u = completed_trip
    Trip.objects.filter(pk=trip.pk).update(end_datetime=timezone.now() - timedelta(days=31),
                                           start_datetime=timezone.now() - timedelta(days=33))
    res = _post(login(u["a"], client=APIClient()), trip)
    assert res.status_code == 400 and "30 days" in str(res.json())


@pytest.mark.django_db
@pytest.mark.parametrize("rating", [0, 6])
def test_rating_must_be_1_to_5(completed_trip, login, rating):
    trip, u = completed_trip
    assert _post(login(u["a"], client=APIClient()), trip, rating=rating).status_code == 400


@pytest.mark.django_db
def test_campsite_comes_from_the_trip_and_cannot_be_forged(completed_trip, login):
    trip, u = completed_trip
    other = Location.objects.create(name="Elsewhere", province="Krabi", latitude=8.0,
                                    longitude=98.9, status=LocationStatus.PUBLISHED)
    res = _post(login(u["a"], client=APIClient()), trip, location_id=other.pk)
    assert res.json()["campsite_id"] == trip.location_id
    assert Location.objects.get(pk=other.pk).review_count == 0


@pytest.mark.django_db
def test_anonymous_cannot_review_but_can_read(completed_trip, api_client):
    trip, _ = completed_trip
    assert _post(api_client, trip).status_code == 401
    assert api_client.get(f"/api/campsites/{trip.location_id}/reviews/").status_code == 200


# ---------------- Editing / deleting ------------------------------------------------

@pytest.mark.django_db
def test_author_edits_review_and_rating_follows(completed_trip, login):
    trip, u = completed_trip
    client = login(u["a"], client=APIClient())
    review_id = _post(client, trip, rating=2).json()["id"]
    res = client.patch(f"/api/reviews/{review_id}/", {"rating": 5}, format="json")
    assert res.status_code == 200 and res.json()["edited_at"] is not None
    assert Location.objects.get(pk=trip.location_id).avg_rating == Decimal("5.00")

    other = login(u["b"], client=APIClient())
    assert other.patch(f"/api/reviews/{review_id}/", {"rating": 1},
                       format="json").status_code == 404


@pytest.mark.django_db
def test_author_deletes_review_and_rating_resets(completed_trip, login):
    trip, u = completed_trip
    client = login(u["a"], client=APIClient())
    review_id = _post(client, trip).json()["id"]
    assert client.delete(f"/api/reviews/{review_id}/").status_code == 204
    loc = Location.objects.get(pk=trip.location_id)
    assert loc.avg_rating is None and loc.review_count == 0


# ---------------- Moderation --------------------------------------------------------

@pytest.mark.django_db
def test_moderator_hides_review_and_it_leaves_the_rating(completed_trip, login, api_client):
    trip, u = completed_trip
    _post(login(u["a"], client=APIClient()), trip, rating=1, text="spam spam")
    good = _post(login(u["b"], client=APIClient()), trip, rating=5).json()["id"]
    spam = Review.objects.get(user=u["a"]).pk

    mod = User.objects.create_superuser(email="mod@example.com", password="Adm1n-Pass!")
    mod_client = login(mod, password="Adm1n-Pass!", client=APIClient())
    assert login(u["b"], client=APIClient()).post(f"/api/reviews/{spam}/hide/").status_code == 403
    assert mod_client.post(f"/api/reviews/{spam}/hide/").json()["status"] == "hidden"

    loc = Location.objects.get(pk=trip.location_id)
    assert loc.avg_rating == Decimal("5.00") and loc.review_count == 1
    ids = [r["id"] for r in api_client.get(f"/api/campsites/{trip.location_id}/reviews/")
           .json()["results"]]
    assert ids == [good]

    mod_client.post(f"/api/reviews/{spam}/restore/")
    assert Location.objects.get(pk=trip.location_id).review_count == 2


@pytest.mark.django_db
def test_admin_hide_action(completed_trip, login, client):
    trip, u = completed_trip
    _post(login(u["a"], client=APIClient()), trip)
    admin = User.objects.create_superuser(email="adm@example.com", password="Adm1n-Pass!")
    client.force_login(admin)
    review = Review.objects.get()
    assert client.get("/admin/reviews/review/").status_code == 200
    client.post("/admin/reviews/review/", {"action": "hide_selected",
                                           "_selected_action": [str(review.pk)]})
    review.refresh_from_db()
    assert review.status == "hidden"
    assert Location.objects.get(pk=trip.location_id).review_count == 0


# ---------------- Integration with trips & campsites -------------------------------

@pytest.mark.django_db
def test_trip_detail_can_review_flag(completed_trip, login):
    trip, u = completed_trip
    a = login(u["a"], client=APIClient())
    url = f"/api/trips/{trip.pk}/"
    assert a.get(url).json()["can_review"] is True
    assert login(u["no_show"], client=APIClient()).get(url).json()["can_review"] is False
    assert login(trip.organizer, client=APIClient()).get(url).json()["can_review"] is False
    _post(a, trip)
    assert a.get(url).json()["can_review"] is False


@pytest.mark.django_db
def test_campsite_min_rating_filter_uses_real_reviews(completed_trip, login, api_client):
    trip, u = completed_trip
    _post(login(u["a"], client=APIClient()), trip, rating=5)
    names = [c["name"] for c in api_client.get("/api/campsites/?min_rating=4.5").json()["results"]]
    assert names == [trip.location.name]


@pytest.mark.django_db
def test_my_reviews(completed_trip, login):
    trip, u = completed_trip
    client = login(u["a"], client=APIClient())
    _post(client, trip)
    assert len(client.get("/api/reviews/mine/").json()) == 1
