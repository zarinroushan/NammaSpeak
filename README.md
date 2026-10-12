# NammaSpeak — Kannada for Real Life

**Event:** Kannada Digital Innovation Hackathon 2026  
**Organizers:** HackerRank Campus Crew & The National Institute of Engineering, Mysuru  
**Theme:** Code. Create. Celebrate Kannada.  
**Problem Statement:** *Kannada in Everyday Life* (Practical communication for travel, dining, shopping, transit, and healthcare)  
**Submission Deadline:** 25 October 2026 at 10:00 PM IST  

---

## 1. Executive Summary & Mission

Moving to or traveling through Karnataka often presents non-Kannada speakers with immediate communication friction in daily situations:
- Asking whether a BMTC/KSRTC bus reaches your destination before it pulls away.
- Ordering coffee and breakfast with ease at a local Darshini.
- Asking prices and negotiating courteously at KR Market or neighborhood stores.
- Communicating symptoms or locating an open pharmacy during a health emergency.

**NammaSpeak** is an interactive, solo-built full-stack web application designed to bridge this gap. Rather than memorizing abstract grammar rules, learners acquire practical conversational confidence through:
1. **Contextual Phrase Explorer:** Filterable and searchable phrases with Kannada script, Roman transliteration, English meaning, and situational etiquette notes.
2. **Audio Pronunciation Support:** Server-side ElevenLabs speech generation for Kannada pronunciation, with normal and browser-rate-adjusted slow playback. Slow playback uses `HTMLAudioElement.playbackRate` at approximately 0.7×; pitch-preservation is requested where supported, but exact sound quality depends on the browser.
3. **Interactive Situational Quizzes:** Real-life dialogues featuring simulated conductors, waiters, and shopkeepers, with educational explanations for every response.
4. **Adaptive Mistake Revision:** Spaced review prioritizing phrases where errors occurred, persisted in an SQLite database.
5. **Personal Phrasebook:** Offline-accessible saved collection.
6. **Replaceable AI Conversation Companion:** Interactive conversational practice backed by Google Gemini or OpenAI when configured, with a 100% offline deterministic fallback engine.

---

## 2. Diagnosis: Root Cause of Previous Blank Page & 404 `/app.js`

When first extracted, the project experienced a blank page and a 404 error when requesting `/app.js`:

1. **Root Directory Mismatch & Relative Path Resolution:**  
   When developers run `python -m http.server 8000` from a parent directory (e.g. `Desktop/`) rather than the project folder, navigating to `/NammaSpeak/` caused absolute requests like `/app.js` to look at the web server root `http://localhost:8000/app.js` rather than `http://localhost:8000/NammaSpeak/app.js`, returning a 404 status.
2. **Dynamic DOM Dependency:**  
   The application uses dynamic DOM rendering for the category grid, phrase cards, and scenario quizzes. When `/app.js` failed to load due to the 404, no JavaScript executed, leaving the DOM containers empty and appearing as a blank page.
3. **Missing Flask Backend & Static Routing:**  
   The original starter relied purely on browser `localStorage` without a persistent database or Flask backend. When moving to a full-stack Flask architecture, Flask must route static assets cleanly.

### How We Fixed It:
- **Canonical Architecture:** Organized code into `backend/` and `frontend/` with clean separation of concerns.
- **Universal Static Fallback in Flask:** In `backend/app.py`, Flask is configured to serve both direct routes (`/styles.css`, `/app.js`) and modular paths (`/frontend/styles.css`, `/frontend/app.js`).
- **Resilient Root Entry Point:** Updated `index.html` and root files to seamlessly forward to the modular frontend assets.
- **Local Fallback Protection:** `frontend/api.js` gracefully handles network transitions without throwing uncaught page-freezing errors.

---

## 3. Technology Stack

- **Frontend:** HTML5, CSS3 (Custom Properties, responsive Grid & Flexbox, accessible semantic markup), Vanilla JavaScript (ES Modules).
- **Backend:** Python 3, Flask 3.1+, SQLite3 with standard library parameter binding (SQL injection proof).
- **Data Persistence:** SQLite (`instance/nammaspeak.db`) tracking phrases, scenarios, saved phrasebook, user progress, and mistake-driven adaptive revision metrics.
- **AI Conversation Architecture:** Replaceable provider abstraction (`BaseAIProvider`) with `LocalFallbackProvider` (deterministic, offline-first), `GeminiProvider`, and `OpenAIProvider` (official REST APIs).
- **Testing:** Pytest 9.1+ with isolated in-memory/temp database fixtures.

---

## 4. Project Directory Structure

```text
NammaSpeak/
├── .env.example              # Template for environment secrets
├── .gitignore                # Excludes venv, instance/*.db, .env, __pycache__
├── index.html                # Single-page application entry point
├── app.js                    # Backwards-compatible root forwarder
├── styles.css                # Synced root stylesheet
├── requirements.txt          # Python dependencies
├── README.md                 # Complete documentation & demo guide
├── frontend/
│   ├── app.js                # Main state controller & UI event orchestrator
│   ├── api.js                # Fetch API client with error handling
│   ├── ui.js                 # DOM renderers, SpeechSynthesis, clipboard & toast
│   ├── styles.css            # Responsive layout, palette, and typography
│   └── assets/               # Static icons and graphic assets
├── backend/
│   ├── __init__.py
│   ├── app.py                # Flask app factory, static routing, entry point
│   ├── config.py             # Configuration loader from .env
│   ├── models.py             # SQLite schema, connection pool & idempotent seeder
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── health.py         # Health check and provider status
│   │   ├── phrases.py        # Phrase search, filtering, and detail
│   │   ├── practice.py       # Situational scenarios and answer validation
│   │   ├── progress.py       # Phrasebook, stats, and adaptive revision queue
│   │   └── ai.py             # AI chat and phrase explanation endpoints
│   ├── services/
│   │   ├── __init__.py
│   │   ├── phrase_service.py # Phrase querying & phrasebook logic
│   │   ├── revision_service.py # Adaptive spaced review & scoring
│   │   ├── ai_provider.py    # Replaceable AI interface (Local, Gemini & OpenAI)
│   │   └── conversation_engine.py # Facade orchestrating dialogues
│   ├── data/
│   │   ├── seed_phrases.json # Curated everyday Kannada phrase dataset
│   │   └── seed_scenarios.json # Real-life situational conversation quizzes
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py       # Isolated temp database fixtures
│       ├── test_health.py    # Health check tests
│       ├── test_phrases.py   # Phrase listing, search, category filters
│       ├── test_practice.py  # Answer correctness & mistake routing
│       ├── test_phrasebook_and_progress.py # CRUD & persistent stats
│       ├── test_ai_fallback.py # Local fallback, input validation & disclaimers
│       └── verify_live.py    # Live HTTP endpoint suite
└── instance/
    └── .gitkeep              # Local SQLite database directory (nammaspeak.db)
```

---

## 5. Quick Start Instructions (Windows)

### Prerequisites:
- Python 3.10+ (tested on Python 3.14)
- Google Chrome or modern web browser

### Step 1: Clone or Open the Repository
Open PowerShell in the project directory:
```powershell
cd c:\Users\user\Desktop\NammaSpeak
```

### Step 2: Create and Activate Virtual Environment
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### Step 3: Install Dependencies
```powershell
pip install -r requirements.txt
```

### Step 4: Run the Application
Start the Flask server:
```powershell
python backend/app.py
```
Output:
```text
[NammaSpeak] Server running on http://127.0.0.1:5000
 * Serving Flask app 'app'
 * Running on http://127.0.0.1:5000
```

### Step 5: Open in Your Browser
Visit:
```
http://127.0.0.1:5000
```
*Note: The frontend can also be viewed by opening `index.html` directly or running `python -m http.server 8000` from this folder.*

---

## 6. Optional AI Configuration

By default, NammaSpeak uses the built-in **Deterministic Local Engine**. It requires **zero API keys** and works completely offline.

To enable live generative AI responses using Google Gemini or OpenAI:
1. Copy `.env.example` to `.env`:
   ```powershell
   Copy-Item .env.example .env
   ```
2. Open `.env` and configure your API key:
   ```env
   AI_PROVIDER=gemini
   GEMINI_API_KEY=your_gemini_api_key_here
   AI_MODEL=gemini-3.8-flash
   # Alternatively, select OpenAI without changing the Gemini settings:
   # AI_PROVIDER=openai
   # OPENAI_API_KEY=your_openai_api_key_here
   # OPENAI_MODEL=gpt-4o-mini
   # OPENAI_REQUEST_TIMEOUT=15
   ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
   ELEVENLABS_VOICE_ID=your_kannada_supported_voice_id
   ELEVENLABS_MODEL=eleven_v3
   ELEVENLABS_TTS_TIMEOUT=15
   ```
3. `AI_MODEL` is checked against the models advertised for the configured key. Leave it blank to automatically select an advertised stable model that supports `generateContent`.
4. Restart the Flask server. The status badge in the header will display the selected provider.
5. If the selected provider has an invalid key, quota, billing, or network failure, NammaSpeak returns a localized unavailable response rather than presenting an unrelated hardcoded lesson as an AI answer. The 22 offline phrases remain available in phrase search and learning views.

---

## 7. Backend REST API Summary

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Service health, database status, active AI provider |
| `GET` | `/api/categories` | List of phrase categories with icons and metadata |
| `GET` | `/api/phrases` | Query phrases with `?category=` and `?search=` |
| `GET` | `/api/phrases/<id>` | Retrieve specific phrase details by ID |
| `GET` | `/api/practice/scenarios` | List situational conversation practice scenarios |
| `GET` | `/api/practice/scenarios/<id>` | Retrieve a single scenario with dialogue options |
| `POST` | `/api/practice/answer` | Validate answer, update SQLite progress, route mistakes |
| `GET` | `/api/progress` | User learning metrics, accuracy, saved count |
| `POST` | `/api/progress` | Update or reset user statistics (`action: "reset"`) |
| `GET` | `/api/phrasebook` | Get all saved phrases in user's phrasebook |
| `POST` | `/api/phrasebook` | Add phrase to phrasebook (`{"phrase_id": "p1"}`) |
| `DELETE` | `/api/phrasebook/<id>` | Remove phrase from phrasebook |
| `GET` | `/api/revision` | Adaptive revision queue of missed phrases |
| `POST` | `/api/revision/resolve` | Mark tricky phrase as mastered |
| `POST` | `/api/ai/chat` | Simulated conversational response turn |
| `POST` | `/api/ai/explain` | Contextual etiquette & grammar explanation |

---

## 8. Adaptive Revision Algorithm

Rather than showing a generic score, NammaSpeak implements an adaptive mistake-priority learning loop:
1. When a user selects an answer during conversation practice, the selection is sent to `/api/practice/answer`.
2. If incorrect, the related phrase is flagged in SQLite table `phrase_learning_stats` with `mistakes = mistakes + 1` and `needs_revision = 1`.
3. The **Adaptive Revision** view displays phrases prioritized by mistake count (`ORDER BY mistakes DESC`).
4. Users can review the phrase, hear its pronunciation, read why the mistake occurred, and mark it as **Mastered** once comfortable.

---

## 9. Healthcare & Emergency Disclaimer

NammaSpeak includes communication assistance for clinics, pharmacies, and urgent situations (e.g. asking for the nearest hospital or doctor).
- **Communication Only:** Content is strictly limited to language translation and situational phrases.
- **No Medical Advice:** NammaSpeak does **not** provide medical diagnoses or treatment recommendations.
- **Emergency Numbers:** The application prominently displays Karnataka emergency helplines: **108** (Ambulance) and **112** (National Emergency Helpline).

---

## 10. Automated Tests & Quality Verification

NammaSpeak includes an automated Pytest test suite covering all core backend logic, database persistence, and AI fallbacks.

To run the test suite:
```powershell
.\venv\Scripts\pytest -v
```

### Test Results:
```text
backend/tests/test_ai_fallback.py::test_ai_chat_local_fallback PASSED
backend/tests/test_ai_fallback.py::test_ai_chat_missing_message PASSED
backend/tests/test_ai_fallback.py::test_ai_chat_excessive_length PASSED
backend/tests/test_ai_fallback.py::test_ai_explain_endpoint PASSED
backend/tests/test_ai_fallback.py::test_ai_healthcare_disclaimer_behavior PASSED
backend/tests/test_health.py::test_health_endpoint PASSED
backend/tests/test_phrasebook_and_progress.py::test_phrasebook_crud_and_progress PASSED
backend/tests/test_phrasebook_and_progress.py::test_phrasebook_invalid_operations PASSED
backend/tests/test_phrases.py::test_list_categories PASSED
backend/tests/test_phrases.py::test_list_phrases PASSED
backend/tests/test_phrases.py::test_filter_phrases_by_category PASSED
backend/tests/test_phrases.py::test_search_phrases PASSED
backend/tests/test_phrases.py::test_get_phrase_by_id_success PASSED
backend/tests/test_phrases.py::test_get_phrase_by_id_unknown_returns_404 PASSED
backend/tests/test_practice.py::test_list_scenarios PASSED
backend/tests/test_practice.py::test_get_scenario_by_id PASSED
backend/tests/test_practice.py::test_get_scenario_by_id_unknown PASSED
backend/tests/test_practice.py::test_submit_correct_answer PASSED
backend/tests/test_practice.py::test_submit_incorrect_answer PASSED
backend/tests/test_practice.py::test_submit_answer_missing_fields PASSED
backend/tests/test_practice.py::test_submit_answer_invalid_option PASSED
============================= 21 passed in 1.50s ==============================
```

To run the live HTTP endpoint integration test against the running server:
```powershell
python backend/tests/verify_live.py
```

---

## 11. Hackathon Judges Demo Script (3-Minute Walkthrough)

1. **Introduction (30s):**
   - *"Namaskara! I am presenting NammaSpeak for the Kannada in Everyday Life hackathon theme. Many people who move to Bengaluru or Karnataka want to speak Kannada, but traditional apps teach disconnected vocabulary rather than situational confidence."*
2. **Contextual Phrase Explorer (45s):**
   - Click **Explore**. Show category chips (Transport, Food, Shopping, Health, Work, Courtesy).
   - Type `"bus"` or `"coffee"` in search. Show the Kannada script, clear transliteration, and situational notes.
   - Click **▶ Listen** to demonstrate audio pronunciation.
   - Click **💡 Learn Context** to open the in-depth etiquette modal.
   - Click **♥ Save** on a phrase and show the **Phrasebook** view updating instantly.
3. **Real Practice & Adaptive Revision (60s):**
   - Click **Practice**. Show Scenario 1: *"At the Bus Stand with a BMTC Conductor"*.
   - Intentionally select an incorrect option to show educational feedback: explain why that phrase belongs in a café instead of a bus stand.
   - Navigate to the **Revision** tab to show how the missed phrase was automatically routed for adaptive practice with mistake counts.
   - Answer correctly on the next attempt and click **✓ Mastered** to resolve it.
4. **AI Conversation Companion (45s):**
   - Click **AI Partner 💬**.
   - Select *"Ordering Food at Darshini / Café"*.
   - Send: *"How do I order one masala dosa and coffee?"*
   - Show the structured Kannada response, English breakdown, and etiquette tip.
   - Point to the connection pill showing the active provider (Offline Deterministic or Gemini API).
   - Highlight the emergency disclaimer ensuring responsible AI use.

---

## 12. Known Limitations & Roadmap

1. **Browser Speech Synthesis Variations:** OS-level support for native Kannada TTS voices varies across Windows, macOS, Android, and Linux. When an OS lacks a native Kannada voice, NammaSpeak gracefully falls back to transliteration display. A planned iteration will integrate dedicated server-side neural TTS audio clips.
2. **Native Speaker Dataset Expansion:** The starter dataset includes 22 curated phrases and 6 situational scenarios. All phrases were structured for real life; future releases will include audio recorded by native Kannada speakers across Karnataka dialects (Old Mysuru, North Karnataka, Coastal/Mangaluru).
3. **Multi-User Accounts:** The current MVP operates in single-user demo mode. Adding optional JWT authentication will allow multi-device progress syncing.

---

## 13. License & Acknowledgments

Created with passion for the **Kannada Digital Innovation Hackathon 2026**.  
*ಕನ್ನಡ ಕಲಿಯೋಣ, ಕನ್ನಡದಲ್ಲೇ ಮಾತನಾಡೋಣ!* (Let us learn Kannada, let us speak in Kannada!)
