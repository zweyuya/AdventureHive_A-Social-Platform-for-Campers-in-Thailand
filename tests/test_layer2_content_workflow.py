"""
UATs for the campsite content workflow (content-management problem set).

UAT-CM-1  A member submits a campsite → pending_review, not public
UAT-CM-2  An admin approves → published, on the list and map, version 1 recorded
UAT-CM-3  An admin rejects with a note → submitter sees note, edits, resubmits
UAT-CM-4  A non-admin cannot approve or reject
UAT-CM-5  A member suggests an edit to a published campsite; approved → version 2, history
"""
import pytest
from rest_framework.test import APIClient

from accounts.models import User
from locations.models import Location, LocationRevision, LocationStatus, RevisionStatus
from notifications.models import Notification

NEW_SITE = {
    "name": "Mon Jam Campsite",
    "province": "Chiang Mai",
    "latitude": 18.93,
    "longitude": 98.82,
    "category": "campsite",
    "description": "Hilltop camping with flower farms.",
    "has_restrooms": True,
}


@pytest.fixture
def member(make_user, login):
    user = make_user()
    return user, login(user, client=APIClient())


@pytest.fixture
def admin(login):
    user = User.objects.create_superuser(email="mod@example.com", password="Adm1n-Pass!")
    return user, login(user, password="Adm1n-Pass!", client=APIClient())


def _public_names():
    client = APIClient()
    listed = {s["name"] for s in client.get("/api/campsites/").json()["results"]}
    mapped = {f["properties"]["name"] for f in client.get("/api/map/campsites/").json()["features"]}
    return listed, mapped


def _create_and_submit(client):
    created = client.post("/api/campsites/", NEW_SITE, format="json")
    assert created.status_code == 201, created.content
    site_id = created.json()["id"]
    assert client.post(f"/api/campsites/{site_id}/submit/").status_code == 200
    return site_id


# ---------------- UAT-CM-1 ---------------------------------------------------------

@pytest.mark.django_db
def test_uat_cm_1_member_submits_campsite_and_it_is_not_public(member):
    user, client = member
    created = client.post("/api/campsites/", NEW_SITE, format="json")
    assert created.status_code == 201
    assert created.json()["status"] == "draft"
    site_id = created.json()["id"]

    submitted = client.post(f"/api/campsites/{site_id}/submit/")
    assert submitted.json()["status"] == "pending_review"

    listed, mapped = _public_names()
    assert "Mon Jam Campsite" not in listed and "Mon Jam Campsite" not in mapped
    # ...but the submitter can still see it
    assert client.get(f"/api/campsites/{site_id}/").status_code == 200
    assert [s["status"] for s in client.get("/api/campsites/mine/").json()] == ["pending_review"]


@pytest.mark.django_db
def test_created_by_and_status_cannot_be_forged(member):
    _, client = member
    res = client.post("/api/campsites/", {**NEW_SITE, "status": "published", "created_by": 1,
                                          "avg_rating": 5}, format="json")
    assert res.json()["status"] == "draft" and res.json()["avg_rating"] is None


@pytest.mark.django_db
def test_coordinates_outside_thailand_rejected(member):
    _, client = member
    res = client.post("/api/campsites/", {**NEW_SITE, "latitude": 35.6, "longitude": 139.7},
                      format="json")
    assert res.status_code == 400 and "latitude" in res.json()


# ---------------- UAT-CM-2 ---------------------------------------------------------

@pytest.mark.django_db
def test_uat_cm_2_admin_approves_and_campsite_is_published(member, admin):
    user, client = member
    mod, mod_client = admin
    site_id = _create_and_submit(client)

    res = mod_client.post(f"/api/campsites/{site_id}/approve/")
    assert res.status_code == 200 and res.json()["status"] == "published"

    listed, mapped = _public_names()
    assert "Mon Jam Campsite" in listed and "Mon Jam Campsite" in mapped

    site = Location.objects.get(pk=site_id)
    assert site.current_version == 1 and site.reviewed_by == mod
    v1 = site.revisions.get()
    assert v1.version_no == 1 and v1.edited_by == user and v1.snapshot["name"] == "Mon Jam Campsite"
    assert Notification.objects.filter(recipient=user, type="submission_approved").exists()


@pytest.mark.django_db
def test_approving_twice_or_approving_a_draft_fails(member, admin):
    _, client = member
    _, mod_client = admin
    draft_id = client.post("/api/campsites/", NEW_SITE, format="json").json()["id"]
    assert mod_client.post(f"/api/campsites/{draft_id}/approve/").status_code == 400

    site_id = _create_and_submit(client)
    assert mod_client.post(f"/api/campsites/{site_id}/approve/").status_code == 200
    assert mod_client.post(f"/api/campsites/{site_id}/approve/").status_code == 400


# ---------------- UAT-CM-3 ---------------------------------------------------------

@pytest.mark.django_db
def test_uat_cm_3_reject_with_note_then_edit_and_resubmit(member, admin):
    user, client = member
    _, mod_client = admin
    site_id = _create_and_submit(client)

    # A reason is mandatory
    assert mod_client.post(f"/api/campsites/{site_id}/reject/", {}, format="json").status_code == 400

    note = "Coordinates point to a car park. Please move the pin to the campsite."
    res = mod_client.post(f"/api/campsites/{site_id}/reject/", {"note": note}, format="json")
    assert res.json()["status"] == "rejected"
    assert Notification.objects.filter(recipient=user, type="submission_rejected").exists()

    # Submitter sees the note on their submissions page
    mine = client.get("/api/campsites/mine/").json()[0]
    assert mine["status"] == "rejected" and mine["moderation_note"] == note

    # Edit and resubmit
    edited = client.patch(f"/api/campsites/{site_id}/", {"latitude": 18.94}, format="json")
    assert edited.status_code == 200 and edited.json()["latitude"] == 18.94
    assert client.post(f"/api/campsites/{site_id}/submit/").json()["status"] == "pending_review"

    listed, _ = _public_names()
    assert "Mon Jam Campsite" not in listed


@pytest.mark.django_db
def test_submitter_cannot_edit_while_pending_and_others_cannot_edit(member, make_user, login):
    _, client = member
    site_id = _create_and_submit(client)
    assert client.patch(f"/api/campsites/{site_id}/", {"name": "X"}, format="json").status_code == 400

    other = login(make_user(), client=APIClient())
    assert other.patch(f"/api/campsites/{site_id}/", {"name": "X"}, format="json").status_code == 404
    assert other.post(f"/api/campsites/{site_id}/submit/").status_code == 404


# ---------------- UAT-CM-4 ---------------------------------------------------------

@pytest.mark.django_db
def test_uat_cm_4_non_admin_cannot_approve_or_reject(member, make_user, login):
    _, client = member
    site_id = _create_and_submit(client)
    other = login(make_user(), client=APIClient())
    for c in (client, other):  # neither the submitter nor another member
        assert c.post(f"/api/campsites/{site_id}/approve/").status_code == 403
        assert c.post(f"/api/campsites/{site_id}/reject/", {"note": "no"},
                      format="json").status_code == 403
    assert APIClient().post(f"/api/campsites/{site_id}/approve/").status_code == 401
    assert Location.objects.get(pk=site_id).status == LocationStatus.PENDING_REVIEW


# ---------------- UAT-CM-5 ---------------------------------------------------------

@pytest.mark.django_db
def test_uat_cm_5_suggested_edit_creates_version_2_with_history(member, admin, make_user, login):
    submitter, client = member
    _, mod_client = admin
    site_id = _create_and_submit(client)
    mod_client.post(f"/api/campsites/{site_id}/approve/")

    editor = make_user()
    editor_client = login(editor, client=APIClient())
    res = editor_client.post(f"/api/campsites/{site_id}/revisions/", {
        "permit_status": "required",
        "permit_details": "Pay 30 THB at the gate.",
        "edit_summary": "Added permit info from park signboard",
    }, format="json")
    assert res.status_code == 201 and res.json()["status"] == "pending"
    rev_id = res.json()["id"]

    # Not applied until approved
    assert APIClient().get(f"/api/campsites/{site_id}/").json()["permit_status"] == "unknown"
    assert [r["id"] for r in mod_client.get("/api/campsite-revisions/").json()] == [rev_id]

    approved = mod_client.post(f"/api/campsite-revisions/{rev_id}/approve/")
    assert approved.status_code == 200 and approved.json()["version_no"] == 2

    public = APIClient()
    detail = public.get(f"/api/campsites/{site_id}/").json()
    assert detail["permit_status"] == "required" and detail["current_version"] == 2

    history = public.get(f"/api/campsites/{site_id}/history/").json()
    assert [h["version_no"] for h in history] == [2, 1]
    assert history[0]["edit_summary"] == "Added permit info from park signboard"
    assert history[0]["edited_by"] == editor.profile.display_name
    assert history[1]["edited_by"] == submitter.profile.display_name
    assert history[1]["snapshot"]["permit_status"] == "unknown"  # old version kept intact


@pytest.mark.django_db
def test_suggestion_rejected_with_note_is_not_applied(member, admin):
    _, client = member
    _, mod_client = admin
    site_id = _create_and_submit(client)
    mod_client.post(f"/api/campsites/{site_id}/approve/")
    rev_id = client.post(f"/api/campsites/{site_id}/revisions/",
                         {"name": "Spam Camp", "edit_summary": "rename"}, format="json").json()["id"]

    res = mod_client.post(f"/api/campsite-revisions/{rev_id}/reject/",
                          {"note": "Name is not correct."}, format="json")
    assert res.json()["status"] == "rejected"
    assert Location.objects.get(pk=site_id).name == "Mon Jam Campsite"
    assert LocationRevision.objects.get(pk=rev_id).version_no is None


@pytest.mark.django_db
def test_stale_suggestion_cannot_overwrite_newer_version(member, admin):
    """Two suggestions made on version 1: approving the second would silently undo the first."""
    _, client = member
    _, mod_client = admin
    site_id = _create_and_submit(client)
    mod_client.post(f"/api/campsites/{site_id}/approve/")
    url = f"/api/campsites/{site_id}/revisions/"
    a = client.post(url, {"rules": "No drones", "edit_summary": "a"}, format="json").json()["id"]
    b = client.post(url, {"name": "Mon Jam Camp", "edit_summary": "b"}, format="json").json()["id"]

    assert mod_client.post(f"/api/campsite-revisions/{a}/approve/").status_code == 200
    res = mod_client.post(f"/api/campsite-revisions/{b}/approve/")
    assert res.status_code == 400 and "version" in str(res.json())
    assert Location.objects.get(pk=site_id).rules == "No drones"


@pytest.mark.django_db
def test_empty_or_unpublished_suggestions_rejected(member, admin):
    _, client = member
    _, mod_client = admin
    draft_id = client.post("/api/campsites/", NEW_SITE, format="json").json()["id"]
    assert client.post(f"/api/campsites/{draft_id}/revisions/",
                       {"name": "X", "edit_summary": "x"}, format="json").status_code == 404

    site_id = _create_and_submit(client)
    mod_client.post(f"/api/campsites/{site_id}/approve/")
    same = client.post(f"/api/campsites/{site_id}/revisions/",
                       {"name": NEW_SITE["name"], "edit_summary": "no-op"}, format="json")
    assert same.status_code == 400


@pytest.mark.django_db
def test_non_admin_cannot_see_or_moderate_suggestion_queue(member):
    _, client = member
    assert client.get("/api/campsite-revisions/").status_code == 403
    assert client.post("/api/campsite-revisions/1/approve/").status_code == 403
