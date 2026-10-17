# Plan: Real accident videos as claim incident footage

| Field | Value |
| --- | --- |
| Task ID | `20261017T135729Z-cursor-real-accident-videos-as-claim-incident-footage-31388` |
| Created by | cursor |
| Scope | `poodle/media/incidents,poodle/media/raw,server/data/claims.json,server/data/detections.json,server/tools,poodle,README.md` |
| Created | 2026-10-17T13:57:29Z |
| Initial status | planned |

## Goal

The eight claims use the real dashcam videos in `poodle/media/raw/` as their
incident footage, with findings, statement checks and Jev answers that describe
each clip.

## Done

- Mapping (claim -> video): PD-0147 002 pull-out at give-way, PD-0204 006 van
  onto roundabout across a motorcyclist (policyholder is the van), PD-0188 009
  slip-road cut-in and brake (fraud), PD-0211 004 oncoming Prius spins on wet
  bend, PD-0219 005 insured car pulls out at night (unnamed son, E1), PD-0226
  001 rear-ended in traffic, PD-0231 008 van loses control on motorway, PD-0236
  003 witness footage, Passat crosses hatching. 007 and 010 unused.
- Kept ids, places, dates, people; policy vehicles changed to match; rules
  HC130, HC211, HC227 added. Seeded decisions keep the demo's spread.
- `build_media.py` builds clips/posters from raw; `detect_stills.py` runs YOLO
  on each finding's frame (conf >= 0.5, bonnet and phone photos excluded).
- Desk: click a finding to pause on its frame with its boxes; "Real footage"
  chip with credit; custody hashes the original video.
- Live Jev rates evidence < 0.5 on every claim (old claims too), so live mode
  refers everything; seeded mode gives the planned decisions.

## Plan

1. Identify relevant files, dependencies, and constraints.
2. Make the smallest scoped change that fulfils the task.
3. Validate the result with appropriate checks.

## Files and impact

- Planned files: _to be filled before implementation_
- Expected impact: _to be filled before implementation_

## Validation

- Checks to run: _to be filled before implementation_

## Handoff checkpoint

- Last completed: Task registered; implementation has not started.
- Current state: Planning.
- Next action: Complete this plan, then log a checkpoint before editing.
- Blockers: None known.
- Validation state: Not started.

## Plan changes and decisions

- 2026-10-17T13:57:29Z — Task created. Fill this plan before modifying scoped files.
