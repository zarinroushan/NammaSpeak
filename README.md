# NammaSpeak — Kannada for Real Life

A solo hackathon MVP for the Kannada Digital Innovation Hackathon 2026, aligned with problem statement **“Kannada in Everyday Life.”**

## Current features
- Responsive interface with Explore, Practice, and Saved views.
- Phrase search and category filters.
- Kannada script, transliteration, English meaning, and situational context.
- Browser speech synthesis when a Kannada voice is available.
- Five-question situation-based practice quiz with answer feedback and scoring.
- Saved phrases, learned phrase count, and practice statistics persisted in `localStorage`.

## Run locally
No build tools or backend are required for this first iteration.
1. Extract the ZIP.
2. Open `index.html` in Chrome, Edge, or Firefox.
3. For best browser speech support, run a local static server from this folder:
   - Python: `python -m http.server 8000`
   - Visit `http://localhost:8000`

## Stack
HTML, CSS, vanilla JavaScript, `localStorage`, and the browser Web Speech API. Flask is intentionally deferred until a real backend need emerges.

## Important language-quality note
This starter includes a small illustrative phrase dataset. Before public judging or real-world use, verify every Kannada phrase, transliteration, translation, and situational explanation with a knowledgeable Kannada speaker or reliable language source. Browser text-to-speech availability and pronunciation quality vary by operating system and browser.

## Next iterations
1. Validate and expand the phrase dataset.
2. Make wrong-answer revision targeted and reliable.
3. Improve accessibility and test mobile layouts.
4. Add an onboarding/use-case explanation and a demo mode.
5. Deploy the static site and test it on a clean browser/device.
6. Prepare a short demo, screenshots, and final submission materials.

## Submission reminder
The event listing provided by the participant states that project submission opens 24 October 2026 at 12:00 AM IST and closes 25 October 2026 at 10:00 PM IST. Confirm the final requirements on Unstop.
