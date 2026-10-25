"""Layer 2 — public campsite browsing: list, filters, detail, GeoJSON map, seed data."""
from decimal import Decimal

import pytest
from django.core.management import call_command

from locations.models import Authority, Location, LocationStatus


def _site(name, province="Chiang Mai", status=LocationStatus.PUBLISHED, **kw):
    defaults = dict(latitude=18.8, longitude=98.9, category="campground")
    defaults.update(kw)
    return Location.objects.create(name=name, province=province, status=status, **defaults)


@pytest.fixture
def sites(db):
    return {
        "inthanon": _site("Inthanon Camp", has_restrooms=True, has_water_source=True,
                          avg_rating=Decimal("4.60"), review_count=5),
        "chiangdao": _site("Chiang Dao Ridge", category="backcountry", avg_rating=Decimal("3.90")),
        "khaoyai": _site("Lam Ta Khong", province="Nakhon Ratchasima", latitude=14.43,
                         longitude=101.38, has_restrooms=True, fire_pit_allowed=True),
        "pending": _site("Secret Spot", status=LocationStatus.PENDING_REVIEW),
        "draft": _site("My Draft", status=LocationStatus.DRAFT),
    }


def _names(res):
    body = res.json()
    items = body["results"] if isinstance(body, dict) and "results" in body else body
    return sorted(i["name"] for i in items)


# ---------------- List & filters ---------------------------------------------

@pytest.mark.django_db
def test_list_is_public_and_shows_only_published(api_client, sites):
    res = api_client.get("/api/campsites/")
    assert res.status_code == 200
    assert _names(res) == ["Chiang Dao Ridge", "Inthanon Camp", "Lam Ta Khong"]
    assert res.json()["count"] == 3


@pytest.mark.django_db
@pytest.mark.parametrize("query, expected", [
    ("province=chiang mai", ["Chiang Dao Ridge", "Inthanon Camp"]),          # case-insensitive
    ("category=backcountry", ["Chiang Dao Ridge"]),
    ("category=backcountry&category=campground",
     ["Chiang Dao Ridge", "Inthanon Camp", "Lam Ta Khong"]),
    ("has_restrooms=true", ["Inthanon Camp", "Lam Ta Khong"]),
    ("has_restrooms=true&has_water_source=true", ["Inthanon Camp"]),
    ("fire_pit_allowed=true", ["Lam Ta Khong"]),
    ("min_rating=4", ["Inthanon Camp"]),                                     # unrated excluded
    ("search=ridge", ["Chiang Dao Ridge"]),
    ("search=nakhon", ["Lam Ta Khong"]),
])
def test_filters(api_client, sites, query, expected):
    assert _names(api_client.get(f"/api/campsites/?{query}")) == expected


@pytest.mark.django_db
def test_ordering_by_rating(api_client, sites):
    res = api_client.get("/api/campsites/?ordering=-avg_rating&min_rating=1")
    assert [i["name"] for i in res.json()["results"]] == ["Inthanon Camp", "Chiang Dao Ridge"]


# ---------------- Detail -------------------------------------------------------

@pytest.mark.django_db
def test_detail_includes_authority_and_permit_info(api_client):
    auth = Authority.objects.create(name="Doi Inthanon NP Office", authority_type="national_park",
                                    booking_url="https://reservation.dnp.go.th")
    site = _site("Inthanon Camp", authority=auth, permit_status="required",
                 permit_details="Book online", rules="Quiet after 22:00")
    body = api_client.get(f"/api/campsites/{site.pk}/").json()
    assert body["authority"]["booking_url"] == "https://reservation.dnp.go.th"
    assert body["permit_status"] == "required" and body["rules"] == "Quiet after 22:00"
    assert "moderation_note" not in body  # private to submitter / staff


@pytest.mark.django_db
def test_unpublished_detail_hidden_from_public_and_other_members(api_client, login, make_user, sites):
    url = f"/api/campsites/{sites['pending'].pk}/"
    assert api_client.get(url).status_code == 404
    login(make_user())
    assert api_client.get(url).status_code == 404


# ---------------- GeoJSON map ---------------------------------------------------

@pytest.mark.django_db
def test_geojson_is_valid_and_filtered(api_client, sites):
    body = api_client.get("/api/map/campsites/").json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) == 3  # published only
    feature = next(f for f in body["features"] if f["properties"]["name"] == "Lam Ta Khong")
    assert feature["type"] == "Feature"
    assert feature["geometry"] == {"type": "Point", "coordinates": [101.38, 14.43]}  # [lng, lat]
    assert set(feature["properties"]) == {"id", "name", "category", "province", "avg_rating",
                                       "cover_image"}

    filtered = api_client.get("/api/map/campsites/?province=Nakhon Ratchasima").json()
    assert [f["properties"]["name"] for f in filtered["features"]] == ["Lam Ta Khong"]


# ---------------- Seed data -----------------------------------------------------

@pytest.mark.django_db
def test_seed_campsites_is_idempotent_and_versioned(api_client):
    call_command("seed_campsites")
    call_command("seed_campsites")
    assert Location.objects.published().count() == 15
    assert Authority.objects.count() == 14
    site = Location.objects.get(name="Lam Ta Khong Campground")
    assert site.current_version == 1 and site.revisions.count() == 1
    assert site.permit_status == "unknown" and site.permit_info_verified_at is None
    assert len(api_client.get("/api/map/campsites/").json()["features"]) == 15
