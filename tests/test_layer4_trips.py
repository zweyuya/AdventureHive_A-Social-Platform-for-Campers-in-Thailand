"""Layer 4 — trip CRUD, visibility, status lifecycle, equipment, meeting-point privacy."""
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from locations.models import Location, LocationStatus
from notifications.models import Notification
from trips.models import ParticipantStatus as PS
from trips.models import Trip, TripParticipant, TripStatus


def _future(days):
    return (timezone.now() + timedelta(days=days)).isoformat()


@pytest.fixture
def organizer(make_user, login):
    user = make_user()
    return user, login(user, client=APIClient())


@pytest.fixture
def payload(location):
    return {
        "location_id": location.pk,
        "title": "Stargazing at Pha Taem",
        "description": "Two nights on the cliff.",
        "start_datetime": _future(10),
        "end_datetime": _future(12),
        "participant_capacity": 4,
        "difficulty": "easy",
        "meeting_point_name": "Pha Taem visitor centre",
        "meeting_latitude": 15.40,
        "meeting_longitude": 105.50,
    }


# ---------------- Create / publish -------------------------------------------------

@pytest.mark.django_db
def test_create_trip_is_draft_and_hidden_until_published(organizer, payload):
    user, client = organizer
    res = client.post("/api/trips/", payload, format="json")
    assert res.status_code == 201, res.content
    body = res.json()
    assert body["status"] == "draft" and body["organizer"]["id"] == user.pk
    trip_id = body["id"]

    public = APIClient()
    assert public.get(f"/api/trips/{trip_id}/").status_code == 404
    assert public.get("/api/trips/").json()["count"] == 0

    assert client.post(f"/api/trips/{trip_id}/publish/").json()["status"] == "published"
    assert public.get("/api/trips/").json()["count"] == 1


@pytest.mark.django_db
@pytest.mark.parametrize("change, field", [
    ({"end_datetime": _future(9)}, "end_datetime"),        # ends before it starts
    ({"start_datetime": _future(-1)}, "start_datetime"),   # in the past
    ({"participant_capacity": 0}, "participant_capacity"),
    ({"meeting_longitude": None}, "meeting_latitude"),     # only one coordinate
    ({"meeting_latitude": 35.6, "meeting_longitude": 139.7}, "meeting_latitude"),  # not Thailand
])
def test_create_validation(organizer, payload, change, field):
    _, client = organizer
    res = client.post("/api/trips/", {**payload, **change}, format="json")
    assert res.status_code == 400 and field in res.json(), res.json()


@pytest.mark.django_db
def test_trip_must_use_a_published_campsite(organizer, payload):
    _, client = organizer
    pending = Location.objects.create(name="Unapproved", province="Loei", latitude=17.5,
                                      longitude=101.3, status=LocationStatus.PENDING_REVIEW)
    res = client.post("/api/trips/", {**payload, "location_id": pending.pk}, format="json")
    assert res.status_code == 400 and "location_id" in res.json()


@pytest.mark.django_db
def test_only_organizer_can_edit_or_publish(make_trip, make_user, login):
    trip = make_trip(status=TripStatus.DRAFT)
    other = login(make_user(), client=APIClient())
    assert other.patch(f"/api/trips/{trip.pk}/", {"title": "X"}, format="json").status_code == 404
    trip.status = TripStatus.PUBLISHED
    trip.save()
    assert other.patch(f"/api/trips/{trip.pk}/", {"title": "X"}, format="json").status_code == 403
    assert other.post(f"/api/trips/{trip.pk}/publish/").status_code == 403


@pytest.mark.django_db
def test_status_cannot_be_set_directly(make_trip, login):
    trip = make_trip(status=TripStatus.DRAFT)
    client = login(trip.organizer, client=APIClient())
    client.patch(f"/api/trips/{trip.pk}/", {"status": "completed", "confirmed_count": 99},
                 format="json")
    trip.refresh_from_db()
    assert trip.status == TripStatus.DRAFT and trip.confirmed_count == 0


# ---------------- Listing & filters ---------------------------------------------

@pytest.mark.django_db
def test_list_defaults_to_upcoming_open_trips(make_trip, api_client):
    open_trip = make_trip()
    make_trip(status=TripStatus.CANCELLED)
    make_trip(status=TripStatus.COMPLETED)
    make_trip(status=TripStatus.DRAFT)
    make_trip(days_from_now=-5)  # published but in the past
    ids = [t["id"] for t in api_client.get("/api/trips/").json()["results"]]
    assert ids == [open_trip.pk]
    completed = api_client.get("/api/trips/?status=completed").json()["results"]
    assert len(completed) == 1


@pytest.mark.django_db
def test_list_filters(make_trip, api_client):
    loc2 = Location.objects.create(name="Doi Inthanon", province="Chiang Mai", latitude=18.5,
                                   longitude=98.5, status=LocationStatus.PUBLISHED)
    easy = make_trip(difficulty="easy")
    hard = make_trip(difficulty="difficult", loc=loc2, capacity=1)
    Trip.objects.filter(pk=hard.pk).update(confirmed_count=1, status=TripStatus.FULL)

    def ids(q):
        return [t["id"] for t in api_client.get(f"/api/trips/?{q}").json()["results"]]

    assert ids("province=chiang mai") == [hard.pk]
    assert ids("difficulty=easy") == [easy.pk]
    assert ids("has_spots=true") == [easy.pk]
    assert ids(f"location={loc2.pk}") == [hard.pk]
    assert ids("search=inthanon") == [hard.pk]


# ---------------- Cancel (DELETE) --------------------------------------------------

@pytest.mark.django_db
def test_delete_cancels_trip_and_notifies_participants(make_trip, make_user, login):
    trip = make_trip(capacity=1)
    a, b = make_user(), make_user()
    from trips import services
    services.rsvp(trip, a)
    services.rsvp(trip, b)  # waitlisted
    client = login(trip.organizer, client=APIClient())
    res = client.delete(f"/api/trips/{trip.pk}/")
    assert res.status_code == 200 and res.json()["status"] == "cancelled"
    assert Trip.objects.filter(pk=trip.pk).exists()  # not deleted
    for user in (a, b):
        assert Notification.objects.filter(recipient=user, type="trip_cancelled").exists()
    assert client.delete(f"/api/trips/{trip.pk}/").status_code == 400  # already cancelled


@pytest.mark.django_db
def test_moderator_can_cancel_but_other_members_cannot(make_trip, make_user, login):
    trip = make_trip()
    other = login(make_user(), client=APIClient())
    assert other.delete(f"/api/trips/{trip.pk}/").status_code == 403
    mod = User.objects.create_superuser(email="mod@example.com", password="Adm1n-Pass!")
    mod_client = login(mod, password="Adm1n-Pass!", client=APIClient())
    assert mod_client.delete(f"/api/trips/{trip.pk}/").json()["status"] == "cancelled"


@pytest.mark.django_db
def test_changing_date_notifies_participants(make_trip, make_user, login):
    trip = make_trip()
    joiner = make_user()
    from trips import services
    services.rsvp(trip, joiner)
    client = login(trip.organizer, client=APIClient())
    client.patch(f"/api/trips/{trip.pk}/", {"start_datetime": _future(20),
                                            "end_datetime": _future(21)}, format="json")
    assert Notification.objects.filter(recipient=joiner, type="trip_updated").exists()


# ---------------- Privacy ---------------------------------------------------------

@pytest.mark.django_db
def test_meeting_point_visible_only_to_organizer_and_confirmed(make_trip, make_user, login):
    trip = make_trip(capacity=1, meeting_point_name="Gate 2", meeting_latitude=15.4,
                     meeting_longitude=105.5)
    confirmed, waitlisted = make_user(), make_user()
    from trips import services
    services.rsvp(trip, confirmed)
    services.rsvp(trip, waitlisted)
    url = f"/api/trips/{trip.pk}/"

    def meeting(client):
        return client.get(url).json()["meeting_latitude"]

    assert meeting(APIClient()) is None
    assert meeting(login(waitlisted, client=APIClient())) is None
    assert meeting(login(confirmed, client=APIClient())) == 15.4
    assert meeting(login(trip.organizer, client=APIClient())) == 15.4


@pytest.mark.django_db
def test_participant_list_is_organizer_only_even_for_admins(make_trip, make_user, login):
    trip = make_trip()
    joiner = make_user()
    from trips import services
    services.rsvp(trip, joiner)
    url = f"/api/trips/{trip.pk}/participants/"
    assert login(joiner, client=APIClient()).get(url).status_code == 403
    admin = User.objects.create_superuser(email="adm@example.com", password="Adm1n-Pass!")
    assert login(admin, password="Adm1n-Pass!", client=APIClient()).get(url).status_code == 403
    res = login(trip.organizer, client=APIClient()).get(url)
    assert res.status_code == 200 and res.json()[0]["user_id"] == joiner.pk


@pytest.mark.django_db
def test_my_status_and_mine_endpoint(make_trip, make_user, login):
    trip = make_trip(capacity=1)
    other_trip = make_trip()
    a, b = make_user(), make_user()
    from trips import services
    services.rsvp(trip, a)
    services.rsvp(trip, b)
    client_b = login(b, client=APIClient())
    detail = client_b.get(f"/api/trips/{trip.pk}/").json()
    assert detail["my_status"] == "waitlisted" and detail["my_waitlist_position"] == 1
    assert detail["waitlist_count"] == 1 and detail["spots_left"] == 0
    assert [t["id"] for t in client_b.get("/api/trips/mine/").json()] == [trip.pk]
    organizer_client = login(other_trip.organizer, client=APIClient())
    assert [t["id"] for t in organizer_client.get("/api/trips/mine/").json()] == [other_trip.pk]


# ---------------- Equipment -------------------------------------------------------

@pytest.mark.django_db
def test_equipment_organizer_edits_others_read(make_trip, make_user, login):
    trip = make_trip()
    base = f"/api/trips/{trip.pk}/equipment/"
    org = login(trip.organizer, client=APIClient())
    res = org.post(base, {"item_name": "Tent", "provided_by": "organizer"}, format="json")
    assert res.status_code == 201
    item = res.json()["id"]
    assert org.patch(f"{base}{item}/", {"notes": "2-person"}, format="json").status_code == 200

    other = login(make_user(), client=APIClient())
    assert other.post(base, {"item_name": "Stove", "provided_by": "participant"},
                      format="json").status_code == 403
    assert other.delete(f"{base}{item}/").status_code == 403
    listing = APIClient().get(base).json()
    assert [i["item_name"] for i in listing] == ["Tent"]
    assert APIClient().get(f"/api/trips/{trip.pk}/").json()["equipment_items"][0]["notes"] == "2-person"


@pytest.mark.django_db
def test_transitions_are_enforced(make_trip):
    from trips.services import TripError, transition
    trip = make_trip(status=TripStatus.COMPLETED)
    with pytest.raises(TripError):
        transition(trip, TripStatus.PUBLISHED)
    draft = make_trip(status=TripStatus.DRAFT)
    with pytest.raises(TripError):
        transition(draft, TripStatus.COMPLETED)


@pytest.mark.django_db
def test_participant_rows_survive_trip_cancellation(make_trip, make_user):
    trip = make_trip()
    u = make_user()
    from trips import services
    services.rsvp(trip, u)
    services.cancel_trip(trip, trip.organizer)
    assert TripParticipant.objects.get(trip=trip, user=u).status == PS.CONFIRMED


@pytest.mark.django_db
def test_admin_trip_pages_and_cancel_action(client, make_trip, make_user):
    admin = User.objects.create_superuser(email="adm2@example.com", password="Adm1n-Pass!")
    client.force_login(admin)
    trip = make_trip()
    from trips import services
    services.rsvp(trip, make_user())
    assert client.get("/admin/trips/trip/").status_code == 200
    assert client.get(f"/admin/trips/trip/{trip.pk}/change/").status_code == 200
    res = client.post("/admin/trips/trip/", {"action": "cancel_selected",
                                             "_selected_action": [str(trip.pk)]})
    assert res.status_code == 302
    assert Trip.objects.get(pk=trip.pk).status == TripStatus.CANCELLED
