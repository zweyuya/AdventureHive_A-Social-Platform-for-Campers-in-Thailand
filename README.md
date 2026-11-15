# AdventureHive

A camping community platform for Thailand: find campsites on a map, join groups, organise
trips with RSVP and a waitlist, check in with a trip code, and read reviews written **only
by people who really attended**.

**Stack:** Django 5.2 + Django REST Framework + PostgreSQL (backend) · React 18 + Vite +
Tailwind CSS + Leaflet/OpenStreetMap (frontend) · pytest (550+ tests).

**Team:** The Layer Cake — Zwe Yu Ya Kyaw Zin Oo (st125990), Imtiaz Ahmad (st126685) · FSAD 2026, AIT

## Live site

| What | URL |
|---|---|
| The app | https://adventurehive.indonesiacentral.cloudapp.azure.com/ |
| User research pages (PS3: personas, scenarios, findings, requirements, MVP) | https://adventurehive.indonesiacentral.cloudapp.azure.com/ps4/ |
| Clickable prototype used in the user sessions | https://adventurehive.indonesiacentral.cloudapp.azure.com/ps4/prototype/ |
| Django admin | https://adventurehive.indonesiacentral.cloudapp.azure.com/admin/ |

Demo login: `nok@demo.adventurehive.test` / `DemoCamp123!` (fictional demo data; see
[Demo data](#demo-data)).

## Main features

| Area | What it does |
|---|---|
| Accounts | Register with PDPA consent, email login (JWT in httpOnly cookies + CSRF), profiles with photo, encrypted emergency contact, account deletion |
| Campsites | Map and list with filters, campsite pages with rating breakdown, Q&A, version history; members suggest campsites and edits, moderators approve or reject (with a reason); map pins checked against Thai province boundaries; permit box with fees, how to get the permit, the managing park office (call / book buttons), rules, and a "checked by a moderator" date that warns when it's over a year old; submitted campsites show straight away as **"Not yet verified"** (grey map pin), but trips, questions, reviews and edits only open once a moderator approves them |
| Groups | Public and private groups, admin / co-admin / member roles, post approval in private groups |
| Trips | Create, publish, edit and cancel trips; RSVP with automatic waitlist and promotion (row lock, safe under concurrency); meeting point shown only to people going; one active trip per title and no overlapping trips per organizer; straight-line distance from the meeting point to the campsite, with Car / On foot / Bike directions in OpenStreetMap; duplicate-trip errors link to the trip that's in the way; "Repeat this trip" copies a completed trip and lets its past attendees join first for 48 h; a "Trips organised" dashboard (account menu) shows every trip you run and what needs doing |
| Attendance | 6-digit check-in code (from 2 h before the start to 24 h after the end); organizer records attended / no-show, with a reason if someone did not check in; suspicious trips are flagged and admins notified; a no-show can appeal to an admin |
| Reviews | Only attended participants of completed trips can review (API **and** database trigger); badges show how attendance was recorded ("Verified attendee · checked in", "Marked as attended by organizer", "Marked as attended by an admin (appeal)"), and the page says organizers can't edit or remove reviews; members can report reviews; each person's newest review counts once in the rating; optional organizer rating, shown as an organizer's average on trip pages and profiles (only hard-to-fake trips count) |
| Social | Feed, trip posts, comments, reactions, notifications; a reminder to share a recap 2 days after a trip; "Helpful" votes on Q&A answers |
| Privacy | Opt-in emergency contact sharing with the organizer (1 day before to 1 day after the trip), every view logged |

## Setup (first time)

You need **Python 3.10+**, **PostgreSQL 14+** and **Node.js 18+**.

### 1. Backend

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Database (once)

```bash
psql postgres -c "CREATE ROLE advhiveuser LOGIN PASSWORD 'devpass' CREATEDB;"
psql postgres -c "CREATE DATABASE advhive_db OWNER advhiveuser;"
```

(On Linux, run these as `sudo -u postgres psql -c "…"`.)

`CREATEDB` is needed so `pytest` can create its own test database. Any role and database
name work, as long as they match `DATABASE_URL` in `.env`.

### 3. Environment file

```bash
cp .env.example .env
```

Then edit `.env`:
- `DATABASE_URL=postgres://advhiveuser:devpass@localhost:5432/advhive_db`
- `SECRET_KEY`: any long random string, e.g. from
  `python -c "import secrets; print(secrets.token_urlsafe(50))"`
- `FIELD_ENCRYPTION_KEY`: from
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

### 4. Create the tables and load data

```bash
python manage.py migrate
python manage.py seed_interest_tags
python manage.py seed_campsites       # 15 real Thai campsites; needed: the demo trips use Lam Ta Khong
python manage.py seed_demo            # demo users (Ploy, Nok, Beam, June, Mint …), groups, trips, reviews, posts
python manage.py tidy_demo_accounts   # optional: full Thai names for demo users, removes old test accounts (--dry-run to preview)
python manage.py createsuperuser      # asks for email, not username
```

`migrate` also turns on the PostgreSQL `btree_gist` extension (used by the
"no overlapping trips" rule). If your database user is not allowed to, run
`CREATE EXTENSION btree_gist;` once as the `postgres` superuser.

### 5. Run it (two terminals)

```bash
# Terminal 1: backend (http://localhost:8000)
python manage.py runserver

# Terminal 2: frontend (http://localhost:5173)
cd frontend
npm install        # first time only
npm run dev
```

Open **http://localhost:5173**. Vite forwards `/api`, `/admin` and `/ps4` to Django, so the
browser sees one site.

| URL | What |
|---|---|
| http://localhost:5173 | The app |
| http://localhost:8000/admin/ | Django admin (moderator UI: approve campsites, hide reviews, flagged trips) |
| http://localhost:8000/ps4/ | User research pages (PS3), no login needed |
| http://localhost:8000/api/docs/ | Swagger UI |
| http://localhost:8000/api/schema/ | OpenAPI schema |
| http://localhost:8000/api/health/ | Liveness check (Django + DB) |

## Demo data

After `seed_demo`, log in as any of these with the password **`DemoCamp123!`**:
`nok`, `ploy`, `mint`, `palm`, `tono`, `june`, `jee`, `beam` `@demo.adventurehive.test`
(e.g. `ploy@demo.adventurehive.test`). See [`frontend/README.md`](frontend/README.md) for
what each account shows.

`kai@demo.adventurehive.test` is a **campsite moderator**. In the account menu, *Campsite
moderation* opens the queue, with two submissions waiting (one is a possible duplicate).

### Review demo scenario (check-in → attendance → verified review)

```bash
python manage.py demo_checkin_trip    # for the review demo scenario
```

Creates **"Khao Yai Overnight (just finished)"**: organised by Ploy at Lam Ta Khong, ended
2 hours ago, with Nok, Beam and June confirmed. Check-in stays open for about 22 more hours.
It prints the trip link and the check-in code. Then:

1. Log in as **ploy**: the trip page shows the 6-digit check-in code.
2. Log in as **nok**: enter the code → checked in.
3. Log in as **ploy**: *Record attendance*. Nok is pre-ticked; Beam needs a reason (did not
   check in); mark June as a no-show.
4. Log in as **nok**: *Write a review* → badge "Verified attendee · checked in".
5. Log in as **june**: trying to review is refused (no-show).

Running it again **deletes the previous demo trip and its reviews** and creates a fresh one
(only that exact trip by the demo Ploy; nothing else is touched). Run it about an hour before
a presentation, and again just before if you tested the flow.

Note: check-in only opens **2 hours before** a trip starts. For a normal trip created in the
app, the organizer will not see the code before that.

### Start again with a clean database

```bash
python manage.py flush                # deletes ALL data (asks for "yes")
python manage.py seed_interest_tags
python manage.py seed_campsites
python manage.py seed_demo
python manage.py createsuperuser
```

### Finishing trips

`python manage.py complete_trips` marks trips whose end time has passed as `completed`
and, 2 days after a trip, reminds the people who attended to share a recap (once per trip, after
attendance is recorded; not to people who already posted). In production, run it every 15 minutes with cron; see Layer 4 below).

## Tests

```bash
pytest                                   # all tests (about 9-14 minutes)
pytest tests/test_ps4.py -q              # the /ps4/ research pages (21 tests)
pytest tests/test_layer4_concurrency.py  # 20 users racing for the last seat
pytest tests/test_duplicate_trips.py     # duplicate-trip rules
pytest -m unit                           # fast unit tests only, no database
```

Tests need PostgreSQL: several rules (constraints, triggers, row locks, exclusion
constraints) only exist there. The database user needs `CREATEDB`.

## Deployment (Azure + Docker)

The live site runs on a Microsoft Azure virtual machine (Azure for Students, Ubuntu 24.04,
Standard B2als v2) with Docker Compose. The CSIM course server could only be reached from the
AIT campus network, so remote interview participants could not open it; the TA approved using
another server.

| Container | Role |
|---|---|
| `db` | PostgreSQL 16; data in the `pgdata` volume |
| `web` | Django + Gunicorn; runs `migrate` and `collectstatic` on start (`deploy/docker/entrypoint.sh`) |
| `caddy` | Automatic HTTPS (Let's Encrypt); serves the built React app at `/`, static files and uploads (`media` volume); forwards `/api`, `/admin` and `/ps4` to Django |

The React app is built inside the Caddy image (`deploy/docker/caddy.Dockerfile`), so the server
needs only Docker and git. Settings come from a server-only `.env` file created once by
`deploy/docker/make-env.sh`; it is never committed.

**First-time data on the server**

```bash
docker compose exec web python manage.py seed_interest_tags
docker compose exec web python manage.py seed_campsites
docker compose exec web python manage.py seed_demo
docker compose exec web python manage.py seed_demo_posts
docker compose exec web python manage.py createsuperuser
```

**Update the live site** after pushing to `main`:

```bash
cd ~/adventurehive
git pull
docker compose up -d --build
```

Uploaded photos (`media`) and the database (`pgdata`) are kept across rebuilds. **Never run
`docker compose down -v`**: the `-v` deletes both volumes. Photos uploaded locally are not copied
to the server (they live in your local `media/` folder and database). More detail:
[`deploy/docker/README.md`](deploy/docker/README.md).

## User research pages (Problem Set 3)

The `ps4` Django app publishes the user research for the course at `/ps4/`: an index, three
persona profile pages (Mai the weekend camper, Krit the trip organizer, Fah the first-time
camper), four usage scenarios, findings, the role/permission matrix and user stories, the
revised MVP, and the clickable prototype used in the sessions. Pages are plain Django views
and templates, public and login-free.

| File | Purpose |
|---|---|
| `ps4/content.py` | All page content: participants (codes only), findings, personas, scenarios, permissions, user stories, decisions, MVP. Edit this file to update the pages |
| `ps4/views.py`, `ps4/urls.py` | Views and routes (`personas/<slug>/`, `scenarios/<slug>/`, `findings/`, `requirements/`, `mvp/`, `prototype/`) |
| `ps4/templates/ps4/` | Templates |
| `ps4/static/ps4/prototype/` | Screenshots of the app (demo data) for the clickable prototype |
| `tests/test_ps4.py` | Every page loads without login; links and prototype hotspots are valid |

Participants appear only as codes (P1–P4). Raw interview notes and survey responses are not
committed. The full PS3 report is submitted on Moodle; see [`ProbSet3/`](ProbSet3/).

## Project notes

Detailed write-ups (simple English) are in [`progress_report/`](progress_report/):

| File | Topic |
|---|---|
| `PRESENTATION_review_credibility.md` | Check-in code, two-sided attendance, flags, reports |
| `PRESENTATION_security.md`, `CHANGES_security.md` | Authorization, CSRF, sensitive data |
| `CHANGES_duplicate_trips.md` | One active title / no overlapping trips per organizer |
| `NOTES_campsite_pin_checks.md` | Map pin and province checks |
| `updateddb_v2.txt` | Current database design (DBML, 24 tables) |

## Apps

| App | Tables |
|---|---|
| `core` | shared: timestamps, `ExperienceLevel`, Thailand bounding box, `EncryptedTextField`, pagination |
| `accounts` | users, profiles, interest_tags, profile_interest_tags, emergency_contacts |
| `locations` | authorities, locations (+ submission workflow), location_revisions |
| `communities` | groups (`CampingGroup`), group_members |
| `trips` | trips, trip_equipment_items, trip_participants (check-in and attendance evidence), attendance_appeals, emergency_contact_accesses |
| `reviews` | reviews, review_reports + review-gate triggers |
| `qa` | questions, answers (Q&A forum) |
| `social` | posts, comments, reactions, follows |
| `notifications` | notifications |

Not modelled yet (future work): messaging (conversations, messages), shares, semantic-search embeddings (pgvector).

## Design decisions in Layer 0

**Schema changes from the original DBML**
- Composite primary keys → surrogate `id` + `UniqueConstraint` (works with DRF and the admin).
- `users.password_hash` → Django's `password` (bcrypt via `BCryptSHA256PasswordHasher`).
- `locations` gains `province`, workflow `status`, `reviewed_by/at`, `moderation_note`, `current_version`; new `location_revisions` table for full version history.
- `trips` gains `confirmed_count` (denormalised, checked against capacity).
- `trip_participants` has no default status, and gains `attendance_marked_by/at`.
- `reviews` gains `status` (published/hidden) and `edited_at`.
- New `questions` / `answers` tables (Q&A forum).
- `notification_type` / `reference_type` extended for RSVP, workflow and Q&A events.
- `emergency_contacts` is one per user (matches `/api/users/{id}/emergency-contact/`).
- `groups` app renamed `communities` (clashes with Django's auth `Group`).

**Guarantees enforced by PostgreSQL (all covered by tests)**

| Rule | Mechanism |
|---|---|
| Trip can never exceed capacity | `CHECK confirmed_count <= participant_capacity` on the counter, and deferred triggers `participants_enforce_seats` / `trips_enforce_seats` that count the real confirmed rows at COMMIT |
| No duplicate RSVP | `UNIQUE (trip_id, user_id)` |
| Waitlist positions consistent | `CHECK` (waitlisted ⇔ position ≥ 1) + `UNIQUE (trip_id, waitlist_position) DEFERRABLE` so promotion can renumber in one transaction |
| `attended` / `no_show` only after attendance is recorded | `CHECK attendance_marked_at IS NOT NULL` |
| Only attended participants of completed trips can review; organizer can't review own trip; review location = trip location | trigger `reviews_enforce_attended` |
| A reviewer's attendance can't be revoked while the review exists | trigger `participants_protect_reviewed` |
| One review per trip per user, rating 1–5 | `UNIQUE`, `CHECK` |
| Coordinates inside Thailand | `CHECK` on locations and trip meeting points |
| Rejected submissions carry a reason | `CHECK moderation_note <> ''` |
| Only approved revisions have a version number | `CHECK` + `UNIQUE (location_id, version_no)` |
| No self-follow | `CHECK follower_id <> followee_id` |
| *attended* always has evidence: a check-in, or a written reason (organizer or admin) | `CHECK` on `verification_method` / `override_reason` |
| Only confirmed people can become attended / no-show | trigger `participants_attendance_rules` |
| Reviews only within 30 days of the trip, and not on trips an admin flagged | trigger `reviews_enforce_attended` (v2) |
| An organizer can't have two active trips with the same title (ignoring case and outer spaces) | partial `UNIQUE (lower(trim(title)), organizer_id)` on draft/published/full trips |
| An organizer can't lead two active trips at overlapping times | `EXCLUDE USING gist (organizer_id WITH =, tstzrange(start, end) WITH &&)` (needs `btree_gist`) |

**Security baseline**
- Email login, bcrypt hashes, non-active/deleted accounts cannot authenticate (`User.is_active`).
- `CookieJWTAuthentication`: JWT read from an httpOnly cookie, **CSRF enforced** on unsafe methods (double-submit `X-CSRFToken`), SameSite=Strict cookies; 15-min access / 7-day rotating refresh tokens with blacklist.
- Emergency contact name/phone encrypted with Fernet (`EncryptedTextField`); not registered in the admin.
- Secrets only from environment variables; HTTPS/HSTS switched on via `SECURE_SSL_REDIRECT=True` in production.

## Layer 1 — Auth & profile endpoints

| Method | Endpoint | Auth | Notes |
|---|---|---|---|
| GET | `/api/auth/csrf/` | none | Sets the `csrftoken` cookie. Call once when the app loads. |
| POST | `/api/auth/register/` | none | `email, password, display_name, camping_experience_level, interest_tag_ids[], pdpa_consent` — rejected unless `pdpa_consent` is `true` |
| POST | `/api/auth/login/` | none | Sets `ah_access` + `ah_refresh` httpOnly cookies; tokens never in the body |
| POST | `/api/auth/token/refresh/` | refresh cookie | New access token; refresh token rotated, old one blacklisted |
| POST | `/api/auth/logout/` | refresh cookie | Blacklists refresh token, clears cookies |
| DELETE | `/api/auth/account/` | yes + password | PDPA deletion: anonymises the account, deletes the emergency contact, revokes all tokens |
| GET | `/api/users/me/` | yes | Own full profile (email, phone, consent date…) |
| PUT / DELETE | `/api/users/me/avatar/` | yes | Upload (multipart `avatar`) or remove the profile photo; resized to 400×400 JPEG with metadata (GPS) stripped |
| GET | `/api/users/{id}/` | none | Public profile (no email/phone/birth date/gender) |
| PATCH | `/api/users/{id}/` | owner | Edit own profile; email/status/consent are read-only |
| GET/PUT/DELETE | `/api/users/{id}/emergency-contact/` | owner only | 403 for everyone else, **including admins** |
| GET | `/api/interest-tags/` | none | Tags for the registration form |

Login and register are throttled (10/min per client).

### Calling the API from React

```js
// once at startup
await fetch("/api/auth/csrf/", { credentials: "include" });

const csrf = () => document.cookie.match(/csrftoken=([^;]+)/)?.[1];

export function api(path, { method = "GET", body } = {}) {
  return fetch(path, {
    method,
    credentials: "include",                       // send the httpOnly JWT cookies
    headers: {
      "Content-Type": "application/json",
      ...(method !== "GET" && { "X-CSRFToken": csrf() }),  // CSRF double-submit
    },
    body: body && JSON.stringify(body),
  });
}
// On a 401: POST /api/auth/token/refresh/ once, then retry; if that fails, go to login.
```

Account deletion policy: personal data is erased, but the row stays as an anonymous
"Deleted user" so trips and reviews other people rely on stay consistent. (Layer 4 will
also cancel the user's active RSVPs and promote the waitlist.)

## Layer 2 — Campsites & content workflow

| Method | Endpoint | Who | Notes |
|---|---|---|---|
| GET | `/api/campsites/` | anyone | Published campsites and ones waiting for a moderator (`status: pending_review` = "Not yet verified"). Drafts and rejected ones stay private. Filters: `verified` (`true` = only checked), `province`, `category` (repeatable), `has_water_source`, `has_restrooms`, `fire_pit_allowed`, `permit_status`, `min_rating`; `search=`; `ordering=name,-avg_rating,…`; 20 per page |
| GET | `/api/campsites/{id}/` | anyone | Detail with authority (booking URL), permit info and `is_mine`. Unverified ones are visible to everyone; submitters also see their own drafts |
| GET | `/api/map/campsites/` | anyone | GeoJSON `FeatureCollection` for the map (same filters, not paginated); each feature has `verified` |
| GET | `/api/campsites/{id}/history/` | anyone | Approved versions: who changed what, when, full snapshot |
| POST | `/api/campsites/` | member | Create a **draft** (not public) |
| PATCH/PUT | `/api/campsites/{id}/` | submitter | Only while draft or rejected |
| POST | `/api/campsites/{id}/submit/` | submitter | draft/rejected → pending_review (public as "Not yet verified"). Limited to 10 per day per member |
| GET | `/api/campsites/mine/` | member | Own submissions with status and moderator's note |
| POST | `/api/campsites/{id}/revisions/` | member | Suggest an edit to a published campsite (any fields + `edit_summary`). Approving a change to permit information (authority, permit, `fees`, rules, booking link, source) updates `permit_info_verified_at` (cleared while the permit status is unknown) |
| GET | `/api/authorities/` | anyone | Park offices and other managers of campsites (name, type, phone, website, booking link), for the "Managed by" dropdown. Read-only |
| GET | `/api/campsites/moderation/` | moderator, staff | Pending submissions, oldest first, with pin check and campsites within 1 km |
| POST | `/api/campsites/{id}/approve/` | moderator, staff | pending_review → published (version 1). Refused if the pin is bad. A moderator can't decide their own submission |
| POST | `/api/campsites/{id}/reject/` | moderator, staff | `{"note": "..."}` required → rejected |
| GET | `/api/campsite-revisions/` | staff | Queue of pending suggested edits |
| POST | `/api/campsite-revisions/{id}/approve/` | staff | Applies the suggestion as version N+1 |
| POST | `/api/campsite-revisions/{id}/reject/` | staff | `{"note": "..."}` required |

**Workflow**

```
draft ──submit──▶ pending_review ──approve──▶ published (v1) ──suggested edit approved──▶ v2, v3 …
  ▲                     │
  └── edit & resubmit ◀─┴──reject (reason required)──▶ rejected
```

- Public endpoints and the map only ever read `status = published`.
- **Versioning:** full history for campsites. Every approved change (first approval,
  approved suggestion, or a moderator's direct edit in the admin) stores a complete
  snapshot with author, reviewer and summary in `location_revisions`.
- **Stale-edit protection:** a suggestion records the version it was based on; if the
  campsite has changed since, approval is refused so it can't silently undo a newer edit.
- Submitters get a notification when their submission/suggestion is approved or rejected.

**Campsite moderators** (`is_moderator`) review new submissions on the *Campsite moderation*
page in the app. They aren't staff: no Django admin, and nothing else an admin can do. To give
someone the role: `/admin/` → Users → select them → action **Make campsite moderator**.

**Moderating in the Django admin** (`/admin/` → Locations):
- *Locations* → filter **Status: Pending review** → select → action **Approve selected** or
  **Reject selected (with reason)** (asks for the reason on the next page).
- *Location revisions* → filter **Status: Pending** → approve / reject suggested edits.
- Editing a published campsite directly in the admin also creates a new version.

**Removing users in the admin:** there is no hard delete (it would skip seat updates). Select
users → action **Delete account** → confirm. This runs the same `delete_account` service as the
app: personal data erased, seats freed, waitlist promoted.

**Seed data:** `seed_campsites` loads 15 real campsites in 14 provinces with their managing
authorities. Coordinates are approximate and permit information is marked *unverified*
(`permit_status = unknown`) until someone checks with the park office.

## Layer 3 — Community groups

| Method | Endpoint | Who | Notes |
|---|---|---|---|
| GET | `/api/groups/` | anyone | Filters: `category`, `privacy_type`; `search=`; sorted by size. Includes `my_role` |
| GET | `/api/groups/{id}/` | anyone | |
| POST | `/api/groups/` | member | Creator becomes the group **admin** |
| PATCH / DELETE | `/api/groups/{id}/` | group admin | Deleting keeps the group's trips (group set to null) |
| POST / DELETE | `/api/groups/{id}/join/` | member | Join a **public** group / leave. The last admin can't leave |
| GET | `/api/groups/{id}/members/` | anyone (private: members only) | Active members |
| POST | `/api/groups/{id}/members/` | admin, co-admin | `{"user_id"}` — the only way into a private group |
| POST | `/api/groups/{id}/members/{user_id}/remove/` | admin, co-admin | Co-admins may remove ordinary members only |
| POST | `/api/groups/{id}/members/{user_id}/ban/` | admin | Banned users can't rejoin by themselves |
| POST | `/api/groups/{id}/members/{user_id}/role/` | admin | `{"role": "member" \| "co_admin" \| "admin"}`; at least one admin must remain |
| GET | `/api/groups/{id}/trips/` | anyone (private: members only) | The group's trips |
| GET | `/api/groups/mine/` | member | Groups I belong to |

- **In-group roles** (`role_in_group`) are separate from Django's platform roles and are
  checked by the `IsGroupAdmin` / `IsGroupModerator` permission classes.
- **member_count** counts active members only and is changed only inside a transaction with
  the group row locked, so it always matches the membership table (tested).
- Rejoining after leaving reuses the same membership row (`UNIQUE (group, user)`).
- Trips can be attached to a group only by its members; trips in private groups are
  visible to members only.
- Account deletion: the user leaves all groups; a sole admin is succeeded by the
  longest-standing co-admin, otherwise the longest-standing member.

## Layer 4 — Trips, RSVP, waitlist, attendance

| Method | Endpoint | Who | Notes |
|---|---|---|---|
| GET | `/api/trips/` | anyone | Upcoming published/full trips by default; `?status=completed` etc. Filters: `location`, `province`, `difficulty`, `min_experience_level`, `start_after`, `start_before`, `has_spots`; `search=` |
| GET | `/api/trips/{id}/` | anyone | Includes `my_status`, `my_waitlist_position`, `spots_left`, `waitlist_count`, `meeting_distance_km` (straight line to the campsite; hidden together with the meeting point). Exact meeting point only for the organizer and confirmed participants |
| POST | `/api/trips/` | member | Creates a **draft** at a published campsite. Optional `repeat_of_id` (my own completed trip): on publish, its attendees are invited and only they can join for 48 h (`priority` on the trip page). Duplicate errors include `conflicting_trip_id` |
| PATCH/PUT | `/api/trips/{id}/` | organizer | Raising capacity promotes the waitlist; date/place changes notify participants |
| DELETE | `/api/trips/{id}/` | organizer or moderator | **Cancels** the trip (never deleted); participants notified |
| POST | `/api/trips/{id}/publish/` | organizer | draft → published |
| POST | `/api/trips/{id}/rsvp/` | member | Join: `confirmed` if a seat is free, else `waitlisted` with a position. Rate-limited (10/min) |
| DELETE | `/api/trips/{id}/rsvp/` | participant | Leave: waitlist #1 is promoted automatically; positions renumbered |
| GET | `/api/trips/{id}/participants/` | organizer only | Admins get 403 too (participant privacy) |
| POST | `/api/trips/{id}/attendance/` | organizer | After completion, within 7 days: `{"records": [{"user_id": 5, "status": "attended", "reason": "…"}, …]}`. A `reason` is required for anyone marked attended who did not check in |
| GET | `/api/trips/{id}/check-in-code/` | organizer | The trip's 6-digit code (derived from `SECRET_KEY`, never stored). Only while check-in is open; otherwise 400 |
| POST | `/api/trips/{id}/attendance-appeal/` | participant marked no-show | `{"reason": "…"}`; once, within 14 days of the trip ending. An admin decides |
| POST | `/api/trips/{id}/check-in/` | confirmed participant | `{"code": "123456"}`; open from 2 h before the start to 24 h after the end; 5 tries/min |
| POST / DELETE | `/api/trips/{id}/emergency-sharing/` | participant | Share / stop sharing my emergency contact with the organizer |
| GET | `/api/trips/{id}/emergency-contacts/` | organizer | Shared contacts, only from 1 day before to 1 day after the trip; every read is logged and the participant is notified |
| GET | `/api/trips/mine/` | member | Trips I organise or joined |
| GET | `/api/trips/organised/` | member | My own trips for the "Trips organised" dashboard, with `waitlist_count`, `needs_attendance`, `attendance_due`, `open_appeals`, `flag_status`, `repeat_of` |
| GET/POST/PATCH/DELETE | `/api/trips/{id}/equipment/` | read: anyone · write: organizer | Equipment checklist |

**Status lifecycle** (one central `transition()` function rejects anything else):

```
draft ──publish──▶ published ◀── seats free / last seat taken ──▶ full
  │                    │                                           │
  └──────── cancel ────┴───────────────────────────────────────────┴──▶ cancelled
                       └──── end time passes (complete_trips) ─────┴──▶ completed
```

**How overbooking is prevented**
1. Every seat-changing operation (`rsvp`, `cancel_rsvp`, capacity edit) runs in
   `transaction.atomic()` and locks the trip row with `select_for_update()`.
   Concurrent requests for the same trip are processed one after another.
2. Database backstops: `CHECK (confirmed_count <= participant_capacity)`, a deferred trigger
   counting the real confirmed rows at COMMIT,
   `UNIQUE (trip_id, user_id)`, and a deferrable `UNIQUE (trip_id, waitlist_position)`.
3. `tests/test_layer4_concurrency.py` releases 20 threads at the same instant for one
   seat: exactly 1 confirmed, 19 waitlisted at positions 1–19. With the lock removed,
   the same test fails (requests collide on the same waitlist position).

**Attendance & review credibility**
- `python manage.py complete_trips` (schedule it, e.g. every 15 min with cron) marks
  finished trips `completed`. Confirmed participants stay *confirmed* (not automatically
  attended); anyone still waitlisted becomes *cancelled*; the organizer is reminded.
- The organizer then records **attended / no-show** within 7 days. Only *attended*
  participants can review (enforced by the API **and** the database trigger), and a
  reviewer's attendance can't be revoked afterwards.

**Design decision:** the organizer is not counted as a participant (capacity = seats for
people joining).

Cron example on the server:
```
*/15 * * * * cd /path/to/adventurehive && .venv/bin/python manage.py complete_trips
```

## Layer 5 — Verified reviews & Q&A forum

**Reviews**

| Method | Endpoint | Who | Notes |
|---|---|---|---|
| GET | `/api/campsites/{id}/reviews/` | anyone | Published reviews, newest first, with a verification badge (`check_in` or `organizer_only`) and whether it counts in the rating |
| POST | `/api/reviews/` | attended participant | `{"trip_id", "rating" 1–5, "review_text", "organizer_rating" 1–5 (optional)}`; campsite is taken from the trip. The organizer rating is only ever shown to its author |
| PATCH / DELETE | `/api/reviews/{id}/` | author | Within the review window; ratings recalculated |
| GET | `/api/reviews/mine/` | member | My reviews |
| POST | `/api/reviews/{id}/hide/` · `/restore/` | moderator | Hidden reviews leave the rating |
| POST | `/api/reviews/{id}/report/` | member | Report a review to the moderators (reason + note); 10/min |

Who may review: the trip is **completed**, the organizer marked you **attended**, you are
not the organizer, one review per trip, within **30 days** of the trip ending. Checked in
the API (clear error messages) *and* by the PostgreSQL trigger. `avg_rating` and
`review_count` are recalculated in the same transaction (campsite row locked).
`GET /api/trips/{id}/` returns `can_review` so the app knows when to show the button.

If someone reviewed the same campsite on several trips, only their **newest** review counts
in the rating (one person = one vote). An admin can flag a suspicious trip and hide all its
reviews; trips where most attendees, or 3 or more, were confirmed without a check-in are
flagged automatically, and admins are notified. Reviews with 3 or more open reports go to the
top of the moderation queue, and admins are notified.

**No-show appeals:** a participant marked as a no-show can appeal from the trip page. In the
admin: *Trips → Attendance appeals*, then **Approve** (marks them attended, badge "Marked as
attended by an admin (appeal)") or **Reject** (a reason is required and shown to them).

**Q&A forum**

| Method | Endpoint | Who | Notes |
|---|---|---|---|
| GET | `/api/questions/?location={campsite id}` | anyone | Filters: `location`, `status`, `unanswered`; `search=` |
| GET | `/api/questions/{id}/` | anyone | With answers |
| POST | `/api/questions/` | member | `{"location_id" (optional), "title", "body"}` |
| PATCH | `/api/questions/{id}/` | author | Sets `edited_at`, `last_edited_by` |
| POST | `/api/questions/{id}/answers/` | member | Asker is notified |
| PATCH | `/api/answers/{id}/` | author | Sets `edited_at` |
| POST / DELETE | `/api/answers/{id}/vote/` | member (not the author) | Mark as helpful / take it back; one vote per person. Answers show `helpful_count`, `i_found_helpful`; accepted first, then most helpful |
| POST | `/api/questions/{id}/accept/` | asker | `{"answer_id"}` → question `answered` |
| POST | `/api/questions/{id}/close/` | asker or moderator | No more answers |
| POST | `/api/questions/{id}/hide/` · `/restore/`, `/api/answers/{id}/hide/` · `/restore/` | moderator | Hiding the accepted answer re-opens the question |

Q&A is **post-moderated** (appears immediately; moderators hide abuse). Versioning:
current version + edited marker (no full history — single-author content).

## Notifications

`GET /api/notifications/` (latest 30 + unread count, with a readable message and an app link)
and `POST /api/notifications/read-all/` power the bell icon. `GET /api/reviews/` is the public
feed of recent verified reviews.

## End-to-end test

`tests/test_end_to_end.py` walks the whole demo flow through the public API only:
register (PDPA) → browse campsites & map → create/publish trip → RSVP → second user
waitlisted → cancel → automatic promotion → trip completes → organizer marks attendance →
verified review → campsite rating updated.

## Next layers
1. ~~Auth & profile endpoints~~ ✅ done.
2. ~~Campsites & content workflow~~ ✅ done.
3. ~~Community groups~~ ✅ done.
4. ~~Trips, RSVP, waitlist, attendance~~ ✅ done.
5. ~~Reviews + Q&A endpoints~~ ✅ done.
6. ~~React frontend~~ ✅ done.
7. ~~Review credibility (check-in, two-sided attendance, flags, reports), security hardening, duplicate-trip rules~~ ✅ done.
8. ~~Moderation page in the React app, no-show appeals~~ ✅ done.
9. ~~Deployment~~ ✅ done: Azure VM with Docker Compose and HTTPS (see [Deployment](#deployment-azure--docker)).
10. ~~User research, personas and requirements validation (PS3)~~ ✅ done: `/ps4/` pages.
11. Future work: keeping campers connected (follow, "you camped together", camping history);
    real-time messaging and semantic search stay out of scope this semester.
