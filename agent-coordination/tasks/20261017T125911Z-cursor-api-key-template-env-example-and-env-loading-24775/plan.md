# Plan: API key template (.env.example) and .env loading

| Field | Value |
| --- | --- |
| Task ID | `20261017T125911Z-cursor-api-key-template-env-example-and-env-loading-24775` |
| Created by | cursor |
| Scope | `.env.example,server/services.py,server/app.py,README.md` |
| Created | 2026-10-17T12:59:11Z |
| Initial status | planned |

## Goal

The builder wants one file listing every key Poodle needs, so they can paste them in.

Success: `.env.example` lists exactly the variables the code reads, grouped by service, each with what it switches on and where to get it. Keys pasted into `.env` reach the server without exporting anything. No real key can end up in git.

## Plan

1. List every `env(...)` / `os.environ` read in `server/` (done: 19 variables).
2. Add a dependency-free `.env` loader in `server/services.py` that never overrides variables already set (the event VM may set them).
3. Implement the Cosmos Reason call for "Ask the footage": today `COSMOS3_REASON_URL` only flips the status dot, which would claim Cosmos is live while nothing calls it.
4. Write `.env.example`; copy it to `.env` (gitignored) for the builder to fill in.
5. README: point at `cp .env.example .env` and the restart.

## Design decisions

- Real keys go in `.env`, never `.env.example`: `.env.example` is committed and every commit is pushed automatically.
- Every key is optional; without it the matching service runs in replay mode. The template says which feature each key turns on.
- Request shapes for YOLO and Cosmos on the event stack follow `docs/hack-plan.md` and stay marked as unverified.

## Files and impact

- `.env.example` — new template (committed).
- `.env` — local copy for real keys (gitignored, not committed).
- `server/services.py` — `.env` loader, Cosmos adapter, status uses the same checks.
- `server/app.py` — Ask the footage tries Cosmos, then W&B Inference, then replay.
- `README.md` — setup step.

## Validation

- `git check-ignore .env` passes; `.env.example` is not ignored.
- Loader unit check with a temp file: sets new keys, skips blanks and comments, never overrides.
- Server reloads; `/api/health` unchanged with an empty `.env`; ask endpoint still answers in replay.

## Handoff checkpoint

- Last completed: Variables listed.
- Current state: Plan written.
- Next action: Add the loader and the Cosmos adapter.
- Blockers: None.
- Validation state: Not started.

## Plan changes and decisions

- 2026-10-17T12:59:11Z — Task created. Fill this plan before modifying scoped files.
- 2026-10-17T13:00:00Z — Plan filled. Found that `.env` was never loaded and Cosmos had no call behind its status dot; both fixed in this task.
