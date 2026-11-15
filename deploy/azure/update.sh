#!/usr/bin/env bash
# Run on the VM after uploading or pulling new code. Never touches .env or the database contents.
set -euo pipefail
cd "$(dirname "$0")/../.."
.venv/bin/pip install -r requirements.txt -q
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py collectstatic --noinput -v0
sudo systemctl restart adventurehive
echo "Updated. Check the site in your browser."
