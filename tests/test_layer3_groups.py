"""Layer 3 — community groups: membership, member_count, in-group roles and permissions."""
import pytest
from rest_framework.test import APIClient

from communities.models import CampingGroup, GroupMember
from trips.models import TripStatus


@pytest.fixture
def people(make_user, login):
    """name -> (user, logged-in client)"""
    out = {}
    for name in ("owner", "co", "alice", "bob", "carol"):
        u = make_user()
        out[name] = (u, login(u, client=APIClient()))
    return out


def _create(client, privacy="public", name="Bangkok Weekend Campers"):
    res = client.post("/api/groups/", {"name": name, "category": "car_camping",
                                       "privacy_type": privacy}, format="json")
    assert res.status_code == 201, res.content
    return res.json()["id"]


def _count(gid):
    return CampingGroup.objects.get(pk=gid).member_count


def _active(gid):
    return GroupMember.objects.filter(group_id=gid, status="active").count()


def _role(gid, user):
    return GroupMember.objects.get(group_id=gid, user=user).role_in_group


@pytest.fixture
def group(people):
    """Public group: owner (admin), co (co-admin), alice (member)."""
    owner, oc = people["owner"]
    gid = _create(oc)
    for name in ("co", "alice"):
        people[name][1].post(f"/api/groups/{gid}/join/")
    oc.post(f"/api/groups/{gid}/members/{people['co'][0].pk}/role/", {"role": "co_admin"},
            format="json")
    return gid


# ---------------- Create / browse -------------------------------------------------------

@pytest.mark.django_db
def test_creator_becomes_admin_and_count_is_one(people):
    owner, oc = people["owner"]
    res = oc.post("/api/groups/", {"name": "Khao Yai Regulars"}, format="json")
    body = res.json()
    assert body["member_count"] == 1 and body["my_role"] == "admin"
    assert body["privacy_type"] == "public" and body["category"] == "general"
    assert _role(body["id"], owner) == "admin"


@pytest.mark.django_db
def test_list_search_and_filter_are_public(people, api_client):
    _, oc = people["owner"]
    _create(oc, name="Bangkok Weekend Campers")
    _create(oc, privacy="private", name="Secret Waterfall Club")
    names = [g["name"] for g in api_client.get("/api/groups/").json()["results"]]
    assert set(names) == {"Bangkok Weekend Campers", "Secret Waterfall Club"}
    assert [g["name"] for g in api_client.get("/api/groups/?search=waterfall").json()["results"]] \
        == ["Secret Waterfall Club"]
    assert [g["name"] for g in api_client.get("/api/groups/?privacy_type=public").json()["results"]] \
        == ["Bangkok Weekend Campers"]


# ---------------- Join / leave & member_count ---------------------------------------------

@pytest.mark.django_db
def test_join_and_leave_keep_member_count_in_sync(group, people):
    assert _count(group) == _active(group) == 3
    _, bc = people["bob"]
    assert bc.post(f"/api/groups/{group}/join/").status_code == 201
    assert _count(group) == _active(group) == 4
    assert bc.delete(f"/api/groups/{group}/join/").json()["status"] == "inactive"
    assert _count(group) == _active(group) == 3


@pytest.mark.django_db
def test_duplicate_join_blocked(group, people):
    _, ac = people["alice"]
    res = ac.post(f"/api/groups/{group}/join/")
    assert res.status_code == 400 and "already a member" in str(res.json())
    assert _count(group) == 3


@pytest.mark.django_db
def test_rejoin_after_leaving_reuses_row(group, people):
    alice, ac = people["alice"]
    ac.delete(f"/api/groups/{group}/join/")
    assert ac.post(f"/api/groups/{group}/join/").status_code == 201
    assert GroupMember.objects.filter(group_id=group, user=alice).count() == 1
    assert _count(group) == 3


@pytest.mark.django_db
def test_cannot_leave_a_group_you_are_not_in(group, people):
    assert people["bob"][1].delete(f"/api/groups/{group}/join/").status_code == 400


@pytest.mark.django_db
def test_last_admin_cannot_leave(group, people):
    owner, oc = people["owner"]
    res = oc.delete(f"/api/groups/{group}/join/")
    assert res.status_code == 400 and "only admin" in str(res.json())
    # after handing over the admin role they can leave
    oc.post(f"/api/groups/{group}/members/{people['co'][0].pk}/role/", {"role": "admin"},
            format="json")
    assert oc.delete(f"/api/groups/{group}/join/").status_code == 200
    assert _count(group) == 2


# ---------------- Private groups -----------------------------------------------------

@pytest.mark.django_db
def test_private_group_cannot_be_joined_directly(people):
    _, oc = people["owner"]
    bob, bc = people["bob"]
    gid = _create(oc, privacy="private")
    res = bc.post(f"/api/groups/{gid}/join/")
    assert res.status_code == 400 and "private" in str(res.json())
    # an admin adds them instead
    assert oc.post(f"/api/groups/{gid}/members/", {"user_id": bob.pk},
                   format="json").status_code == 201
    assert _count(gid) == 2


@pytest.mark.django_db
def test_private_group_members_and_trips_hidden_from_outsiders(people, make_trip, api_client):
    owner, oc = people["owner"]
    _, bc = people["bob"]
    gid = _create(oc, privacy="private")
    make_trip(organizer=owner, group=CampingGroup.objects.get(pk=gid))
    for client in (api_client, bc):
        assert client.get(f"/api/groups/{gid}/members/").status_code in (401, 403)
        assert client.get(f"/api/groups/{gid}/trips/").status_code in (401, 403)
    assert len(oc.get(f"/api/groups/{gid}/members/").json()) == 1
    assert len(oc.get(f"/api/groups/{gid}/trips/").json()) == 1


@pytest.mark.django_db
def test_public_group_members_and_trips_visible(group, people, make_trip, api_client):
    owner = people["owner"][0]
    make_trip(organizer=owner, group=CampingGroup.objects.get(pk=group))
    make_trip(organizer=owner, group=CampingGroup.objects.get(pk=group), status=TripStatus.DRAFT)
    assert len(api_client.get(f"/api/groups/{group}/members/").json()) == 3
    assert len(api_client.get(f"/api/groups/{group}/trips/").json()) == 1  # drafts hidden


# ---------------- Permissions (IsGroupAdmin / IsGroupModerator) ---------------------------

@pytest.mark.django_db
def test_only_admin_edits_or_deletes_group(group, people):
    _, ac = people["alice"]
    _, cc = people["co"]
    _, oc = people["owner"]
    for client in (ac, cc):  # member and co-admin
        assert client.patch(f"/api/groups/{group}/", {"name": "X"}, format="json").status_code == 403
        assert client.delete(f"/api/groups/{group}/").status_code == 403
    assert oc.patch(f"/api/groups/{group}/", {"description": "Weekend trips"},
                    format="json").json()["description"] == "Weekend trips"
    assert oc.delete(f"/api/groups/{group}/").status_code == 204
    assert not CampingGroup.objects.filter(pk=group).exists()


@pytest.mark.django_db
def test_co_admin_can_remove_members_but_not_admins_or_change_roles(group, people):
    alice = people["alice"][0]
    owner = people["owner"][0]
    _, cc = people["co"]
    assert cc.post(f"/api/groups/{group}/members/{owner.pk}/remove/").status_code == 403
    assert cc.post(f"/api/groups/{group}/members/{alice.pk}/role/", {"role": "admin"},
                   format="json").status_code == 403
    assert cc.post(f"/api/groups/{group}/members/{alice.pk}/ban/").status_code == 403
    res = cc.post(f"/api/groups/{group}/members/{alice.pk}/remove/")
    assert res.status_code == 200 and res.json()["status"] == "removed"
    assert _count(group) == _active(group) == 2


@pytest.mark.django_db
def test_ordinary_member_has_no_moderation_rights(group, people):
    bob, _ = people["bob"]
    co = people["co"][0]
    _, ac = people["alice"]
    assert ac.post(f"/api/groups/{group}/members/", {"user_id": bob.pk},
                   format="json").status_code == 403
    assert ac.post(f"/api/groups/{group}/members/{co.pk}/remove/").status_code == 403


@pytest.mark.django_db
def test_removed_and_banned_users_cannot_rejoin_themselves(group, people):
    alice, ac = people["alice"]
    bob, bc = people["bob"]
    _, oc = people["owner"]
    bc.post(f"/api/groups/{group}/join/")
    oc.post(f"/api/groups/{group}/members/{alice.pk}/remove/")
    oc.post(f"/api/groups/{group}/members/{bob.pk}/ban/")
    for client, word in ((ac, "removed"), (bc, "banned")):
        res = client.post(f"/api/groups/{group}/join/")
        assert res.status_code == 400 and word in str(res.json())
    assert _count(group) == _active(group) == 2


@pytest.mark.django_db
def test_only_admin_can_readmit_banned_user(group, people):
    bob, bc = people["bob"]
    _, cc = people["co"]
    _, oc = people["owner"]
    bc.post(f"/api/groups/{group}/join/")
    oc.post(f"/api/groups/{group}/members/{bob.pk}/ban/")
    assert cc.post(f"/api/groups/{group}/members/", {"user_id": bob.pk},
                   format="json").status_code == 403
    assert oc.post(f"/api/groups/{group}/members/", {"user_id": bob.pk},
                   format="json").status_code == 201
    assert _count(group) == _active(group) == 4


@pytest.mark.django_db
def test_group_must_keep_an_admin(group, people):
    owner, oc = people["owner"]
    res = oc.post(f"/api/groups/{group}/members/{owner.pk}/role/", {"role": "member"},
                  format="json")
    assert res.status_code == 400 and "at least one admin" in str(res.json())


@pytest.mark.django_db
def test_cannot_remove_yourself(group, people):
    owner, oc = people["owner"]
    assert oc.post(f"/api/groups/{group}/members/{owner.pk}/remove/").status_code == 400


@pytest.mark.django_db
def test_anonymous_cannot_join_or_create(group, api_client):
    assert api_client.post(f"/api/groups/{group}/join/").status_code == 401
    assert api_client.post("/api/groups/", {"name": "x"}, format="json").status_code == 401


@pytest.mark.django_db
def test_my_role_and_mine(group, people):
    _, cc = people["co"]
    _, bc = people["bob"]
    assert cc.get(f"/api/groups/{group}/").json()["my_role"] == "co_admin"
    assert bc.get(f"/api/groups/{group}/").json()["my_role"] is None
    assert [g["id"] for g in cc.get("/api/groups/mine/").json()] == [group]
    assert bc.get("/api/groups/mine/").json() == []


# ---------------- Trips & account deletion ------------------------------------------

@pytest.mark.django_db
def test_trip_can_only_be_attached_to_a_group_you_belong_to(group, people, location):
    from datetime import timedelta
    from django.utils import timezone
    start = timezone.now() + timedelta(days=5)
    payload = {"location_id": location.pk, "title": "Group trip", "group_id": group,
               "start_datetime": start.isoformat(),
               "end_datetime": (start + timedelta(days=1)).isoformat(),
               "participant_capacity": 5}
    assert people["bob"][1].post("/api/trips/", payload, format="json").status_code == 400
    assert people["alice"][1].post("/api/trips/", payload, format="json").status_code == 201


@pytest.mark.django_db
def test_deleted_sole_admin_is_succeeded_by_co_admin(group, people):
    from accounts.services import delete_account
    owner = people["owner"][0]
    co = people["co"][0]
    delete_account(owner)
    assert _role(group, co) == "admin"
    assert GroupMember.objects.get(group_id=group, user=owner).status == "inactive"
    assert _count(group) == _active(group) == 2


@pytest.mark.django_db
def test_admin_group_page_loads(group, client):
    from accounts.models import User
    admin = User.objects.create_superuser(email="adm@example.com", password="Adm1n-Pass!")
    client.force_login(admin)
    assert client.get(f"/admin/communities/campinggroup/{group}/change/").status_code == 200
