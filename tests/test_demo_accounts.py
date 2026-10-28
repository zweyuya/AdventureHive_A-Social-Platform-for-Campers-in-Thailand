"""tidy_demo_accounts: full Thai names for demo users, old test accounts removed safely."""
import io

import pytest
from django.core.management import call_command

from accounts.models import Profile, User, UserStatus
from social.models import Post
from trips.models import Trip

DEMO = "demo.adventurehive.test"


def _run(*args):
    call_command("tidy_demo_accounts", *args, stdout=io.StringIO())


def _name(email):
    return Profile.objects.get(user__email=email).display_name


@pytest.mark.django_db
def test_seed_demo_uses_full_names_and_posts_still_seed():
    call_command("seed_demo", stdout=io.StringIO())
    assert _name(f"nok@{DEMO}") == "Nok Srisuk"
    assert _name(f"ploy@{DEMO}") == "Ploy Chaiyaporn"
    assert Post.objects.filter(user__email=f"ploy@{DEMO}").exists()  # posts found users by email


@pytest.mark.django_db
def test_renames_existing_short_names_and_keeps_their_data():
    call_command("seed_demo", stdout=io.StringIO())
    Profile.objects.filter(user__email__endswith=f"@{DEMO}").update(display_name="X")
    Profile.objects.filter(user__email=f"nok@{DEMO}").update(display_name="Nok")
    trips_before = Trip.objects.count()

    _run()

    assert _name(f"nok@{DEMO}") == "Nok Srisuk"
    assert _name(f"beam@{DEMO}") == "Beam Boonmee"
    assert Trip.objects.count() == trips_before
    assert User.objects.get(email=f"nok@{DEMO}").check_password("DemoCamp123!")  # login unchanged
    _run()  # re-run is harmless
    assert _name(f"nok@{DEMO}") == "Nok Srisuk"


@pytest.mark.django_db
def test_old_account_without_content_is_deleted(make_user):
    make_user(email="mali@example.com")
    _run()
    assert not User.objects.filter(email="mali@example.com").exists()


@pytest.mark.django_db
def test_old_account_that_organised_a_trip_is_anonymised_not_deleted(make_user, make_trip):
    old = make_user(email="nok@example.com")
    trip = make_trip(organizer=old)
    _run()
    old.refresh_from_db()
    assert old.status == UserStatus.DELETED and old.email.endswith("@deleted.invalid")
    assert old.profile.display_name == "Deleted user"
    assert Trip.objects.filter(pk=trip.pk).exists()  # other people's trip data kept


@pytest.mark.django_db
def test_dry_run_changes_nothing(make_user):
    call_command("seed_demo", stdout=io.StringIO())
    Profile.objects.filter(user__email=f"nok@{DEMO}").update(display_name="Nok")
    make_user(email="mali@example.com")
    _run("--dry-run")
    assert _name(f"nok@{DEMO}") == "Nok"
    assert User.objects.filter(email="mali@example.com").exists()


@pytest.mark.django_db
def test_staff_account_is_never_touched(make_user):
    make_user(email="mali@example.com", is_staff=True)
    _run()
    assert User.objects.filter(email="mali@example.com", is_staff=True).exists()
