"""
The campsite moderation queue, and the least-privilege moderator role.

A moderator reviews campsite submissions in the app. They are not staff: no Django
admin, and none of the other powers of an admin. The API checks this on every request,
whatever the React page shows.
"""
import pytest
from django.test import Client
from rest_framework.test import APIClient

from accounts.models import EmergencyContact, UserStatus
from accounts.services import delete_account
from locations.models import Location, LocationStatus
from notifications.models import Notification, NotificationType as N

URL = "/api/campsites/moderation/"
SITE = {"province": "Chiang Mai", "latitude": 18.93, "longitude": 98.93,
        "category": "campground", "description": "A quiet spot."}


@pytest.fixture
def moderator(make_user):
    return make_user(is_moderator=True)


@pytest.fixture
def member(make_user):
    return make_user()


@pytest.fixture
def pending(db, make_user):
    def _make(name="New Camp", created_by=None, **extra):
        return Location.objects.create(**{**SITE, "name": name, **extra},
                                       created_by=created_by or make_user(),
                                       status=LocationStatus.PENDING_REVIEW)
    return _make


@pytest.fixture
def as_user(login):
    return lambda user: login(user, client=APIClient())


# ---- who can open the queue --------------------------------------------------------
@pytest.mark.django_db
def test_queue_is_closed_to_visitors_and_members(api_client, as_user, member, pending):
    pending()
    assert api_client.get(URL).status_code == 401
    assert as_user(member).get(URL).status_code == 403


@pytest.mark.django_db
def test_queue_is_open_to_moderators_and_admins(as_user, moderator, make_user, pending):
    pending()
    admin = make_user(is_staff=True)
    for user in (moderator, admin):
        assert as_user(user).get(URL).json()["count"] == 1


@pytest.mark.django_db
def test_queue_shows_only_pending_oldest_first(as_user, moderator, pending, make_user):
    first = pending("First")
    second = pending("Second")
    Location.objects.create(**SITE, name="A draft", created_by=make_user(), status=LocationStatus.DRAFT)
    Location.objects.create(**SITE, name="Live", created_by=make_user(), status=LocationStatus.PUBLISHED)
    rows = as_user(moderator).get(URL).json()["results"]
    assert [r["id"] for r in rows] == [first.pk, second.pk]


@pytest.mark.django_db
def test_queue_does_not_expose_the_submitters_contact_details(as_user, moderator, pending, make_user):
    submitter = make_user(phone="0812345678")
    pending(created_by=submitter)
    res = as_user(moderator).get(URL)
    row = res.json()["results"][0]
    assert row["submitted_by"]["id"] == submitter.pk
    assert submitter.email not in res.content.decode() and "0812345678" not in res.content.decode()


# ---- pin check and nearby duplicates -----------------------------------------------
@pytest.mark.django_db
def test_queue_reports_a_good_pin(as_user, moderator, pending):
    pending()
    check = as_user(moderator).get(URL).json()["results"][0]["pin_check"]
    assert check["in_thailand"] is True and check["province"] == "Chiang Mai"
    assert check["problem"] is None


@pytest.mark.django_db
def test_queue_reports_a_pin_in_the_wrong_province(as_user, moderator, pending):
    pending(province="Phuket")
    check = as_user(moderator).get(URL).json()["results"][0]["pin_check"]
    assert "not Phuket" in check["problem"]


@pytest.mark.django_db
def test_queue_reports_a_pin_in_another_country(as_user, moderator, pending):
    pending(latitude=18.0, longitude=102.6, province="Nong Khai")  # Vientiane, Laos
    check = as_user(moderator).get(URL).json()["results"][0]["pin_check"]
    assert check["in_thailand"] is False and "Laos" in check["problem"]


@pytest.mark.django_db
def test_nearby_lists_published_and_pending_but_not_far_or_draft(as_user, moderator, pending, make_user):
    site = pending("New Camp")
    Location.objects.create(**{**SITE, "latitude": 18.932}, name="Close and live",
                            created_by=make_user(), status=LocationStatus.PUBLISHED)
    pending("Close and pending", latitude=18.931)
    Location.objects.create(**{**SITE, "latitude": 18.932}, name="Close but a draft",
                            created_by=make_user(), status=LocationStatus.DRAFT)
    Location.objects.create(**{**SITE, "latitude": 18.99}, name="Far away",
                            created_by=make_user(), status=LocationStatus.PUBLISHED)
    rows = as_user(moderator).get(URL).json()["results"]
    row = next(r for r in rows if r["id"] == site.pk)
    assert [n["name"] for n in row["nearby"]] == ["Close and pending", "Close and live"]
    assert all(n["distance_km"] <= 1 for n in row["nearby"])


# ---- approve and reject ------------------------------------------------------------
@pytest.mark.django_db
def test_moderator_approves_and_the_campsite_goes_public(as_user, moderator, pending, api_client):
    site = pending()
    res = as_user(moderator).post(f"/api/campsites/{site.pk}/approve/")
    assert res.status_code == 200
    site.refresh_from_db()
    assert site.status == LocationStatus.PUBLISHED and site.reviewed_by == moderator
    assert api_client.get("/api/campsites/").json()["count"] == 1
    assert Notification.objects.filter(recipient=site.created_by, type=N.SUBMISSION_APPROVED).exists()


@pytest.mark.django_db
def test_moderator_rejects_with_a_reason_the_submitter_can_read(as_user, moderator, pending):
    site = pending()
    client = as_user(moderator)
    assert client.post(f"/api/campsites/{site.pk}/reject/", {}, format="json").status_code == 400
    res = client.post(f"/api/campsites/{site.pk}/reject/", {"note": "Duplicate"}, format="json")
    assert res.status_code == 200
    mine = as_user(site.created_by).get("/api/campsites/mine/").json()[0]
    assert mine["status"] == "rejected" and mine["moderation_note"] == "Duplicate"


@pytest.mark.django_db
def test_a_member_cannot_approve_or_reject(as_user, member, pending):
    site = pending()
    client = as_user(member)
    assert client.post(f"/api/campsites/{site.pk}/approve/").status_code == 403
    assert client.post(f"/api/campsites/{site.pk}/reject/", {"note": "x"}, format="json").status_code == 403
    site.refresh_from_db()
    assert site.status == LocationStatus.PENDING_REVIEW


@pytest.mark.django_db
def test_a_moderator_cannot_decide_their_own_submission(as_user, moderator, pending):
    site = pending(created_by=moderator)
    client = as_user(moderator)
    res = client.post(f"/api/campsites/{site.pk}/approve/")
    assert res.status_code == 403 and "another moderator" in str(res.json())
    assert client.post(f"/api/campsites/{site.pk}/reject/", {"note": "x"}, format="json").status_code == 403
    site.refresh_from_db()
    assert site.status == LocationStatus.PENDING_REVIEW


@pytest.mark.django_db
def test_a_lone_admin_can_still_approve_their_own(as_user, make_user, pending):
    admin = make_user(is_staff=True)
    site = pending(created_by=admin)
    assert as_user(admin).post(f"/api/campsites/{site.pk}/approve/").status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("bad", [{"province": "Phuket"},
                                 {"latitude": 18.0, "longitude": 102.6, "province": "Nong Khai"}])
def test_a_bad_pin_cannot_be_approved(as_user, moderator, pending, bad):
    site = pending(**bad)
    res = as_user(moderator).post(f"/api/campsites/{site.pk}/approve/")
    assert res.status_code == 400 and "cannot be approved" in str(res.json())
    site.refresh_from_db()
    assert site.status == LocationStatus.PENDING_REVIEW


@pytest.mark.django_db
def test_two_moderators_cannot_both_decide(as_user, moderator, make_user, pending):
    site = pending()
    assert as_user(moderator).post(f"/api/campsites/{site.pk}/approve/").status_code == 200
    res = as_user(make_user(is_moderator=True)).post(f"/api/campsites/{site.pk}/reject/",
                                                     {"note": "Late"}, format="json")
    assert res.status_code == 400
    site.refresh_from_db()
    assert site.status == LocationStatus.PUBLISHED


# ---- least privilege: everything else stays closed ---------------------------------
@pytest.mark.django_db
def test_moderator_cannot_open_the_django_admin(moderator):
    client = Client()
    client.force_login(moderator)
    assert client.get("/admin/").status_code == 302
    assert client.get("/admin/accounts/user/").status_code == 302


@pytest.mark.django_db
def test_moderator_has_no_other_admin_powers(as_user, moderator, make_user, make_trip, pending):
    client = as_user(moderator)
    other = make_user()
    EmergencyContact.objects.create(user=other, name="Mum", phone="0811111111", relationship="Mother")
    trip = make_trip()
    site = Location.objects.create(**SITE, name="Live", created_by=other, status=LocationStatus.PUBLISHED)
    refused = {
        "read another user's emergency contact": client.get(f"/api/users/{other.pk}/emergency-contact/"),
        "edit another user's profile": client.patch(f"/api/users/{other.pk}/", {"city": "X"}, format="json"),
        "cancel a trip": client.delete(f"/api/trips/{trip.pk}/"),
        "edit a trip": client.patch(f"/api/trips/{trip.pk}/", {"title": "X"}, format="json"),
        "see a trip's participants": client.get(f"/api/trips/{trip.pk}/participants/"),
        "see the suggested-edit queue": client.get("/api/campsite-revisions/"),
        "edit a published campsite": client.patch(f"/api/campsites/{site.pk}/", {"name": "X"}, format="json"),
    }
    assert {k: v.status_code for k, v in refused.items() if v.status_code != 403} == {}


@pytest.mark.django_db
def test_moderator_cannot_see_other_peoples_drafts(as_user, moderator, make_user):
    draft = Location.objects.create(**SITE, name="Private draft", created_by=make_user(),
                                    status=LocationStatus.DRAFT)
    assert as_user(moderator).get(f"/api/campsites/{draft.pk}/").status_code == 404


@pytest.mark.django_db
def test_nobody_can_make_themselves_a_moderator(as_user, member):
    client = as_user(member)
    client.patch(f"/api/users/{member.pk}/", {"is_moderator": True, "can_moderate": True}, format="json")
    client.patch("/api/users/me/", {"is_moderator": True}, format="json")
    member.refresh_from_db()
    assert member.is_moderator is False
    assert client.get(URL).status_code == 403


@pytest.mark.django_db
def test_profile_tells_the_app_whether_to_show_the_page(as_user, moderator, member, make_user):
    assert as_user(moderator).get("/api/users/me/").json()["can_moderate"] is True
    assert as_user(member).get("/api/users/me/").json()["can_moderate"] is False
    assert as_user(make_user(is_staff=True)).get("/api/users/me/").json()["can_moderate"] is True


@pytest.mark.django_db
def test_role_stops_working_when_removed_or_when_the_account_is_deleted(as_user, moderator, pending):
    pending()
    client = as_user(moderator)
    assert client.get(URL).status_code == 200
    type(moderator).objects.filter(pk=moderator.pk).update(is_moderator=False)
    assert client.get(URL).status_code == 403

    type(moderator).objects.filter(pk=moderator.pk).update(is_moderator=True)
    moderator.refresh_from_db()
    delete_account(moderator)
    moderator.refresh_from_db()
    assert moderator.is_moderator is False


# ---- admins grant the role ---------------------------------------------------------
@pytest.mark.django_db
def test_admin_grants_and_removes_the_role(make_user, member):
    admin = make_user(is_staff=True, is_superuser=True)
    client = Client()
    client.force_login(admin)
    data = {"_selected_action": [member.pk]}
    client.post("/admin/accounts/user/", {**data, "action": "make_moderators"})
    member.refresh_from_db()
    assert member.is_moderator is True
    client.post("/admin/accounts/user/", {**data, "action": "remove_moderators"})
    member.refresh_from_db()
    assert member.is_moderator is False


@pytest.mark.django_db
def test_a_suspended_user_is_not_made_a_moderator(make_user):
    admin = make_user(is_staff=True, is_superuser=True)
    suspended = make_user(status=UserStatus.SUSPENDED)
    client = Client()
    client.force_login(admin)
    client.post("/admin/accounts/user/", {"_selected_action": [suspended.pk], "action": "make_moderators"})
    suspended.refresh_from_db()
    assert suspended.is_moderator is False


@pytest.mark.django_db
def test_demo_data_has_a_moderator_and_a_possible_duplicate():
    from django.core.management import call_command
    from accounts.models import User
    call_command("seed_campsites")
    call_command("seed_demo")
    kai = User.objects.get(email="kai@demo.adventurehive.test")
    assert kai.is_moderator and not kai.is_staff
    client = APIClient()
    client.force_authenticate(kai)
    rows = client.get(URL).json()["results"]
    names = {r["name"]: r for r in rows}
    assert [n["name"] for n in names["Lam Ta Khong Riverside Camp"]["nearby"]] == ["Lam Ta Khong Campground"]
    assert names["Mae Ngat Lakeside Camp"]["nearby"] == []
    assert all(r["pin_check"]["problem"] is None for r in rows)
