# AdventureHive — Backend (Layers 0–2)

Camping community platform for Thailand. Django 5.2 + DRF + PostgreSQL.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# PostgreSQL (once)
sudo -u postgres psql -c "CREATE ROLE adventurehive LOGIN PASSWORD 'devpass' CREATEDB;"
sudo -u postgres psql -c "CREATE DATABASE adventurehive OWNER adventurehive;"

cp .env.example .env          # then set SECRET_KEY and FIELD_ENCRYPTION_KEY
python manage.py migrate
python manage.py seed_interest_tags
python manage.py seed_campsites      # 15 real Thai campsites (safe to re-run)
python manage.py createsuperuser   # asks for email, not username
python manage.py runserver
```

| URL | What |
|---|---|
| `/admin/` | Django admin (moderator UI) |
| `/api/docs/` | Swagger UI |
| `/api/schema/` | OpenAPI schema |
| `/api/health/` | Liveness check (Django + DB) |

Run tests: `pytest` (needs PostgreSQL — the triggers and constraints are PostgreSQL features; the test user needs `CREATEDB`).

## Apps

| App | Tables |
|---|---|
| `core` | shared: timestamps, `ExperienceLevel`, Thailand bounding box, `EncryptedTextField`, pagination |
| `accounts` | users, profiles, interest_tags, profile_interest_tags, emergency_contacts |
| `locations` | authorities, locations (+ submission workflow), location_revisions |
| `communities` | groups (`CampingGroup`), group_members |
| `trips` | trips, trip_equipment_items, trip_participants |
| `reviews` | reviews + review-gate triggers |
| `qa` | questions, answers (Q&A forum) |
| `social` | posts, comments, likes, follows |
| `notifications` | notifications |

Not modelled yet (future work): messaging (conversations, messages), media uploads, shares, semantic-search embeddings (pgvector).

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
| Trip can never exceed capacity | `CHECK confirmed_count <= participant_capacity` |
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
| GET | `/api/campsites/` | anyone | Published only. Filters: `province`, `category` (repeatable), `has_water_source`, `has_restrooms`, `fire_pit_allowed`, `permit_status`, `min_rating`; `search=`; `ordering=name,-avg_rating,…`; 20 per page |
| GET | `/api/campsites/{id}/` | anyone | Detail with authority (booking URL) and permit info. Submitters also see their own unpublished ones |
| GET | `/api/map/campsites/` | anyone | GeoJSON `FeatureCollection` for the map (same filters, not paginated) |
| GET | `/api/campsites/{id}/history/` | anyone | Approved versions: who changed what, when, full snapshot |
| POST | `/api/campsites/` | member | Create a **draft** (not public) |
| PATCH/PUT | `/api/campsites/{id}/` | submitter | Only while draft or rejected |
| POST | `/api/campsites/{id}/submit/` | submitter | draft/rejected → pending_review |
| GET | `/api/campsites/mine/` | member | Own submissions with status and moderator's note |
| POST | `/api/campsites/{id}/revisions/` | member | Suggest an edit to a published campsite (any fields + `edit_summary`) |
| POST | `/api/campsites/{id}/approve/` | staff | pending_review → published (version 1) |
| POST | `/api/campsites/{id}/reject/` | staff | `{"note": "..."}` required → rejected |
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

**Moderating in the Django admin** (`/admin/` → Locations):
- *Locations* → filter **Status: Pending review** → select → action **Approve selected** or
  **Reject selected (with reason)** (asks for the reason on the next page).
- *Location revisions* → filter **Status: Pending** → approve / reject suggested edits.
- Editing a published campsite directly in the admin also creates a new version.

**Seed data:** `seed_campsites` loads 15 real campsites in 14 provinces with their managing
authorities. Coordinates are approximate and permit information is marked *unverified*
(`permit_status = unknown`) until someone checks with the park office.

## Next layers
1. ~~Auth & profile endpoints~~ ✅ done.
2. ~~Campsites & content workflow~~ ✅ done.
3. Groups (optional for the progress report).
4. Trips: CRUD, status lifecycle, RSVP with `select_for_update`, waitlist promotion, completion command, organizer attendance marking.
5. Reviews + Q&A endpoints.
