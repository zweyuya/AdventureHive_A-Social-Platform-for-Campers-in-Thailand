"""
Database-level review gate (PostgreSQL triggers).

Django cannot express "the reviewer must be an ATTENDED participant of a
COMPLETED trip" as a constraint, so it is enforced here. This runs no matter
which code path writes to the table (API, admin, shell, raw SQL).

1. reviews_enforce_attended  (BEFORE INSERT OR UPDATE ON reviews)
   - author must have status 'attended' on that trip
   - the trip must be 'completed'
   - the organizer cannot review their own trip
   - reviews.location_id must equal trips.location_id
   - (trip_id, user_id) cannot be changed after creation

2. participants_protect_reviewed  (BEFORE UPDATE ON trip_participants)
   - a participant who has written a review cannot be moved away from
     'attended', so a review never loses its proof of attendance.
     (Deletes are allowed so cascading trip/account deletion still works;
     the review is deleted in the same cascade.)
"""
from django.db import migrations

FORWARD = r"""
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

    SELECT status, location_id, organizer_id
      INTO t_status, t_location, t_organizer
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
            NEW.location_id, t_location
            USING ERRCODE = 'check_violation';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM trip_participants
         WHERE trip_id = NEW.trip_id AND user_id = NEW.user_id AND status = 'attended'
    ) THEN
        RAISE EXCEPTION 'review_gate: user % did not attend trip %', NEW.user_id, NEW.trip_id
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER reviews_enforce_attended
    BEFORE INSERT OR UPDATE ON reviews
    FOR EACH ROW EXECUTE FUNCTION reviews_enforce_attended();


CREATE OR REPLACE FUNCTION participants_protect_reviewed() RETURNS trigger AS $$
BEGIN
    IF OLD.status = 'attended'
       AND NEW.status <> 'attended'
       AND EXISTS (SELECT 1 FROM reviews
                    WHERE trip_id = OLD.trip_id AND user_id = OLD.user_id) THEN
        RAISE EXCEPTION 'review_gate: participant % has reviewed trip %; remove the review first',
            OLD.user_id, OLD.trip_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER participants_protect_reviewed
    BEFORE UPDATE ON trip_participants
    FOR EACH ROW EXECUTE FUNCTION participants_protect_reviewed();
"""

REVERSE = r"""
DROP TRIGGER IF EXISTS participants_protect_reviewed ON trip_participants;
DROP FUNCTION IF EXISTS participants_protect_reviewed();
DROP TRIGGER IF EXISTS reviews_enforce_attended ON reviews;
DROP FUNCTION IF EXISTS reviews_enforce_attended();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("reviews", "0001_initial"),
        ("trips", "0001_initial"),
    ]

    operations = [migrations.RunSQL(FORWARD, REVERSE)]
