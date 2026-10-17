# Plan: Readable README with dashboard screenshots

| Field | Value |
| --- | --- |
| Task ID | `20261017T145411Z-cursor-readable-readme-with-dashboard-screenshots-14787` |
| Created by | cursor |
| Scope | `README.md,docs/screens` |
| Created | 2026-10-17T14:54:11Z |
| Initial status | planned |

## Goal

Rewrite README.md so a first-time reader (judge, teammate, visitor) understands Poodle
quickly: plain, simplified English, sentence-case headings, no em dashes, no AI-writing
tells (humanizer skill), and fresh screenshots of the current dashboard where they help.

## Plan

1. Capture fresh 1440x900 screenshots into `docs/screens/`:
   - from a seeded instance (no Jev key, copy of the library) so the claim views show
     the recorded decisions the demo script describes: inbox, claim, statement check
     with an answer;
   - from the live dev server: cameras near claims, a YOLO live scan, the incident
     library with real incidents, one incident dialog.
2. Add a small Poodle mark SVG for the header.
3. Rewrite README.md: what it is, a short tour with screenshots, how it decides,
   run it, live vs replayed, incident library, demo script, footage credits,
   project layout, working with coding agents.
4. Humanizer pass (draft, list remaining tells, revise). Grep for em dashes, en dashes,
   curly quotes and emojis.

## Files and impact

- Planned files: `README.md`, new `docs/screens/*.jpg`, `docs/screens/poodle-mark.svg`.
- Expected impact: docs only, about 1-1.5 MB of images. No code changes.

## Validation

- Every image and link path in README.md exists.
- No em dash, en dash, curly quote or emoji in README.md.
- Facts checked against the running app (claims, shortcuts, env vars, costs).

## Handoff checkpoint

- Last completed: Facts gathered (claims, incidents, shortcuts, event name).
- Current state: Plan written.
- Next action: Capture screenshots.
- Blockers: None. Another chat's uncommitted sidebar change (Services panel removed)
  is in the working tree; screenshots will show the sidebar without it.
- Validation state: Not started.

## Plan changes and decisions

- 2026-10-17T14:54:11Z — Task created. Fill this plan before modifying scoped files.
- 2026-10-17T14:58Z — Claim screenshots come from a seeded instance because live Jev
  currently refers every claim; the README says the walkthrough uses recorded answers.
- 2026-10-17T14:59Z — Out-of-scope one-line fix in `poodle/app.css`: the rule
  `.overlay g.det:not(.at)` (from 68c522e) hid the YOLO boxes on live camera scans; it is
  now scoped to `#incident-player`. Needed for the live-scan screenshot and demo step 5.
- 2026-10-17T15:06Z — Tour images cropped or clipped to the panel or dialog so they show
  near 1:1 in GitHub's ~890 px column; the hero keeps the full app.
- 2026-10-17T15:06Z — Old demo step pointed at the "give-way line" finding for a YOLO box;
  that finding has none. README now uses "Blue car broadside across the policyholder's lane".
