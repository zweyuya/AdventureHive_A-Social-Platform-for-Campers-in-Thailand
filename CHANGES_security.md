# Security round: what changed and what was added

Date: 2026-10-26 · Professor's feedback #3 (authorization, CSRF, sensitive data)

The security features themselves were mostly built already. This round adds **one bug fix**, **one new privacy feature**, **a test that proves the authorization rules**, and the presentation document (`PRESENTATION_security.md`).

## 1. Bug fix: deleting a private group made its trips public

**Problem:** trips point to their group with `on_delete=SET_NULL`, and privacy was decided only by the group. When a private group was deleted, its trips lost their group and became visible and joinable by everyone.

**Fix:**
1. `communities/services.py` → `delete_group()`: for a **private** group, first:
   - **cancel** its upcoming trips (draft/published/full) through the normal `cancel_trip()`, so everyone who joined is **notified**
   - mark **all** its trips `members_only = True`
   - then delete the group (public groups behave as before)
2. `trips/models.py` → new field **`Trip.members_only`** (boolean, default `False`).
3. `trips/views.py` → `visible_trips()`: a members-only trip is visible only to its **organizer**, people who **joined** it, and staff. Logged-out users get `404`.
4. `trips/admin.py` → `members_only` shown (read-only) and filterable.

## 2. New feature: opt-in emergency contact sharing

**Why:** emergency contacts were readable by **nobody** but the owner, so they couldn't help in an emergency. Now the owner can **choose** to share with the trip organizer, for that trip only.

| # | What | Where |
|---|---|---|
| 1 | `TripParticipant.share_emergency_contact` (boolean, default `False`). Reset when someone leaves and re-joins | `trips/models.py`, `trips/services.py` (`rsvp`) |
| 2 | New table **`emergency_contact_accesses`** (`EmergencyContactAccess`): trip, organizer, participant, time. Audit log only: it never stores the contact | `trips/models.py` |
| 3 | `emergency_window()`: from **1 day before the start to 1 day after the end** | `trips/services.py` |
| 4 | `set_emergency_sharing()`: only **confirmed/attended** participants who **have** a contact can share | `trips/services.py` |
| 5 | `read_emergency_contacts()`: organizer only, inside the window only; logs **every** read; notifies the participant **once per trip** | `trips/services.py` |
| 6 | `POST/DELETE /api/trips/{id}/emergency-sharing/` (participant: share / stop) | `trips/views.py` |
| 7 | `GET /api/trips/{id}/emergency-contacts/` (**organizer only**, admins get 403) | `trips/views.py`, `trips/serializers.py` (`SharedEmergencyContactSerializer`) |
| 8 | Trip details include `emergency`: window dates, `is_open`, `i_share`, `i_have_contact` | `trips/serializers.py` |
| 9 | New notification type `emergency_contact_viewed`: *"Ploy (organizer of …) opened the emergency contact you shared."* | `notifications/models.py`, `notifications/serializers.py` |
| 10 | Django admin: **Emergency contact accesses** (read-only, can't be edited or deleted); "share" column in a trip's participant list | `trips/admin.py` |
| 11 | Trip page, participant: **"Emergency contact"** card with Share / Stop sharing, or a link to add a contact first | `frontend/src/pages/TripDetail.jsx` (`EmergencyShareCard`) |
| 12 | Trip page, organizer: **"Emergency contacts"** button in Organizer tools. Loads **only on click**, opens a list with tap-to-call numbers; outside the window it shows when it will open | `frontend/src/pages/TripDetail.jsx` (`EmergencyContacts`) |

## 3. Authorization matrix test

`tests/test_authorization_matrix.py` (60 tests):
- **10 actions × 5 roles** (not logged in, other member, participant, organizer, admin). Each cell logs in as that role, calls the real API and checks the exact status code (200 / 401 / 403).
- **Meeting point** is included only for the organizer and participants (5 checks).
- **Public profile** never contains email/phone/birth date/gender, for any role (5 checks).
- It found **no permission bugs**: all cells matched on the first run, except two expectations of mine (cancel returns 200, not 204), which I corrected in the table.

## 4. Other new tests

`tests/test_security_privacy.py` (9 tests): the private-group fix (and that public groups are unchanged), plus emergency sharing: only shared contacts are visible, every read logged, one notification, stop sharing, closed outside the window, admins and other participants blocked, sharing needs a contact and a confirmed seat, re-joining resets.

## 5. Database migrations

| Migration | Contents |
|---|---|
| `trips/migrations/0004_members_only_and_emergency_sharing.py` | `Trip.members_only`, `TripParticipant.share_emergency_contact`, `EmergencyContactAccess` table |
| `notifications/migrations/0003_emergency_contact_viewed.py` | new notification type (choices only) |

Already applied to the local development database. Teammates run `python manage.py migrate`.

## 6. Documents

| File | For |
|---|---|
| `PRESENTATION_security.md` | Presenting feedback #3: numbered explanation, authorization matrix, CSRF diagram, sensitive-data table, demo script, evidence |
| `CHANGES_security.md` | This file: what changed in the code |

## Not changed

- The CSRF protection, cookies, encryption and permission classes were already correct. They're **documented and proven** now, not rewritten.
- No change for public groups, normal trips or existing endpoints. All earlier tests still pass.
