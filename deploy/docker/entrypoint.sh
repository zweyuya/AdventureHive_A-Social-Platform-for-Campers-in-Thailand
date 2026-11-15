#!/bin/sh
# Runs every time the web container starts: wait for PostgreSQL, apply migrations, collect static files.
set -e
echo "Waiting for the database..."
python - <<'PY'
import os, time, psycopg
url = os.environ["DATABASE_URL"]
for attempt in range(60):
    try:
        psycopg.connect(url).close()
        break
    except psycopg.OperationalError:
        time.sleep(1)
else:
    raise SystemExit("Database not reachable after 60 s")
PY
python manage.py migrate --noinput
python manage.py collectstatic --noinput -v0
exec "$@"
