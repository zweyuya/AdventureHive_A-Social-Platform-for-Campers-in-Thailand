"""
End-to-end workflow through the public API only (no shortcuts into the database),
following the demo flow the professor asked to see:

register (PDPA) → log in → browse campsites/map → create & publish a trip →
RSVP (seat taken → next person waitlisted) → cancel → waitlist promotion →
trip completes → organizer marks attendance → verified review → campsite rating
"""
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from trips.models import Trip


def _register_and_login(email, name):
    client = APIClient()
    res = client.post("/api/auth/register/", {
        "email": email, "password": "Tent-and-Stars-42", "display_name": name,
        "camping_experience_level": "intermediate", "pdpa_consent": True,
    }, format="json")
    assert res.status_code == 201, res.content
    res = client.post("/api/auth/login/", {"email": email, "password": "Tent-and-Stars-42"},
                      format="json")
    assert res.status_code == 200
    return client, res.json()["id"]


@pytest.mark.django_db
def test_full_demo_flow():
    call_command("seed_campsites")

    # 1. Three people sign up (PDPA consent required)
    organizer, _ = _register_and_login("ploy@example.com", "Ploy")
    nok, nok_id = _register_and_login("nok@example.com", "Nok")
    mali, mali_id = _register_and_login("mali@example.com", "Mali")

    # 2. Browse campsites and the map (public)
    public = APIClient()
    loei = public.get("/api/campsites/?province=Loei").json()["results"]
    campsite = next(c for c in loei if c["name"] == "Phu Ruea Campground")
    pins = public.get("/api/map/campsites/").json()["features"]
    assert len(pins) == 15

    # 3. Ploy creates a 1-seat trip and publishes it
    start = timezone.now() + timedelta(days=7)
    trip = organizer.post("/api/trips/", {
        "location_id": campsite["id"], "title": "Cold-weather weekend at Phu Ruea",
        "start_datetime": start.isoformat(),
        "end_datetime": (start + timedelta(days=2)).isoformat(),
        "participant_capacity": 1, "meeting_point_name": "Park HQ car park",
        "meeting_latitude": 17.50, "meeting_longitude": 101.35,
    }, format="json").json()
    trip_id = trip["id"]
    assert organizer.post(f"/api/trips/{trip_id}/publish/").json()["status"] == "published"
    assert [t["id"] for t in public.get("/api/trips/").json()["results"]] == [trip_id]

    # 4. Nok takes the only seat; Mali is waitlisted
    assert nok.post(f"/api/trips/{trip_id}/rsvp/").json()["status"] == "confirmed"
    r = mali.post(f"/api/trips/{trip_id}/rsvp/").json()
    assert (r["status"], r["waitlist_position"]) == ("waitlisted", 1)
    assert public.get(f"/api/trips/{trip_id}/").json()["status"] == "full"
    assert mali.get(f"/api/trips/{trip_id}/").json()["meeting_latitude"] is None  # private

    # 5. Nok cancels → Mali is promoted automatically
    nok.delete(f"/api/trips/{trip_id}/rsvp/")
    mali_view = mali.get(f"/api/trips/{trip_id}/").json()
    assert mali_view["my_status"] == "confirmed"
    assert mali_view["meeting_latitude"] == 17.50  # now visible to her

    # 6. The trip happens (simulate time passing) and the scheduled job completes it
    Trip.objects.filter(pk=trip_id).update(start_datetime=timezone.now() - timedelta(days=3),
                                           end_datetime=timezone.now() - timedelta(days=1))
    call_command("complete_trips")
    assert organizer.get(f"/api/trips/{trip_id}/").json()["status"] == "completed"

    # 7. Before attendance is recorded, Mali cannot review yet
    assert mali.get(f"/api/trips/{trip_id}/").json()["can_review"] is False
    assert mali.post("/api/reviews/", {"trip_id": trip_id, "rating": 5},
                     format="json").status_code == 400

    # 8. Ploy records attendance → Mali can now write a verified review
    res = organizer.post(f"/api/trips/{trip_id}/attendance/",
                         {"records": [{"user_id": mali_id, "status": "attended"}]}, format="json")
    assert res.status_code == 200
    assert mali.get(f"/api/trips/{trip_id}/").json()["can_review"] is True
    review = mali.post("/api/reviews/", {"trip_id": trip_id, "rating": 5,
                                         "review_text": "Freezing but beautiful sunrise."},
                       format="json").json()
    assert review["verified_attendee"] is True

    # 9. Nok (cancelled, never went) cannot review
    assert nok.post("/api/reviews/", {"trip_id": trip_id, "rating": 1},
                    format="json").status_code == 400

    # 10. The campsite now shows the verified rating publicly
    detail = public.get(f"/api/campsites/{campsite['id']}/").json()
    assert detail["avg_rating"] == "5.00" and detail["review_count"] == 1
    reviews = public.get(f"/api/campsites/{campsite['id']}/reviews/").json()["results"]
    assert reviews[0]["author"]["display_name"] == "Mali"
