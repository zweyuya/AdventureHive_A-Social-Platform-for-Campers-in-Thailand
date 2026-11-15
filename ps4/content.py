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
    {"code": "P1", "user_class": "First-time camper (has never camped)",
     "mode": "Online (Zoom), clickable prototype", "duration": "about 20 min"},
    {"code": "P2", "user_class": "Regular camper and camping-club member",
     "mode": "Online (Zoom), clickable prototype", "duration": "about 20 min"},
    {"code": "P3", "user_class": "Trip organizer",
     "mode": "Online (Zoom), clickable prototype", "duration": "about 20 min"},
    {"code": "P4", "user_class": "First-time camper (has never camped)",
     "mode": "Online (Zoom), clickable prototype", "duration": "about 20 min"},
]

FINDINGS = [
    {"id": "I1", "title": "Trust needs a credible verification signal",
     "evidence": "All four participants look for proof before trusting a review: P1 and P2 trust reviews "
                 "backed by official or authorised sources, P4 checks the verification status and the "
                 "reviewer, and P3 looks at whether the user is verified. P2 read the attendance badge as "
                 "meaning the review is trustworthy.",
     "meaning": "The attendance gate stays the core of the design. Some users also want official "
                "backing, which attendance alone does not give."},
    {"id": "I2", "title": "Fees, permits and facilities are hard to find for everyone",
     "evidence": "P2 found permit pages on an official park site confusing to navigate, P1 named permits "
                 "and facilities as the hardest information, and P3 had to ask hotels near the campsite "
                 "to confirm them because no proper website existed.",
     "meaning": "Checked fee, permit and facility information matters to campers and beginners, not "
                "only to organizers."},
    {"id": "I3", "title": "Outdated information and slow responses drive people away",
     "evidence": "Asked what would stop them using the service, all four named outdated pages, "
                 "unanswered questions, misinformation or many negative reviews.",
     "meaning": "Users need to see when information was last checked and when answers were written."},
    {"id": "I4", "title": "Some prefer direct contact over Q&A",
     "evidence": "P1 and P2 named Q&A as the least useful feature and preferred a phone call or direct "
                 "contact; P3 and P4 found no feature least useful.",
     "meaning": "Q&A must stay fresh to be useful. Personal phone numbers can't be published, but the "
                "park office's public contact can."},
    {"id": "I5", "title": "Verification and check-in labels need explaining",
     "evidence": "P2 asked what “marked by organizer” means, P3 needed a hint on “Checked in” versus "
                 "“Did not check in”, and P2 suggested renaming “Trips” to “Upcoming trips”.",
     "meaning": "Labels about trust and check-in need a short explanation next to them."},
    {"id": "I6", "title": "Organizers accept light attendance work but need clear feedback",
     "evidence": "P3 found the trip under “Needs your attention” without help, found attendance "
                 "tracking very helpful and the reason rule fair, but was only sure the list had saved "
                 "after refreshing.",
     "meaning": "Keep the dashboard and the reason rule; add a “saved” confirmation and show the "
                "list first."},
    {"id": "I7", "title": "Beginners rely on friends and explicit level information",
     "evidence": "P1 and P4 find places and companions through friends. Both completed the beginner "
                 "task with no hints and found the experience levels and equipment list clear.",
     "meaning": "Experience levels, the refusal message and the equipment list work for beginners."},
    {"id": "I8", "title": "Missing or shared equipment causes problems on trips",
     "evidence": "P2's group ran short of firewood; P3 said people forget torches or batteries, so "
                 "torches get shared.",
     "meaning": "A clear equipment list per trip addresses a real problem."},
]

DISAGREEMENTS = [
    ("Q&A versus direct contact", "P1 and P2 found Q&A the least useful feature; P3 and P4 found "
                                  "nothing least useful."),
    ("Where trust comes from", "P1 and P2 want official or association backing; P3 and P4 judge the "
                               "reviewer's verification and writing."),
    ("Camper versus organizer tasks", "The three campers needed no hints; the organizer needed hints on "
                                      "two of four steps."),
]

OPEN_QUESTIONS = [
    "We did not ask whether “unresponsive” meant slow pages or unanswered questions.",
    "Two participants' camping experience is from outside Thailand, so Thai-specific habits are under-represented.",
    "All sessions were on a laptop; the phone scenario and campsites without signal are untested.",
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
            ("Frustrations", "Official permit pages that send her from page to page; posts and answers that "
                             "are out of date; no way to tell if a reviewer really went."),
            ("Technology and access", "Uses a phone for almost everything; mobile signal at campsites is "
                                      "weak or missing."),
            ("Expectations", "Reviews she can trust, information that shows when it was last checked, and "
                             "labels that explain themselves."),
        ],
        "findings": ["I1", "I2", "I3", "I5", "I8"],
        "evidence_note": "Mainly built on P2, a regular camper and club member.",
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
            ("Frustrations", "No single reliable source for permits and facilities, so he calls around; "
                             "people forgetting shared items such as torches; extra admin after the trip."),
            ("Technology and access", "Uses a laptop to plan and a phone on the trip."),
            ("Expectations", "One place to see every trip and what needs doing; quick attendance with a "
                             "clear saved message; accurate, checked campsite data."),
        ],
        "findings": ["I2", "I5", "I6", "I8"],
        "evidence_note": "Mainly built on P3, a trip organizer.",
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
        "findings": ["I7", "I2", "I1", "I3"],
        "evidence_note": "Built on P1 and P4, two first-time campers.",
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
            "After the trip, “Trips organised” shows the attendance deadline. One participant's phone "
            "battery died, so he marks her as attended with a reason and saves.",
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
            "She opens the trips list and looks for a trip with no minimum experience.",
            "On the trip page she checks the difficulty and the equipment list, "
            "which says the organizer brings the cooking stove and each person brings a tent and sleeping bag.",
            "On the campsite page she checks the fees and confirms there are restrooms and water.",
            "She joins the trip and gets a confirmed seat.",
        ],
        "outcome": "Fah joins a trip that suits a beginner and knows what to bring and what it costs.",
        "exception": "The first trip she likes requires intermediate experience, so the app refuses her "
                     "and explains why. She picks another trip marked as suitable for beginners instead.",
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
     "story": "As a first-time camper, I am stopped from joining a trip above my experience level so "
              "that I don't end up on a trip that is too hard.",
     "criteria": ["Given a trip requiring intermediate experience and my profile says beginner, when I "
                  "press Join, then I am not added and I see a message explaining the required level."]},
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
     "story": "As an organizer, I am the only one who can see and change my trip's attendance list so "
              "that participants' privacy is protected.",
     "criteria": ["Given a trip, when anyone other than its organizer (including a platform admin) "
                  "requests or changes the attendance list, then the server returns 403."]},
    {"id": "US6", "priority": "Must",
     "story": "As an organizer, I can mark a participant who could not check in as attended, with a "
              "reason, and see that it was saved.",
     "criteria": ["Given a participant who did not check in, when I mark them attended without a "
                  "reason, then the save is refused.",
                  "When I add a reason and save, then the status changes to attended, the reason is "
                  "stored, and an “Attendance saved” message is shown."]},
    {"id": "US7", "priority": "Should",
     "story": "As an organizer, I can see all my trips and what needs doing so that I don't miss tasks.",
     "criteria": ["Given I organised a completed trip without recorded attendance, when I open “Trips "
                  "organised”, then it appears under “Needs your attention” with the deadline."]},
    {"id": "US8", "priority": "Should",
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
    {"evidence": "All four participants look for verification before trusting a review (I1)",
     "implication": "Keep the attendance gate", "decision": "Keep",
     "rationale": "It is the main reason participants would trust AdventureHive over social media."},
    {"evidence": "P2 asked what “marked by organizer” means; P3 needed a hint on check-in (I5)",
     "implication": "Trust and check-in labels must explain themselves", "decision": "Change",
     "rationale": "A one-line explanation under each review badge and a check-in note on the attendance list."},
    {"evidence": "P3 was only sure attendance had saved after refreshing (I6)",
     "implication": "Visible feedback after saving", "decision": "Add",
     "rationale": "An “Attendance saved” confirmation (US6)."},
    {"evidence": "P3 suggested the participant checklist above the check-in code (I6)",
     "implication": "The organizer's main job comes first", "decision": "Change",
     "rationale": "Reorder the attendance page."},
    {"evidence": "P2 found the “Trips” tab name unclear (I5)",
     "implication": "Clearer navigation wording", "decision": "Change",
     "rationale": "Rename the tab “Upcoming trips”."},
    {"evidence": "P3 found the reason for missed check-ins fair (I6)",
     "implication": "Keep the rule", "decision": "Keep",
     "rationale": "It stops organizers marking people attended without thought, which protects review trust."},
    {"evidence": "Permits and facilities were hard to find for P1, P2 and P3 (I2)",
     "implication": "Checked fee, permit and facility fields", "decision": "Keep",
     "rationale": "Fields and a “checked by a moderator” date exist; also show them on trip pages."},
    {"evidence": "All four would leave over outdated or unresponsive pages (I3)",
     "implication": "Show freshness", "decision": "Change",
     "rationale": "Show the “last checked” date prominently and a date on every Q&A answer."},
    {"evidence": "P1 and P2 found Q&A least useful; P3 and P4 did not (I4)",
     "implication": "Quicker, more authoritative answers", "decision": "Keep",
     "rationale": "Kept despite criticism: one shared answer helps every later visitor. Members' phone "
                  "numbers are not published (PDPA); the park office's public contact is shown instead."},
    {"evidence": "P1 and P4 completed the beginner task without help (I7)",
     "implication": "The level and refusal design works", "decision": "Keep",
     "rationale": "Experience levels, the refusal message and the equipment list stay (US2)."},
    {"evidence": "P1 and P2 want official backing (I1); sign-in with Google was suggested",
     "implication": "Partner validation; faster sign-up", "decision": "Defer",
     "rationale": "Park-authority partnerships and an external sign-in provider are beyond this semester."},
    {"evidence": "Survey: only 1 of 4 would trust AdventureHive reviews more than Facebook or LINE",
     "implication": "Trust has to be earned visibly", "decision": "Keep",
     "rationale": "Keep the badge, but explain it and show “last checked” dates; ask again after launch."},
    {"evidence": "P3 found the trip under “Needs your attention” without help (I6)",
     "implication": "Organizers need one overview", "decision": "Keep",
     "rationale": "Keep the “Trips organised” dashboard."},
]

MVP_FEATURES = [
    ("Trips", "Create, publish, join and leave, automatic waitlist, capacity that can never be exceeded, "
              "and experience-level checks with a clear refusal message."),
    ("Attendance", "Self check-in code, organizer confirmation with a required reason, and a visible "
                   "“saved” message."),
    ("Verified reviews", "Only attendees review; badges with one-line explanations; reporting and moderator hiding."),
    ("Campsite information", "Map, filters, checked fees, permits and facilities with a “last checked” date "
                             "and the park office contact."),
    ("Organizer tools", "“Trips organised” dashboard, repeat a trip, organizer record."),
    ("Campsite contributions", "Suggestions shown as “Not yet verified”, moderator approval, and version history."),
    ("Privacy", "PDPA consent, opt-in emergency contact sharing, account deletion."),
    ("Community", "Groups with post approval, trip posts, Q&A with helpful votes and dated answers, notifications."),
]

OUT_OF_SCOPE = [
    "Real-time messaging", "Semantic search", "Weather alerts", "Ratings by category",
    "Evidence photos on edit suggestions", "Assigning shared equipment to people", "Sign-in with Google",
    "Partnerships with park authorities", "A native mobile app (the web app works on phones instead)",
]

CHANGES_FROM_PROPOSAL = (
    "Messaging and semantic search were moved out of scope. Attendance verification, the organizer "
    "dashboard, repeat trips, helpful votes, fee and permit fields, the “Not yet verified” campsite "
    "state and experience-level checks were added or strengthened because of user and course feedback. "
    "The prototype sessions added explanation labels, a save confirmation and freshness dates."
)

PERSONAS_BY_SLUG = {p["slug"]: p for p in PERSONAS}
SCENARIOS_BY_SLUG = {s["slug"]: s for s in SCENARIOS}
