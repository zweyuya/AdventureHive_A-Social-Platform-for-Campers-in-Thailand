"""
Campsite permit improvement: fees, rules, managing authority, booking link, and the
"checked by a moderator" date.

  * New campsites carry fees, rules, authority and booking link through submission.
  * Approving a new campsite records when its permit information was checked.
  * Approving a suggested edit updates that date only when permit information changed.
  * Fees are versioned like every other editable field.
  * The authority list (for the "Managed by" dropdown) is public and read-only.
"""
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from locations.models import Authority, AuthorityType, Location

SITE = {
    "name": "Mon Jam Campsite", "province": "Chiang Mai", "latitude": 18.93, "longitude": 98.82,
    "category": "campsite", "permit_status": "required",
    "fees": "Entry 100 THB/person · Camping 30 THB/person/night",
    "permit_details": "Register at the park office on arrival.",
    "rules": "No fires outside the fire pits\nQuiet after 22:00",
    "permit_booking_url": "https://reservation.dnp.go.th",
    "permit_info_source": "Park website",
}


@pytest.fixture
def park(db):
    return Authority.objects.create(name="Doi Suthep-Pui National Park Office",
                                    authority_type=AuthorityType.NATIONAL_PARK, phone="053 000 000")


@pytest.fixture
def member(make_user, login):
    return login(make_user(), client=APIClient())


@pytest.fixture
def moderator(login):
    user = User.objects.create_superuser(email="mod@example.com", password="Adm1n-Pass!")
    return login(user, password="Adm1n-Pass!", client=APIClient())


def _publish(member, moderator, **extra):
    res = member.post("/api/campsites/", {**SITE, **extra}, format="json")
    assert res.status_code == 201, res.content
    site_id = res.json()["id"]
    assert member.post(f"/api/campsites/{site_id}/submit/").status_code == 200
    assert moderator.post(f"/api/campsites/{site_id}/approve/").status_code == 200
    return site_id


def _suggest(client, site_id, **changes):
    res = client.post(f"/api/campsites/{site_id}/revisions/",
                      {"edit_summary": "Update from the park gate", **changes}, format="json")
    assert res.status_code == 201, res.content
    return res.json()["id"]


# ---------------- New campsites ----------------------------------------------------

@pytest.mark.django_db
def test_new_campsite_keeps_fees_rules_authority_and_booking_link(member, moderator, park):
    site_id = _publish(member, moderator, authority_id=park.pk)
    c = APIClient().get(f"/api/campsites/{site_id}/").json()
    assert c["fees"] == SITE["fees"]
    assert c["rules"] == SITE["rules"]  # rules no longer end up inside permit details
    assert c["permit_details"] == SITE["permit_details"]
    assert c["permit_booking_url"] == SITE["permit_booking_url"]
    assert c["authority"]["name"] == park.name and c["authority"]["phone"] == "053 000 000"


@pytest.mark.django_db
def test_moderator_sees_fees_and_booking_link_in_the_queue(member, moderator):
    site_id = member.post("/api/campsites/", SITE, format="json").json()["id"]
    member.post(f"/api/campsites/{site_id}/submit/")
    queued = moderator.get("/api/campsites/moderation/").json()
    queued = queued["results"] if isinstance(queued, dict) else queued
    item = next(c for c in queued if c["id"] == site_id)
    assert item["fees"] == SITE["fees"] and item["permit_booking_url"] == SITE["permit_booking_url"]


@pytest.mark.django_db
def test_fees_are_limited_and_booking_link_must_be_a_url(member):
    too_long = member.post("/api/campsites/", {**SITE, "fees": "x" * 301}, format="json")
    assert too_long.status_code == 400 and "fees" in too_long.json()
    bad_url = member.post("/api/campsites/", {**SITE, "permit_booking_url": "call the office"}, format="json")
    assert bad_url.status_code == 400 and "permit_booking_url" in bad_url.json()


# ---------------- "Checked by a moderator" date --------------------------------------

@pytest.mark.django_db
def test_approving_a_new_campsite_records_when_it_was_checked(member, moderator):
    site_id = member.post("/api/campsites/", SITE, format="json").json()["id"]
    member.post(f"/api/campsites/{site_id}/submit/")
    assert Location.objects.get(pk=site_id).permit_info_verified_at is None  # not before approval

    before = timezone.now()
    moderator.post(f"/api/campsites/{site_id}/approve/")
    checked = Location.objects.get(pk=site_id).permit_info_verified_at
    assert checked is not None and checked >= before
    assert APIClient().get(f"/api/campsites/{site_id}/").json()["permit_info_verified_at"]


@pytest.mark.django_db
def test_rejected_campsite_is_not_marked_checked(member, moderator):
    site_id = member.post("/api/campsites/", SITE, format="json").json()["id"]
    member.post(f"/api/campsites/{site_id}/submit/")
    moderator.post(f"/api/campsites/{site_id}/reject/", {"note": "Wrong fee."}, format="json")
    assert Location.objects.get(pk=site_id).permit_info_verified_at is None


@pytest.mark.django_db
def test_approved_fee_change_updates_the_checked_date_and_makes_a_new_version(member, moderator, make_user, login):
    site_id = _publish(member, moderator)
    old = timezone.now() - timedelta(days=400)
    Location.objects.filter(pk=site_id).update(permit_info_verified_at=old)

    editor = login(make_user(), client=APIClient())
    rev = _suggest(editor, site_id, fees="Entry 200 THB/person · Camping 30 THB/person/night")
    assert APIClient().get(f"/api/campsites/{site_id}/").json()["fees"] == SITE["fees"]  # not yet

    assert moderator.post(f"/api/campsite-revisions/{rev}/approve/").status_code == 200
    site = Location.objects.get(pk=site_id)
    assert site.fees.startswith("Entry 200 THB") and site.current_version == 2
    assert site.permit_info_verified_at > old + timedelta(days=399)

    history = APIClient().get(f"/api/campsites/{site_id}/history/").json()
    assert history[0]["snapshot"]["fees"].startswith("Entry 200")
    assert history[1]["snapshot"]["fees"] == SITE["fees"]  # the old fee is kept


@pytest.mark.django_db
def test_edit_that_does_not_touch_permit_information_keeps_the_checked_date(member, moderator, make_user, login):
    site_id = _publish(member, moderator)
    old = timezone.now() - timedelta(days=400)
    Location.objects.filter(pk=site_id).update(permit_info_verified_at=old)

    editor = login(make_user(), client=APIClient())
    rev = _suggest(editor, site_id, has_water_source=True)
    moderator.post(f"/api/campsite-revisions/{rev}/approve/")
    assert Location.objects.get(pk=site_id).permit_info_verified_at == old


@pytest.mark.django_db
def test_changing_who_manages_the_campsite_counts_as_permit_information(member, moderator, park, make_user, login):
    site_id = _publish(member, moderator)
    Location.objects.filter(pk=site_id).update(permit_info_verified_at=None)
    editor = login(make_user(), client=APIClient())
    rev = _suggest(editor, site_id, authority_id=park.pk)
    moderator.post(f"/api/campsite-revisions/{rev}/approve/")
    site = Location.objects.get(pk=site_id)
    assert site.authority_id == park.pk and site.permit_info_verified_at is not None


# ---------------- Authorities ------------------------------------------------------------

@pytest.mark.django_db
def test_authority_list_is_public_and_sorted(park):
    Authority.objects.create(name="Chiang Dao Wildlife Sanctuary Office", authority_type=AuthorityType.OTHER)
    res = APIClient().get("/api/authorities/")
    assert res.status_code == 200
    names = [a["name"] for a in res.json()]
    assert names == sorted(names) and park.name in names
    assert {"id", "name", "phone", "booking_url"} <= set(res.json()[0])


@pytest.mark.django_db
def test_authorities_cannot_be_created_or_changed_through_the_api(member, park):
    assert member.post("/api/authorities/", {"name": "Fake office"}, format="json").status_code == 405
    assert member.patch(f"/api/authorities/{park.pk}/", {"phone": "1"}, format="json").status_code in (404, 405)


@pytest.mark.django_db
def test_no_checked_date_while_the_permit_is_unknown(member, moderator, make_user, login):
    site_id = _publish(member, moderator, permit_status="unknown")
    assert Location.objects.get(pk=site_id).permit_info_verified_at is None
    # Once someone adds the permit status and a moderator approves it, the date appears
    editor = login(make_user(), client=APIClient())
    rev = _suggest(editor, site_id, permit_status="not_required")
    moderator.post(f"/api/campsite-revisions/{rev}/approve/")
    assert Location.objects.get(pk=site_id).permit_info_verified_at is not None
