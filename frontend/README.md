# AdventureHive — Frontend (React)

React 18 + Vite + Tailwind CSS + Leaflet (OpenStreetMap). Talks to the Django API.

## Run it (development)

You need **two terminals**: Django and the React dev server.

```powershell
# Terminal 1 — backend (in the adventurehive folder, with .venv activated)
python manage.py runserver

# Terminal 2 — frontend
cd frontend
npm install        # first time only (needs Node.js 18+)
npm run dev
```

Open **http://localhost:5173**. Vite forwards `/api` and `/admin` to Django on port 8000,
so the browser sees a single site: login cookies stay `SameSite=Strict`, no CORS needed.

## Demo data (for screenshots)

```powershell
python manage.py seed_campsites
python manage.py seed_demo
```

Log in as `nok@demo.adventurehive.test` (also `ploy`, `mint`, `palm`, `tono`, `june`,
`jee`, `beam`) with password `DemoCamp123!`. Good accounts to show:

| Account | Shows |
|---|---|
| nok | Organizer of "Khao Yai Weekend Camp" (organizer tools, participant list) and admin of a group |
| palm | On the waitlist of "Kanchanaburi River Camp" |
| tono | Attended the completed "Pha Taem Sunrise Trip" and can write a verified review |
| jee | Was a no-show on that trip, so cannot review |
| ploy | Organizer of the completed trip (attendance already recorded) |
| tono | Admin of the private "Kanchanaburi River Crew" — Nok's post is waiting in his approval queue |

## Pages (matching the design sheet)

| Design | Route |
|---|---|
| 1 Login | `/login` |
| 2 Register (PDPA consent, experience, interests) | `/register` |
| 3 Dashboard | `/` |
| 4–5 Group / individual chat | `/groups/:id/chat` — layout only; messaging is planned for the next phase |
| 6 Campsite map with filters | `/campsites` (map or list) |
| 7 Trip detail (join / waitlist / organizer tools / attendance / review) | `/trips/:id` |
| 8 Create trip (meeting point on map, equipment) | `/trips/new`, edit at `/trips/:id/edit` |
| 9 Campsite page (facilities, permit, trips, reviews, Q&A, history) | `/campsites/:id` |
| Extra | `/feed`, `/posts/:id`, `/trips`, `/groups`, `/groups/:id`, `/questions`, `/questions/:id`, `/campsites/new`, `/my/submissions`, `/profile`, `/privacy` |

## Campsite photos

Moderators add a cover photo in the Django admin: **Locations → (campsite) → Photo** →
choose a JPEG/PNG/WebP (max 5 MB) and fill in **Cover image credit**, e.g.
`Photo: Jane Doe, CC BY-SA 4.0, via Wikimedia Commons`. The credit is shown under the
photo. Campsites without a photo show a generated illustration (`LandscapeArt.jsx`).
Uploaded files go to `media/` (not committed to Git). Map tiles © OpenStreetMap contributors.

## Home page slideshow

The hero on the home page fades through up to **five campsites that have a cover photo**
(most-reviewed first), every 6 seconds, with the campsite name and photo credit. It pauses
while hovered or focused and doesn't auto-play for visitors who turned on "reduce motion".
To change which photos appear, add or remove campsite cover photos in the admin.

## Profile photos

Members add a photo on **Profile → Add a profile photo** (JPEG, PNG or WebP, max 5 MB).
The server crops it to a 400×400 square and re-encodes it, which removes all metadata —
including GPS coordinates from phone cameras. Removing the photo or deleting the account
deletes the file. Moderators can view photos in the admin and use the user-list action
**Remove profile photo**; they cannot upload photos for others.

## Newsfeed (group & trip posts)

There is no public feed. Posts live **in a group** or **on a trip**:

| Where | Who can read | Who can post, react, comment |
|---|---|---|
| Public group | Anyone | Members — posts go live at once |
| Private group | Members only | Members — **an admin or co-admin approves each post first** (admins' own posts go live) |
| Trip | Organizer + confirmed / attended participants | Same people (read-only once cancelled) |

- `/feed` shows posts from your groups and trips, plus your own posts that are waiting or weren't approved.
- Reactions: 👍 Like, ❤️ Love, 😂 Haha, 😮 Wow, 😢 Sad — one per person, hover the Like button to choose, click again to remove.
- Comments allow one level of replies. Authors delete their own; group admins / trip organizers can hide or delete anything in their place.
- Private-group approval: the admin sees **Waiting for your approval** at the top of the group's Posts tab. Rejecting needs a note, which the author sees. An edited post goes back for approval, so an approved post can't be swapped for something else.
- Photos are resized to 1600 px and their EXIF/GPS data is stripped, same as profile photos.
- Demo: `python manage.py seed_demo_posts` (it runs automatically from `seed_demo` on a fresh database). Use `--reset` to put the demo posts back to their starting state before taking screenshots.
- API: `/api/posts/` (Swagger tag **feed**).

## Production build

`npm run build` creates `frontend/dist/` — static files to serve from the same domain
as the API (e.g. nginx serving `dist/` and proxying `/api` + `/admin` to Django).
