"""
Final-phase review credibility: admins are told about flagged trips and escalated
reviews, a stricter flag rule, no-show appeals, and a check-in code that the API
only gives out while check-in is open.
"""
from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.test import Client
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import UserStatus
from accounts.services import delete_account
from notifications.models import Notification, NotificationType as N
from reviews import services as review_services
from reviews.models import ReportReason, ReportStatus
from trips import services
from trips.models import AppealStatus, AttendanceAppeal, FlagStatus
from trips.models import ParticipantStatus as PS
from trips.models import Trip, TripParticipant, VerificationMethod


def _finish(trip, ended_ago=timedelta(hours=1)):
    now = timezone.now()
    Trip.objects.filter(pk=trip.pk).update(start_datetime=now - ended_ago - timedelta(days=1),
                                           end_datetime=now - ended_ago)
    services.complete_finished_trips()
    trip.refresh_from_db()
    return trip


def _finished_trip(make_trip, make_user, people=1, **kwargs):
    trip = make_trip(capacity=max(people, 1), **kwargs)
    users = [make_user() for _ in range(people)]
    for u in users:
        services.rsvp(Trip.objects.get(pk=trip.pk), u)
    return _finish(trip), users


def _mark(trip, statuses):
    """statuses = {user: 'attended' | 'no_show'}; attended without a check-in gets a reason."""
    services.mark_attendance(trip, trip.organizer, [
        {"user_id": u.pk, "status": st, "reason": "Phone battery died"} for u, st in statuses.items()])


def _row(trip, user):
    return TripParticipant.objects.get(trip=trip, user=user)


def _notes(user, type=None):
    qs = Notification.objects.filter(recipient=user)
    return qs.filter(type=type) if type else qs


@pytest.fixture
def staff(make_user):
    return make_user(is_staff=True, is_superuser=True)


@pytest.fixture
def no_show(make_trip, make_user):
    """A completed trip with one person marked as a no-show."""
    trip, (person,) = _finished_trip(make_trip, make_user)
    _mark(trip, {person: PS.NO_SHOW})
    return trip, person


def _admin(user):
    client = Client()
    client.force_login(user)
    return client


# ---- stricter flag rule ------------------------------------------------------------
@pytest.mark.django_db
def test_three_without_check_in_flags_even_when_they_are_not_most(make_trip, make_user):
    trip, users = _finished_trip(make_trip, make_user, people=7)
    for u in users[3:]:
        services.check_in(trip, u, services.checkin_code(trip))
    _mark(trip, {u: PS.ATTENDED for u in users})  # 3 of 7 = 43%
    trip.refresh_from_db()
    assert trip.flag_status == FlagStatus.NEEDS_REVIEW and "3 of 7" in trip.flag_note


@pytest.mark.django_db
def test_two_of_five_without_check_in_is_not_flagged(make_trip, make_user):
    trip, users = _finished_trip(make_trip, make_user, people=5)
    for u in users[2:]:
        services.check_in(trip, u, services.checkin_code(trip))
    _mark(trip, {u: PS.ATTENDED for u in users})
    trip.refresh_from_db()
    assert trip.flag_status == FlagStatus.NONE


@pytest.mark.django_db
def test_more_than_half_still_flags_a_small_trip(make_trip, make_user):
    trip, users = _finished_trip(make_trip, make_user, people=1)
    _mark(trip, {users[0]: PS.ATTENDED})
    trip.refresh_from_db()
    assert trip.flag_status == FlagStatus.NEEDS_REVIEW


# ---- admins are told about flagged trips -------------------------------------------
@pytest.mark.django_db
def test_flagging_notifies_active_admins_once(make_trip, make_user, staff):
    suspended = make_user(is_staff=True, status=UserStatus.SUSPENDED)
    member = make_user()
    trip, users = _finished_trip(make_trip, make_user, people=1)
    _mark(trip, {users[0]: PS.ATTENDED})
    _mark(trip, {users[0]: PS.ATTENDED})  # saved again: already flagged, no second notice
    assert _notes(staff, N.TRIP_FLAGGED).count() == 1
    assert not _notes(suspended, N.TRIP_FLAGGED).exists()
    assert not _notes(member, N.TRIP_FLAGGED).exists()


@pytest.mark.django_db
def test_an_admin_who_organised_the_trip_is_not_the_one_told(make_trip, make_user, staff):
    other = make_user(is_staff=True)
    trip, users = _finished_trip(make_trip, make_user, organizer=staff)
    _mark(trip, {users[0]: PS.ATTENDED})
    assert not _notes(staff, N.TRIP_FLAGGED).exists()
    assert _notes(other, N.TRIP_FLAGGED).exists()


@pytest.mark.django_db
def test_a_trip_without_a_flag_tells_nobody(make_trip, make_user, staff):
    trip, users = _finished_trip(make_trip, make_user)
    services.check_in(trip, users[0], services.checkin_code(trip))
    _mark(trip, {users[0]: PS.ATTENDED})
    assert not _notes(staff, N.TRIP_FLAGGED).exists()


@pytest.mark.django_db
def test_admin_notification_links_to_the_django_admin(make_trip, make_user, staff, login):
    trip, users = _finished_trip(make_trip, make_user)
    _mark(trip, {users[0]: PS.ATTENDED})
    note = login(staff).get("/api/notifications/").json()["results"][0]
    assert note["link"] == f"/admin/trips/trip/{trip.pk}/change/"
    assert trip.title in note["message"]


# ---- reviews with 3 or more open reports -------------------------------------------
@pytest.fixture
def review(make_trip, make_user):
    trip, (author,) = _finished_trip(make_trip, make_user)
    services.check_in(trip, author, services.checkin_code(trip))
    _mark(trip, {author: PS.ATTENDED})
    return review_services.create_review(author, trip, 5, "Lovely")


def _report(review, user):
    return review_services.report_review(review, user, ReportReason.FAKE)


@pytest.mark.django_db
def test_third_open_report_notifies_admins_once(review, make_user, staff):
    _report(review, make_user())
    _report(review, make_user())
    assert not _notes(staff, N.REVIEW_ESCALATED).exists()
    _report(review, make_user())
    assert _notes(staff, N.REVIEW_ESCALATED).count() == 1
    _report(review, make_user())  # the fourth does not notify again
    assert _notes(staff, N.REVIEW_ESCALATED).count() == 1


@pytest.mark.django_db
def test_only_open_reports_count_towards_escalation(review, make_user, staff):
    _report(review, make_user())
    _report(review, make_user())
    review_services.resolve_reports(review, staff, hide=False)  # dismissed
    _report(review, make_user())
    assert not _notes(staff, N.REVIEW_ESCALATED).exists()


@pytest.mark.django_db
def test_escalated_note_names_the_campsite(review, make_user, staff, login):
    for _ in range(3):
        _report(review, make_user())
    note = login(staff).get("/api/notifications/").json()["results"][0]
    assert review.location.name in note["message"]
    assert note["link"] == f"/admin/reviews/review/{review.pk}/change/"


@pytest.mark.django_db
def test_escalated_reports_go_to_the_top_of_the_queue(make_trip, make_user, staff):
    trip, users = _finished_trip(make_trip, make_user, people=2)
    for u in users:
        services.check_in(trip, u, services.checkin_code(trip))
    _mark(trip, {u: PS.ATTENDED for u in users})
    busy = review_services.create_review(users[0], trip, 5, "Reported a lot")
    quiet = review_services.create_review(users[1], trip, 5, "Reported once")
    for _ in range(3):
        _report(busy, make_user())
    _report(quiet, make_user())  # the newest report, but not escalated

    res = _admin(staff).get("/admin/reviews/reviewreport/")
    rows = list(res.context["cl"].result_list)
    assert [r.review_id for r in rows] == [busy.pk, busy.pk, busy.pk, quiet.pk]
    assert rows[0]._escalated == 1 and rows[3]._escalated == 0

    res = _admin(staff).get("/admin/reviews/review/")
    assert res.context["cl"].result_list[0].pk == busy.pk


@pytest.mark.django_db
def test_closed_reports_are_not_escalated_in_the_queue(review, make_user, staff):
    for _ in range(3):
        _report(review, make_user())
    review_services.resolve_reports(review, staff, hide=False)
    rows = _admin(staff).get("/admin/reviews/reviewreport/").context["cl"].result_list
    assert all(r._escalated == 0 and r.status == ReportStatus.DISMISSED for r in rows)


# ---- no-show appeal: the participant -----------------------------------------------
def _appeal_url(trip):
    return f"/api/trips/{trip.pk}/attendance-appeal/"


@pytest.mark.django_db
def test_no_show_can_appeal_and_people_are_told(no_show, login, staff):
    trip, person = no_show
    client = login(person)
    assert client.get(f"/api/trips/{trip.pk}/").json()["appeal"]["can_appeal"] is True
    res = client.post(_appeal_url(trip), {"reason": " I was there, no signal. "}, format="json")
    assert res.status_code == 201 and res.json()["status"] == "open"
    assert AttendanceAppeal.objects.get().reason == "I was there, no signal."
    assert _notes(staff, N.APPEAL_SUBMITTED).exists()
    assert _notes(trip.organizer, N.APPEAL_ON_MY_TRIP).exists()
    appeal = client.get(f"/api/trips/{trip.pk}/").json()["appeal"]
    assert appeal["can_appeal"] is False and appeal["status"] == "open"


@pytest.mark.django_db
def test_appeal_needs_a_reason_and_a_login(no_show, login, api_client):
    trip, person = no_show
    assert api_client.post(_appeal_url(trip), {"reason": "x"}, format="json").status_code == 401
    assert login(person).post(_appeal_url(trip), {"reason": "   "}, format="json").status_code == 400
    assert not AttendanceAppeal.objects.exists()


@pytest.mark.django_db
def test_only_the_no_show_can_appeal(make_trip, make_user, login):
    trip, (came, stayed_away) = _finished_trip(make_trip, make_user, people=2)
    services.check_in(trip, came, services.checkin_code(trip))
    _mark(trip, {came: PS.ATTENDED, stayed_away: PS.NO_SHOW})
    for user in (came, make_user(), trip.organizer):
        res = login(user, client=APIClient()).post(_appeal_url(trip), {"reason": "x"}, format="json")
        assert res.status_code == 400, user
    assert login(came, client=APIClient()).get(f"/api/trips/{trip.pk}/").json()["appeal"] is None


@pytest.mark.django_db
def test_one_appeal_per_person(no_show):
    trip, person = no_show
    services.submit_appeal(trip, person, "First")
    with pytest.raises(services.TripError, match="already appealed"):
        services.submit_appeal(trip, person, "Second")


@pytest.mark.django_db
def test_appeals_close_after_two_weeks(make_trip, make_user):
    trip, (person,) = _finished_trip(make_trip, make_user)
    _mark(trip, {person: PS.NO_SHOW})
    Trip.objects.filter(pk=trip.pk).update(end_datetime=timezone.now() - timedelta(days=15),
                                           start_datetime=timezone.now() - timedelta(days=16))
    trip.refresh_from_db()
    with pytest.raises(services.TripError, match="14 days"):
        services.submit_appeal(trip, person, "Too late")


# ---- no-show appeal: the admin decides ---------------------------------------------
@pytest.mark.django_db
def test_approved_appeal_lets_them_review_with_the_right_badge(no_show, staff, login):
    trip, person = no_show
    appeal = services.submit_appeal(trip, person, "I was there")
    services.decide_appeal(appeal, staff, approve=True)

    row = _row(trip, person)
    assert row.status == PS.ATTENDED and row.verification_method == VerificationMethod.ADMIN_APPEAL
    assert row.attendance_marked_by == staff
    assert _notes(person, N.APPEAL_APPROVED).exists()

    review = review_services.create_review(person, trip, 4, "I was there")  # the DB trigger agrees
    res = login(person).get(f"/api/campsites/{trip.location_id}/reviews/").json()["results"][0]
    assert res["id"] == review.pk and res["verification"] == "admin_appeal"


@pytest.mark.django_db
def test_approved_appeal_with_a_real_check_in_keeps_the_check_in_badge(make_trip, make_user, staff):
    trip, (person,) = _finished_trip(make_trip, make_user)
    services.check_in(trip, person, services.checkin_code(trip))
    _mark(trip, {person: PS.NO_SHOW})
    services.decide_appeal(services.submit_appeal(trip, person, "I checked in"), staff, approve=True)
    assert _row(trip, person).verification_method == VerificationMethod.CHECK_IN


@pytest.mark.django_db
def test_rejected_appeal_needs_a_note_and_changes_nothing(no_show, staff, login):
    trip, person = no_show
    appeal = services.submit_appeal(trip, person, "I was there")
    with pytest.raises(services.TripError, match="Say why"):
        services.decide_appeal(appeal, staff, approve=False, note="  ")
    services.decide_appeal(appeal, staff, approve=False, note="Nobody else saw you")

    assert _row(trip, person).status == PS.NO_SHOW
    assert _notes(person, N.APPEAL_REJECTED).exists()
    with pytest.raises(Exception, match="(?i)attended"):
        review_services.create_review(person, trip, 1, "Angry")
    shown = login(person).get(f"/api/trips/{trip.pk}/").json()["appeal"]
    assert shown["status"] == "rejected" and shown["decision_note"] == "Nobody else saw you"
    assert shown["can_appeal"] is False


@pytest.mark.django_db
def test_an_appeal_is_decided_only_once(no_show, staff):
    trip, person = no_show
    appeal = services.submit_appeal(trip, person, "I was there")
    services.decide_appeal(appeal, staff, approve=False, note="No")
    with pytest.raises(services.TripError, match="already been decided"):
        services.decide_appeal(appeal, staff, approve=True)
    assert _row(trip, person).status == PS.NO_SHOW


@pytest.mark.django_db
def test_an_admin_involved_in_the_trip_cannot_decide(make_trip, make_user, staff):
    trip, (person,) = _finished_trip(make_trip, make_user, organizer=staff)
    _mark(trip, {person: PS.NO_SHOW})
    appeal = services.submit_appeal(trip, person, "I was there")
    with pytest.raises(services.TripError, match="another admin"):
        services.decide_appeal(appeal, staff, approve=False, note="No")


@pytest.mark.django_db
def test_the_organizer_cannot_overrule_an_approved_appeal(no_show, staff, login):
    trip, person = no_show
    services.decide_appeal(services.submit_appeal(trip, person, "Here"), staff, approve=True)
    with pytest.raises(services.TripError, match="stay attended"):
        services.mark_attendance(trip, trip.organizer, [{"user_id": person.pk, "status": "no_show"}])
    # Saving the form again, with no reason for this person, leaves their record alone.
    services.mark_attendance(trip, trip.organizer, [{"user_id": person.pk, "status": "attended"}])
    assert _row(trip, person).verification_method == VerificationMethod.ADMIN_APPEAL


@pytest.mark.django_db
def test_the_organizer_correcting_a_no_show_closes_the_appeal(no_show, staff):
    trip, person = no_show
    appeal = services.submit_appeal(trip, person, "I was there")
    _mark(trip, {person: PS.ATTENDED})
    appeal.refresh_from_db()
    assert appeal.status == AppealStatus.APPROVED and appeal.decided_by == trip.organizer
    with pytest.raises(services.TripError, match="already been decided"):
        services.decide_appeal(appeal, staff, approve=False, note="No")


@pytest.mark.django_db
def test_database_refuses_a_rejection_without_a_note(no_show):
    trip, person = no_show
    appeal = services.submit_appeal(trip, person, "I was there")
    with pytest.raises(IntegrityError, match="rejection_has_note"), transaction.atomic():
        AttendanceAppeal.objects.filter(pk=appeal.pk).update(status=AppealStatus.REJECTED,
                                                             decided_at=timezone.now())


@pytest.mark.django_db
def test_database_refuses_an_appeal_badge_without_a_reason(no_show):
    trip, person = no_show
    with pytest.raises(IntegrityError, match="verification_evidence"), transaction.atomic():
        TripParticipant.objects.filter(trip=trip, user=person).update(
            status=PS.ATTENDED, verification_method=VerificationMethod.ADMIN_APPEAL, override_reason="")


@pytest.mark.django_db
def test_deleting_the_account_removes_the_written_reason(no_show):
    trip, person = no_show
    services.submit_appeal(trip, person, "Private details about my health")
    delete_account(person)
    assert not AttendanceAppeal.objects.exists()


# ---- no-show appeal: the admin site ------------------------------------------------
@pytest.mark.django_db
def test_admin_approves_from_the_list(no_show, staff):
    trip, person = no_show
    appeal = services.submit_appeal(trip, person, "I was there")
    client = _admin(staff)
    assert client.get("/admin/trips/attendanceappeal/").status_code == 200
    assert client.get(f"/admin/trips/attendanceappeal/{appeal.pk}/change/").status_code == 200
    client.post("/admin/trips/attendanceappeal/", {"action": "approve_selected",
                                                   "_selected_action": [appeal.pk]})
    assert _row(trip, person).status == PS.ATTENDED


@pytest.mark.django_db
def test_admin_rejects_with_a_reason_from_the_list(no_show, staff):
    trip, person = no_show
    appeal = services.submit_appeal(trip, person, "I was there")
    client = _admin(staff)
    data = {"action": "reject_selected", "_selected_action": [appeal.pk]}
    assert b"note" in client.post("/admin/trips/attendanceappeal/", data).content
    appeal.refresh_from_db()
    assert appeal.status == AppealStatus.OPEN  # asked first, nothing changed
    client.post("/admin/trips/attendanceappeal/", {**data, "apply": "1", "note": "Nobody saw you"})
    appeal.refresh_from_db()
    assert appeal.status == AppealStatus.REJECTED and appeal.decision_note == "Nobody saw you"


@pytest.mark.django_db
def test_admin_cannot_add_or_delete_appeals(no_show, staff):
    trip, person = no_show
    appeal = services.submit_appeal(trip, person, "I was there")
    client = _admin(staff)
    assert client.get("/admin/trips/attendanceappeal/add/").status_code == 403
    assert client.get(f"/admin/trips/attendanceappeal/{appeal.pk}/delete/").status_code == 403


@pytest.mark.django_db
def test_open_appeals_come_first(make_trip, make_user, staff):
    first, (a,) = _finished_trip(make_trip, make_user)
    _mark(first, {a: PS.NO_SHOW})
    second, (b,) = _finished_trip(make_trip, make_user)
    _mark(second, {b: PS.NO_SHOW})
    waiting = services.submit_appeal(first, a, "Waiting")
    decided = services.submit_appeal(second, b, "Newer, but decided")
    services.decide_appeal(decided, staff, approve=False, note="No")
    rows = _admin(staff).get("/admin/trips/attendanceappeal/").context["cl"].result_list
    assert [r.pk for r in rows] == [waiting.pk, decided.pk]


# ---- the check-in code from the API ------------------------------------------------
def _code_response(trip, login):
    return login(trip.organizer).get(f"/api/trips/{trip.pk}/check-in-code/")


@pytest.mark.django_db
def test_code_is_not_given_before_check_in_opens(make_trip, login):
    trip = make_trip(days_from_now=3)
    res = _code_response(trip, login)
    assert res.status_code == 400 and "available from" in str(res.json())
    assert services.checkin_code(trip) not in str(res.content)


@pytest.mark.django_db
def test_code_is_given_while_check_in_is_open(make_trip, login):
    trip = make_trip()
    Trip.objects.filter(pk=trip.pk).update(start_datetime=timezone.now() + timedelta(hours=1),
                                           end_datetime=timezone.now() + timedelta(days=1))
    trip.refresh_from_db()
    res = _code_response(trip, login)
    assert res.status_code == 200 and res.json()["code"] == services.checkin_code(trip)


@pytest.mark.django_db
def test_code_is_not_given_after_check_in_closes(make_trip, login):
    trip = make_trip()
    Trip.objects.filter(pk=trip.pk).update(start_datetime=timezone.now() - timedelta(days=3),
                                           end_datetime=timezone.now() - timedelta(days=2))
    trip.refresh_from_db()
    res = _code_response(trip, login)
    assert res.status_code == 400 and services.checkin_code(trip) not in str(res.content)
