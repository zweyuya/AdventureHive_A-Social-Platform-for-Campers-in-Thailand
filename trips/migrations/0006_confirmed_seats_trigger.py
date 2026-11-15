"""
Second safety net against overbooking (PostgreSQL trigger).

The CHECK on trips only sees the stored counter (confirmed_count). If a code path
ever skips the row lock, requests overwrite each other's counter (a lost update):
the counter stays low while too many people are confirmed, and the CHECK passes.

trips_check_confirmed_seats counts the real 'confirmed' rows instead.

  participants_enforce_seats  (AFTER INSERT OR UPDATE ON trip_participants, when confirmed)
  trips_enforce_seats         (AFTER UPDATE OF participant_capacity ON trips, when lowered)

Both are DEFERRED constraint triggers, so they run at COMMIT, when the transaction is
complete: raising a capacity promotes people before the new capacity is saved, which
is fine as long as the final result fits. The trip row is locked first, so transactions
committing at the same moment are checked one after the other and each one counts the
seats of those before it. FOR NO KEY UPDATE, because FOR UPDATE would conflict with the
key-share locks that the foreign keys of uncommitted rows hold on the trip (deadlock).
"""
from django.db import migrations

FORWARD = r"""
CREATE OR REPLACE FUNCTION trips_check_confirmed_seats() RETURNS trigger AS $$
DECLARE
    t_id        bigint;
    t_capacity  integer;
    t_confirmed integer;
BEGIN
    IF TG_TABLE_NAME = 'trips' THEN
        t_id := NEW.id;
    ELSE
        t_id := NEW.trip_id;
    END IF;

    SELECT participant_capacity INTO t_capacity
      FROM trips WHERE id = t_id FOR NO KEY UPDATE;

    SELECT count(*) INTO t_confirmed
      FROM trip_participants WHERE trip_id = t_id AND status = 'confirmed';

    IF t_confirmed > t_capacity THEN
        RAISE EXCEPTION 'seat_rule: trip % has % confirmed participants but only % seats',
            t_id, t_confirmed, t_capacity USING ERRCODE = 'check_violation';
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER participants_enforce_seats
    AFTER INSERT OR UPDATE ON trip_participants
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW WHEN (NEW.status = 'confirmed')
    EXECUTE FUNCTION trips_check_confirmed_seats();

CREATE CONSTRAINT TRIGGER trips_enforce_seats
    AFTER UPDATE OF participant_capacity ON trips
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW WHEN (NEW.participant_capacity < OLD.participant_capacity)
    EXECUTE FUNCTION trips_check_confirmed_seats();
"""

REVERSE = r"""
DROP TRIGGER IF EXISTS participants_enforce_seats ON trip_participants;
DROP TRIGGER IF EXISTS trips_enforce_seats ON trips;
DROP FUNCTION IF EXISTS trips_check_confirmed_seats();
"""


class Migration(migrations.Migration):
    dependencies = [("trips", "0005_unique_title_and_no_overlap")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
