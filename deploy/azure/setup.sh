#!/usr/bin/env bash
# One-time setup of AdventureHive on a fresh Ubuntu 24.04 Azure VM.
#   Usage (on the VM, inside the project folder):  bash deploy/azure/setup.sh <your-dns-name>
#   e.g. bash deploy/azure/setup.sh adventurehive-tlc.southeastasia.cloudapp.azure.com
# Safe to re-run. It never overwrites an existing .env.
set -euo pipefail

DOMAIN="${1:?Give the DNS name of the VM, e.g. adventurehive-tlc.southeastasia.cloudapp.azure.com}"
APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
APP_USER="$(whoami)"
echo "==> Project: $APP_DIR   user: $APP_USER   domain: $DOMAIN"

echo "==> 1/7 System packages"
sudo apt-get update -y
sudo apt-get install -y python3-venv python3-dev build-essential libpq-dev postgresql nginx certbot python3-certbot-nginx

echo "==> 2/7 PostgreSQL database"
if [ ! -f "$APP_DIR/.env" ]; then
  DB_PASS="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
  sudo -u postgres psql -v ON_ERROR_STOP=1 -c "DO \$\$ BEGIN
      IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'adventurehive') THEN
        CREATE ROLE adventurehive LOGIN PASSWORD '$DB_PASS';
      ELSE ALTER ROLE adventurehive PASSWORD '$DB_PASS'; END IF; END \$\$;"
  sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='adventurehive'" | grep -q 1 \
    || sudo -u postgres createdb -O adventurehive adventurehive
fi

echo "==> 3/7 Python environment"
cd "$APP_DIR"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q

echo "==> 4/7 Production settings (.env)"
if [ -f .env ]; then
  echo "    .env already exists: leaving it unchanged."
else
  SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')"
  FERNET="$(.venv/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
  cat > .env <<ENV
DEBUG=False
SECRET_KEY=$SECRET
DATABASE_URL=postgres://adventurehive:$DB_PASS@localhost:5432/adventurehive
ALLOWED_HOSTS=$DOMAIN
CSRF_TRUSTED_ORIGINS=https://$DOMAIN
CORS_ALLOWED_ORIGINS=https://$DOMAIN
FIELD_ENCRYPTION_KEY=$FERNET
JWT_COOKIE_SECURE=True
SECURE_SSL_REDIRECT=True
ENV
  chmod 600 .env
  echo "    Created .env (keep it secret; back up FIELD_ENCRYPTION_KEY)."
fi

echo "==> 5/7 Database tables, static files, demo data"
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py collectstatic --noinput -v0
.venv/bin/python manage.py seed_interest_tags
.venv/bin/python manage.py seed_campsites
.venv/bin/python manage.py seed_demo
mkdir -p media
chmod o+x "$HOME" "$APP_DIR"   # let nginx read static/ and media/

echo "==> 6/7 Gunicorn service"
sed -e "s#__APP_DIR__#$APP_DIR#g" -e "s#__APP_USER__#$APP_USER#g" deploy/azure/adventurehive.service \
  | sudo tee /etc/systemd/system/adventurehive.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now adventurehive
sudo systemctl restart adventurehive

echo "==> 7/7 Nginx + HTTPS certificate"
sed -e "s#__APP_DIR__#$APP_DIR#g" -e "s#__DOMAIN__#$DOMAIN#g" deploy/azure/nginx.conf \
  | sudo tee /etc/nginx/sites-available/adventurehive >/dev/null
sudo ln -sf /etc/nginx/sites-available/adventurehive /etc/nginx/sites-enabled/adventurehive
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email --redirect \
  || echo "!! HTTPS certificate failed. Check that ports 80 and 443 are open in Azure, then run: sudo certbot --nginx -d $DOMAIN"

echo
echo "Done. Open https://$DOMAIN/ps4/  (admin: https://$DOMAIN/admin/)"
echo "Next: .venv/bin/python manage.py createsuperuser"
