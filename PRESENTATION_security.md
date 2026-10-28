# Security: authorization, CSRF and sensitive data

**Professor's feedback:**
> *Security: Strengthen the explanation of authorization, CSRF protection, and access to sensitive user information.*

**Our answer in one sentence:**
Every request is checked on the **server** for *who you are* (login), *what role you have* (organizer, participant, admin…) and *whether this object is yours*. Logins live in cookies that JavaScript can't read, with CSRF tokens on every change. Sensitive data is encrypted, hidden from public views, or only shared when the user chooses.

---

## Part 1: Authorization (who can do what)

1. **Login is required by default.** Every API endpoint needs a login unless we deliberately open it, e.g. browsing campsites. Forgetting a check therefore fails *closed* (blocked), not *open*.
2. **Three layers of checks** on every request:
   - **Who are you?** No valid login → `401 Unauthorized`.
   - **What role do you have?** E.g. only the trip organizer can mark attendance, only moderators can approve campsites → otherwise `403 Forbidden`.
   - **Is this object yours?** E.g. you can edit only *your* profile and *your* review → otherwise `403`.
3. **You can't see other people's data by changing the ID in the URL** (this attack is called IDOR). Lists and detail pages only search what you're allowed to see: drafts only for their organizer, private-group trips only for members, notifications only your own. Something you may not see answers `404`, as if it didn't exist.
4. **Admins don't get everything.** Moderators manage content (approve campsites, hide reviews, cancel bad trips), but they **cannot** read emergency contacts, participant lists or meeting points. Those belong to the trip and its people. (*Principle of least privilege.*)
5. **Abuse limits (rate limiting):** login/register 10 per minute, joining trips 10/min, check-in code guesses 5/min, review reports 10/min.
6. **The rules are on the server.** The React app hides buttons people can't use, but that's just convenience: the server checks again on every request.

### The authorization matrix

Each cell is the real answer from our API, **checked by an automated test** (`tests/test_authorization_matrix.py`, one test per cell: 50 cells + 10 privacy checks = 60 tests).

| Action | Not logged in | Other member | Participant | Organizer | Admin |
|---|---|---|---|---|---|
| Edit a trip | 401 | 403 | 403 | ✅ | 403 |
| Cancel a trip | 401 | 403 | 403 | ✅ | ✅ (moderation) |
| See the participant list | 401 | 403 | 403 | ✅ | 403 |
| Record attendance | 401 | 403 | 403 | ✅ | 403 |
| See the check-in code | 401 | 403 | 403 | ✅ | 403 |
| Read shared emergency contacts | 401 | 403 | 403 | ✅ (around the trip only) | 403 |
| Read a person's own emergency contact | 401 | 403 | ✅ (owner) | 403 | 403 |
| Edit a person's profile | 401 | 403 | ✅ (owner) | 403 | 403 |
| Approve a campsite submission | 401 | 403 | 403 | 403 | ✅ |
| Hide a review | 401 | 403 | 403 | 403 | ✅ |
| **See the exact meeting point** | hidden | hidden | ✅ | ✅ | hidden |
| **See email / phone / birth date on a profile** | hidden | hidden | hidden | hidden | hidden |

`401` = please log in · `403` = logged in, but not allowed · ✅ = allowed

Group permissions (admin / co-admin / member of a group) are covered by `tests/test_layer3_groups.py`.

7. **A privacy bug we found and fixed this round:** when a **private group was deleted**, its trips lost their group and became **public**. Now:
   - its **upcoming** trips are **cancelled** and everyone is notified
   - **all** its trips become **members-only**: only the organizer and the people who joined can still open them
   - test: `test_deleting_a_private_group_does_not_make_its_trips_public`

## Part 2: CSRF protection

8. **What CSRF is, in simple words:** you're logged in to AdventureHive. You visit a bad website. It secretly submits a form to `adventurehive/api/trips/5/rsvp/`. Your browser **automatically attaches your login cookie**, so without protection the request would work as if *you* clicked it.
9. **Why we need it:** we keep the login token in a **cookie** (safer against XSS than browser storage), and browsers send cookies automatically. So CSRF protection is required for our design.
10. **Our three layers:**

```
 Browser (our React app)                         Server (Django)
 ─────────────────────────                       ────────────────────────────────
 1. GET /api/auth/csrf/     ───────────────────▶  sets cookie  csrftoken=abc123
                                                  (readable by our page's JS)
 2. POST /api/trips/5/rsvp/
    Cookie: ah_access=<login, httpOnly>
            csrftoken=abc123
    Header: X-CSRFToken: abc123   ─────────────▶  CookieJWTAuthentication:
                                                  ✔ login cookie valid?
                                                  ✔ header == cookie?   → allowed
 Bad website's hidden form:
    Cookie: ah_access=…, csrftoken=abc123
    Header: (none, it can't read our cookie) ──▶  ✘ header missing     → 403 "CSRF Failed"
```

   - **Layer 1, CSRF token (double-submit):** every change (POST/PUT/PATCH/DELETE) must send the `X-CSRFToken` header with the same value as the `csrftoken` cookie. Another website can't read our cookies, so it can't copy the value.
   - **Layer 2, SameSite=Strict cookies:** the browser doesn't send our cookies at all on requests started by other websites.
   - **Layer 3, CORS allowlist:** only our own frontend's address may make requests with cookies.
11. **The login cookie is `httpOnly`:** JavaScript can't read it, so even an XSS bug couldn't steal the token. Access tokens last **15 minutes**; refresh tokens last **7 days**, **rotate** on each use and are **blacklisted** on logout.
12. **Note:** DRF's standard JWT login does **not** check CSRF. We wrote `CookieJWTAuthentication` to add it. Test: `test_csrf_required_for_unsafe_requests_with_cookie_auth` (no header → 403; with header → allowed).

## Part 3: Access to sensitive user information

| Data | Who can see it | How it's protected |
|---|---|---|
| **Password** | nobody | stored only as a **bcrypt hash**; strength rules on registration |
| **Emergency contact** (name, phone) | the **owner**; the **trip organizer** only if the owner **chooses to share**, and only around the trip | **encrypted in the database** (Fernet, key in an environment variable); not in the Django admin; every organizer view is **logged** and the owner is **notified** |
| **Email, phone, birth date, gender** | the owner only | separate **public** and **private** profile formats; the public one never includes them |
| **Exact meeting point** | organizer + confirmed participants | the server sends `null` to everyone else, so it never reaches their browser |
| **Check-in code** | organizer only | **never stored**; calculated from the server's secret key |
| **Participant list, attendance reasons** | organizer only | organizer-only endpoint; admins get 403 |
| **Photos** | public (profile/campsite/posts) | GPS/EXIF location data is **removed** on upload |
| **Login token** | nobody (not even our own JavaScript) | `httpOnly`, `SameSite=Strict`, `Secure` cookie in production |
| **Deleted account** (PDPA) | — | needs the password; personal data **anonymised**, photos removed, seats freed |

13. **New this round: emergency contact sharing (opt-in).** Before, *nobody* could read an emergency contact, so it wasn't useful in an emergency. Now:
    1. A confirmed participant clicks **"Share with the organizer"** on the trip page. It's **off by default**, and they can stop sharing any time.
    2. The organizer can open shared contacts **only from 1 day before the trip until 1 day after it**. Outside that window, the server refuses.
    3. Contacts are loaded only when the organizer **clicks** "Emergency contacts", never automatically.
    4. **Every view is logged** (Django admin → *Emergency contact accesses*: who, whose, when; never the contact itself), and the participant gets a **notification** the first time.
    5. Admins and other participants still get **403**.
    6. Leaving and re-joining a trip turns sharing **off** again.

## Part 4: What we're honest about

14. **Not everything is server-side encrypted.** Emails, phones and birth dates are protected by **access rules**, not encryption. We encrypted the most sensitive item (emergency contacts), which is a common trade-off. Full database encryption (disk level) is a hosting/deployment setting.
15. **Rate limits use a per-server cache.** With several servers in production we'd move this to a shared cache such as Redis.
16. **HTTPS:** the code switches on HTTPS-only cookies and HSTS with `SECURE_SSL_REDIRECT=True`. It has to be enabled on the real server, not on localhost.

---

## Live demo script (about 3 minutes)

Demo users' password: `DemoCamp123!`. Admin: your superuser. Run `python manage.py demo_checkin_trip` first; it prints a trip number (e.g. #7) whose trip just ended, so the emergency window is open.

1. **Authorization (403):** log in as **Nok** (a participant). Try `http://localhost:8000/api/trips/7/participants/` → **403 "Only the trip organizer can do this."**
2. **IDOR (404):** as a user who isn't in a private group, open one of its trips by ID → **404**.
3. **CSRF:** in the browser dev tools (Network tab), show that a POST carries the `X-CSRFToken` header. Then run the test: `pytest tests/test_layer1_auth.py -k csrf -v`.
4. **httpOnly:** in dev tools → Application → Cookies, `ah_access` is marked **HttpOnly**, and `document.cookie` in the console does **not** show it.
5. **Emergency sharing:**
   - first give **Nok** an emergency contact on the Profile page
   - as **Nok**, open trip #7 → **"Share with the organizer"**
   - as **Ploy** (organizer), open trip #7 → Organizer tools → **"Emergency contacts"** → Nok's contact appears
   - as **Nok**, the bell shows *"Ploy … opened the emergency contact you shared"*
   - Django admin → **Emergency contact accesses**: the log row
6. **Evidence:** run `pytest tests/test_authorization_matrix.py -v` and show the 60 green lines: one per cell of the table, plus the privacy checks.

## Evidence: automated tests

| Test file | What it proves |
|---|---|
| `tests/test_authorization_matrix.py` (60 tests) | **Every cell** of the authorization table, plus meeting-point and private-profile-field hiding for every role |
| `tests/test_security_privacy.py` (9 tests) | Private-group deletion fix; emergency sharing (opt-in only, time window, log + notification, admins blocked, stop sharing, re-join resets) |
| `tests/test_layer1_auth.py` | CSRF required, httpOnly cookies, token rotation and blacklist, rate limits, suspended users |
| `tests/test_layer1_profile.py` | Public profile hides private fields; only the owner edits; emergency contact owner-only (even admins get 403) |
| `tests/test_layer0_accounts.py` | Emergency contact is **encrypted in the database** (reads the raw database value) |

Details of every code change: see **`CHANGES_security.md`**.
