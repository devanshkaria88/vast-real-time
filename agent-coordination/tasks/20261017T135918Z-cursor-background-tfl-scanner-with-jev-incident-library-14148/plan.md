# Plan: Background TfL scanner with Jev incident library

| Field | Value |
| --- | --- |
| Task ID | `20261017T135918Z-cursor-background-tfl-scanner-with-jev-incident-library-14148` |
| Created by | cursor |
| Scope | `server/watch.py,server/app.py,server/services.py,server/tfl.py,poodle/js,poodle/app.css,.env.example,.gitignore,README.md,AGENTS.md` |
| Created | 2026-10-17T13:59:18Z |
| Initial status | planned |

## Goal

While the Poodle server runs, scan every live TfL JamCam in the background, let Jev
judge each new frame, and keep a browsable library of every incident it finds
(frames, the camera's 10 s clip, Jev answers, conditions, human review label).
Every judged frame is also logged as a compact observation row: the data mine.

Success: server starts the scanner by itself when a Jev key is set; new frames are
judged within ~1 min of TfL publishing them; incidents open, confirm (2 frames) and
clear on their own; the desk has an "Incident library" view with live scanner
status, filters, a detail dialog with box overlay and clip, and review buttons.

## Findings that shape the design (probed 17 Oct 2026)

- JamCam stills: 352x288 baseline JPEG, 15-24 KB. Inside Jev image limits as is
  (>= 280 px per side, >= 78,400 px). Clip: ~165 KB MP4 with the same Last-Modified.
- S3 honours `If-None-Match` (304, 0 bytes): poll every camera cheaply.
- Camera list `modified` field is weeks old: useless for change detection.
- Frame age median 5.1 min, p90 7.5 min: each camera refreshes every ~5-7 min,
  so all 811 live cameras give ~8k frames/hour.
- Jev 1.14.0 with images works on our key: crash stills scored incident 0.94-0.99,
  kind collision ~1.00; live normal frames 0.10-0.13, kind normal. 250-940 ms.
  ~590 tokens per image, ~100 per question; 12 questions = ~1,700 tokens
  = $0.00007/frame, ~$0.60/hour for all of London.

## Plan

1. `server/watch.py` (new): the one reviewable file for frame questions and
   thresholds; scheduler that conditional-GETs due cameras (bounded concurrency),
   skips unchanged/frozen/placeholder frames; Jev judge workers (one batched
   request per frame, box only on 1.14); incident tracker (open at incident >= 0.7
   with an incident kind, keep at >= 0.5, confirm after 2 flagged frames, clear
   after 2 quiet frames or 30 min without frames); saves frames + MP4 clip with
   SHA-256; daily observation JSONL; incidents.json; status + cost; pause/resume;
   optional daily budget and camera limit; backoff on Jev errors.
2. `server/services.py`: share Jev endpoint/key/model resolution.
3. `server/app.py`: start/stop the watcher in lifespan; `/api/watch` (GET, POST
   pause/resume), `/api/incidents` (list), `/api/incidents/{id}` (detail),
   `/api/incidents/{id}/review`; mount `server/data/library` at `/library`;
   watch summary in `/api/health`; incident lifecycle events via `record_event`
   (so they reach VastDB when configured).
4. Frontend: new `poodle/js/incidents.js` (library view, scanner strip, detail
   dialog with box overlay, frames filmstrip, clip, review buttons); sidebar item,
   route `#/incidents`, command menu entry, `G L` shortcut, polling while open.
5. `.gitignore` (library runtime data), `.env.example`, README, AGENTS.md notes.

## Files and impact

- New: `server/watch.py`, `poodle/js/incidents.js`.
- Edited: `server/app.py`, `server/services.py`, `poodle/js/main.js`, `poodle/js/ui.js`
  (icons), `poodle/app.css`, `.gitignore`, `.env.example`, `README.md`, `AGENTS.md`.
- Runtime data (gitignored): `server/data/library/{incidents.json,observations-*.jsonl,frames/,clips/}`.
- Spends Jev tokens whenever the server runs with a key (~$0.60/hour all London);
  `POODLE_WATCH=off`, `POODLE_WATCH_LIMIT`, `POODLE_WATCH_DAILY_USD` and the Pause
  button control it.

## Validation

- Unit-style check of the tracker with synthetic answers (open, confirm, clear).
- Run the server with a small camera limit, confirm frames are judged, observation
  rows written, 304s counted, status endpoint sane.
- Inject a known crash still through the judge path to prove an incident opens,
  saves frame + clip, shows in `/api/incidents` and in the UI.
- Browser check of the library view and detail dialog; no console errors.

## Handoff checkpoint

- Last completed: Scanner, library, API, desk view, docs. Live on the dev server.
- Current state: Scanning all ~811 cameras; no real incident yet (live frames peak at 0.63).
- Next action: Review the first real incidents and retune thresholds with the labels.
- Blockers: None.
- Validation state: Tracker test (scripted answers), end-to-end run with real Jev on crash
  stills + live frames (open, confirm, clear, frames, clip), live sweep of 811 cameras with
  no errors, restart judged 39 changed stills instead of 811, browser check of list, dialog,
  clip, review, tabs, filter, shortcut with no runtime errors.

## Plan changes and decisions

- 2026-10-17T13:59:18Z — Task created. Fill this plan before modifying scoped files.
- 2026-10-17T14:10Z — One batched Jev request per frame (speculative fan-out) rather
  than a two-stage triage: the image dominates cost and a second call re-sends it.
- 2026-10-17T14:10Z — Observations stay in local daily JSONL (high volume); incident
  lifecycle events go through the existing `record_event` sink, which reaches VastDB
  when configured.
- 2026-10-17T14:12Z — Measured refresh from 722 real intervals: 5-8 min (median 7.1), not
  1-3 min; corrected README, tfl.py and two camera UI strings.
- 2026-10-17T14:12Z — Added `POODLE_LIBRARY_DIR` (also used to test the UI on a throwaway
  library), frame pinning so the scanner strip loads during a sweep burst, and
  `cams.json` saved on shutdown so restarts skip unchanged stills.
