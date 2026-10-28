# Campsite map-pin checks — what was added and changed

Date: 2026-10-26

## Why

Testing "Suggest a campsite" showed four problems:

1. After clicking the map, the form showed no coordinates or place, so you couldn't see what you'd picked.
2. Province was free text and never compared with the pin. Example: "AIT lake" was saved as *Chiang Mai*, but its pin is in *Khon Kaen*.
3. "Inside Thailand" was only a rectangle (lat 5.6–20.5, lng 97.3–105.7). That rectangle also covers parts of Laos, Cambodia, Myanmar and Malaysia. Example: "Khao tai" was accepted, but its pin is in Cambodia.
4. Nothing warned when a campsite was submitted on top of one that already exists.

## What it does now

| Where | Behaviour |
|---|---|
| **Suggest-a-campsite form** | After a click, it shows the coordinates and the detected province, and fills in the Province field. A red warning appears if the pin is in another country, and an amber warning lists published campsites within 1 km. |
| **API (create/edit a submission, suggest an edit)** | Rejects a pin outside Thailand ("This pin is in Cambodia…"). Rejects a province that doesn't match the pin ("The pin is in Khon Kaen, not Chiang Mai…"). A blank province is filled in from the pin, and the spelling is normalised ("chiang mai" → "Chiang Mai"). |
| **Django admin: campsite list** | New **Pin OK** column (✓/✗): is the pin in Thailand and in the stated province? |
| **Django admin: campsite page** | New **Map check** field: a verdict (✓ match / ⚠ wrong province / ✗ not in Thailand), a list of other campsites within 1 km as possible duplicates, an embedded OpenStreetMap preview, and an "Open in OpenStreetMap" link. Admin edits follow the same pin rule as the API. |

### How the province is found

The province is looked up offline from real province borders. There's no external service and no new Python package.

- A pin inside a province gets that province. If the pin is within **3 km** of a border, the neighbouring province is also accepted, because the simplified borders can be about 1–2 km off.
- A pin inside Laos, Cambodia, Myanmar or Malaysia is outside Thailand, unless it's within 3 km of the Thai border.
- A pin at sea gets the nearest province within **100 km**. Small islands such as the Similans are missing from the simplified data, so this keeps them working.
- Anything else is outside Thailand.

**Known limit:** along the Mekong, the simplified border is about 2 km off. So the very edge of Vientiane counts as Nong Khai, while points 2 km into Laos are rejected. Moderators still check every submission with the map preview.

## Files

### Added
| File | What |
|---|---|
| `core/provinces.py` | Province lookup: `check_pin()`, `province_at()`, `canonical_province()`, `province_names()`, `distance_km()`. Pure Python ray-casting. |
| `core/data/th_provinces.json` | Boundaries of the 77 Thai provinces plus neighbouring countries (≈1.4 MB). Source: geoBoundaries / OpenStreetMap. License: ODbL 1.0; Myanmar CC BY-SA 2.0. The source and license are written inside the file. |
| `core/data/build_th_provinces.py` | Script that rebuilds the JSON from geoBoundaries downloads. Usage is at the bottom of the file. |
| `tests/test_layer2_pin_checks.py` | 22 tests: 13 **unit** (lookup only, no database) and 9 **integration** (API and admin form). |
| (meeting points) | See Part 2 below. |
| `NOTES_campsite_pin_checks.md` | This file. |

### Changed
| File | Change |
|---|---|
| `locations/services.py` | New `check_pin_and_province()` (the rule), `nearby_campsites()` (1 km duplicate search), `PIN_FIELDS` and `NEARBY_KM`. `propose_edit()` now runs the pin rule on suggested edits. |
| `locations/serializers.py` | `CampsiteWriteSerializer`: province is optional (filled in from the pin), and `validate()` runs the pin rule. New `PinCheckSerializer`. |
| `locations/views.py` | New endpoint **`GET /api/campsites/pin-check/?lat=&lng=[&exclude=<id>]`** (logged-in users). Returns `in_thailand`, `country`, `province`, `provinces` (allowed choices) and `nearby` (published campsites within 1 km). It appears in Swagger at `/api/docs/`. |
| `locations/admin.py` | `LocationAdminForm` applies the same rule, plus the **Pin OK** column and the **Map check** field. |
| `frontend/src/pages/SuggestCampsite.jsx` | Calls `pin-check` after each click and fills in the province. New `PinSummary` component under the map shows coordinates, province and warnings. It won't submit while the pin is outside Thailand. |
| `pytest.ini` | Registered a `unit` marker. `pytest -m unit` runs only unit tests, and `pytest -m "not unit"` runs the rest. |

### Not changed
- No database migration. The table columns are the same, and the old rectangle CHECK constraint stays as a coarse safety net.
- Seed data (`seed_campsites`) is unchanged. All 15 seed campsites pass the new check.

## Part 2: trip meeting points (same day)

Testing "Create a trip → Dates and meeting point" showed the same problems: no coordinates after clicking, no place shown, meeting points in Laos/Cambodia accepted, and the campsite not visible on the meeting-point map.

| File | Change |
|---|---|
| `trips/serializers.py` | `TripWriteSerializer.validate()` rejects a meeting point outside Thailand ("This meeting point is in Laos…"). It only checks when the meeting point is sent, so editing a trip's title doesn't re-check it. |
| `frontend/src/components/maps.jsx` | `PinPicker` takes a new `markers` prop (extra read-only pins with a hover label), and pans to `center` when it changes. Choosing another campsite moves the map there. |
| `frontend/src/pages/TripForm.jsx` | The **campsite pin (green)** is shown next to the **meeting-point pin (orange)**, with a small legend. Under the map: coordinates and province, or a red warning if outside Thailand. Saving is blocked while outside Thailand. |
| `tests/test_layer4_trips.py` | 3 new cases: meeting point in Laos, in Cambodia, and "edit without moving it isn't re-checked / moving it abroad is rejected". |

The meeting point **name** is still typed by the organizer. A real place name would need an online reverse-geocoding service. The province shown under the map makes a wrong pin easy to spot.

## Part 3: trip page map (campsite + meeting point)

The trip page used to show one orange pin with no label and no campsite. Now it has:

- **Two pins:** the campsite (green) and the meeting point (orange). The map zooms to fit both.
- **A legend above the map:** "🟢 Campsite · 🟠 Meeting point".
- **Labels:** hovering shows "Campsite: <name>" / "Meeting point: <name>". A click or tap opens the same label, so it works on phones; the campsite one includes a "View campsite" link.
- **Non-confirmed visitors** see a "Campsite location" map with only the campsite pin, and a 🔒 "Meeting point shown to confirmed participants" note.

### Privacy and security

| Rule | How it's enforced |
|---|---|
| Only the **organizer** and **confirmed/attended** participants see the meeting point (name **and** coordinates) | **On the server.** `TripDetailSerializer.to_representation` returns `meeting_point_name`, `meeting_latitude` and `meeting_longitude` as `null`, plus `meeting_point_hidden: true`, for everyone else: logged-out visitors, waitlisted, cancelled, other users. The browser never receives the hidden values, so the page can't leak them, even through dev tools. |
| The page only draws what the API sent | `TripMap` adds the meeting pin only when `meeting_point_hidden` is false **and** both coordinates are present. |
| The campsite pin is safe to show | Campsite locations are already public (campsite list, map, campsite page). Trips in a private group are still visible only to group members (`visible_trips`), so the trip page itself, and therefore this map, stays private. |
| No XSS through names | Pin labels are React text (auto-escaped). No HTML strings go into Leaflet (`bindTooltip`/`bindPopup` with HTML is not used). A meeting point name like `<script>…` is shown as plain text. |
| Admins don't see participants' meeting points | Unchanged. Staff get no special access to the meeting point. |

**Proof:** new test `test_trip_map_data_hides_every_meeting_field_but_keeps_the_public_campsite` in `tests/test_layer4_trips.py`. It checks that logged-out, waitlisted, cancelled and unrelated users get all three meeting fields as `null` but do get the campsite coordinates, and that the organizer and confirmed participant get the real values.

| File | Change |
|---|---|
| `frontend/src/components/maps.jsx` | New `PinsMap`: read-only map with several labelled pins (hover tooltip plus tap popup), zoomed to fit all of them. `FitBounds` takes a `maxZoom` (default unchanged). |
| `frontend/src/pages/TripDetail.jsx` | New `TripMap` section replaces the single-pin `MiniMap`. |
| `tests/test_layer4_trips.py` | The privacy test above. |

**Decided for the final phase:** distance from the meeting point to the campsite (straight line, shown under the map) and renaming the existing "Distance (km)" field.

## Existing data to fix

The two test submissions in the local database are still `pending_review` and now show ✗ in **Pin OK**:
- **AIT lake**: province Chiang Mai, but the pin is in Khon Kaen. AIT itself is in Pathum Thani, around 14.08, 100.61.
- **Khao tai**: the pin is in Cambodia.

Reject them in the admin with a note, or fix the pin.

## How to verify

```bash
pytest tests/test_layer2_pin_checks.py -v   # the new tests
pytest -m unit -v                           # unit tests only
pytest                                      # whole suite
```

Manual check: open *Campsites → Suggest a campsite*, then:
1. Click in Chiang Mai. You should see coordinates, "Chiang Mai", and the Province field filled in.
2. Click in Laos or Cambodia. A red warning appears, and saving is blocked.
3. Click right next to an existing campsite. An amber "Already on AdventureHive within 1 km" box appears.
4. In `/admin/`, under Locations, check the **Pin OK** column, then open a campsite to see the **Map check** field.
