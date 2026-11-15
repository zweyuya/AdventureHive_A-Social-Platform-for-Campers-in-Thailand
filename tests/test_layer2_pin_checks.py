"""
Campsite map pins: inside Thailand, province matches the pin, duplicate warning.

Unit tests (no database) cover the province lookup in core/provinces.py;
integration tests go through the API and the Django admin form.
"""
import pytest
from rest_framework.test import APIClient

from core.provinces import canonical_province, check_pin
from locations.admin import LocationAdminForm
from locations.models import Location, LocationStatus

CHIANG_MAI = (18.93, 98.82)       # Mon Jam
CAMBODIA = (14.09396, 103.05176)  # just across the border from Buri Ram / Surin
LAOS = (18.05, 102.60)            # Vientiane
KHON_KAEN = (16.75458, 102.29919)
SIMILAN = (8.570, 97.640)         # island too small for the simplified boundaries

SITE = {"name": "Mon Jam Campsite", "category": "campsite", "description": "Hilltop camping."}


def _site(lat_lng, province=""):
    return {**SITE, "latitude": lat_lng[0], "longitude": lat_lng[1], "province": province}


@pytest.fixture
def member(make_user, login):
    return login(make_user(), client=APIClient())


# ---------------- unit: province lookup ----------------------------------------

@pytest.mark.unit
@pytest.mark.parametrize("point, province", [
    (CHIANG_MAI, "Chiang Mai"),
    (KHON_KAEN, "Khon Kaen"),
    ((13.75, 100.50), "Bangkok"),
    (SIMILAN, "Phang Nga"),          # at sea → nearest province
    ((10.10, 99.84), "Surat Thani"),  # Ko Tao
])
def test_pin_inside_thailand_gives_its_province(point, province):
    pin = check_pin(*point)
    assert pin.in_thailand and pin.province == province and province in pin.allowed


@pytest.mark.unit
@pytest.mark.parametrize("point, country", [
    (CAMBODIA, "Cambodia"), (LAOS, "Laos"), ((16.49, 97.63), "Myanmar"), ((5.41, 100.33), "Malaysia"),
])
def test_pin_in_a_neighbouring_country_is_outside_thailand(point, country):
    """These points are all inside the old latitude/longitude box, which accepted them."""
    pin = check_pin(*point)
    assert not pin.in_thailand and pin.country == country and pin.allowed == set()


@pytest.mark.unit
def test_pin_far_out_at_sea_is_outside_thailand():
    assert not check_pin(10.5, 101.5).in_thailand  # middle of the Gulf


@pytest.mark.unit
def test_pin_near_a_province_border_allows_both_provinces():
    pin = check_pin(14.430, 101.385)  # Lam Ta Khong, Khao Yai: on the Nakhon Ratchasima border
    assert {"Nakhon Ratchasima", "Nakhon Nayok"} <= pin.allowed


@pytest.mark.unit
def test_province_names_are_matched_case_insensitively():
    assert canonical_province("  chiang   mai ") == "Chiang Mai"
    assert canonical_province("Atlantis") is None


# ---------------- integration: API ---------------------------------------------

@pytest.mark.django_db
def test_blank_province_is_filled_in_from_the_pin(member):
    res = member.post("/api/campsites/", _site(KHON_KAEN), format="json")
    assert res.status_code == 201 and res.json()["province"] == "Khon Kaen"


@pytest.mark.django_db
def test_province_is_saved_with_canonical_spelling(member):
    res = member.post("/api/campsites/", _site(CHIANG_MAI, "chiang mai"), format="json")
    assert res.status_code == 201 and res.json()["province"] == "Chiang Mai"


@pytest.mark.django_db
def test_province_that_does_not_match_the_pin_is_rejected(member):
    res = member.post("/api/campsites/", _site(KHON_KAEN, "Chiang Mai"), format="json")
    assert res.status_code == 400
    assert "Khon Kaen" in res.json()["province"][0]
    assert not Location.objects.exists()


@pytest.mark.django_db
def test_pin_in_cambodia_is_rejected(member):
    res = member.post("/api/campsites/", _site(CAMBODIA, "Buri Ram"), format="json")
    assert res.status_code == 400 and "Cambodia" in res.json()["latitude"][0]


@pytest.mark.django_db
def test_editing_a_draft_rechecks_the_pin(member):
    site_id = member.post("/api/campsites/", _site(CHIANG_MAI), format="json").json()["id"]
    moved = member.patch(f"/api/campsites/{site_id}/", {"latitude": LAOS[0], "longitude": LAOS[1]},
                         format="json")
    assert moved.status_code == 400 and "Laos" in moved.json()["latitude"][0]
    # Editing other fields of the draft does not need the pin again.
    assert member.patch(f"/api/campsites/{site_id}/", {"description": "x"},
                        format="json").status_code == 200


@pytest.mark.django_db
def test_suggested_edit_cannot_move_a_campsite_out_of_its_province(member, location):
    # conftest location: Pha Taem, Ubon Ratchathani (published)
    res = member.post(f"/api/campsites/{location.pk}/revisions/",
                      {"latitude": CHIANG_MAI[0], "longitude": CHIANG_MAI[1],
                       "edit_summary": "moved"}, format="json")
    assert res.status_code == 400 and "Chiang Mai" in res.json()["province"][0]


@pytest.mark.django_db
def test_pin_check_reports_province_and_nearby_campsites(member, location):
    # A pin ~0.5 km from the published Pha Taem campground (15.40, 105.50)
    info = member.get("/api/campsites/pin-check/?lat=15.404&lng=105.502").json()
    assert info["in_thailand"] and info["province"] == "Ubon Ratchathani"
    assert [c["name"] for c in info["nearby"]] == [location.name]
    assert info["nearby"][0]["distance_km"] < 1

    # Editing that same campsite: it is not its own duplicate.
    info = member.get(f"/api/campsites/pin-check/?lat=15.404&lng=105.502&exclude={location.pk}").json()
    assert info["nearby"] == []


@pytest.mark.django_db
def test_pin_check_ignores_drafts_but_warns_about_unverified(member, location):
    location.status = LocationStatus.DRAFT
    location.save()
    assert member.get("/api/campsites/pin-check/?lat=15.404&lng=105.502").json()["nearby"] == []
    location.status = LocationStatus.PENDING_REVIEW  # waiting for a moderator: still a duplicate risk
    location.save()
    nearby = member.get("/api/campsites/pin-check/?lat=15.404&lng=105.502").json()["nearby"]
    assert [(n["id"], n["verified"]) for n in nearby] == [(location.pk, False)]


@pytest.mark.django_db
def test_pin_check_outside_thailand_and_bad_input(member, api_client):
    info = member.get(f"/api/campsites/pin-check/?lat={CAMBODIA[0]}&lng={CAMBODIA[1]}").json()
    assert info["in_thailand"] is False and info["country"] == "Cambodia" and info["province"] is None
    assert member.get("/api/campsites/pin-check/?lat=abc&lng=1").status_code == 400
    assert member.get("/api/campsites/pin-check/?lat=1&lng=1&exclude=x").status_code == 400
    assert api_client.get("/api/campsites/pin-check/?lat=15&lng=100").status_code in (401, 403)


# ---------------- integration: Django admin form -------------------------------

def _admin_form(instance=None, **overrides):
    data = {"name": "Admin site", "province": "Chiang Mai", "latitude": CHIANG_MAI[0],
            "longitude": CHIANG_MAI[1], "category": "campsite", "status": LocationStatus.PUBLISHED,
            "permit_status": "unknown", "review_count": 0, "current_version": 0, **overrides}
    return LocationAdminForm(data=data, instance=instance)


@pytest.mark.django_db
def test_admin_form_applies_the_same_pin_rule():
    assert _admin_form().is_valid()
    wrong = _admin_form(province="Loei")
    assert not wrong.is_valid() and "Chiang Mai" in wrong.errors["province"][0]
    abroad = _admin_form(latitude=LAOS[0], longitude=LAOS[1])
    assert not abroad.is_valid() and "Laos" in abroad.errors["latitude"][0]
