"""
Authorization matrix (professor's comment: "strengthen the explanation of authorization").

One table — endpoint × role → expected HTTP status — and one test per cell that
logs in as that role and checks the real API. The same table is in
PRESENTATION_security.md; if the code and the slide ever disagree, this fails.

Roles
  anon        — not logged in
  member      — logged in, unrelated to the trip
  participant — confirmed on the trip (owner of their own profile / contact)
  organizer   — organised the trip
  admin       — platform moderator (is_staff + superuser)

Expected values: an HTTP status code. 200 = allowed; 401 = log in first;
403 = logged in but not allowed.
"""
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import EmergencyContact, User
from locations.models import Location, LocationStatus
from reviews import services as review_services
from trips import services
from trips.models import Trip

ROLES = ["anon", "member", "participant", "organizer", "admin"]

#            endpoint                                anon  member participant organizer admin
MATRIX = {
    "edit trip":                                   (401,  403,   403,        200,      403),
    "cancel trip":                                 (401,  403,   403,        200,      200),
    "see participant list":                        (401,  403,   403,        200,      403),
    "record attendance":                           (401,  403,   403,        200,      403),
    "see check-in code":                           (401,  403,   403,        200,      403),
    "read shared emergency contacts":              (401,  403,   403,        200,      403),
    "read participant's own emergency contact":    (401,  403,   200,        403,      403),
    "edit participant's profile":                  (401,  403,   200,        403,      403),
    "approve a campsite submission":               (401,  403,   403,        403,      200),
    "hide a review":                               (401,  403,   403,        403,      200),
}

# Field-level privacy: is the exact meeting point included in the trip details?
MEETING_POINT_VISIBLE = {"anon": False, "member": False, "participant": True,
                         "organizer": True, "admin": False}
PRIVATE_PROFILE_FIELDS = ("email", "phone", "date_of_birth", "gender")


@pytest.fixture
def world(make_trip, make_user, location):
    """An upcoming trip and a just-finished trip with one confirmed participant."""
    organizer, participant, member = make_user(), make_user(), make_user()
    admin = User.objects.create_superuser(email="mod@example.com", password="Adm1n-Pass!")
    EmergencyContact.objects.create(user=participant, name="Mya", phone="+66812345678",
                                    relationship="sister")

    upcoming = make_trip(organizer=organizer, capacity=3, meeting_point_name="Gate 2",
                         meeting_latitude=15.40, meeting_longitude=105.50)
    finished = make_trip(organizer=organizer, capacity=3)
    for trip in (upcoming, finished):
        services.rsvp(trip, participant)
    now = timezone.now()
    Trip.objects.filter(pk=finished.pk).update(start_datetime=now - timedelta(days=1),
                                               end_datetime=now - timedelta(hours=1))
    services.complete_finished_trips()
    finished.refresh_from_db()
    services.set_emergency_sharing(finished, participant, share=True)
    services.check_in(finished, participant, services.checkin_code(finished))
    services.mark_attendance(finished, organizer, [{"user_id": participant.pk,
                                                    "status": "attended"}])
    review = review_services.create_review(participant, finished, 5, "Great")
    pending_site = Location.objects.create(
        name="Pending site", province="Chiang Mai", latitude=18.93, longitude=98.82,
        status=LocationStatus.PENDING_REVIEW, created_by=member)

    users = {"member": (member, "Camp1ng!Pass"), "participant": (participant, "Camp1ng!Pass"),
             "organizer": (organizer, "Camp1ng!Pass"), "admin": (admin, "Adm1n-Pass!")}
    return {"users": users, "upcoming": upcoming, "finished": finished, "review": review,
            "pending_site": pending_site, "participant": participant}


def _client(world, role, login):
    if role == "anon":
        return APIClient()
    user, password = world["users"][role]
    return login(user, password=password, client=APIClient())


def _call(client, endpoint, w):
    up, fin, p = w["upcoming"].pk, w["finished"].pk, w["participant"].pk
    return {
        "edit trip": lambda: client.patch(f"/api/trips/{up}/", {"title": "Renamed"}, format="json"),
        "cancel trip": lambda: client.delete(f"/api/trips/{up}/"),
        "see participant list": lambda: client.get(f"/api/trips/{up}/participants/"),
        "record attendance": lambda: client.post(
            f"/api/trips/{fin}/attendance/",
            {"records": [{"user_id": p, "status": "attended"}]}, format="json"),
        "see check-in code": lambda: client.get(f"/api/trips/{fin}/check-in-code/"),
        "read shared emergency contacts": lambda: client.get(f"/api/trips/{fin}/emergency-contacts/"),
        "read participant's own emergency contact": lambda: client.get(
            f"/api/users/{p}/emergency-contact/"),
        "edit participant's profile": lambda: client.patch(f"/api/users/{p}/", {"bio": "Hi"},
                                                           format="json"),
        "approve a campsite submission": lambda: client.post(
            f"/api/campsites/{w['pending_site'].pk}/approve/"),
        "hide a review": lambda: client.post(f"/api/reviews/{w['review'].pk}/hide/"),
    }[endpoint]()


@pytest.mark.django_db
@pytest.mark.parametrize("endpoint", list(MATRIX))
@pytest.mark.parametrize("role", ROLES)
def test_authorization_matrix(world, login, endpoint, role):
    expected = MATRIX[endpoint][ROLES.index(role)]
    res = _call(_client(world, role, login), endpoint, world)
    assert res.status_code == expected, f"{role} → {endpoint}: {res.status_code} {res.content[:200]}"


@pytest.mark.django_db
@pytest.mark.parametrize("role", ROLES)
def test_meeting_point_is_only_sent_to_organizer_and_participants(world, login, role):
    data = _client(world, role, login).get(f"/api/trips/{world['upcoming'].pk}/").json()
    assert (data["meeting_latitude"] is not None) == MEETING_POINT_VISIBLE[role]


@pytest.mark.django_db
@pytest.mark.parametrize("role", ROLES)
def test_public_profile_never_contains_private_fields(world, login, role):
    data = _client(world, role, login).get(f"/api/users/{world['participant'].pk}/").json()
    assert not set(PRIVATE_PROFILE_FIELDS) & set(data)
