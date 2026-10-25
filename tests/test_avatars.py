"""Profile photos: processed server-side (square, resized, metadata stripped), PDPA-safe."""
import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient

from reviews.models import Review
from trips import services


def _photo(fmt="JPEG", size=(1200, 800), gps=False, name="me.jpg"):
    buf = io.BytesIO()
    img = Image.new("RGB", size, (200, 120, 40))
    kwargs = {}
    if gps:
        exif = Image.Exif()
        exif[0x8825] = {1: "N", 2: (13.0, 44.0, 0.0), 3: "E", 4: (100.0, 30.0, 0.0)}  # GPSInfo
        exif[0x010F] = "PhoneMaker"
        kwargs["exif"] = exif
    img.save(buf, fmt, **kwargs)
    return SimpleUploadedFile(name, buf.getvalue(), content_type=f"image/{fmt.lower()}")


@pytest.fixture(autouse=True)
def media_tmp(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def _upload(client, file):
    return client.put("/api/users/me/avatar/", {"avatar": file}, format="multipart")


@pytest.mark.django_db
def test_upload_is_cropped_resized_and_gps_stripped(user, login, settings):
    client = login(user, client=APIClient())
    original = _photo(gps=True)
    assert Image.open(io.BytesIO(original.read())).getexif().get_ifd(0x8825)  # GPS present before
    original.seek(0)
    res = _upload(client, original)
    assert res.status_code == 200, res.content
    url = res.json()["avatar"]
    assert url.startswith("/media/avatars/") and url.endswith(".jpg")

    user.profile.refresh_from_db()
    stored = Image.open(user.profile.avatar.path)
    assert stored.size == (400, 400) and stored.format == "JPEG"
    assert len(stored.getexif()) == 0  # no GPS, no camera info


@pytest.mark.django_db
def test_png_and_webp_accepted(user, login):
    client = login(user, client=APIClient())
    assert _upload(client, _photo("PNG", name="a.png")).status_code == 200
    assert _upload(client, _photo("WEBP", name="a.webp")).status_code == 200


@pytest.mark.django_db
def test_fake_or_wrong_files_rejected(user, login):
    client = login(user, client=APIClient())
    fake = SimpleUploadedFile("evil.jpg", b"<script>alert(1)</script>", content_type="image/jpeg")
    res = _upload(client, fake)
    assert res.status_code == 400 and "valid image" in str(res.json())
    gif = io.BytesIO(); Image.new("RGB", (10, 10)).save(gif, "GIF")
    res = _upload(client, SimpleUploadedFile("a.gif", gif.getvalue(), content_type="image/gif"))
    assert res.status_code == 400 and "JPEG, PNG or WebP" in str(res.json())


@pytest.mark.django_db
def test_too_large_rejected(user, login):
    client = login(user, client=APIClient())
    big = _photo(); big.size = 6 * 1024 * 1024
    from accounts.images import process_avatar
    from rest_framework.exceptions import ValidationError
    with pytest.raises(ValidationError, match="5 MB"):
        process_avatar(big)


@pytest.mark.django_db
def test_replacing_deletes_old_file_and_delete_removes_it(user, login):
    client = login(user, client=APIClient())
    _upload(client, _photo())
    user.profile.refresh_from_db()
    first = user.profile.avatar.path
    _upload(client, _photo(name="second.jpg"))
    import os
    assert not os.path.exists(first)
    user.profile.refresh_from_db()
    second = user.profile.avatar.path
    res = client.delete("/api/users/me/avatar/")
    assert res.status_code == 200 and res.json()["avatar"] is None
    assert not os.path.exists(second)


@pytest.mark.django_db
def test_account_deletion_erases_photo(user, login):
    import os
    from accounts.services import delete_account
    client = login(user, client=APIClient())
    _upload(client, _photo())
    user.profile.refresh_from_db()
    path = user.profile.avatar.path
    delete_account(user)
    user.profile.refresh_from_db()
    assert not user.profile.avatar and not os.path.exists(path)


@pytest.mark.django_db
def test_avatar_shown_next_to_content(make_trip, make_user, login, api_client):
    organizer = make_user()
    trip = make_trip(organizer=organizer)
    _upload(login(organizer, client=APIClient()), _photo())
    url = api_client.get(f"/api/trips/{trip.pk}/").json()["organizer"]["avatar"]
    assert url and url.startswith("/media/avatars/")
    assert api_client.get(f"/api/users/{organizer.pk}/").json()["avatar"] == url


@pytest.mark.django_db
def test_anonymous_cannot_upload(api_client):
    assert _upload(api_client, _photo()).status_code == 401


@pytest.mark.django_db
def test_admin_can_remove_photo(user, login, client):
    from accounts.models import User
    _upload(login(user, client=APIClient()), _photo())
    admin = User.objects.create_superuser(email="mod@example.com", password="Adm1n-Pass!")
    client.force_login(admin)
    assert b"border-radius:50%" in client.get(f"/admin/accounts/user/{user.pk}/change/").content
    client.post("/admin/accounts/user/", {"action": "remove_profile_photos", "_selected_action": [str(user.pk)]})
    user.profile.refresh_from_db()
    assert not user.profile.avatar
