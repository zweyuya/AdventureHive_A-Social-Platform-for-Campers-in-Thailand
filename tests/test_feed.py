"""Newsfeed — group & trip posts, private-group approval, reactions, comments."""
import io

import pytest
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from notifications.models import Notification
from social.models import Comment, Post, Reaction


@pytest.fixture
def people(make_user, login):
    out = {}
    for name in ("admin", "co", "mem", "outsider"):
        u = make_user()
        out[name] = (u, login(u, client=APIClient()))
    return out


def _group(people, privacy):
    _, ac = people["admin"]
    gid = ac.post("/api/groups/", {"name": f"{privacy} crew", "privacy_type": privacy},
                  format="json").json()["id"]
    for n in ("co", "mem"):
        if privacy == "public":
            people[n][1].post(f"/api/groups/{gid}/join/")
        else:
            res = ac.post(f"/api/groups/{gid}/members/", {"user_id": people[n][0].pk}, format="json")
            assert res.status_code in (200, 201), res.content
    ac.post(f"/api/groups/{gid}/members/{people['co'][0].pk}/role/", {"role": "co_admin"}, format="json")
    return gid


@pytest.fixture
def public_gid(people):
    return _group(people, "public")


@pytest.fixture
def private_gid(people):
    return _group(people, "private")


def _post(client, **data):
    return client.post("/api/posts/", data, format="json")


def _ids(res):
    return [p["id"] for p in res.json()["results"]]


# ---------------- Public group ---------------------------------------------------------

@pytest.mark.django_db
def test_public_group_post_goes_live_and_anyone_can_read(people, public_gid):
    res = _post(people["mem"][1], content_text="Fog at sunrise!", group_id=public_gid)
    assert res.status_code == 201 and res.json()["status"] == "published"
    pid = res.json()["id"]
    assert pid in _ids(APIClient().get(f"/api/posts/?group={public_gid}"))
    assert pid in _ids(people["outsider"][1].get(f"/api/posts/?group={public_gid}"))


@pytest.mark.django_db
def test_non_member_cannot_post_react_or_comment(people, public_gid):
    oc = people["outsider"][1]
    assert _post(oc, content_text="hi", group_id=public_gid).status_code == 403
    pid = _post(people["mem"][1], content_text="x", group_id=public_gid).json()["id"]
    assert oc.put(f"/api/posts/{pid}/react/", {"type": "like"}, format="json").status_code == 403
    assert oc.post(f"/api/posts/{pid}/comments/", {"content_text": "y"}, format="json").status_code == 403


@pytest.mark.django_db
def test_post_needs_exactly_one_place_and_some_content(people, public_gid, make_trip):
    mc = people["mem"][1]
    assert _post(mc, content_text="nowhere").status_code == 400
    trip = make_trip(organizer=people["mem"][0])
    assert _post(mc, content_text="both", group_id=public_gid, trip_id=trip.pk).status_code == 400
    assert _post(mc, content_text="  ", group_id=public_gid).status_code == 400


# ---------------- Private group approval -------------------------------------------------

@pytest.mark.django_db
def test_private_member_post_waits_for_admin_approval(people, private_gid):
    (mem, mc), (admin, ac), (co, cc) = people["mem"], people["admin"], people["co"]
    res = _post(mc, content_text="Can we camp at Erawan?", group_id=private_gid)
    assert res.status_code == 201 and res.json()["status"] == "pending_review"
    pid = res.json()["id"]

    # moderators were notified; other members can't see it yet; the author can
    assert Notification.objects.filter(recipient=admin, type="post_pending", reference_id=pid).exists()
    assert Notification.objects.filter(recipient=co, type="post_pending").exists()
    assert pid in _ids(mc.get(f"/api/posts/?group={private_gid}"))
    assert pid not in _ids(cc.get(f"/api/posts/?group={private_gid}"))

    # queue is moderator-only
    assert mc.get(f"/api/posts/?group={private_gid}&status=pending_review").status_code == 403
    assert _ids(cc.get(f"/api/posts/?group={private_gid}&status=pending_review")) == [pid]
    assert mc.post(f"/api/posts/{pid}/approve/").status_code == 403

    # nobody can react to a pending post
    assert ac.put(f"/api/posts/{pid}/react/", {"type": "like"}, format="json").status_code == 400

    res = cc.post(f"/api/posts/{pid}/approve/")
    assert res.status_code == 200 and res.json()["status"] == "published"
    assert Notification.objects.filter(recipient=mem, type="post_approved").exists()
    assert pid in _ids(ac.get(f"/api/posts/?group={private_gid}"))


@pytest.mark.django_db
def test_reject_requires_note_and_note_only_shown_to_author_and_mods(people, private_gid):
    (mem, mc), (_, ac), (_, cc) = people["mem"], people["admin"], people["co"]
    pid = _post(mc, content_text="Selling gear, DM me", group_id=private_gid).json()["id"]
    assert ac.post(f"/api/posts/{pid}/reject/", {}, format="json").status_code == 400
    res = ac.post(f"/api/posts/{pid}/reject/", {"note": "No selling in this group."}, format="json")
    assert res.json()["status"] == "rejected"
    assert mc.get(f"/api/posts/{pid}/").json()["moderation_note"] == "No selling in this group."
    assert Notification.objects.filter(recipient=mem, type="post_rejected").exists()
    assert cc.get(f"/api/posts/{pid}/").json()["moderation_note"] == "No selling in this group."
    # can't approve something that isn't pending
    assert ac.post(f"/api/posts/{pid}/reject/", {"note": "again"}, format="json").status_code == 400


@pytest.mark.django_db
def test_admin_posts_go_live_and_member_edit_returns_to_review(people, private_gid):
    _, ac = people["admin"]
    assert _post(ac, content_text="Meeting Saturday", group_id=private_gid).json()["status"] == "published"
    mc = people["mem"][1]
    pid = _post(mc, content_text="v1", group_id=private_gid).json()["id"]
    ac.post(f"/api/posts/{pid}/approve/")
    res = mc.put(f"/api/posts/{pid}/", {"content_text": "v2 with a link"}, format="json")
    assert res.status_code == 200 and res.json()["status"] == "pending_review"
    assert res.json()["edited_at"]
    # someone else can't edit it
    assert ac.put(f"/api/posts/{pid}/", {"content_text": "hijack"}, format="json").status_code == 403


@pytest.mark.django_db
def test_private_group_posts_invisible_to_outsiders(people, private_gid):
    pid = _post(people["admin"][1], content_text="secret spot", group_id=private_gid).json()["id"]
    oc = people["outsider"][1]
    assert oc.get(f"/api/posts/?group={private_gid}").status_code == 403
    assert oc.get(f"/api/posts/{pid}/").status_code == 404
    assert APIClient().get(f"/api/posts/{pid}/").status_code == 404
    assert pid not in _ids(oc.get("/api/posts/"))


# ---------------- Trips ------------------------------------------------------------------

@pytest.mark.django_db
def test_trip_posts_limited_to_organizer_and_people_going(people, make_trip):
    (org, oc), (mem, mc), (_, xc) = people["admin"], people["mem"], people["outsider"]
    trip = make_trip(organizer=org, capacity=5)
    assert mc.post(f"/api/trips/{trip.pk}/rsvp/").status_code in (200, 201)
    pid = _post(mc, content_text="Who brings the stove?", trip_id=trip.pk).json()["id"]
    assert Post.objects.get(pk=pid).status == "published"
    assert pid in _ids(oc.get(f"/api/posts/?trip={trip.pk}"))
    assert xc.get(f"/api/posts/?trip={trip.pk}").status_code == 403
    assert _post(xc, content_text="me too", trip_id=trip.pk).status_code == 403
    # organizer moderates trip posts
    assert oc.post(f"/api/posts/{pid}/hide/").json()["status"] == "hidden"
    assert pid not in _ids(people["co"][1].get("/api/posts/"))


# ---------------- Feed ---------------------------------------------------------------------

@pytest.mark.django_db
def test_home_feed_shows_my_groups_and_trips_only(people, public_gid, private_gid, make_user, login):
    stranger = make_user()
    sc = login(stranger, client=APIClient())
    other_gid = sc.post("/api/groups/", {"name": "Elsewhere"}, format="json").json()["id"]
    elsewhere = _post(sc, content_text="not for you", group_id=other_gid).json()["id"]
    mine = _post(people["admin"][1], content_text="ours", group_id=private_gid).json()["id"]
    pub = _post(people["co"][1], content_text="pub", group_id=public_gid).json()["id"]
    feed = _ids(people["mem"][1].get("/api/posts/"))
    assert mine in feed and pub in feed and elsewhere not in feed
    assert APIClient().get("/api/posts/").status_code in (401, 403)


# ---------------- Reactions ---------------------------------------------------------------

@pytest.mark.django_db
def test_one_reaction_per_user_type_can_change(people, public_gid):
    (author, ac) = people["mem"]
    pid = _post(ac, content_text="Milky Way!", group_id=public_gid).json()["id"]
    cc, oc = people["co"][1], people["admin"][1]
    cc.put(f"/api/posts/{pid}/react/", {"type": "love"}, format="json")
    res = oc.put(f"/api/posts/{pid}/react/", {"type": "wow"}, format="json")
    assert res.json()["reaction_count"] == 2 and res.json()["reactions"] == {"love": 1, "wow": 1}
    assert res.json()["my_reaction"] == "wow"
    res = cc.put(f"/api/posts/{pid}/react/", {"type": "wow"}, format="json")  # change, not add
    assert res.json()["reaction_count"] == 2 and res.json()["reactions"] == {"wow": 2}
    assert cc.put(f"/api/posts/{pid}/react/", {"type": "angry"}, format="json").status_code == 400
    res = cc.delete(f"/api/posts/{pid}/react/")
    assert res.json()["reaction_count"] == 1 and res.json()["my_reaction"] is None
    assert Reaction.objects.filter(post_id=pid).count() == 1
    # author notified once per reactor, not for own reactions
    ac.put(f"/api/posts/{pid}/react/", {"type": "haha"}, format="json")
    assert Notification.objects.filter(recipient=author, type="reaction").count() == 2


# ---------------- Comments ----------------------------------------------------------------

@pytest.mark.django_db
def test_comments_with_one_level_of_replies_and_notifications(people, public_gid):
    (author, ac), (co, cc), (adm, dc) = people["mem"], people["co"], people["admin"]
    pid = _post(ac, content_text="Best campsite near Bangkok?", group_id=public_gid).json()["id"]
    c1 = cc.post(f"/api/posts/{pid}/comments/", {"content_text": "Khao Yai"}, format="json").json()
    assert Notification.objects.filter(recipient=author, type="comment").count() == 1
    r1 = dc.post(f"/api/posts/{pid}/comments/", {"content_text": "+1", "parent_comment_id": c1["id"]},
                 format="json").json()
    assert Notification.objects.filter(recipient=co, type="reply").count() == 1
    # reply to a reply is attached to the top-level comment
    r2 = ac.post(f"/api/posts/{pid}/comments/", {"content_text": "thanks", "parent_comment_id": r1["id"]},
                 format="json")
    assert Comment.objects.get(pk=r2.json()["id"]).parent_comment_id == c1["id"]
    thread = cc.get(f"/api/posts/{pid}/comments/").json()
    assert len(thread) == 1 and len(thread[0]["replies"]) == 2
    assert Post.objects.get(pk=pid).comment_count == 3


@pytest.mark.django_db
def test_comment_delete_and_moderator_hide(people, public_gid):
    (_, ac), (_, cc), (_, mc) = people["mem"], people["co"], people["admin"]
    pid = _post(ac, content_text="post", group_id=public_gid).json()["id"]
    cid = cc.post(f"/api/posts/{pid}/comments/", {"content_text": "rude"}, format="json").json()["id"]
    assert ac.delete(f"/api/comments/{cid}/").status_code == 403  # post author isn't a moderator
    assert mc.post(f"/api/comments/{cid}/hide/").json()["status"] == "hidden"
    assert ac.get(f"/api/posts/{pid}/comments/").json() == []
    assert Post.objects.get(pk=pid).comment_count == 0
    cid2 = ac.post(f"/api/posts/{pid}/comments/", {"content_text": "mine"}, format="json").json()["id"]
    assert ac.delete(f"/api/comments/{cid2}/").status_code == 204


@pytest.mark.django_db
def test_post_delete_by_author_or_moderator_only(people, public_gid):
    (_, ac), (_, cc), (_, xc) = people["mem"], people["co"], people["outsider"]
    p1 = _post(ac, content_text="a", group_id=public_gid).json()["id"]
    p2 = _post(ac, content_text="b", group_id=public_gid).json()["id"]
    assert xc.delete(f"/api/posts/{p1}/").status_code == 403
    assert ac.delete(f"/api/posts/{p1}/").status_code == 204
    assert cc.delete(f"/api/posts/{p2}/").status_code == 204
    assert not Post.objects.filter(pk__in=[p1, p2]).exists()


# ---------------- Photos & privacy ---------------------------------------------------------

def _jpeg_with_gps():
    img = Image.new("RGB", (2400, 1200), (40, 120, 60))
    exif = Image.Exif()
    exif[0x8825] = {1: "N", 2: (13.0, 45.0, 0.0)}
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    return SimpleUploadedFile("camp.jpg", buf.getvalue(), content_type="image/jpeg")


@pytest.mark.django_db
def test_post_photo_is_resized_and_gps_stripped(people, public_gid, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    res = people["mem"][1].post("/api/posts/", {"group_id": public_gid, "content_text": "",
                                                "image": _jpeg_with_gps()}, format="multipart")
    assert res.status_code == 201, res.content
    post = Post.objects.get(pk=res.json()["id"])
    with Image.open(post.image.path) as im:
        assert max(im.size) == 1600 and not im.getexif().get(0x8825)
    bad = SimpleUploadedFile("x.jpg", b"not an image", content_type="image/jpeg")
    assert people["mem"][1].post("/api/posts/", {"group_id": public_gid, "image": bad},
                                 format="multipart").status_code == 400


@pytest.mark.django_db
def test_account_deletion_removes_posts_comments_reactions(people, public_gid, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    (mem, mc), (_, cc) = people["mem"], people["co"]
    mine = mc.post("/api/posts/", {"group_id": public_gid, "content_text": "bye",
                                   "image": _jpeg_with_gps()}, format="multipart").json()["id"]
    path = Post.objects.get(pk=mine).image.path
    theirs = _post(cc, content_text="hello", group_id=public_gid).json()["id"]
    mc.put(f"/api/posts/{theirs}/react/", {"type": "love"}, format="json")
    mc.post(f"/api/posts/{theirs}/comments/", {"content_text": "hi"}, format="json")
    from accounts.services import delete_account
    delete_account(mem)
    assert not Post.objects.filter(pk=mine).exists()
    import os
    assert not os.path.exists(path)
    p = Post.objects.get(pk=theirs)
    assert p.reaction_count == 0 and p.comment_count == 0
