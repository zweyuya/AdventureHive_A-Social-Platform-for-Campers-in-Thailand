#!/usr/bin/env bash
# Creates the production .env for Docker. Never overwrites an existing .env.
#   Usage:  bash deploy/docker/make-env.sh adventurehive-tlc.southeastasia.cloudapp.azure.com
set -euo pipefail
DOMAIN="${1:?Give the DNS name of the server}"
cd "$(dirname "$0")/../.."
if [ -f .env ]; then
  echo ".env already exists, leaving it unchanged."
  exit 0
fi
rand() { python3 -c "import secrets; print(secrets.token_urlsafe($1))"; }
FERNET="$(python3 -c 'import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"
cat > .env <<ENV
DOMAIN=$DOMAIN
POSTGRES_PASSWORD=$(rand 24)
DEBUG=False
SECRET_KEY=$(rand 50)
ALLOWED_HOSTS=$DOMAIN
CSRF_TRUSTED_ORIGINS=https://$DOMAIN
CORS_ALLOWED_ORIGINS=https://$DOMAIN
FIELD_ENCRYPTION_KEY=$FERNET
JWT_COOKIE_SECURE=True
SECURE_SSL_REDIRECT=True
ENV
chmod 600 .env
echo "Created .env for $DOMAIN. Keep it secret and back up FIELD_ENCRYPTION_KEY."
