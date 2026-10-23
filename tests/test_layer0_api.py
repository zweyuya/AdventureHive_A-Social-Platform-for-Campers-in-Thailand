import pytest


@pytest.mark.django_db
def test_health(api_client):
    assert api_client.get("/api/health/").json() == {"status": "ok"}


@pytest.mark.django_db
def test_swagger_and_schema_load(api_client):
    assert api_client.get("/api/docs/").status_code == 200
    assert api_client.get("/api/schema/").status_code == 200


@pytest.mark.django_db
def test_admin_login_page_loads(client):
    assert client.get("/admin/login/").status_code == 200
