# Plan: Poodle end-to-end: Linear-style desk, incident video, live TfL cams

| Field | Value |
| --- | --- |
| Task ID | `20261017T123347Z-cursor-poodle-end-to-end-linear-style-desk-incident-vid-17094` |
| Created by | cursor |
| Scope | `poodle,server,docs/ui-audit.md,README.md,AGENTS.md,.gitignore` |
| Created | 2026-10-17T12:33:47Z |
| Initial status | planned |

## Goal

Turn the static Poodle desk into a working app an adjuster can demo end to end:

- A claims desk that looks and behaves like Linear (dark, dense, keyboard-first, restrained colour).
- Each claim opens on the incident footage (a player with event markers and detection boxes) next to the nearest live TfL JamCams.
- A live London cameras view backed by the real TfL feed.
- A Python backend on port 8080 that serves the desk, proxies TfL, hashes evidence, answers questions, computes the coverage decision, and exports an evidence pack. Sponsor-stack calls (YOLO, Cosmos, W&B, Jev, VastDB) switch on from env vars; without them the app runs in replay mode and says so.
- A written UI audit of the old desk (`docs/ui-audit.md`) that marks every place to change and tracks what was fixed.

Success: `uv run server/app.py` (or `python -m uvicorn`) serves the desk on :8080; every claim shows footage, the decision, the timeline and nearby live cams; the cameras view shows live TfL stills and plays the 10 s clips; Cmd+K and J/K work; it holds up at 1440 px and 390 px.

## Research (12:20–12:35 UTC)

- Linear tokens pulled from linear.app CSS: bg `#08090a`/`#0f1011`/`#141516`/`#191a1b`, text `#f7f8f8`/`#d0d6e0`/`#8a8f98`/`#62666d`, borders `#23252a`/`#34343a`, brand `#5e6ad2`, accent `#7170ff`, green `#27a644`, red `#eb5757`, orange `#fc7840`, yellow `#f0bf00`, blue `#4ea7fc`. Inter Variable with `cv01`,`ss03`; weights 400/510/590/680; 12–15 px UI text; radii 4/6/8/12; sidebar 232 px. Principles from "How we redesigned the Linear UI": reduce chrome, hierarchy via brightness not size, colour only for status.
- TfL JamCams are live again: `https://api.tfl.gov.uk/Place/Type/JamCam` returns 890 cameras (811 available), `access-control-allow-origin: *`. Stills refresh every ~1–3 min on S3; MP4 clips are 10.4 s, 352x288, 25 fps. Licence: images must not be cropped; attribute "Powered by TfL Open Data".
- `Demo img/` (teammate upload): 10 synthetic CCTV stills of UK collisions with burned-in clocks and camera ids.

## Plan

1. Audit the current desk with screenshots; write `docs/ui-audit.md` with numbered findings tied to lines in the old `poodle/index.html`.
2. Media: build demo incident clips from `Demo img/` with ffmpeg (re-rendered OSD clock, camera label), plus posters. Precompute YOLO detections for the stills if a local detector installs in time.
3. Backend `server/`: FastAPI app on :8080. Claims store (JSON seed), TfL cams proxy with cache + nearest-camera lookup, SHA-256 custody log, Q&A, coverage decision (code rules, Jev when keyed), evidence pack export, optional YOLO/Cosmos/W&B/Weave/VastDB adapters behind env vars.
4. Frontend `poodle/`: no build step. Linear-style shell (sidebar, inset content panel, list rows, properties panel), claim view with player + timeline + decision + nearby live cams, cameras wall, Cmd+K command menu, keyboard navigation. Poodle mascot kept, scaled to fit.
5. Validate in the browser at desktop and phone widths; update the audit with fix status; document run steps in README and AGENTS project notes.

## Design decisions

- Follow the user's brief: Linear's design system. Dark by default; colour is reserved for decision status and live indicators.
- Decision colours map to Linear's status hues: accept green `#27a644`, partial yellow `#f0bf00`, reject red `#eb5757`, refer blue `#4ea7fc`, fraud flag orange `#fc7840`.
- Inter for everything, tabular figures for ids and times; monospace only for hashes.
- TfL stills and clips shown uncropped (`object-fit: contain`) with attribution.
- Demo footage is labelled "Demo footage"; TfL is labelled "Live". Replay mode is visible in the UI when sponsor services are not connected.
- The mascot stays (earlier request: an animated poodle on top of the dashboard) but shrinks to a small perched figure that keeps signalling mood, so it does not compete with the evidence.

## Files and impact

- `poodle/` — rewritten desk: `index.html`, `app.css`, `js/*.js`, `media/` (demo clips and posters).
- `server/` — new FastAPI backend, seed data, adapters, requirements.
- `docs/ui-audit.md` — new audit with fix status.
- `README.md`, `AGENTS.md` (project notes section only), `.gitignore` — run instructions and ignores.
- `docs/IDEA.md` still points at `poodle/index.html`; the path stays valid.

## Validation

- `curl` the API endpoints (claims, cams, nearest, ask, decision, pack).
- Browser: load the desk, open every claim, play footage, open a live cam clip, use Cmd+K and J/K, check 1440 px and 390 px.
- Lints on edited files.

## Handoff checkpoint

- Last completed: Research and plan.
- Current state: Ready to audit the old desk.
- Next action: Screenshot the old desk and write docs/ui-audit.md.
- Blockers: No sponsor-stack credentials on this laptop (replay mode needed).
- Validation state: Not started.

## Plan changes and decisions

- 2026-10-17T12:33:47Z — Task created. Fill this plan before modifying scoped files.
- 2026-10-17T12:36:00Z — Plan filled after the Linear and TfL research. Waited for the previous Cursor task (Poodle dashboard) to complete before starting.
