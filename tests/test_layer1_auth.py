"""Layer 1 — registration (PDPA), cookie JWT login, CSRF, refresh, logout."""
import pytest
from django.conf import settings
from rest_framework.test import APIClient

from accounts.models import InterestTag, User, UserStatus

ACCESS = settings.JWT_AUTH_COOKIE
REFRESH = settings.JWT_REFRESH_COOKIE


def _register_payload(**overrides):
    data = {
        "email": "Nok@Example.com",
        "password": "Tent-and-Stars-42",
        "display_name": "Nok",
        "camping_experience_level": "intermediate",
        "pdpa_consent": True,
    }
    data.update(overrides)
    return data


# ---------------- Registration ----------------------------------------------

@pytest.mark.django_db
def test_register_creates_user_profile_tags_and_records_consent(api_client):
    tags = [InterestTag.objects.create(tag_name=t) for t in ("hiking", "stargazing")]
    res = api_client.post("/api/auth/register/",
                          _register_payload(interest_tag_ids=[t.id for t in tags]), format="json")
    assert res.status_code == 201, res.content
    user = User.objects.get(email="nok@example.com")
    assert user.pdpa_consent_at is not None
    assert user.password.startswith("bcrypt_sha256$")
    assert user.profile.camping_experience_level == "intermediate"
    assert set(user.profile.interest_tags.values_list("tag_name", flat=True)) == {"hiking", "stargazing"}
    assert "password" not in res.json()


@pytest.mark.django_db
@pytest.mark.parametrize("consent", [False, None, "yes-ish"])
def test_register_without_pdpa_consent_is_rejected(api_client, consent):
    payload = _register_payload()
    if consent is None:
        payload.pop("pdpa_consent")
    else:
        payload["pdpa_consent"] = consent
    res = api_client.post("/api/auth/register/", payload, format="json")
    assert res.status_code == 400
    assert "pdpa_consent" in res.json()
    assert not User.objects.exists()


@pytest.mark.django_db
def test_register_duplicate_email_case_insensitive(api_client, make_user):
    make_user(email="nok@example.com")
    res = api_client.post("/api/auth/register/", _register_payload(), format="json")
    assert res.status_code == 400 and "email" in res.json()


@pytest.mark.django_db
@pytest.mark.parametrize("weak", ["short", "password123", "12345678"])
def test_register_weak_password_rejected(api_client, weak):
    res = api_client.post("/api/auth/register/", _register_payload(password=weak), format="json")
    assert res.status_code == 400 and "password" in res.json()


@pytest.mark.django_db
def test_register_unknown_interest_tag_rejected(api_client):
    res = api_client.post("/api/auth/register/", _register_payload(interest_tag_ids=[999]),
                          format="json")
    assert res.status_code == 400


# ---------------- Login / cookies -------------------------------------------

@pytest.mark.django_db
def test_login_sets_httponly_cookies_and_no_tokens_in_body(api_client, user):
    res = api_client.post("/api/auth/login/",
                          {"email": user.email, "password": "Camp1ng!Pass"}, format="json")
    assert res.status_code == 200
    body = res.json()
    assert "access" not in body and "refresh" not in body
    assert res.cookies[ACCESS]["httponly"] and res.cookies[REFRESH]["httponly"]
    assert res.cookies[ACCESS]["samesite"] == "Strict"
    assert res.cookies[REFRESH]["path"] == "/api/auth/"
    assert "csrftoken" in res.cookies  # for the double-submit check


@pytest.mark.django_db
def test_login_wrong_password(api_client, user):
    res = api_client.post("/api/auth/login/",
                          {"email": user.email, "password": "nope"}, format="json")
    assert res.status_code == 401 and ACCESS not in res.cookies


@pytest.mark.django_db
@pytest.mark.parametrize("status", [UserStatus.SUSPENDED, UserStatus.BANNED])
def test_suspended_or_banned_users_cannot_log_in(api_client, make_user, status):
    u = make_user(status=status)
    res = api_client.post("/api/auth/login/",
                          {"email": u.email, "password": "Camp1ng!Pass"}, format="json")
    assert res.status_code == 401


@pytest.mark.django_db
def test_cookie_authenticates_requests(login, user, api_client):
    assert api_client.get("/api/users/me/").status_code == 401  # not logged in
    login(user)
    res = api_client.get("/api/users/me/")
    assert res.status_code == 200 and res.json()["email"] == user.email


@pytest.mark.django_db
def test_token_stops_working_when_account_is_suspended(login, user, api_client):
    login(user)
    User.objects.filter(pk=user.pk).update(status=UserStatus.SUSPENDED)
    assert api_client.get("/api/users/me/").status_code == 401


# ---------------- CSRF -------------------------------------------------------

@pytest.mark.django_db
def test_csrf_required_for_unsafe_requests_with_cookie_auth(user):
    client = APIClient(enforce_csrf_checks=True)  # behave like a real browser
    res = client.post("/api/auth/login/",
                      {"email": user.email, "password": "Camp1ng!Pass"}, format="json")
    assert res.status_code == 200
    url = f"/api/users/{user.pk}/"

    # Cookie present but no X-CSRFToken header → forged cross-site request blocked
    blocked = client.patch(url, {"city": "Chiang Mai"}, format="json")
    assert blocked.status_code == 403 and "CSRF" in blocked.json()["detail"]

    # Same request with the token from the csrftoken cookie → allowed
    token = client.cookies["csrftoken"].value
    ok = client.patch(url, {"city": "Chiang Mai"}, format="json", HTTP_X_CSRFTOKEN=token)
    assert ok.status_code == 200 and ok.json()["city"] == "Chiang Mai"


@pytest.mark.django_db
def test_csrf_endpoint_sets_cookie(api_client):
    res = api_client.get("/api/auth/csrf/")
    assert res.status_code == 200 and "csrftoken" in res.cookies


# ---------------- Refresh / logout --------------------------------------------

@pytest.mark.django_db
def test_refresh_rotates_and_old_refresh_token_is_blacklisted(login, user, api_client):
    login(user)
    old_refresh = api_client.cookies[REFRESH].value
    res = api_client.post("/api/auth/token/refresh/")
    assert res.status_code == 200
    new_refresh = res.cookies[REFRESH].value
    assert new_refresh and new_refresh != old_refresh

    # Re-using the old refresh token (e.g. stolen) fails
    replay = APIClient()
    replay.cookies[REFRESH] = old_refresh
    assert replay.post("/api/auth/token/refresh/").status_code == 401


@pytest.mark.django_db
def test_refresh_without_cookie(api_client):
    assert api_client.post("/api/auth/token/refresh/").status_code == 401


@pytest.mark.django_db
def test_logout_clears_cookies_and_blacklists_refresh(login, user, api_client):
    login(user)
    refresh = api_client.cookies[REFRESH].value
    res = api_client.post("/api/auth/logout/")
    assert res.status_code == 200
    assert res.cookies[ACCESS].value == "" and res.cookies[REFRESH].value == ""

    replay = APIClient()
    replay.cookies[REFRESH] = refresh
    assert replay.post("/api/auth/token/refresh/").status_code == 401
