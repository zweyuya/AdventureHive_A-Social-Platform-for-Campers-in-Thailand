"""
Database rule for attendance (PostgreSQL trigger).

participants_attendance_rules  (BEFORE INSERT OR UPDATE ON trip_participants)
  - a new row can only be 'confirmed' or 'waitlisted' (what an RSVP creates)
  - a row can only become 'attended' or 'no_show' from 'confirmed'
    (or be corrected between attended / no_show): a waitlisted or cancelled
    person can never be marked as attended, whatever code path writes the row.
"""
from django.db import migrations

FORWARD = r"""
CREATE OR REPLACE FUNCTION participants_attendance_rules() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'INSERT' AND NEW.status NOT IN ('confirmed', 'waitlisted') THEN
        RAISE EXCEPTION 'attendance_rule: a new participant must be confirmed or waitlisted, not %',
            NEW.status USING ERRCODE = 'check_violation';
    END IF;
    IF TG_OP = 'UPDATE'
       AND NEW.status IN ('attended', 'no_show')
       AND OLD.status NOT IN ('confirmed', 'attended', 'no_show') THEN
        RAISE EXCEPTION 'attendance_rule: only confirmed participants can be marked % (was %)',
            NEW.status, OLD.status USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER participants_attendance_rules
    BEFORE INSERT OR UPDATE ON trip_participants
    FOR EACH ROW EXECUTE FUNCTION participants_attendance_rules();
"""

REVERSE = r"""
DROP TRIGGER IF EXISTS participants_attendance_rules ON trip_participants;
DROP FUNCTION IF EXISTS participants_attendance_rules();
"""


class Migration(migrations.Migration):
    dependencies = [("trips", "0002_attendance_checkin_and_flags")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
