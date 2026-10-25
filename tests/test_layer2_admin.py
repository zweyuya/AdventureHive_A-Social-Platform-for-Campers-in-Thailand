"""The Django admin is the moderator UI: approve / reject actions and versioned edits."""
import pytest

from accounts.models import User
from locations.models import Location, LocationRevision, LocationStatus, RevisionStatus
from locations.services import propose_edit


@pytest.fixture
def admin_client(client, db):
    admin = User.objects.create_superuser(email="mod@example.com", password="Adm1n-Pass!")
    client.force_login(admin)
    client.admin = admin
    return client


@pytest.fixture
def pending(make_user):
    return Location.objects.create(
        name="Mon Jam Campsite", province="Chiang Mai", latitude=18.93, longitude=98.82,
        status=LocationStatus.PENDING_REVIEW, created_by=make_user(),
    )


def _action(client, url, action, ids, **extra):
    return client.post(url, {"action": action, "_selected_action": [str(i) for i in ids], **extra})


@pytest.mark.django_db
def test_admin_pages_load(admin_client, pending):
    assert admin_client.get("/admin/locations/location/?status__exact=pending_review").status_code == 200
    assert admin_client.get(f"/admin/locations/location/{pending.pk}/change/").status_code == 200
    assert admin_client.get("/admin/locations/locationrevision/").status_code == 200


@pytest.mark.django_db
def test_admin_approve_action_publishes(admin_client, pending):
    res = _action(admin_client, "/admin/locations/location/", "approve_selected", [pending.pk])
    assert res.status_code == 302
    pending.refresh_from_db()
    assert pending.status == LocationStatus.PUBLISHED and pending.current_version == 1


@pytest.mark.django_db
def test_admin_reject_action_asks_for_reason_then_rejects(admin_client, pending):
    url = "/admin/locations/location/"
    page = _action(admin_client, url, "reject_selected", [pending.pk])
    assert page.status_code == 200 and b"Reason" in page.content  # intermediate form

    blank = _action(admin_client, url, "reject_selected", [pending.pk], apply="1", note="")
    assert blank.status_code == 200  # form re-shown, nothing rejected
    pending.refresh_from_db()
    assert pending.status == LocationStatus.PENDING_REVIEW

    done = _action(admin_client, url, "reject_selected", [pending.pk], apply="1",
                   note="Duplicate of an existing campsite.")
    assert done.status_code == 302
    pending.refresh_from_db()
    assert pending.status == LocationStatus.REJECTED
    assert pending.moderation_note == "Duplicate of an existing campsite."


@pytest.mark.django_db
def test_admin_edit_of_published_campsite_creates_new_version(admin_client, pending):
    from locations.services import approve_submission
    approve_submission(pending, admin_client.admin)
    url = f"/admin/locations/location/{pending.pk}/change/"
    form = admin_client.get(url).context["adminform"].form
    data = {k: v for k, v in form.initial.items() if v is not None and k != "cover_image"}
    data.update({
        "rules": "Quiet hours 22:00–06:00",
        "authority": "", "permit_info_verified_at_0": "", "permit_info_verified_at_1": "",
        "revisions-TOTAL_FORMS": "1", "revisions-INITIAL_FORMS": "1",
        "revisions-MIN_NUM_FORMS": "0", "revisions-MAX_NUM_FORMS": "1000",
        "revisions-0-id": str(pending.revisions.get().pk), "revisions-0-location": str(pending.pk),
    })
    res = admin_client.post(url, data)
    assert res.status_code == 302, res.context["adminform"].form.errors if res.context else res
    pending.refresh_from_db()
    assert pending.rules == "Quiet hours 22:00–06:00" and pending.current_version == 2
    v2 = pending.revisions.get(version_no=2)
    assert v2.edited_by == admin_client.admin and "rules" in v2.edit_summary


@pytest.mark.django_db
def test_admin_approves_suggested_edit(admin_client, pending, make_user):
    from locations.services import approve_submission
    approve_submission(pending, admin_client.admin)
    rev = propose_edit(pending, make_user(), {"has_water_source": True}, "There is a tap")
    res = _action(admin_client, "/admin/locations/locationrevision/", "approve_selected", [rev.pk])
    assert res.status_code == 302
    rev.refresh_from_db()
    assert rev.status == RevisionStatus.APPROVED and rev.version_no == 2
    assert Location.objects.get(pk=pending.pk).has_water_source is True
    assert LocationRevision.objects.filter(location=pending, status="approved").count() == 2
