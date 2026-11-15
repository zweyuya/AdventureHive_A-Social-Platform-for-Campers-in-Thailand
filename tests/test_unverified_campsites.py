"""
"Visible but limited": a submitted campsite is public straight away, marked "Not yet verified",
but nobody can organise a trip, ask a question or suggest an edit there until a moderator
approves it. Drafts and rejected campsites stay private.
"""
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User

SITE = {"name": "Huay Mae Khamin Campground", "province": "Kanchanaburi", "latitude": 14.63,
        "longitude": 98.85, "category": "campground", "description": "Near the waterfall."}


@pytest.fixture
def member(make_user, login):
    return login(make_user(), client=APIClient())


@pytest.fixture
def moderator(login):
    user = User.objects.create_superuser(email="mod@example.com", password="Adm1n-Pass!")
    return login(user, password="Adm1n-Pass!", client=APIClient())


def _draft(client, **extra):
    res = client.post("/api/campsites/", {**SITE, **extra}, format="json")
    assert res.status_code == 201, res.content
    return res.json()["id"]


def _submitted(client, **extra):
    site_id = _draft(client, **extra)
    assert client.post(f"/api/campsites/{site_id}/submit/").status_code == 200
    return site_id


def _public_list(**params):
    return {c["id"]: c for c in APIClient().get("/api/campsites/", params).json()["results"]}


def _public_map(**params):
    return {f["properties"]["id"]: f["properties"]
            for f in APIClient().get("/api/map/campsites/", params).json()["features"]}


def _trip_body(site_id):
    start = timezone.now() + timedelta(days=20)
    return {"location_id": site_id, "title": "Waterfall weekend", "participant_capacity": 4,
            "start_datetime": start.isoformat(), "end_datetime": (start + timedelta(days=1)).isoformat()}


# ---------------- Visible ------------------------------------------------------------

@pytest.mark.django_db
def test_submitted_campsite_is_public_and_marked_not_yet_verified(member, location):
    site_id = _submitted(member)
    listed, mapped = _public_list(), _public_map()
    assert listed[site_id]["status"] == "pending_review"
    assert listed[location.pk]["status"] == "published"
    assert mapped[site_id]["verified"] is False and mapped[location.pk]["verified"] is True
    detail = APIClient().get(f"/api/campsites/{site_id}/")
    assert detail.status_code == 200 and detail.json()["status"] == "pending_review"
    assert "moderation_note" not in detail.json()  # still private to the submitter and staff
    assert detail.json()["is_mine"] is False
    assert member.get(f"/api/campsites/{site_id}/").json()["is_mine"] is True


@pytest.mark.django_db
def test_drafts_and_rejected_campsites_stay_private(member, moderator):
    draft = _draft(member)
    rejected = _submitted(member, name="Wrong pin camp")
    moderator.post(f"/api/campsites/{rejected}/reject/", {"note": "Pin is a car park."}, format="json")
    for site_id in (draft, rejected):
        assert site_id not in _public_list() and site_id not in _public_map()
        assert APIClient().get(f"/api/campsites/{site_id}/").status_code == 404
    assert member.get(f"/api/campsites/{draft}/").status_code == 200  # the submitter still can


@pytest.mark.django_db
def test_filter_to_verified_or_not_yet_verified(member, location):
    site_id = _submitted(member)
    assert set(_public_list(verified="true")) == {location.pk}
    assert set(_public_list(verified="false")) == {site_id}
    assert set(_public_map(verified="true")) == {location.pk}


@pytest.mark.django_db
def test_approval_makes_it_a_normal_verified_campsite(member, moderator):
    site_id = _submitted(member)
    moderator.post(f"/api/campsites/{site_id}/approve/")
    assert _public_list()[site_id]["status"] == "published"
    assert _public_map()[site_id]["verified"] is True


@pytest.mark.django_db
def test_reviews_and_history_of_an_unverified_campsite_are_just_empty(member):
    site_id = _submitted(member)
    reviews = APIClient().get(f"/api/campsites/{site_id}/reviews/")
    assert reviews.status_code == 200 and reviews.json()["results"] == []
    history = APIClient().get(f"/api/campsites/{site_id}/history/")
    assert history.status_code == 200 and history.json() == []


@pytest.mark.django_db
def test_pin_check_warns_about_unverified_campsites_nearby(member, make_user, login):
    site_id = _submitted(member)
    other = login(make_user(), client=APIClient())
    nearby = other.get("/api/campsites/pin-check/", {"lat": 14.631, "lng": 98.851}).json()["nearby"]
    assert [(n["id"], n["verified"]) for n in nearby] == [(site_id, False)]


# ---------------- Limited ------------------------------------------------------------

@pytest.mark.django_db
def test_no_trips_at_an_unverified_campsite_until_approved(member, moderator, make_user, login):
    site_id = _submitted(member)
    organizer = login(make_user(), client=APIClient())
    refused = organizer.post("/api/trips/", _trip_body(site_id), format="json")
    assert refused.status_code == 400
    assert "isn't verified yet" in str(refused.json()["location_id"])

    moderator.post(f"/api/campsites/{site_id}/approve/")
    assert organizer.post("/api/trips/", _trip_body(site_id), format="json").status_code == 201


@pytest.mark.django_db
def test_no_questions_or_suggested_edits_at_an_unverified_campsite(member, make_user, login):
    site_id = _submitted(member)
    other = login(make_user(), client=APIClient())
    q = other.post("/api/questions/", {"location_id": site_id, "title": "Is the road paved?",
                                       "body": "Going by scooter."}, format="json")
    assert q.status_code == 400 and "isn't verified yet" in str(q.json()["location_id"])
    edit = other.post(f"/api/campsites/{site_id}/revisions/",
                      {"fees": "Free", "edit_summary": "Fee"}, format="json")
    assert edit.status_code == 404


@pytest.mark.django_db
def test_others_cannot_change_or_resubmit_an_unverified_campsite(member, make_user, login):
    site_id = _submitted(member)
    other = login(make_user(), client=APIClient())
    assert other.patch(f"/api/campsites/{site_id}/", {"name": "Mine now"}, format="json").status_code == 403
    assert other.post(f"/api/campsites/{site_id}/submit/").status_code == 400


@pytest.mark.django_db
def test_sending_campsites_for_review_is_rate_limited(member):
    for i in range(10):
        _submitted(member, name=f"Camp {i}", province="", latitude=14.0 + i / 100, longitude=100.6)
    eleventh = _draft(member, name="Camp 10", province="", latitude=14.2, longitude=100.6)
    assert member.post(f"/api/campsites/{eleventh}/submit/").status_code == 429
