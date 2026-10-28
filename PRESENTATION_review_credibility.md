# Review credibility: what we built and how to present it

**Professor's feedback:**
> *Review credibility: Clarify how attendance is verified and how the system prevents false attendance records or misleading reviews.*

**Our answer in one sentence:**
Only people who really went on a trip can review. They prove it **twice**: they enter the trip's check-in code, and the organizer confirms them. Then members can report bad reviews, admins can hide a whole suspicious trip, and each person counts only once in a campsite's rating.

---

## Part 1: How attendance is verified (step by step)

1. **A user joins a trip.** They become `confirmed` (or `waitlisted` if it's full).
2. **The organizer gets a 6-digit check-in code.** It appears on the trip page, for the organizer only.
   - The code is **not stored** in the database. It's calculated from the server's secret key, so someone reading the database can't see it.
3. **Check-in is open from 2 hours before the start until 24 hours after the end.**
   - 2 hours before: people can check in at the meeting point, which usually has phone signal.
   - 24 hours after: people who had **no signal at the campsite** can check in once they're home.
4. **Each participant types the code in their app.** This records `checked_in_at`.
   - Only `confirmed` participants can check in.
   - Wrong-code guesses are limited to **5 per minute**, so the code can't be guessed (1,000,000 possibilities).
5. **The trip ends.** Nobody becomes `attended` automatically just because time passed.
6. **The organizer records attendance** within **7 days**. After that, the list is locked.
   - People who checked in are **pre-selected** as "Attended".
   - The organizer marks each person **Attended** or **No-show**.
7. **Rule: "attended" needs both sides.**
   - **Normal case:** the participant checked in **and** the organizer confirms → `verification_method = check_in`.
   - **Forgot to check in** (phone died, no signal): the organizer can still mark them attended, but **must write a reason**. This is saved → `verification_method = organizer_only`.
   - **Checked in but then didn't come:** the organizer marks them **No-show**. A check-in alone proves nothing.
   - **Checked in late** (within 24 hours): an "organizer only" record is **upgraded** to "check_in".
8. **Everything is recorded (audit trail):** `checked_in_at`, `attendance_marked_by`, `attendance_marked_at`, `verification_method` and `override_reason`.
9. **The organizer gets an attendance page** that shows "✓ Checked in 08:20" or "Did not check in" for each person, plus a reason box that appears when needed.

## Part 2: How we prevent false attendance records

10. **Participants can never change their own status.** Status isn't writable in any API. It changes only through join, leave, check-in and attendance.
11. **Only confirmed people can become attended.** A waitlisted or cancelled person can **never** be marked attended. This is enforced by a **database trigger**, so even buggy code can't break it.
12. **Database rules (CHECK constraints) make the evidence required:**
    - an `attended` row must have a verification method
    - `check_in` must have a real `checked_in_at`
    - `organizer_only` must have a written reason
13. **Suspicious trips are flagged automatically.** If **more than half** of the attended people did **not** check in, the trip is marked **"Needs admin review"**. One forgotten check-in is normal; a whole trip of "organizer only" records looks like friends being marked.
14. **Admins can act on a suspicious trip** in the Django admin (Trips → select → Action):
    - **"Suspicious trip: hide all its reviews and block new ones"**: every review of that trip is hidden and removed from the campsite rating, and nobody can add new reviews to it (blocked by the database too).
    - **"Checked and OK: clear the flag and restore its reviews"**: restores **only** the reviews the flag hid. A review a moderator hid for another reason stays hidden.

## Part 3: How we prevent misleading reviews

15. **Who can review** (checked in the code **and** again by the database trigger):
    - marked **attended** on a **completed** trip
    - **not** the trip's organizer (conflict of interest)
    - within **30 days** after the trip ends, so experiences are fresh
    - the campsite is always taken **from the trip**, so you can't review a campsite you didn't visit
    - one review per person per trip
16. **Two badges show how strong the proof is:**
    - 🟢 **"Verified attendee · checked in"**: checked in with the code **and** confirmed by the organizer
    - ⚪ **"Confirmed by organizer"**: confirmed without a check-in
    - Each review also shows **"Visited Oct 2026"**, so readers know how recent the information is.
17. **One person counts once in the rating.** If someone camps at the same campsite 5 times and reviews 5 times, **only their newest review** counts toward the average. Older reviews are still shown, marked "Earlier visit: not counted in the rating".
18. **"Report" button on every review** (not on your own). Reasons: fake, misleading, offensive, spam, other.
    - One report per person per review, and at most 10 reports per minute.
    - Moderators see the reports in **Django admin → Review reports** and either:
      - **Hide the review** (removed from the rating, reports closed as "Review hidden"), or
      - **Dismiss** (the review stays, reports closed as "Dismissed").
    - The **Reviews** admin list shows an "Open reports" count for each review.
19. **Hidden reviews never count** toward the rating, which is recalculated immediately in the same database transaction.

## Part 4: What we're honest about (say this in the presentation)

20. **No system can make fake attendance impossible.** An organizer could give the code to a friend who didn't go. Our goal is to make it **hard, recorded and visible**:
    - **Prevented:** non-participants, waitlisted/cancelled people, organizers reviewing themselves, reviews after 30 days, reviewing the wrong campsite.
    - **Detected:** trips where most people didn't check in (automatic flag), and reviews that members report.
    - **Visible to readers:** the badge shows whether the reviewer checked in.
21. **Why not GPS?** Remote campsites often have no signal, and tracking location would conflict with our privacy design. The code works offline at the campsite (type it in later) and collects no location.
22. **Future work:** a participant who was wrongly marked "no-show" can dispute it, and an admin decides (feature #10, planned for the final version).

---

## Live demo script (about 3 minutes)

**Before the presentation**, run this so a trip that "just finished" exists. Check-in only stays open for 24 hours, so run it on the day:

```bash
python manage.py demo_checkin_trip
```

It prints the trip number and the code. Demo users' password: `DemoCamp123!`

1. **Log in as Ploy** (`ploy@demo.adventurehive.test`). Open the trip → the **"Trip check-in"** card shows the 6-digit code.
2. **Log in as Nok** in a private window. Open the same trip → type the code → **"✓ You checked in"**.
3. Optional: type a wrong code 6 times → "Too many tries" (rate limit).
4. **Back to Ploy** → **Record attendance**:
   - Nok is pre-selected (✓ checked in 08:20)
   - Mark **Beam** "Attended" → a **reason box** appears (he didn't check in) → type "Phone battery died"
   - Mark **June** "No-show"
   - Save
5. **Back to Nok** → "Write a review" → the campsite page shows the green **"Verified attendee · checked in"** badge.
6. On the **Pha Taem** campsite page, show a review with the grey **"Confirmed by organizer"** badge.
   - With a **fresh** demo database, Nok and Mint have the green badge and Tono has the grey one.
   - In a database seeded **before** this change, the old reviews show the grey badge, because those attendees were recorded before check-in codes existed. The migration labels them honestly instead of pretending they checked in.
7. Click **Report** on a review → choose "Misleading" → send.
8. **Django admin** (`localhost:8000/admin/`):
   - **Review reports** → select → "Hide the reported review" → the campsite rating changes
   - **Trips** → filter "Flag status" → select a trip → "Suspicious trip: hide all its reviews"

## Evidence: automated tests

| Test file | What it proves |
|---|---|
| `tests/test_review_credibility.py` (20 tests) | Check-in code (organizer-only, never stored, window, wrong code, rate limit), both-sides rule, forgot-to-check-in reason, checked-in-but-no-show, late check-in upgrade, automatic flag, admin flag and restore, newest-review-only rating, badges, report and moderation, 30-day rule in the database, demo command |
| `tests/test_layer0_constraints.py` | Database: attended needs evidence; waitlisted/cancelled can never become attended |
| `tests/test_layer0_review_gate.py` | Database trigger: only attended people of completed trips can review |
| `tests/test_end_to_end.py` | Whole journey through the API, now including **check-in with the code** |

Run them:
```bash
pytest tests/test_review_credibility.py -v
pytest
```

## Files changed (for the team)

| File | Change |
|---|---|
| `trips/models.py` | New fields: `checked_in_at`, `verification_method`, `override_reason` (participants); `checkin_salt`, `flag_status`, `flag_note`, `flagged_at` (trips). 2 new CHECK constraints |
| `trips/migrations/0002_…`, `0003_attendance_trigger.py` | New columns, backfill of old data, the "only confirmed → attended" trigger |
| `trips/services.py` | `checkin_code()`, `checkin_window()`, `check_in()`, new `mark_attendance()` (reasons), automatic flag |
| `trips/serializers.py`, `trips/views.py` | `GET /api/trips/{id}/check-in-code/` (organizer), `POST /api/trips/{id}/check-in/` (participant, 5/min), check-in info in trip details, reasons in attendance |
| `trips/admin.py` | Flag column and filter, "hide all reviews" and "clear flag" actions, check-in info per participant |
| `trips/management/commands/demo_checkin_trip.py` | New command for the live demo |
| `reviews/models.py` + migrations `0003`, `0004` | `ReviewReport` table, `hidden_reason`; trigger v2 (30 days + flagged trips, on new reviews only) |
| `reviews/services.py` | Newest-review-per-person rating, `report_review()`, `resolve_reports()`, `flag_trip_hide_reviews()`, `clear_trip_flag()` |
| `reviews/serializers.py`, `reviews/views.py` | `verification` and `counts_in_rating` on reviews, `POST /api/reviews/{id}/report/` (10/min) |
| `reviews/admin.py` | "Review reports" queue (hide / dismiss), open-report count |
| `frontend/src/pages/TripDetail.jsx` | "Trip check-in" card (code for the organizer, input for participants), new attendance panel |
| `frontend/src/pages/CampsiteDetail.jsx` | Two badge types, "Visited …", "not counted" note, Report button and form |
| `core/management/commands/seed_demo.py` | Demo data shows both badges, plus a "just finished" trip |
| `config/settings.py` | Rate limits: `checkin` 5/min, `report` 10/min |

testing:
python manage.py demo_checkin_trip