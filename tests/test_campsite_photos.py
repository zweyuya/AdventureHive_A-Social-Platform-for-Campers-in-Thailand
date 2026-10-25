"""Campsite cover photos: uploaded by moderators in the admin, shown via the API."""
import io

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from accounts.models import User
from locations.models import Location


def _jpeg(name="camp.jpg", size=(800, 500)):
    buf = io.BytesIO()
    Image.new("RGB", size, (20, 120, 80)).save(buf, "JPEG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/jpeg")


@pytest.fixture(autouse=True)
def media_tmp(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path  # don't write test uploads into the project


@pytest.mark.django_db
def test_photo_url_and_credit_in_api(location, api_client, make_trip):
    location.cover_image = _jpeg()
    location.cover_image_credit = "Photo: Sora, CC BY 4.0"
    location.save()
    detail = api_client.get(f"/api/campsites/{location.pk}/").json()
    assert detail["cover_image"].startswith("/media/campsites/") and detail["cover_image"].endswith(".jpg")
    assert detail["cover_image_credit"] == "Photo: Sora, CC BY 4.0"
    assert api_client.get("/api/campsites/").json()["results"][0]["cover_image"] == detail["cover_image"]
    feature = api_client.get("/api/map/campsites/").json()["features"][0]
    assert feature["properties"]["cover_image"] == detail["cover_image"]
    trip = make_trip()
    assert api_client.get(f"/api/trips/{trip.pk}/").json()["location"]["cover_image"] == detail["cover_image"]


@pytest.mark.django_db
def test_no_photo_means_null(location, api_client):
    assert api_client.get(f"/api/campsites/{location.pk}/").json()["cover_image"] is None


@pytest.mark.django_db
def test_admin_uploads_photo(client, location):
    admin = User.objects.create_superuser(email="mod@example.com", password="Adm1n-Pass!")
    client.force_login(admin)
    url = f"/admin/locations/location/{location.pk}/change/"
    form = client.get(url).context["adminform"].form
    data = {k: v for k, v in form.initial.items() if v is not None and k != "cover_image"}
    data.update({"authority": "", "permit_info_verified_at_0": "", "permit_info_verified_at_1": "",
                 "revisions-TOTAL_FORMS": "0", "revisions-INITIAL_FORMS": "0",
                 "revisions-MIN_NUM_FORMS": "0", "revisions-MAX_NUM_FORMS": "1000",
                 "cover_image": _jpeg(), "cover_image_credit": "Photo: own work"})
    res = client.post(url, data)
    assert res.status_code == 302, res.context["adminform"].form.errors if res.context else res
    location.refresh_from_db()
    assert location.cover_image and location.cover_image_credit == "Photo: own work"
    assert b"<img" in client.get(url).content  # preview shown


@pytest.mark.django_db
def test_rejects_wrong_type_and_too_large(location):
    location.cover_image = SimpleUploadedFile("notes.pdf", b"%PDF-1.4", content_type="application/pdf")
    with pytest.raises(ValidationError):
        location.full_clean(exclude=["embedding"])
    big = _jpeg(size=(10, 10))
    big.size = 6 * 1024 * 1024
    location.cover_image = big
    with pytest.raises(ValidationError, match="5 MB"):
        location.full_clean(exclude=["embedding"])


@pytest.mark.django_db
def test_photo_survives_suggested_edit(location, make_user):
    from locations.services import approve_revision, propose_edit
    location.cover_image = _jpeg()
    location.save()
    admin = User.objects.create_superuser(email="m2@example.com", password="Adm1n-Pass!")
    rev = propose_edit(location, make_user(), {"rules": "No drones"}, "rules")
    approve_revision(rev, admin)
    assert Location.objects.get(pk=location.pk).cover_image


@pytest.mark.django_db
def test_has_photo_filter(location, api_client):
    other = Location.objects.create(name="No Photo Camp", province="Loei", latitude=17.5,
                                    longitude=101.3, status="published")
    location.cover_image = _jpeg(); location.save()
    names = lambda q: [c["name"] for c in api_client.get(f"/api/campsites/?{q}").json()["results"]]
    assert names("has_photo=true") == [location.name]
    assert names("has_photo=false") == [other.name]
