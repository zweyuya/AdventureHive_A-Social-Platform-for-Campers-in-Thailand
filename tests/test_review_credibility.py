"""
Review credibility (professor's comment: "clarify how attendance is verified and
how the system prevents false attendance records or misleading reviews").

A. Check-in code        — participant side of attendance
B. Two-sided attendance — check-in + organizer, or organizer + written reason
C. Suspicious trips     — automatic flag, admin hides all reviews of a trip
D. Rating               — only each person's newest review of a campsite counts
E. Report a review      — members report, moderators hide or dismiss
F. Database rules       — 30-day window and flagged trips, enforced by the trigger
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from reviews import services as review_services
from reviews.models import HiddenReason, ReportStatus, Review, ReviewReport, ReviewStatus
from trips import services
from trips.models import FlagStatus
from trips.models import ParticipantStatus as PS
from trips.models import Trip, TripParticipant


def _finish(trip, ended_ago=timedelta(hours=1)):
    """Simulate the trip happening; ended an hour ago → check-in still open."""
    now = timezone.now()
    Trip.objects.filter(pk=trip.pk).update(start_datetime=now - ended_ago - timedelta(days=1),
                                           end_datetime=now - ended_ago)
    services.complete_finished_trips()
    trip.refresh_from_db()
    return trip


@pytest.fixture
def trip_with_people(make_trip, make_user):
    """A trip with 3 confirmed participants that ended an hour ago (completed)."""
    trip = make_trip(capacity=3)
    people = [make_user() for _ in range(3)]
    for p in people:
        services.rsvp(trip, p)
    return _finish(trip), people


def _check_in(trip, user, code=None):
    return services.check_in(trip, user, code or services.checkin_code(trip))


def _row(trip, user):
    return TripParticipant.objects.get(trip=trip, user=user)


# ---------------- A. Check-in code -------------------------------------------------

@pytest.mark.django_db
def test_code_is_six_digits_per_trip_and_never_stored(make_trip):
    t1, t2 = make_trip(), make_trip()
    c1 = services.checkin_code(t1)
    assert len(c1) == 6 and c1.isdigit()
    assert c1 == services.checkin_code(Trip.objects.get(pk=t1.pk))  # stable
    assert c1 != services.checkin_code(t2)                          # different per trip
    stored = Trip.objects.filter(pk=t1.pk).values().first()
    assert c1 not in {str(v) for v in stored.values()}              # derived, not stored


@pytest.mark.django_db
def test_only_the_organizer_can_see_the_code(trip_with_people, login, api_client):
    trip, (a, _, _) = trip_with_people
    url = f"/api/trips/{trip.pk}/check-in-code/"
    assert api_client.get(url).status_code == 401
    assert login(a, client=APIClient()).get(url).status_code == 403
    res = login(trip.organizer, client=APIClient()).get(url).json()
    assert res["code"] == services.checkin_code(trip) and res["is_open"] is True


@pytest.mark.django_db
def test_participant_checks_in_through_the_api(trip_with_people, login):
    trip, (a, _, _) = trip_with_people
    client = login(a, client=APIClient())
    res = client.post(f"/api/trips/{trip.pk}/check-in/",
                      {"code": services.checkin_code(trip)}, format="json")
    assert res.status_code == 200 and _row(trip, a).checked_in_at is not None
    detail = client.get(f"/api/trips/{trip.pk}/").json()
    assert detail["checkin"]["my_checked_in_at"] is not None
    # Checking in twice is harmless
    assert client.post(f"/api/trips/{trip.pk}/check-in/",
                       {"code": services.checkin_code(trip)}, format="json").status_code == 200


@pytest.mark.django_db
def test_wrong_code_is_rejected_and_guessing_is_rate_limited(trip_with_people, login):
    trip, (a, _, _) = trip_with_people
    client = login(a, client=APIClient())
    wrong = "000000" if services.checkin_code(trip) != "000000" else "111111"
    codes = [client.post(f"/api/trips/{trip.pk}/check-in/", {"code": wrong},
                         format="json").status_code for _ in range(6)]
    assert codes[:5] == [400] * 5 and codes[5] == 429  # 5 guesses per minute
    assert _row(trip, a).checked_in_at is None


@pytest.mark.django_db
def test_check_in_only_inside_the_window(make_trip, make_user):
    trip, user = make_trip(days_from_now=1), make_user()  # starts tomorrow
    services.rsvp(trip, user)
    with pytest.raises(services.TripError, match="Check-in is open from"):
        _check_in(trip, user)                         # too early (opens 2 h before the start)
    Trip.objects.filter(pk=trip.pk).update(start_datetime=timezone.now() + timedelta(hours=1))
    trip.refresh_from_db()
    _check_in(trip, user)                             # at the meeting point: OK
    late = _finish(make_trip(), ended_ago=timedelta(hours=25))
    with pytest.raises(services.TripError, match="Check-in is open from"):
        _check_in(late, user)                         # more than 24 h after the end (checked first)


@pytest.mark.django_db
def test_only_confirmed_participants_can_check_in(make_trip, make_user):
    trip = make_trip(capacity=1)
    confirmed, waiting, stranger = make_user(), make_user(), make_user()
    services.rsvp(trip, confirmed)
    services.rsvp(trip, waiting)
    trip = _finish(trip)  # completing the trip cancels the waitlist
    for user in (waiting, stranger):
        with pytest.raises(services.TripError, match="Only confirmed"):
            _check_in(trip, user)


# ---------------- B. Two-sided attendance ------------------------------------------

@pytest.mark.django_db
def test_checked_in_and_confirmed_is_the_strong_verification(trip_with_people):
    trip, (a, _, _) = trip_with_people
    _check_in(trip, a)
    services.mark_attendance(trip, trip.organizer, [{"user_id": a.pk, "status": "attended"}])
    row = _row(trip, a)
    assert (row.status, row.verification_method, row.override_reason) == \
        (PS.ATTENDED, "check_in", "")


@pytest.mark.django_db
def test_forgot_to_check_in_needs_a_reason(trip_with_people, login):
    trip, (a, _, _) = trip_with_people
    client = login(trip.organizer, client=APIClient())
    url = f"/api/trips/{trip.pk}/attendance/"
    res = client.post(url, {"records": [{"user_id": a.pk, "status": "attended"}]}, format="json")
    assert res.status_code == 400 and "give a reason" in str(res.json())
    assert _row(trip, a).status == PS.CONFIRMED

    res = client.post(url, {"records": [{"user_id": a.pk, "status": "attended",
                                         "reason": "Phone died, she was with us"}]},
                      format="json")
    assert res.status_code == 200
    row = _row(trip, a)
    assert (row.status, row.verification_method, row.override_reason) == \
        (PS.ATTENDED, "organizer_only", "Phone died, she was with us")
    # The organizer sees check-ins and reasons in the participant list
    listed = {p["user_id"]: p for p in client.get(f"/api/trips/{trip.pk}/participants/").json()}
    assert listed[a.pk]["verification_method"] == "organizer_only"
    assert listed[a.pk]["checked_in_at"] is None


@pytest.mark.django_db
def test_checked_in_but_did_not_come_is_still_a_no_show(trip_with_people):
    """A check-in alone proves nothing: the organizer still decides."""
    trip, (a, _, _) = trip_with_people
    _check_in(trip, a)
    services.mark_attendance(trip, trip.organizer, [{"user_id": a.pk, "status": "no_show"}])
    row = _row(trip, a)
    assert row.status == PS.NO_SHOW and row.verification_method == ""
    assert review_services.review_eligibility(trip, a) is not None  # cannot review


@pytest.mark.django_db
def test_late_check_in_upgrades_an_organizer_only_record(trip_with_people):
    trip, (a, _, _) = trip_with_people
    services.mark_attendance(trip, trip.organizer, [{"user_id": a.pk, "status": "attended",
                                                     "reason": "No signal at camp"}])
    _check_in(trip, a)  # back online within 24 h
    assert _row(trip, a).verification_method == "check_in"


# ---------------- C. Suspicious trips --------------------------------------------

@pytest.mark.django_db
def test_trip_is_flagged_when_most_attendees_did_not_check_in(trip_with_people, make_trip,
                                                              make_user):
    trip, (a, b, c) = trip_with_people
    _check_in(trip, a)
    services.mark_attendance(trip, trip.organizer, [
        {"user_id": a.pk, "status": "attended"},
        {"user_id": b.pk, "status": "attended", "reason": "friend"},
        {"user_id": c.pk, "status": "attended", "reason": "friend"},
    ])
    trip.refresh_from_db()
    assert trip.flag_status == FlagStatus.NEEDS_REVIEW and "2 of 3" in trip.flag_note

    # One forgotten check-in out of three is normal: no flag
    other = make_trip(capacity=3)
    people = [make_user() for _ in range(3)]
    for p in people:
        services.rsvp(other, p)
    other = _finish(other)
    _check_in(other, people[0])
    _check_in(other, people[1])
    services.mark_attendance(other, other.organizer, [
        {"user_id": people[0].pk, "status": "attended"},
        {"user_id": people[1].pk, "status": "attended"},
        {"user_id": people[2].pk, "status": "attended", "reason": "forgot"},
    ])
    other.refresh_from_db()
    assert other.flag_status == FlagStatus.NONE


@pytest.fixture
def reviewed_trip(trip_with_people):
    """a and b checked in, attended and reviewed (5 and 3 stars)."""
    trip, (a, b, c) = trip_with_people
    _check_in(trip, a)
    _check_in(trip, b)
    services.mark_attendance(trip, trip.organizer, [{"user_id": a.pk, "status": "attended"},
                                                    {"user_id": b.pk, "status": "attended"}])
    ra = review_services.create_review(a, trip, 5, "Great")
    rb = review_services.create_review(b, trip, 3, "OK")
    return trip, (a, b, c), (ra, rb)


@pytest.mark.django_db
def test_admin_flag_hides_all_reviews_and_clear_restores_only_those(reviewed_trip):
    trip, _, (ra, rb) = reviewed_trip
    review_services.set_review_status(rb, ReviewStatus.HIDDEN)  # hidden by a moderator before
    assert review_services.flag_trip_hide_reviews(trip, None, "Looks fake") == 1
    trip.refresh_from_db()
    ra.refresh_from_db()
    assert trip.flag_status == FlagStatus.REVIEWS_HIDDEN
    assert (ra.status, ra.hidden_reason) == (ReviewStatus.HIDDEN, HiddenReason.TRIP_FLAGGED)
    assert trip.location.__class__.objects.get(pk=trip.location_id).review_count == 0

    assert review_services.clear_trip_flag(trip, None) == 1
    ra.refresh_from_db()
    rb.refresh_from_db()
    assert ra.status == ReviewStatus.PUBLISHED
    assert rb.status == ReviewStatus.HIDDEN  # the moderator's own decision stays


@pytest.mark.django_db
def test_flagged_trip_accepts_no_new_reviews(trip_with_people):
    trip, (a, _, _) = trip_with_people
    _check_in(trip, a)
    services.mark_attendance(trip, trip.organizer, [{"user_id": a.pk, "status": "attended"}])
    review_services.flag_trip_hide_reviews(trip, None)
    trip.refresh_from_db()
    with pytest.raises(review_services.ReviewError, match="closed"):
        review_services.create_review(a, trip, 5)
    with pytest.raises(IntegrityError, match="flagged"), transaction.atomic():  # DB as well
        Review.objects.create(trip=trip, user=a, location=trip.location, rating=5)


@pytest.mark.django_db
def test_admin_flag_action(reviewed_trip):
    trip, _, _ = reviewed_trip
    admin = User.objects.create_superuser(email="mod@example.com", password="Adm1n-Pass!")
    client = APIClient()
    client.force_login(admin)
    res = client.post("/admin/trips/trip/", {"action": "flag_hide_reviews",
                                             "_selected_action": [trip.pk]})
    assert res.status_code == 302
    assert Trip.objects.get(pk=trip.pk).flag_status == FlagStatus.REVIEWS_HIDDEN
    assert not trip.reviews.filter(status=ReviewStatus.PUBLISHED).exists()


# ---------------- D. Rating: newest review per person ------------------------------

@pytest.mark.django_db
def test_only_the_newest_review_per_person_counts(make_trip, make_user, location, api_client):
    camper, other = make_user(), make_user()

    def visit(stars):
        trip = make_trip(capacity=2)  # same campsite every time
        for u in (camper, other):
            services.rsvp(trip, u)
        trip = _finish(trip)
        for u in (camper, other):
            _check_in(trip, u)
        services.mark_attendance(trip, trip.organizer, [{"user_id": camper.pk, "status": "attended"},
                                                        {"user_id": other.pk, "status": "attended"}])
        return review_services.create_review(camper, trip, stars), trip

    first, _ = visit(5)
    second, trip2 = visit(1)
    review_services.create_review(other, trip2, 3)
    location.refresh_from_db()
    # camper counts once (their newest: 1★) + other (3★) → average 2.00 from 2 people
    assert (location.avg_rating, location.review_count) == (Decimal("2.00"), 2)

    listed = {r["id"]: r for r in api_client.get(
        f"/api/campsites/{location.pk}/reviews/").json()["results"]}
    assert listed[first.pk]["counts_in_rating"] is False   # older visit, still shown
    assert listed[second.pk]["counts_in_rating"] is True

    # The star breakdown counts the same reviews as the average
    detail = api_client.get(f"/api/campsites/{location.pk}/").json()
    assert detail["rating_breakdown"] == {"5": 0, "4": 0, "3": 1, "2": 0, "1": 1}
    assert sum(detail["rating_breakdown"].values()) == detail["review_count"] == 2

    # If the newest is hidden, the older one counts again
    review_services.set_review_status(second, ReviewStatus.HIDDEN)
    location.refresh_from_db()
    assert location.avg_rating == Decimal("4.00")  # (5 + 3) / 2


@pytest.mark.django_db
def test_reviews_show_how_attendance_was_verified(trip_with_people, api_client):
    trip, (a, b, _) = trip_with_people
    _check_in(trip, a)
    services.mark_attendance(trip, trip.organizer, [
        {"user_id": a.pk, "status": "attended"},
        {"user_id": b.pk, "status": "attended", "reason": "No signal"}])
    review_services.create_review(a, trip, 5)
    review_services.create_review(b, trip, 4)
    badges = {r["author"]["id"]: r["verification"] for r in api_client.get(
        f"/api/campsites/{trip.location_id}/reviews/").json()["results"]}
    assert badges == {a.pk: "check_in", b.pk: "organizer_only"}


# ---------------- E. Report a review -----------------------------------------------

@pytest.mark.django_db
def test_member_reports_a_review_once(reviewed_trip, make_user, login, api_client):
    _, (a, _, _), (ra, _) = reviewed_trip
    url = f"/api/reviews/{ra.pk}/report/"
    reporter = login(make_user(), client=APIClient())
    assert api_client.post(url, {"reason": "fake"}, format="json").status_code == 401
    assert reporter.post(url, {"reason": "nonsense"}, format="json").status_code == 400
    res = reporter.post(url, {"reason": "fake", "details": "Was not there"}, format="json")
    assert res.status_code == 201
    assert reporter.post(url, {"reason": "spam"}, format="json").status_code == 400  # again
    own = login(a, client=APIClient()).post(url, {"reason": "fake"}, format="json")
    assert own.status_code == 400 and "own review" in str(own.json())
    assert ReviewReport.objects.filter(review=ra, status=ReportStatus.OPEN).count() == 1


@pytest.mark.django_db
def test_moderator_hides_or_dismisses_reported_reviews(reviewed_trip, make_user):
    trip, _, (ra, rb) = reviewed_trip
    for review in (ra, rb):
        review_services.report_review(review, make_user(), "misleading")
    review_services.resolve_reports(ra, None, hide=True)
    review_services.resolve_reports(rb, None, hide=False)
    ra.refresh_from_db()
    rb.refresh_from_db()
    assert (ra.status, ra.hidden_reason) == (ReviewStatus.HIDDEN, HiddenReason.MODERATOR)
    assert rb.status == ReviewStatus.PUBLISHED
    assert set(ReviewReport.objects.values_list("status", flat=True)) == \
        {ReportStatus.ACTIONED, ReportStatus.DISMISSED}
    trip.location.refresh_from_db()
    assert trip.location.review_count == 1  # hidden review left the rating


# ---------------- F. Database rules (trigger) --------------------------------------

@pytest.mark.django_db
def test_database_enforces_the_30_day_window_on_new_reviews_only(reviewed_trip):
    trip, (_, _, c), (ra, _) = reviewed_trip
    _check_in(trip, c)
    services.mark_attendance(trip, trip.organizer, [{"user_id": c.pk, "status": "attended"}])
    Trip.objects.filter(pk=trip.pk).update(end_datetime=timezone.now() - timedelta(days=31),
                                           start_datetime=timezone.now() - timedelta(days=32))
    with pytest.raises(IntegrityError, match="30 days"), transaction.atomic():
        Review.objects.create(trip=trip, user=c, location=trip.location, rating=5)
    # A moderator can still hide an old review (an UPDATE, not an INSERT)
    review_services.set_review_status(ra, ReviewStatus.HIDDEN)
    ra.refresh_from_db()
    assert ra.status == ReviewStatus.HIDDEN


@pytest.mark.django_db
def test_demo_checkin_trip_command_gives_an_open_check_in():
    from django.core.management import call_command
    call_command("seed_campsites")
    call_command("seed_demo")  # includes one demo check-in trip
    first = Trip.objects.get(title__endswith="(just finished)")
    call_command("demo_checkin_trip")  # a fresh one for presentation day replaces it
    demo = Trip.objects.filter(title__endswith="(just finished)")
    assert demo.count() == 1
    trip = demo.get()
    assert trip.pk != first.pk
    assert trip.status == "completed" and services.checkin_is_open(trip)
    assert trip.participants.filter(status=PS.CONFIRMED).count() == 3


@pytest.mark.django_db
def test_demo_checkin_trip_only_replaces_the_demo_organizers_trip():
    from django.core.management import call_command
    from django.utils import timezone
    from accounts.models import User
    call_command("seed_campsites")
    call_command("seed_demo")
    old = Trip.objects.get(title__endswith="(just finished)")
    nok = User.objects.get(email="nok@demo.adventurehive.test")
    now = timezone.now()
    other = Trip.objects.create(
        organizer=nok, location=old.location, title=old.title,
        start_datetime=now + timedelta(days=3), end_datetime=now + timedelta(days=4),
        participant_capacity=4)
    call_command("demo_checkin_trip")
    assert not Trip.objects.filter(pk=old.pk).exists()
    assert Trip.objects.filter(pk=other.pk).exists()
