"""
Extras: Q&A "helpful" votes, the organizer dashboard, the post-trip recap reminder,
"Repeat this trip" (past attendees invited and may join first), and a link to the
conflicting trip in duplicate-trip errors.
"""
from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from notifications.models import Notification, NotificationType as N
from qa import services as qa
from qa.models import Answer, AnswerStatus, AnswerVote, Question
from social.models import Post
from trips import services
from trips.models import ParticipantStatus as PS
from trips.models import Trip, TripStatus


def _finished(make_trip, organizer, people, ended_ago=timedelta(hours=1), **extra):
    """A completed trip where everyone in `people` checked in and attended."""
    trip = make_trip(organizer=organizer, capacity=max(len(people), 1), **extra)
    for p in people:
        services.rsvp(Trip.objects.get(pk=trip.pk), p)
    now = timezone.now()
    Trip.objects.filter(pk=trip.pk).update(start_datetime=now - timedelta(hours=26),
                                           end_datetime=now - timedelta(hours=1))
    services.complete_finished_trips()
    trip.refresh_from_db()
    for p in people:
        services.check_in(trip, p, services.checkin_code(trip))
    if people:
        services.mark_attendance(trip, organizer, [{"user_id": p.pk, "status": "attended"} for p in people])
    Trip.objects.filter(pk=trip.pk).update(start_datetime=now - ended_ago - timedelta(hours=25),
                                           end_datetime=now - ended_ago)
    trip.refresh_from_db()
    return trip


def _notes(user, type):
    return Notification.objects.filter(recipient=user, type=type)


# ---- 1. Q&A helpful votes ----------------------------------------------------------
@pytest.fixture
def answered(db, make_user):
    asker, a1, a2 = make_user(), make_user(), make_user()
    q = Question.objects.create(author=asker, title="Water?", body="Is there water?")
    older = qa.post_answer(q, a1, "Yes, taps by the toilets.")
    newer = qa.post_answer(q, a2, "Bring your own.")
    return q, older, newer


def _answers(client, q):
    return client.get(f"/api/questions/{q.pk}/").json()["answers"]


@pytest.mark.django_db
def test_mark_an_answer_helpful_and_take_it_back(answered, make_user, login):
    q, older, _ = answered
    client = login(make_user())
    res = client.post(f"/api/answers/{older.pk}/vote/")
    assert res.status_code == 200 and res.json() == {"helpful_count": 1, "i_found_helpful": True}
    row = next(a for a in _answers(client, q) if a["id"] == older.pk)
    assert row["helpful_count"] == 1 and row["i_found_helpful"] is True
    assert client.post(f"/api/answers/{older.pk}/vote/").json()["helpful_count"] == 1  # still one
    assert client.delete(f"/api/answers/{older.pk}/vote/").json()["helpful_count"] == 0


@pytest.mark.django_db
def test_no_vote_on_your_own_answer_or_a_hidden_one_or_without_login(answered, login):
    q, older, newer = answered
    assert APIClient().post(f"/api/answers/{newer.pk}/vote/").status_code == 401
    assert login(older.author).post(f"/api/answers/{older.pk}/vote/").status_code == 400
    Answer.objects.filter(pk=newer.pk).update(status=AnswerStatus.HIDDEN)
    assert login(older.author, client=APIClient()).post(f"/api/answers/{newer.pk}/vote/").status_code == 400


@pytest.mark.django_db
def test_one_vote_per_person_in_the_database(answered, make_user):
    _, older, _ = answered
    voter = make_user()
    AnswerVote.objects.create(answer=older, user=voter)
    with pytest.raises(IntegrityError, match="answer_votes_once"), transaction.atomic():
        AnswerVote.objects.create(answer=older, user=voter)


@pytest.mark.django_db
def test_accepted_first_then_most_helpful(answered, make_user, api_client):
    q, older, newer = answered
    for _ in range(2):
        qa.vote_answer(newer, make_user(), helpful=True)
    assert [a["id"] for a in _answers(api_client, q)] == [newer.pk, older.pk]  # more helpful first
    qa.accept_answer(q, q.author, older)
    assert [a["id"] for a in _answers(api_client, q)] == [older.pk, newer.pk]  # accepted stays on top


# ---- 2. organizer dashboard ---------------------------------------------------------
@pytest.mark.django_db
def test_dashboard_lists_my_trips_and_what_needs_doing(make_trip, make_user, login):
    me = make_user()
    upcoming = make_trip(organizer=me, capacity=1)
    services.rsvp(upcoming, make_user())
    services.rsvp(Trip.objects.get(pk=upcoming.pk), make_user())  # waitlisted
    draft = make_trip(organizer=me, status=TripStatus.DRAFT)
    finished = make_trip(organizer=me)
    services.rsvp(finished, make_user())
    Trip.objects.filter(pk=finished.pk).update(start_datetime=timezone.now() - timedelta(days=2),
                                               end_datetime=timezone.now() - timedelta(days=1))
    services.complete_finished_trips()
    make_trip()  # someone else's trip

    rows = {r["id"]: r for r in login(me).get("/api/trips/organised/").json()}
    assert set(rows) == {upcoming.pk, draft.pk, finished.pk}
    assert rows[upcoming.pk]["waitlist_count"] == 1 and rows[upcoming.pk]["needs_attendance"] is False
    assert rows[finished.pk]["needs_attendance"] is True and rows[finished.pk]["attendance_due"]
    assert rows[draft.pk]["status"] == "draft"


@pytest.mark.django_db
def test_dashboard_needs_a_login(api_client):
    assert api_client.get("/api/trips/organised/").status_code == 401


# ---- 3. recap reminder --------------------------------------------------------------
@pytest.mark.django_db
def test_recap_reminder_two_days_after_once_and_not_to_people_who_posted(make_trip, make_user):
    organizer, a, b = make_user(), make_user(), make_user()
    trip = _finished(make_trip, organizer, [a, b], ended_ago=timedelta(days=1))
    assert services.send_recap_reminders() == 0          # too early
    Trip.objects.filter(pk=trip.pk).update(end_datetime=timezone.now() - timedelta(days=2, hours=1))
    Post.objects.create(user=b, trip=trip, content_text="Great weekend!")
    assert services.send_recap_reminders() == 2          # a and the organizer; b already posted
    assert _notes(a, N.RECAP_REMINDER).count() == 1 and not _notes(b, N.RECAP_REMINDER).exists()
    assert services.send_recap_reminders() == 0          # once per trip
    assert _notes(a, N.RECAP_REMINDER).count() == 1


@pytest.mark.django_db
def test_recap_reminder_waits_until_attendance_is_recorded(make_trip, make_user):
    """Otherwise it would fire before anyone counts as attended, and miss them for good."""
    organizer, a = make_user(), make_user()
    trip = make_trip(organizer=organizer)
    services.rsvp(trip, a)
    Trip.objects.filter(pk=trip.pk).update(start_datetime=timezone.now() - timedelta(days=4),
                                           end_datetime=timezone.now() - timedelta(days=3))
    services.complete_finished_trips()                   # a is still only 'confirmed'
    assert services.send_recap_reminders() == 0 and not _notes(organizer, N.RECAP_REMINDER).exists()
    services.mark_attendance(Trip.objects.get(pk=trip.pk), organizer,
                             [{"user_id": a.pk, "status": "attended", "reason": "Was there"}])
    assert services.send_recap_reminders() == 2          # now a and the organizer
    assert _notes(a, N.RECAP_REMINDER).exists()


@pytest.mark.django_db
def test_recap_reminder_still_goes_out_if_attendance_is_never_recorded(make_trip, make_user):
    organizer, a = make_user(), make_user()
    trip = make_trip(organizer=organizer)
    services.rsvp(trip, a)
    Trip.objects.filter(pk=trip.pk).update(start_datetime=timezone.now() - timedelta(days=9),
                                           end_datetime=timezone.now() - timedelta(days=8))
    services.complete_finished_trips()                   # this job also sends the reminders
    assert _notes(organizer, N.RECAP_REMINDER).count() == 1  # only the organizer: nobody attended
    assert not _notes(a, N.RECAP_REMINDER).exists()


@pytest.mark.django_db
def test_no_recap_reminder_for_old_trips_or_no_shows(make_trip, make_user):
    organizer, came, stayed_home = make_user(), make_user(), make_user()
    _finished(make_trip, organizer, [came], ended_ago=timedelta(days=3))  # stayed_home never joined
    old = _finished(make_trip, organizer, [came], ended_ago=timedelta(days=20))
    services.send_recap_reminders()
    assert _notes(came, N.RECAP_REMINDER).count() == 1   # only the recent trip
    assert not _notes(stayed_home, N.RECAP_REMINDER).exists()
    old.refresh_from_db()
    assert old.recap_reminder_sent_at is None


@pytest.mark.django_db
def test_complete_trips_command_sends_recap_reminders(make_trip, make_user):
    from django.core.management import call_command
    from io import StringIO
    organizer, a = make_user(), make_user()
    _finished(make_trip, organizer, [a], ended_ago=timedelta(days=3))
    out = StringIO()
    call_command("complete_trips", stdout=out)
    assert "recap reminder" in out.getvalue() and _notes(a, N.RECAP_REMINDER).exists()


# ---- 4. repeat this trip ------------------------------------------------------------
@pytest.fixture
def repeated(make_trip, make_user):
    organizer, came, other = make_user(), make_user(), make_user()
    first = _finished(make_trip, organizer, [came])
    second = make_trip(organizer=organizer, status=TripStatus.DRAFT, repeat_of=first)
    Trip.objects.filter(pk=second.pk).update(title=first.title)  # same title is allowed again
    services.publish(second)
    second.refresh_from_db()
    return organizer, came, other, first, second


@pytest.mark.django_db
def test_publishing_a_repeat_invites_past_attendees(repeated):
    organizer, came, other, first, second = repeated
    assert second.priority_until > timezone.now() + timedelta(hours=47)
    assert _notes(came, N.TRIP_REPEATED).count() == 1
    assert not _notes(other, N.TRIP_REPEATED).exists() and not _notes(organizer, N.TRIP_REPEATED).exists()


@pytest.mark.django_db
def test_past_attendees_join_first_others_wait(repeated, login):
    organizer, came, other, first, second = repeated
    with pytest.raises(services.TripError, match="can join first"):
        services.rsvp(second, other)
    assert services.rsvp(second, came).status == PS.CONFIRMED
    priority = login(other).get(f"/api/trips/{second.pk}/").json()["priority"]
    assert priority["i_am_invited"] is False and priority["repeat_of"]["id"] == first.pk
    assert login(came, client=APIClient()).get(f"/api/trips/{second.pk}/").json()["priority"]["i_am_invited"] is True


@pytest.mark.django_db
def test_everyone_can_join_after_the_priority_window(repeated):
    organizer, came, other, first, second = repeated
    Trip.objects.filter(pk=second.pk).update(priority_until=timezone.now() - timedelta(minutes=1))
    assert services.rsvp(Trip.objects.get(pk=second.pk), other).status == PS.CONFIRMED


@pytest.mark.django_db
def test_repeat_through_the_api_only_for_my_own_completed_trip(make_trip, make_user, login):
    organizer, came = make_user(), make_user()
    first = _finished(make_trip, organizer, [came])
    start = timezone.now() + timedelta(days=30)
    body = {"location_id": first.location_id, "title": first.title, "participant_capacity": 4,
            "start_datetime": start.isoformat(), "end_datetime": (start + timedelta(days=1)).isoformat(),
            "repeat_of_id": first.pk}
    created = login(organizer).post("/api/trips/", body, format="json")
    assert created.status_code == 201  # same title is fine: the first trip is completed
    assert Trip.objects.get(pk=created.json()["id"]).repeat_of_id == first.pk

    stranger = login(make_user(), client=APIClient())
    res = stranger.post("/api/trips/", {**body, "title": "Mine"}, format="json")
    assert res.status_code == 400 and "repeat_of_id" in res.json()
    upcoming = make_trip(organizer=organizer, days_from_now=60)
    res = login(organizer, client=APIClient()).post(
        "/api/trips/", {**body, "title": "Again", "repeat_of_id": upcoming.pk}, format="json")
    assert res.status_code == 400 and "repeat_of_id" in res.json()


@pytest.mark.django_db
def test_a_normal_trip_has_no_priority_window(make_trip, make_user, login):
    trip = make_trip(status=TripStatus.DRAFT)
    services.publish(trip)
    trip.refresh_from_db()
    assert trip.priority_until is None
    assert login(make_user()).get(f"/api/trips/{trip.pk}/").json()["priority"] is None


# ---- 5. link to the conflicting trip ------------------------------------------------
@pytest.mark.django_db
def test_duplicate_errors_name_the_conflicting_trip(make_user, location, login):
    me = make_user()
    client = login(me)
    start = timezone.now() + timedelta(days=10)
    body = {"location_id": location.pk, "title": "Khao Yai", "participant_capacity": 4,
            "start_datetime": start.isoformat(), "end_datetime": (start + timedelta(days=1)).isoformat()}
    first = client.post("/api/trips/", body, format="json").json()["id"]
    same_title = client.post("/api/trips/", {**body, "start_datetime": (start + timedelta(days=30)).isoformat(),
                                             "end_datetime": (start + timedelta(days=31)).isoformat()}, format="json")
    assert same_title.status_code == 400 and str(first) in str(same_title.json()["conflicting_trip_id"])
    overlap = client.post("/api/trips/", {**body, "title": "Other"}, format="json")
    assert overlap.status_code == 400 and str(first) in str(overlap.json()["conflicting_trip_id"])
