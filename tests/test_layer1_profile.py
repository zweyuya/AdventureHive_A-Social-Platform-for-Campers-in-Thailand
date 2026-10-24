"""Layer 1 — profiles, emergency contact isolation, PDPA account deletion."""
import pytest
from django.conf import settings
from rest_framework.test import APIClient

from accounts.models import EmergencyContact, InterestTag, User, UserStatus

CONTACT = {"name": "Mya Mya", "phone": "+66812345678", "relationship": "sister"}


# ---------------- Profiles ---------------------------------------------------

@pytest.mark.django_db
def test_public_profile_hides_private_fields(api_client, make_user):
    u = make_user(phone="+66811111111")
    res = api_client.get(f"/api/users/{u.pk}/")  # anonymous
    assert res.status_code == 200
    body = res.json()
    for private in ("email", "phone", "date_of_birth", "gender", "status"):
        assert private not in body


@pytest.mark.django_db
def test_user_can_edit_own_profile(login, user, api_client):
    tag = InterestTag.objects.create(tag_name="birdwatching")
    login(user)
    res = api_client.patch(f"/api/users/{user.pk}/", {
        "bio": "Weekend camper", "city": "Bangkok", "phone": "+66899999999",
        "camping_experience_level": "advanced", "interest_tag_ids": [tag.id],
    }, format="json")
    assert res.status_code == 200, res.content
    user.refresh_from_db()
    assert user.phone == "+66899999999"
    assert user.profile.bio == "Weekend camper"
    assert list(user.profile.interest_tags.values_list("tag_name", flat=True)) == ["birdwatching"]


@pytest.mark.django_db
def test_read_only_fields_cannot_be_changed(login, user, api_client):
    login(user)
    api_client.patch(f"/api/users/{user.pk}/", {
        "email": "hacker@example.com", "status": "banned", "pdpa_consent_at": None,
    }, format="json")
    user.refresh_from_db()
    assert user.email != "hacker@example.com" and user.status == UserStatus.ACTIVE


@pytest.mark.django_db
def test_cannot_edit_someone_elses_profile(login, user, make_user, api_client):
    other = make_user()
    login(user)
    res = api_client.patch(f"/api/users/{other.pk}/", {"bio": "pwned"}, format="json")
    assert res.status_code == 403


@pytest.mark.django_db
def test_anonymous_cannot_edit(api_client, user):
    assert api_client.patch(f"/api/users/{user.pk}/", {"bio": "x"}, format="json").status_code == 401


@pytest.mark.django_db
def test_duplicate_phone_rejected(login, make_user, api_client):
    make_user(phone="+66800000000")
    me = make_user()
    login(me)
    res = api_client.patch(f"/api/users/{me.pk}/", {"phone": "+66800000000"}, format="json")
    assert res.status_code == 400


# ---------------- Emergency contact -------------------------------------------

@pytest.mark.django_db
def test_owner_can_create_read_update_delete_contact(login, user, api_client):
    login(user)
    url = f"/api/users/{user.pk}/emergency-contact/"
    assert api_client.get(url).status_code == 404
    assert api_client.put(url, CONTACT, format="json").status_code == 201
    assert api_client.get(url).json()["name"] == "Mya Mya"
    res = api_client.put(url, {**CONTACT, "phone": "+66822222222"}, format="json")
    assert res.status_code == 200 and EmergencyContact.objects.count() == 1
    assert api_client.delete(url).status_code == 204
    assert not EmergencyContact.objects.exists()


@pytest.mark.django_db
def test_other_users_cannot_read_or_write_contact(login, user, make_user):
    EmergencyContact.objects.create(user=user, **CONTACT)
    url = f"/api/users/{user.pk}/emergency-contact/"
    intruder = login(make_user(), client=APIClient())
    assert intruder.get(url).status_code == 403
    assert intruder.put(url, CONTACT, format="json").status_code == 403
    assert intruder.delete(url).status_code == 403
    assert EmergencyContact.objects.get(user=user).phone == CONTACT["phone"]


@pytest.mark.django_db
def test_even_admin_cannot_read_contact(login, user):
    EmergencyContact.objects.create(user=user, **CONTACT)
    admin = User.objects.create_superuser(email="admin@example.com", password="Adm1n-Pass!")
    from accounts.models import Profile
    Profile.objects.create(user=admin, display_name="admin")
    client = login(admin, password="Adm1n-Pass!", client=APIClient())
    assert client.get(f"/api/users/{user.pk}/emergency-contact/").status_code == 403


@pytest.mark.django_db
def test_contact_never_appears_in_profile_responses(login, user, api_client):
    EmergencyContact.objects.create(user=user, **CONTACT)
    login(user)
    for url in ("/api/users/me/", f"/api/users/{user.pk}/"):
        assert "+66812345678" not in api_client.get(url).content.decode()


@pytest.mark.django_db
def test_anonymous_cannot_access_contact(api_client, user):
    assert api_client.get(f"/api/users/{user.pk}/emergency-contact/").status_code == 401


# ---------------- Account deletion (PDPA) -------------------------------------

@pytest.mark.django_db
def test_account_deletion_requires_correct_password(login, user, api_client):
    login(user)
    res = api_client.delete("/api/auth/account/", {"password": "wrong"}, format="json")
    assert res.status_code == 400
    user.refresh_from_db()
    assert user.status == UserStatus.ACTIVE


@pytest.mark.django_db
def test_account_deletion_anonymises_and_logs_out(login, user, api_client):
    EmergencyContact.objects.create(user=user, **CONTACT)
    user.profile.bio = "I love Khao Yai"
    user.profile.save()
    original_email = user.email
    login(user)
    refresh = api_client.cookies[settings.JWT_REFRESH_COOKIE].value

    res = api_client.delete("/api/auth/account/", {"password": "Camp1ng!Pass"}, format="json")
    assert res.status_code == 204

    user.refresh_from_db()
    assert user.status == UserStatus.DELETED and user.deleted_at is not None
    assert user.email.endswith("@deleted.invalid") and user.phone is None
    assert not user.has_usable_password()
    assert user.profile.display_name == "Deleted user" and user.profile.bio == ""
    assert not EmergencyContact.objects.filter(user=user).exists()

    # Cannot log in again, old refresh token is dead, profile is gone publicly
    fresh = APIClient()
    assert fresh.post("/api/auth/login/", {"email": original_email, "password": "Camp1ng!Pass"},
                      format="json").status_code == 401
    fresh.cookies[settings.JWT_REFRESH_COOKIE] = refresh
    assert fresh.post("/api/auth/token/refresh/").status_code == 401
    assert APIClient().get(f"/api/users/{user.pk}/").status_code == 404

    # The email can be used to register a new account
    res = APIClient().post("/api/auth/register/", {
        "email": original_email, "password": "Tent-and-Stars-42",
        "display_name": "New me", "pdpa_consent": True,
    }, format="json")
    assert res.status_code == 201


@pytest.mark.django_db
def test_interest_tags_public(api_client):
    InterestTag.objects.create(tag_name="hiking")
    res = api_client.get("/api/interest-tags/")
    assert res.status_code == 200 and res.json()[0]["tag_name"] == "hiking"


@pytest.mark.django_db
def test_edit_own_profile_when_profile_id_differs_from_user_id(login, user, api_client):
    """Regression: permission must compare the profile's user_id, not profile.pk."""
    from accounts.models import Profile

    user.profile.delete()
    Profile.objects.create(pk=user.pk + 1000, user=user, display_name="shifted")
    login(user)
    res = api_client.patch(f"/api/users/{user.pk}/", {"city": "Krabi"}, format="json")
    assert res.status_code == 200 and res.json()["city"] == "Krabi"
