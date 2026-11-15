"""
Content for the public /ps4/ pages (FSAD Problem Set 3).

Everything here is safe to publish:
  * participants appear only as codes (P1, P2, ...) with their user class;
  * findings are short anonymised paraphrases, never private interview notes;
  * personas are fictional composites, not real people.

TO ADD A NEW INTERVIEW (e.g. P3):
  1. add a row to PARTICIPANTS;
  2. add or extend a finding in FINDINGS (paraphrase, no names, no quotes);
  3. reference the finding id from the persona it supports (PERSONAS[...]["findings"]);
  4. add a row to DECISIONS if it changed the design.
The pages update automatically; tests/test_ps4.py checks the links still work.
"""

PROJECT = {
    "name": "AdventureHive",
    "team": "The Layer Cake",
    "tagline": "A camping community platform for Thailand",
    "summary": (
        "AdventureHive helps people in Thailand find campsites with checked information, "
        "join group camping trips, and trust reviews because only people who really attended "
        "a trip can review its campsite."
    ),
    "plan": [
        ("Problem", "Camping information in Thailand is scattered across Facebook posts, LINE chats "
                    "and park office phone lines. It is often out of date, and there is no way to "
                    "tell whether a reviewer actually went."),
        ("Who it is for", "Weekend campers, trip organisers, and people trying camping for the first time."),
        ("Core idea", "Checked campsite information, trip sign-up with an automatic waitlist, and "
                      "reviews only from verified attendees."),
        ("Stack", "Django + Django REST Framework + PostgreSQL, with a React frontend. These "
                  "research pages are plain Django views and templates."),
        ("This semester", "Campsites, trips, attendance check-in, verified reviews, moderation, "
                          "groups, Q&A and notifications. Real-time chat and semantic search are "
                          "out of scope."),
    ],
}

# Participants: codes only. No names, contact details, photos or recordings.
PARTICIPANTS = [
    {"code": "P1", "user_class": "Camper (camps about 3 times a year)", "mode": "Online, shown the app",
     "duration": "10–15 min"},
    {"code": "P2", "user_class": "Trip organizer", "mode": "Online, shown the app",
     "duration": "10–15 min"},
    # {"code": "P3", "user_class": "First-time user", "mode": "Online, shown the app", "duration": "10–15 min"},
]

FINDINGS = [
    {"id": "I1", "title": "Trust depends on proof of attendance",
     "evidence": "P1 and P2 both said they would trust reviews more if the reviewer had verifiably "
                 "attended the trip.",
     "meaning": "Verified attendance is the main reason people would trust AdventureHive reviews over "
                "social-media posts, so it stays a core feature."},
    {"id": "I2", "title": "Accurate fees and permits matter most to organizers",
     "evidence": "P2 worried that wrong fees, facilities or permit information could cause problems on "
                 "a group trip, and would check the change history when fees change. P1 would not look "
                 "at the history.",
     "meaning": "Organizers carry the risk of wrong information for the whole group, so they value "
                "checked data. Campers care more about finding a place quickly."},
    {"id": "I3", "title": "People want new places to appear quickly",
     "evidence": "P1 wanted new campsites to appear immediately with a 'not yet verified' label. P2 "
                 "supported moderator review but would also show new places as 'not yet verified'.",
     "meaning": "Both accept checking but dislike waiting. A visible but limited 'unverified' state "
                "can satisfy both."},
    {"id": "I4", "title": "Organizer effort must be small",
     "evidence": "P2 accepted spending a few minutes on attendance after a trip and wanted to fix "
                 "records when someone forgets to check in. P1 did not want class-style roll calls.",
     "meaning": "Attendance should be close to automatic (self check-in, pre-filled list) with an easy "
                "way to correct mistakes."},
    {"id": "I5", "title": "Organizers want an overview of their trips",
     "evidence": "P2 asked for one place showing participants, free spaces, the waitlist and "
                 "cancellations, and said it would make them come back.",
     "meaning": "Organizers are power users; a dashboard of what needs doing keeps them engaged."},
    {"id": "I6", "title": "Wording can create wrong mental models",
     "evidence": "P1 read the review badge 'Confirmed by organizer' as meaning organizers can control "
                 "reviews.",
     "meaning": "Labels about trust must say exactly what they mean."},
]

DISAGREEMENTS = [
    ("Checking new reviews", "P1 preferred stronger checks for very high or very low ratings; P2 "
                             "thought publishing immediately with reporting was reasonable."),
    ("Pre-moderation of campsites", "P1 valued speed for spontaneous trips; P2 valued accuracy. Both "
                                    "suggested an 'unverified' label as the middle ground."),
    ("Version history", "Useful for the organizer, ignored by the camper."),
]

OPEN_QUESTIONS = [
    "The first-time camper view is still weakly supported: neither participant so far is new to camping.",
    "We have no evidence yet from people who camp alone.",
    "We don't know whether organizers will keep recording attendance once the novelty wears off.",
]

PERSONAS = [
    {
        "slug": "camper", "name": "Mai", "role": "The weekend camper", "primary": True,
        "initials": "M", "color": "#178a5e",
        "quote": "I just want to find a trip this weekend and know the reviews are real.",
        "rows": [
            ("Background", "University student in Bangkok who camps 3–4 times a year with friends, "
                           "usually in national parks within a few hours' drive. Plans trips at short notice."),
            ("Short-term goals", "Find a campsite and a group for this weekend; know the fees and what to bring."),
            ("Long-term goals", "Camp more often, try new places, and meet people to camp with regularly."),
            ("Typical tasks", "Browse campsites on the map, read reviews, join a trip, check in at the "
                              "campsite, post photos afterwards."),
            ("Frustrations", "Social-media posts are out of date or contradict each other; no way to tell "
                             "if a reviewer really went; waiting for things to be approved."),
            ("Technology and access", "Uses a phone for almost everything; mobile signal at campsites is "
                                      "weak or missing."),
            ("Expectations", "Fast discovery, reviews she can trust, and clear labels that don't need explaining."),
        ],
        "findings": ["I1", "I3", "I6"],
        "evidence_note": "Also built on P1's wish for terrain and weather information and for ratings "
                         "by category.",
        "scenario": "weekend-trip-mobile",
    },
    {
        "slug": "organizer", "name": "Krit", "role": "The trip organizer", "primary": False,
        "initials": "K", "color": "#f58a1f",
        "quote": "I need one place that tells me who's coming and what I still have to do.",
        "rows": [
            ("Background", "Works full time and organises a group trip about once a month, usually for "
                           "5–10 people, some of whom he doesn't know."),
            ("Short-term goals", "Fill the trip, manage the waitlist when people drop out, and make sure "
                                 "everyone knows the fees and permits."),
            ("Long-term goals", "Build a reputation as a reliable organizer and a regular group of campers."),
            ("Typical tasks", "Create and publish trips, answer questions, handle cancellations, record "
                              "attendance after the trip, run the same trip again."),
            ("Frustrations", "Keeping track of who is coming in chat threads; wrong fee or permit "
                             "information; extra admin work after the trip."),
            ("Technology and access", "Uses a laptop to plan and a phone on the trip."),
            ("Expectations", "One place to see every trip and what needs doing; quick attendance; "
                             "accurate, checked campsite data."),
        ],
        "findings": ["I2", "I4", "I5"],
        "evidence_note": "Also built on P2's answers about version history and suggesting edits.",
        "scenario": "run-and-repeat-trip",
    },
    {
        "slug": "first-timer", "name": "Fah", "role": "The first-time camper", "primary": False,
        "initials": "F", "color": "#1b3270",
        "quote": "I've never camped before. I don't want to be the one who brings the wrong things.",
        "rows": [
            ("Background", "First-year university student in Bangkok who has never camped. Friends' "
                           "photos made her curious, but she has no gear and no friends who camp regularly."),
            ("Short-term goals", "Find a beginner-friendly trip with an organizer who explains what to "
                                 "bring, and know the total cost before committing."),
            ("Long-term goals", "Gain enough confidence to camp regularly and buy her own basic gear."),
            ("Typical tasks", "Filter for easy, beginner-friendly trips; read the equipment list and "
                              "fees; ask a question before joining; check which campsites have restrooms."),
            ("Frustrations", "Camping posts assume you already know the rules; unclear whether a "
                             "trip is too hard; worried about joining a group of strangers."),
            ("Technology and access", "Uses her phone for everything; comfortable with booking and "
                                      "social apps, but new to camping terms."),
            ("Expectations", "Clear difficulty and experience levels, a simple equipment list, visible "
                             "facilities, and a friendly way to ask questions."),
        ],
        "findings": ["I1", "I2"],
        "evidence_note": "Built on what P1 and P2 said about trusting reviews and needing accurate "
                         "fees and facilities, applied to someone with no camping experience. This "
                         "persona has the weakest direct evidence so far and is being checked with "
                         "a first-time camper.",
        "scenario": "first-trip-beginner",
    },
]

SCENARIOS = [
    {
        "slug": "weekend-trip-mobile", "number": 1, "persona": "camper", "mobile": True,
        "title": "Mai joins a weekend trip and checks in on her phone",
        "trigger": "On Wednesday, Mai's friends cancel their weekend plan and she wants to go camping anyway.",
        "steps": [
            "On her phone she opens AdventureHive and filters trips to this weekend with free spots.",
            "She opens a trip to Pha Taem, reads campsite reviews marked “Verified attendee · "
            "checked in”, and checks the fees and the equipment list.",
            "She taps “Join this trip” and gets a confirmed seat.",
            "At the campsite the organizer shows the 6-digit check-in code and she enters it on her phone.",
        ],
        "outcome": "Mai is confirmed, attends, is checked in, and can review the campsite after the trip.",
        "exception": "There is no mobile signal at the campsite. Check-in stays open until 24 hours after "
                     "the trip ends, so she enters the code on the drive home. If she forgets, the "
                     "organizer can still mark her as attended with a written reason.",
    },
    {
        "slug": "run-and-repeat-trip", "number": 2, "persona": "organizer", "mobile": False,
        "title": "Krit runs a trip and repeats it",
        "trigger": "Krit wants to run a sunrise trip to Pha Taem for 5 people.",
        "steps": [
            "He creates the trip, picks the campsite and dates, adds equipment, and publishes it.",
            "The trip fills up; the next person who joins is put on the waitlist.",
            "One participant leaves; the first person on the waitlist is promoted automatically and notified.",
            "After the trip, “Trips organised” shows the attendance deadline; he confirms the "
            "pre-filled attendance list.",
            "He presses “Repeat this trip” for next month; past attendees are invited to join first.",
        ],
        "outcome": "A full trip with no manual list-keeping, a recorded attendance list, and a repeat trip "
                   "with returning campers.",
        "exception": "Krit tries to create the new trip with the same title while the old one is still "
                     "active. The error explains the duplicate and links to the trip that is in the way.",
    },
    {
        "slug": "first-trip-beginner", "number": 3, "persona": "first-timer", "mobile": False,
        "title": "Fah joins her first camping trip",
        "trigger": "Fah's friend posts sunrise photos from a camping trip, and Fah decides to try camping herself.",
        "steps": [
            "She opens the trips list and looks for an easy trip with no minimum experience level.",
            "On the trip page she checks the difficulty, the total fees, and the equipment list, "
            "which says the organizer brings the cooking stove and each person brings a tent.",
            "On the campsite page she confirms there are restrooms and water, then asks on the Q&A "
            "“Can I rent a tent at the park?” and gets an answer from an experienced camper.",
            "Reassured, she joins the trip and gets a confirmed seat.",
        ],
        "outcome": "Fah joins a trip that suits a beginner and knows what to bring and what it costs.",
        "exception": "The first trip she likes asks for intermediate experience, so the app does not let "
                     "her join. She picks another trip marked as suitable for beginners instead.",
    },
    {
        "slug": "check-new-campsite", "number": 4, "persona": None, "mobile": False,
        "title": "A moderator checks a new campsite",
        "actor": "Campsite moderator",
        "trigger": "A member suggests a new campsite with a map pin and fee information.",
        "steps": [
            "The campsite appears straight away on the map and list, marked “Not yet verified”. "
            "Nobody can organise a trip or ask a question there yet.",
            "The moderator opens the moderation page and sees the submission, its pin on a map, and "
            "nearby campsites that might be duplicates.",
            "The pin check confirms the pin is in Thailand and inside the stated province.",
            "The moderator approves it; it becomes a verified campsite (version 1) and the submitter is notified.",
        ],
        "outcome": "New places are visible quickly, but trips can only be planned around checked information.",
        "exception": "The pin is outside the stated province, or a duplicate exists nearby. The moderator "
                     "rejects it with a note; it is hidden again and the member can correct and resubmit.",
    },
]

ROLES = [
    ("Visitor", "Not logged in"),
    ("Member", "Any logged-in user"),
    ("Organizer", "Organizer of that trip"),
    ("Participant", "Confirmed or attended participant of that trip"),
    ("Group admin", "Admin or co-admin of that group"),
    ("Moderator", "Campsite moderator (reviews new campsites only)"),
    ("Admin", "Platform administrator"),
]

# One row per action; one cell per role, in ROLES order.
Y, N = "✓", "–"
MATRIX = [
    ("Campsites: view, map, history", [Y, Y, Y, Y, Y, Y, Y]),
    ("Campsite: suggest new or suggest an edit", [N, Y, Y, Y, Y, Y, Y]),
    ("New campsite: approve / reject", [N, N, N, N, N, "✓ (not own)", Y]),
    ("Suggested edit: approve / reject", [N, N, N, N, N, N, Y]),
    ("Trip: view public trips", [Y, Y, Y, Y, Y, Y, Y]),
    ("Trip: create", [N, Y, Y, Y, Y, Y, Y]),
    ("Trip: edit / publish / repeat", [N, N, Y, N, N, N, N]),
    ("Trip: cancel", [N, N, Y, N, N, N, "✓ (moderation)"]),
    ("Trip: join / leave", [N, Y, N, Y, Y, Y, Y]),
    ("Exact meeting point and distance", [N, N, Y, Y, N, N, N]),
    ("Participant list, check-in code, attendance", [N, N, Y, N, N, N, N]),
    ("Emergency contact", [N, "own", "✓ (only if shared, near trip dates)", "own", N, N, N]),
    ("Review: write", [N, N, N, "✓ (attended, completed trip)", N, N, N]),
    ("Review: hide / restore", [N, N, N, N, N, N, Y]),
    ("Review or answer: report", [N, Y, Y, Y, Y, Y, Y]),
    ("Q&A: read", [Y, Y, Y, Y, Y, Y, Y]),
    ("Q&A: ask, answer, vote helpful", [N, "✓ (not own answer)", Y, Y, Y, Y, Y]),
    ("Private group posts: view", [N, "members", N, N, Y, N, N]),
    ("Private group posts: approve / reject", [N, N, N, N, Y, N, N]),
    ("Notifications", [N, "own", "own", "own", "own", "own", "own"]),
]

USER_STORIES = [
    {"id": "US1", "priority": "Must",
     "story": "As a camper, I can join a trip with free seats so that I have a confirmed place.",
     "criteria": ["Given a published trip with a free seat, when I press Join, then I am confirmed and "
                  "the free seats go down by one.",
                  "Given a full trip, when I press Join, then I am put on the waitlist with my position shown."]},
    {"id": "US2", "priority": "Must",
     "story": "As a participant on the waitlist, I am moved up automatically so that I don't need to keep checking.",
     "criteria": ["Given a full trip and I am first on the waitlist, when a confirmed participant "
                  "leaves, then I become confirmed and receive a notification."]},
    {"id": "US3", "priority": "Must · permission",
     "story": "As a camper reading reviews, I see only reviews from people who attended so that I can trust them.",
     "criteria": ["Given a member who was not marked attended on a completed trip to this campsite, when "
                  "they submit a review, then the server rejects it and nothing is saved, even if the "
                  "request bypasses the app."]},
    {"id": "US4", "priority": "Must · privacy",
     "story": "As a participant, my emergency contact is visible to the organizer only if I share it, "
              "and only around the trip dates, so that my data stays private.",
     "criteria": ["Given I have not shared my contact, when the organizer requests it, then it is not returned.",
                  "Given I have shared it, when the organizer views it from 1 day before to 1 day after "
                  "the trip, then it is shown, the view is logged and I am notified. Outside that window "
                  "it is not shown."]},
    {"id": "US5", "priority": "Must · permission",
     "story": "As an organizer, I am the only one who can see my trip's participant list so that "
              "participants' privacy is protected.",
     "criteria": ["Given a trip, when anyone other than its organizer (including a platform admin) "
                  "requests the participant list, then the server returns 403."]},
    {"id": "US6", "priority": "Should",
     "story": "As an organizer, I can see all my trips and what needs doing so that I don't miss tasks.",
     "criteria": ["Given I organised a completed trip without recorded attendance, when I open “Trips "
                  "organised”, then it appears under “Needs your attention” with the deadline."]},
    {"id": "US7", "priority": "Should",
     "story": "As a member, I can suggest a new campsite so that others can find it quickly.",
     "criteria": ["Given I submit a campsite, then it is shown publicly as “Not yet verified” and "
                  "nobody can organise a trip there.",
                  "When a moderator approves it, then it becomes verified (version 1) and I am notified. "
                  "When it is rejected, I see the reason and can resubmit."]},
]

DATA_ROWS = [
    ("Email and password (hashed)", "Login", "The user; never shown to others"),
    ("Display name, optional photo, interests, experience level", "Profile shown to other campers",
     "Everyone; photo location (GPS) data is removed on upload"),
    ("Emergency contact (encrypted)", "Safety on remote trips",
     "The user; the organizer only if shared and only near the trip dates; every view is logged"),
    ("Trip participation, check-ins, attendance", "Seats, waitlist and verified reviews",
     "The user and the trip organizer"),
    ("Posts, reviews, answers, photos", "Community content", "Public, or group members for private groups"),
]

PRIVACY_NOTES = [
    ("Consent", "Users accept the privacy notice (Thai PDPA) when registering. Sharing an emergency "
                "contact is a separate opt-in per trip and can be withdrawn."),
    ("Minimisation and deletion", "Only the data above is collected. Deleting an account anonymises it, "
                                  "deletes the emergency contact and photos, and frees trip seats."),
    ("Ownership", "Users keep the rights to their posts, photos and reviews and allow AdventureHive to "
                  "display them. Campsite information is community-edited with a full version history. "
                  "Map data © OpenStreetMap contributors (ODbL)."),
    ("Server-side enforcement", "Hiding a button is never the only protection. Every API endpoint checks "
                                "permissions on the server, and the key rules (only attendees review; "
                                "seats never exceed capacity) are also enforced by PostgreSQL. Being logged "
                                "in does not by itself grant access."),
    ("Research data", "Interview notes stay with the team under participant codes. No recordings or "
                      "contact details are stored or published."),
]

DECISIONS = [
    {"evidence": "P1 misread the badge “Confirmed by organizer” (I6)",
     "implication": "Trust labels must be explicit", "decision": "Change",
     "rationale": "Renamed to “Marked as attended by organizer”; the reviews section says "
                  "organizers can't edit or remove reviews."},
    {"evidence": "P1 and P2 trust attendance-based reviews (I1)",
     "implication": "Keep the attendance gate", "decision": "Keep",
     "rationale": "It is the main reason users would trust the platform."},
    {"evidence": "P1 and P2 dislike waiting for campsite approval (I3)",
     "implication": "New places should be visible sooner", "decision": "Change",
     "rationale": "Submitted campsites are now shown as “Not yet verified”. Pre-moderation is "
                  "kept where it matters: no trips or questions until a moderator approves, because P2 "
                  "showed wrong information causes real problems on trips."},
    {"evidence": "P2: wrong fees and permits cause problems (I2)",
     "implication": "Fees and permit rules need their own fields", "decision": "Add",
     "rationale": "Added a fees field, separate rules, the managing park office, and a “checked by "
                  "a moderator” date."},
    {"evidence": "P2 asked for an organizer dashboard (I5)",
     "implication": "Overview of trips and tasks", "decision": "Add",
     "rationale": "“Trips organised” page in the account menu."},
    {"evidence": "P2 wanted good answers to stand out",
     "implication": "Rank helpful answers", "decision": "Add",
     "rationale": "“Helpful” votes; the accepted answer stays first."},
    {"evidence": "P2 wants to fix missed check-ins (I4)",
     "implication": "Easy attendance correction", "decision": "Keep",
     "rationale": "The organizer can mark someone attended with a written reason."},
    {"evidence": "P2 wanted group messaging between participants",
     "implication": "Real-time messaging", "decision": "Remove",
     "rationale": "LINE already covers chat well, and real-time messaging needs extra infrastructure."},
    {"evidence": "P1 wants weather/terrain and category ratings; P2 wants evidence photos for edits",
     "implication": "Richer campsite information", "decision": "Defer",
     "rationale": "Useful, but not needed for the core trip workflow."},
]

MVP_FEATURES = [
    ("Campsite discovery", "Map, filters and campsite pages with checked fees, permits and rules."),
    ("Trips", "Create, publish, join and leave, with an automatic waitlist and a capacity that can never be exceeded."),
    ("Attendance", "Self check-in code plus organizer confirmation."),
    ("Verified reviews", "Clear badges, reporting, and moderator hiding."),
    ("Campsite contributions", "Suggestions shown as “Not yet verified”, moderator approval, and version history."),
    ("Organizer tools", "“Trips organised” dashboard, repeat a trip, organizer record."),
    ("Privacy", "PDPA consent, opt-in emergency contact sharing, account deletion."),
    ("Community", "Groups with post approval, trip posts, Q&A with helpful votes, notifications."),
]

OUT_OF_SCOPE = [
    "Real-time messaging", "Semantic search", "Weather alerts", "Ratings by category",
    "Evidence photos on edit suggestions", "A native mobile app (the web app works on phones instead)",
]

CHANGES_FROM_PROPOSAL = (
    "Messaging and semantic search were moved out of scope. Attendance verification, the organizer "
    "dashboard, repeat trips, helpful votes, fee and permit fields, and the “Not yet verified” "
    "campsite state were added or strengthened because of user and course feedback."
)

PERSONAS_BY_SLUG = {p["slug"]: p for p in PERSONAS}
SCENARIOS_BY_SLUG = {s["slug"]: s for s in SCENARIOS}
