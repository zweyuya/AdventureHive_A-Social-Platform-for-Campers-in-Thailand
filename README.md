<<<<<<< HEAD
# AdventureHive — Backend (Layer 0)

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

## Next layers
1. Auth & profile endpoints (register with PDPA consent, login/refresh/logout cookies, `/api/users/{id}/`, emergency contact, account deletion).
2. Campsites: list/filters, detail, GeoJSON map endpoint, seed data, submission → approve/reject workflow with revisions.
3. Groups (optional for the progress report).
4. Trips: CRUD, status lifecycle, RSVP with `select_for_update`, waitlist promotion, completion command, organizer attendance marking.
5. Reviews + Q&A endpoints.
=======
# TheLayerCake_AdventureHive



## Getting started

To make it easy for you to get started with GitLab, here's a list of recommended next steps.

Already a pro? Just edit this README.md and make it your own. Want to make it easy? [Use the template at the bottom](#editing-this-readme)!

## Add your files

* [Create](https://docs.gitlab.com/user/project/repository/web_editor/#create-a-file) or [upload](https://docs.gitlab.com/user/project/repository/web_editor/#upload-a-file) files
* [Add files using the command line](https://docs.gitlab.com/topics/git/add_files/#add-files-to-a-git-repository) or push an existing Git repository with the following command:

```
cd existing_repo
git remote add origin https://gitlab.com/fullstack-ait-2026/thelayercake_adventurehive.git
git branch -M main
git push -uf origin main
```

## Integrate with your tools

* [Set up project integrations](https://gitlab.com/fullstack-ait-2026/thelayercake_adventurehive/-/settings/integrations)

## Collaborate with your team

* [Invite team members and collaborators](https://docs.gitlab.com/user/project/members/)
* [Create a new merge request](https://docs.gitlab.com/user/project/merge_requests/creating_merge_requests/)
* [Automatically close issues from merge requests](https://docs.gitlab.com/user/project/issues/managing_issues/#closing-issues-automatically)
* [Enable merge request approvals](https://docs.gitlab.com/user/project/merge_requests/approvals/)
* [Set auto-merge](https://docs.gitlab.com/user/project/merge_requests/auto_merge/)

## Test and Deploy

Use the built-in continuous integration in GitLab.

* [Get started with GitLab CI/CD](https://docs.gitlab.com/ci/quick_start/)
* [Analyze your code for known vulnerabilities with Static Application Security Testing (SAST)](https://docs.gitlab.com/user/application_security/sast/)
* [Deploy to Kubernetes, Amazon EC2, or Amazon ECS using Auto Deploy](https://docs.gitlab.com/topics/autodevops/requirements/)
* [Use pull-based deployments for improved Kubernetes management](https://docs.gitlab.com/user/clusters/agent/)
* [Set up protected environments](https://docs.gitlab.com/ci/environments/protected_environments/)

***

# Editing this README

When you're ready to make this README your own, just edit this file and use the handy template below (or feel free to structure it however you want - this is just a starting point!). Thanks to [makeareadme.com](https://www.makeareadme.com/) for this template.

## Suggestions for a good README

Every project is different, so consider which of these sections apply to yours. The sections used in the template are suggestions for most open source projects. Also keep in mind that while a README can be too long and detailed, too long is better than too short. If you think your README is too long, consider utilizing another form of documentation rather than cutting out information.

## Name
Choose a self-explaining name for your project.

## Description
Let people know what your project can do specifically. Provide context and add a link to any reference visitors might be unfamiliar with. A list of Features or a Background subsection can also be added here. If there are alternatives to your project, this is a good place to list differentiating factors.

## Badges
On some READMEs, you may see small images that convey metadata, such as whether or not all the tests are passing for the project. You can use Shields to add some to your README. Many services also have instructions for adding a badge.

## Visuals
Depending on what you are making, it can be a good idea to include screenshots or even a video (you'll frequently see GIFs rather than actual videos). Tools like ttygif can help, but check out Asciinema for a more sophisticated method.

## Installation
Within a particular ecosystem, there may be a common way of installing things, such as using Yarn, NuGet, or Homebrew. However, consider the possibility that whoever is reading your README is a novice and would like more guidance. Listing specific steps helps remove ambiguity and gets people to using your project as quickly as possible. If it only runs in a specific context like a particular programming language version or operating system or has dependencies that have to be installed manually, also add a Requirements subsection.

## Usage
Use examples liberally, and show the expected output if you can. It's helpful to have inline the smallest example of usage that you can demonstrate, while providing links to more sophisticated examples if they are too long to reasonably include in the README.

## Support
Tell people where they can go to for help. It can be any combination of an issue tracker, a chat room, an email address, etc.

## Roadmap
If you have ideas for releases in the future, it is a good idea to list them in the README.

## Contributing
State if you are open to contributions and what your requirements are for accepting them.

For people who want to make changes to your project, it's helpful to have some documentation on how to get started. Perhaps there is a script that they should run or some environment variables that they need to set. Make these steps explicit. These instructions could also be useful to your future self.

You can also document commands to lint the code or run tests. These steps help to ensure high code quality and reduce the likelihood that the changes inadvertently break something. Having instructions for running tests is especially helpful if it requires external setup, such as starting a Selenium server for testing in a browser.

## Authors and acknowledgment
Show your appreciation to those who have contributed to the project.

## License
For open source projects, say how it is licensed.

## Project status
If you have run out of energy or time for your project, put a note at the top of the README saying that development has slowed down or stopped completely. Someone may choose to fork your project or volunteer to step in as a maintainer or owner, allowing your project to keep going. You can also make an explicit request for maintainers.
>>>>>>> 939f13d366c1234ce1b933b88ed847b03b4fc4a5
