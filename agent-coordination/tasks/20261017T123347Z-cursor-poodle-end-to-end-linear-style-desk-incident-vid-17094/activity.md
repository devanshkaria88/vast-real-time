# Activity: Poodle end-to-end: Linear-style desk, incident video, live TfL cams

## 2026-10-17T12:33:47Z · cursor · planned

Task registered with an agent-neutral plan. Another agent may take it over
after reading this plan and activity history.

**Next action:** Complete the linked plan before changing task-scoped files.

## 2026-10-17T12:34:07Z · cursor · in-progress

Plan filled: Linear tokens pulled from linear.app CSS; TfL JamCam API confirmed live (890 cams, CORS open); no sponsor keys locally so replay mode is needed.

**Next action:** Screenshot the old desk and write docs/ui-audit.md

## 2026-10-17T12:36:47Z · cursor · in-progress

docs/ui-audit.md written: 25 findings tied to old lines @52ab79b, annotated screenshot in docs/audit/. Local YOLO (ultralytics 8.4, torch 2.14) installed in /tmp/yolo-venv.

**Next action:** Precompute YOLO detections and build demo clips from Demo img

## 2026-10-17T12:41:53Z · cursor · in-progress

Backend up on :8080 (server/): claims API with code decision table, TfL JamCam proxy + nearest cams, live YOLO scan, attach live frame, SHA-256 custody, evidence pack. 8 demo clips + YOLO detections built from Demo img.

**Next action:** Build the Linear-style frontend in poodle/

## 2026-10-17T12:54:14Z · cursor · completed

Poodle rebuilt end to end. server/: FastAPI on :8080 (claims API, code decision table with Jev hook, TfL JamCam proxy + nearest cams, live YOLO scan, attach TfL still as hashed evidence, SHA-256 custody, printable evidence pack, env-gated Cosmos/W&B/Jev/VastDB adapters with replay fallback). poodle/: Linear-style no-build desk (sidebar views, grouped list, claim console with YOLO-boxed incident clip beside nearest live TfL cams, recommendation + citations, findings, statement check, Ask the footage, activity, properties panel, live cameras wall, Cmd+K, J/K). 8 demo clips + real YOLO11s detections from Demo img. docs/ui-audit.md: 25 findings marked on the old desk, all done, before/after screenshots. Validated: all API endpoints via curl, browser click-through (Q&A, live scan, attach, Cmd+K, approve/reopen, J/K), 1440 px and 390 px with no overflow, README run command in a fresh env, lints clean.

**Next action:** No further action; task completed.
