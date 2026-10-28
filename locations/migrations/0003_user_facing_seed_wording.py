"""Replace developer wording ("seed data", "System import") on existing campsites."""
from django.db import migrations

OLD_SOURCE, NEW_SOURCE = "Seed data (unverified)", "AdventureHive team (unverified)"
OLD_SUMMARY, NEW_SUMMARY = "Imported from seed data", "First listed by the AdventureHive team"


def forwards(apps, schema_editor):
    Location = apps.get_model("locations", "Location")
    LocationRevision = apps.get_model("locations", "LocationRevision")
    Location.objects.filter(permit_info_source=OLD_SOURCE).update(permit_info_source=NEW_SOURCE)
    LocationRevision.objects.filter(edit_summary=OLD_SUMMARY).update(edit_summary=NEW_SUMMARY)
    for rev in LocationRevision.objects.filter(snapshot__permit_info_source=OLD_SOURCE):
        rev.snapshot["permit_info_source"] = NEW_SOURCE
        rev.save(update_fields=["snapshot"])


def backwards(apps, schema_editor):
    Location = apps.get_model("locations", "Location")
    LocationRevision = apps.get_model("locations", "LocationRevision")
    Location.objects.filter(permit_info_source=NEW_SOURCE).update(permit_info_source=OLD_SOURCE)
    LocationRevision.objects.filter(edit_summary=NEW_SUMMARY).update(edit_summary=OLD_SUMMARY)
    for rev in LocationRevision.objects.filter(snapshot__permit_info_source=NEW_SOURCE):
        rev.snapshot["permit_info_source"] = OLD_SOURCE
        rev.save(update_fields=["snapshot"])


class Migration(migrations.Migration):
    dependencies = [("locations", "0002_campsite_cover_image")]
    operations = [migrations.RunPython(forwards, backwards)]
