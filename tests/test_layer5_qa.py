"""
Layer 5 — Q&A forum ("Ask about this campsite"). UATs for the content-management
problem set:

UAT-QA-1  A member asks a question on a campsite; another member answers; both visible
UAT-QA-2  The asker accepts an answer → question 'answered'; only the asker can accept
UAT-QA-3  A moderator hides a reported answer → gone from public view, kept in admin
"""
import pytest
from rest_framework.test import APIClient

from accounts.models import User
from locations.models import Location, LocationStatus
from notifications.models import Notification
from qa.models import Answer, Question


@pytest.fixture
def asker(make_user, login):
    u = make_user()
    return u, login(u, client=APIClient())


@pytest.fixture
def helper(make_user, login):
    u = make_user()
    return u, login(u, client=APIClient())


@pytest.fixture
def moderator(login):
    u = User.objects.create_superuser(email="mod@example.com", password="Adm1n-Pass!")
    return u, login(u, password="Adm1n-Pass!", client=APIClient())


def _ask(client, location, title="Is there drinking water?"):
    res = client.post("/api/questions/", {"location_id": location.pk, "title": title,
                                          "body": "Planning a trip in December."}, format="json")
    assert res.status_code == 201, res.content
    return res.json()["id"]


def _answer(client, qid, body="Yes, taps near the restrooms."):
    res = client.post(f"/api/questions/{qid}/answers/", {"body": body}, format="json")
    assert res.status_code == 201, res.content
    return res.json()["id"]


# ---------------- UAT-QA-1 -------------------------------------------------------------

@pytest.mark.django_db
def test_uat_qa_1_ask_and_answer_visible_on_campsite(asker, helper, location, api_client):
    asker_user, ac = asker
    _, hc = helper
    qid = _ask(ac, location)
    _answer(hc, qid)

    listed = api_client.get(f"/api/questions/?location={location.pk}").json()["results"]
    assert [(q["id"], q["answer_count"], q["status"]) for q in listed] == [(qid, 1, "open")]
    detail = api_client.get(f"/api/questions/{qid}/").json()
    assert detail["campsite"]["id"] == location.pk
    assert detail["answers"][0]["body"] == "Yes, taps near the restrooms."
    assert Notification.objects.filter(recipient=asker_user, type="answer_posted").exists()


@pytest.mark.django_db
def test_general_question_without_campsite(asker, api_client):
    _, ac = asker
    res = ac.post("/api/questions/", {"title": "Best beginner tent?", "body": "Budget 2000 THB"},
                  format="json")
    assert res.status_code == 201 and res.json()["campsite"] is None


@pytest.mark.django_db
def test_cannot_ask_about_unpublished_campsite(asker):
    _, ac = asker
    pending = Location.objects.create(name="Hidden", province="Tak", latitude=16.8,
                                      longitude=98.9, status=LocationStatus.PENDING_REVIEW)
    res = ac.post("/api/questions/", {"location_id": pending.pk, "title": "x", "body": "y"},
                  format="json")
    assert res.status_code == 400 and "location_id" in res.json()


@pytest.mark.django_db
def test_anonymous_can_read_but_not_post(api_client, asker, location):
    _, ac = asker
    qid = _ask(ac, location)
    assert api_client.get(f"/api/questions/{qid}/").status_code == 200
    assert api_client.post("/api/questions/", {"title": "x", "body": "y"},
                           format="json").status_code == 401
    assert api_client.post(f"/api/questions/{qid}/answers/", {"body": "x"},
                           format="json").status_code == 401


@pytest.mark.django_db
def test_unanswered_filter_and_search(asker, helper, location, api_client):
    _, ac = asker
    _, hc = helper
    q1 = _ask(ac, location, "Is there drinking water?")
    q2 = _ask(ac, location, "Are fires allowed?")
    _answer(hc, q1)
    unanswered = api_client.get("/api/questions/?unanswered=true").json()["results"]
    assert [q["id"] for q in unanswered] == [q2]
    found = api_client.get("/api/questions/?search=fires").json()["results"]
    assert [q["id"] for q in found] == [q2]


# ---------------- UAT-QA-2 -------------------------------------------------------------

@pytest.mark.django_db
def test_uat_qa_2_asker_accepts_answer(asker, helper, location):
    _, ac = asker
    _, hc = helper
    qid = _ask(ac, location)
    aid = _answer(hc, qid)

    assert hc.post(f"/api/questions/{qid}/accept/", {"answer_id": aid},
                   format="json").status_code == 403  # not the asker
    res = ac.post(f"/api/questions/{qid}/accept/", {"answer_id": aid}, format="json")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "answered" and body["accepted_answer"] == aid
    assert body["answers"][0]["is_accepted"] is True


@pytest.mark.django_db
def test_accepted_answer_can_be_changed_but_must_belong_to_question(asker, helper, location):
    _, ac = asker
    _, hc = helper
    q1, q2 = _ask(ac, location), _ask(ac, location, "Mobile signal?")
    a1, a2 = _answer(hc, q1), _answer(hc, q1, "Ask the ranger.")
    foreign = _answer(hc, q2)
    ac.post(f"/api/questions/{q1}/accept/", {"answer_id": a1}, format="json")
    assert ac.post(f"/api/questions/{q1}/accept/", {"answer_id": a2},
                   format="json").json()["accepted_answer"] == a2
    assert ac.post(f"/api/questions/{q1}/accept/", {"answer_id": foreign},
                   format="json").status_code == 400


@pytest.mark.django_db
def test_closed_question_takes_no_answers(asker, helper, location):
    _, ac = asker
    _, hc = helper
    qid = _ask(ac, location)
    assert hc.post(f"/api/questions/{qid}/close/").status_code == 403
    assert ac.post(f"/api/questions/{qid}/close/").json()["status"] == "closed"
    res = hc.post(f"/api/questions/{qid}/answers/", {"body": "late"}, format="json")
    assert res.status_code == 400 and "closed" in str(res.json())


# ---------------- UAT-QA-3 -------------------------------------------------------------

@pytest.mark.django_db
def test_uat_qa_3_moderator_hides_answer(asker, helper, moderator, location, api_client):
    _, ac = asker
    _, hc = helper
    _, mc = moderator
    qid = _ask(ac, location)
    aid = _answer(hc, qid, "Buy my camping gear at spam.example!")
    ac.post(f"/api/questions/{qid}/accept/", {"answer_id": aid}, format="json")

    assert hc.post(f"/api/answers/{aid}/hide/").status_code == 403
    assert mc.post(f"/api/answers/{aid}/hide/").json()["status"] == "hidden"

    public = api_client.get(f"/api/questions/{qid}/").json()
    assert public["answers"] == [] and public["answer_count"] == 0
    assert public["status"] == "open" and public["accepted_answer"] is None  # re-opened
    staff_view = mc.get(f"/api/questions/{qid}/").json()
    assert [a["status"] for a in staff_view["answers"]] == ["hidden"]  # kept for moderators
    assert Answer.objects.filter(pk=aid).exists()


@pytest.mark.django_db
def test_moderator_hides_and_restores_question(asker, moderator, location, api_client):
    _, ac = asker
    _, mc = moderator
    qid = _ask(ac, location)
    mc.post(f"/api/questions/{qid}/hide/")
    assert api_client.get(f"/api/questions/{qid}/").status_code == 404
    assert api_client.get("/api/questions/").json()["count"] == 0
    mc.post(f"/api/questions/{qid}/restore/")
    assert api_client.get(f"/api/questions/{qid}/").json()["status"] == "open"


# ---------------- Editing (versioning: current + edited marker) ----------------------

@pytest.mark.django_db
def test_author_edits_question_and_answer(asker, helper, location):
    asker_user, ac = asker
    _, hc = helper
    qid = _ask(ac, location)
    res = ac.patch(f"/api/questions/{qid}/", {"title": "Is the tap water drinkable?"},
                   format="json")
    assert res.status_code == 200
    assert res.json()["edited_at"] is not None
    assert res.json()["last_edited_by"]["id"] == asker_user.pk

    assert hc.patch(f"/api/questions/{qid}/", {"title": "hijack"}, format="json").status_code == 403

    aid = _answer(hc, qid)
    res = hc.patch(f"/api/answers/{aid}/", {"body": "Yes, but boil it first."}, format="json")
    assert res.status_code == 200 and res.json()["edited_at"] is not None
    assert ac.patch(f"/api/answers/{aid}/", {"body": "x"}, format="json").status_code == 403


@pytest.mark.django_db
def test_admin_question_actions(asker, location, client):
    _, ac = asker
    qid = _ask(ac, location)
    admin = User.objects.create_superuser(email="adm@example.com", password="Adm1n-Pass!")
    client.force_login(admin)
    assert client.get(f"/admin/qa/question/{qid}/change/").status_code == 200
    client.post("/admin/qa/question/", {"action": "hide_selected", "_selected_action": [str(qid)]})
    assert Question.objects.get(pk=qid).status == "hidden"
