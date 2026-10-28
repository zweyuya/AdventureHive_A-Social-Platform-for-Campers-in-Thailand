"""
Review gate, version 2. Same rules as 0002, plus two checks on INSERT only:
  - the review is written within 30 days after the trip ended
  - the trip has not been flagged as suspicious (flag_status = 'reviews_hidden')
They are INSERT-only on purpose: a moderator must still be able to hide or
restore an old review (an UPDATE) after the 30 days.
Existing hidden reviews are marked as hidden by a moderator.
"""
from django.db import migrations

GATE_V1 = r"""
CREATE OR REPLACE FUNCTION reviews_enforce_attended() RETURNS trigger AS $$
DECLARE
    t_status      text;
    t_location    bigint;
    t_organizer   bigint;
BEGIN
    IF TG_OP = 'UPDATE' AND (NEW.trip_id <> OLD.trip_id OR NEW.user_id <> OLD.user_id) THEN
        RAISE EXCEPTION 'review_gate: trip_id and user_id of a review cannot change'
            USING ERRCODE = 'check_violation';
    END IF;
    SELECT status, location_id, organizer_id INTO t_status, t_location, t_organizer
      FROM trips WHERE id = NEW.trip_id;
    IF t_status IS DISTINCT FROM 'completed' THEN
        RAISE EXCEPTION 'review_gate: trip % is not completed', NEW.trip_id
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.user_id = t_organizer THEN
        RAISE EXCEPTION 'review_gate: organizers cannot review their own trip'
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.location_id <> t_location THEN
        RAISE EXCEPTION 'review_gate: review location % does not match trip location %',
            NEW.location_id, t_location USING ERRCODE = 'check_violation';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM trip_participants
                    WHERE trip_id = NEW.trip_id AND user_id = NEW.user_id AND status = 'attended') THEN
        RAISE EXCEPTION 'review_gate: user % did not attend trip %', NEW.user_id, NEW.trip_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

GATE_V2 = r"""
CREATE OR REPLACE FUNCTION reviews_enforce_attended() RETURNS trigger AS $$
DECLARE
    t_status      text;
    t_location    bigint;
    t_organizer   bigint;
    t_end         timestamptz;
    t_flag        text;
BEGIN
    IF TG_OP = 'UPDATE' AND (NEW.trip_id <> OLD.trip_id OR NEW.user_id <> OLD.user_id) THEN
        RAISE EXCEPTION 'review_gate: trip_id and user_id of a review cannot change'
            USING ERRCODE = 'check_violation';
    END IF;
    SELECT status, location_id, organizer_id, end_datetime, flag_status
      INTO t_status, t_location, t_organizer, t_end, t_flag
      FROM trips WHERE id = NEW.trip_id;
    IF t_status IS DISTINCT FROM 'completed' THEN
        RAISE EXCEPTION 'review_gate: trip % is not completed', NEW.trip_id
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.user_id = t_organizer THEN
        RAISE EXCEPTION 'review_gate: organizers cannot review their own trip'
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.location_id <> t_location THEN
        RAISE EXCEPTION 'review_gate: review location % does not match trip location %',
            NEW.location_id, t_location USING ERRCODE = 'check_violation';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM trip_participants
                    WHERE trip_id = NEW.trip_id AND user_id = NEW.user_id AND status = 'attended') THEN
        RAISE EXCEPTION 'review_gate: user % did not attend trip %', NEW.user_id, NEW.trip_id
            USING ERRCODE = 'check_violation';
    END IF;
    IF TG_OP = 'INSERT' THEN
        IF now() > t_end + interval '30 days' THEN
            RAISE EXCEPTION 'review_gate: reviews must be written within 30 days of the trip'
                USING ERRCODE = 'check_violation';
        END IF;
        IF t_flag = 'reviews_hidden' THEN
            RAISE EXCEPTION 'review_gate: trip % is flagged as suspicious', NEW.trip_id
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


def mark_old_hidden(apps, schema_editor):
    apps.get_model("reviews", "Review").objects.filter(status="hidden", hidden_reason="") \
        .update(hidden_reason="moderator")


class Migration(migrations.Migration):
    dependencies = [
        ("reviews", "0003_review_reports"),
        ("trips", "0002_attendance_checkin_and_flags"),
    ]
    operations = [
        migrations.RunSQL(GATE_V2, GATE_V1),
        migrations.RunPython(mark_old_hidden, migrations.RunPython.noop),
    ]
