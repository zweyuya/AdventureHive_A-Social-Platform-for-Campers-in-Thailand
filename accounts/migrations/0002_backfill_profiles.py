"""Create a profile for any existing user that has none (e.g. earlier superusers)."""
from django.db import migrations


def backfill(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    Profile = apps.get_model("accounts", "Profile")
    for user in User.objects.filter(profile__isnull=True):
        Profile.objects.create(user=user, display_name=user.email.split("@")[0][:100])


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
