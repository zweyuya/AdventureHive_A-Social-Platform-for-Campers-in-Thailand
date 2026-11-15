# Deploying AdventureHive with Docker (Azure VM)

Stack: PostgreSQL 16 + Django/Gunicorn + Caddy (automatic HTTPS). Data is kept in Docker volumes.

## First deployment
On the VM (Ubuntu 24.04, ports 22/80/443 open, DNS name label set):
```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER        # then log out and SSH in again
git clone -b main https://github.com/zweyuya/AdventureHive_A-Social-Platform-for-Campers-in-Thailand.git adventurehive
cd adventurehive
bash deploy/docker/make-env.sh <DNS-NAME>
docker compose up -d --build
docker compose exec web python manage.py seed_interest_tags
docker compose exec web python manage.py seed_campsites
docker compose exec web python manage.py seed_demo
docker compose exec web python manage.py createsuperuser
```
Open `https://<DNS-NAME>/ps4/` (the certificate can take a minute the first time).

## Updating
```bash
cd ~/adventurehive && git pull && docker compose up -d --build
```
Migrations and static files run automatically when the web container starts.

## Useful commands
| What | Command |
|---|---|
| Status | `docker compose ps` |
| App logs | `docker compose logs web --tail 50` |
| HTTPS / Caddy logs | `docker compose logs caddy --tail 50` |
| Reset demo posts | `docker compose exec web python manage.py seed_demo_posts --reset` |
| Restart | `docker compose restart web` |

Never run `docker compose down -v`, and never replace `.env` on the server: `-v` deletes the database
and uploaded photos, and a new `.env` changes the encryption key and database password.
