"""
Database rules against duplicate trips by the same organizer.

trips_unique_active_title_per_organizer  (partial unique index)
  - lower(btrim(title)) + organizer must be unique among draft/published/full trips.
    Completed and cancelled trips do not count, so their title can be used again.

trips_no_overlap_per_organizer  (exclusion constraint, GiST)
  - two draft/published/full trips of the same organizer cannot have overlapping
    [start, end) time ranges. Needs the btree_gist extension.

Before adding them, existing rows are checked: if old data already breaks a rule,
the migration stops with a list of the trips to fix (instead of a raw SQL error).
"""
import django.contrib.postgres.constraints
import django.contrib.postgres.fields.ranges
import django.db.models.functions.text
from django.conf import settings
from django.contrib.postgres.operations import BtreeGistExtension
from django.db import migrations, models

import trips.models

ACTIVE = ["draft", "published", "full"]

FIND_CONFLICTS = """
SELECT a.id, b.id, a.organizer_id,
       CASE WHEN lower(btrim(a.title)) = lower(btrim(b.title)) THEN 'same title'
            ELSE 'overlapping dates' END
FROM trips a JOIN trips b ON a.organizer_id = b.organizer_id AND a.id < b.id
WHERE a.status = ANY(%s) AND b.status = ANY(%s)
  AND (lower(btrim(a.title)) = lower(btrim(b.title))
       OR (a.start_datetime < b.end_datetime AND b.start_datetime < a.end_datetime))
"""


def check_existing(apps, schema_editor):
    with schema_editor.connection.cursor() as cur:
        cur.execute(FIND_CONFLICTS, [ACTIVE, ACTIVE])
        rows = cur.fetchall()
    if rows:
        lines = "\n".join(f"  trips #{a} and #{b} (organizer {o}): {why}" for a, b, o, why in rows)
        raise RuntimeError(
            "Some active trips already break the new duplicate-trip rules:\n"
            f"{lines}\nCancel or rename one trip of each pair (or flush the demo data), "
            "then run migrate again.")


class Migration(migrations.Migration):

    dependencies = [
        ('communities', '0001_initial'),
        ('locations', '0002_campsite_cover_image'),
        ('trips', '0004_members_only_and_emergency_sharing'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        BtreeGistExtension(),
        migrations.RunPython(check_existing, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='trip',
            constraint=models.UniqueConstraint(django.db.models.functions.text.Lower(django.db.models.functions.text.Trim('title')), models.F('organizer'), condition=models.Q(('status__in', ['draft', 'published', 'full'])), name='trips_unique_active_title_per_organizer', violation_error_message='You already have an active trip with this title.'),
        ),
        migrations.AddConstraint(
            model_name='trip',
            constraint=django.contrib.postgres.constraints.ExclusionConstraint(condition=models.Q(('status__in', ['draft', 'published', 'full'])), expressions=[('organizer', '='), (trips.models.TsTzRange('start_datetime', 'end_datetime', django.contrib.postgres.fields.ranges.RangeBoundary()), '&&')], name='trips_no_overlap_per_organizer', violation_error_message='You already have an active trip at this time.'),
        ),
    ]
