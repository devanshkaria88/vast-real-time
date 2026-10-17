# Plan: Bedrock Luma Ray2 accident videos from incident images

| Field | Value |
| --- | --- |
| Task ID | `20261017T131040Z-cursor-bedrock-luma-ray2-accident-videos-from-incident--590` |
| Created by | cursor |
| Scope | `server/tools,poodle/media,.env.example,README.md` |
| Created | 2026-10-17T13:10:40Z |
| Initial status | planned |

## Goal

Generate a few realistic accident clips from the synthetic CCTV incident stills
with Luma Ray2 on Amazon Bedrock, using the same AWS account and SSO auth as
`~/devanshkaria_dev_ecosystem`. Success: the model is provisioned in the region
that offers it, a reusable tool generates clips per claim, and a few clips exist
locally and play.

## Facts established

- Account 762233742141, SSO `AdministratorAccess`, default chain (no keys).
- `luma.ray-v2:0` is offered only in us-west-2. Async API only
  (StartAsyncInvoke), output to S3 in the same region. Image-to-video via
  `keyframes.frame0` (start) and/or `frame1` (end), base64 JPEG/PNG.
- Price: $1.50/s at 720p, $0.75/s at 540p. A 5 s 720p clip costs $7.50.
- Provisioned: Marketplace agreement accepted (status AVAILABLE); output bucket
  `dk-bedrock-video-762233742141-us-west-2` (private, SSE-S3, 30-day expiry,
  tagged project=poodle, managed-by=cli; outside Terraform).

## Plan

1. `server/tools/luma_videos.py`: per-claim prompt, still (with the claim OSD
   from `build_media.frame`) sent as the end keyframe (`frame1`) so Ray2
   animates the lead-up and impact; squash 3:2 to 4:3 for the request, scale
   the result back to 1168x784, redraw the OSD clock ticking up to
   `incidentAt`, write `poodle/media/luma/<claim>.mp4` plus a provenance
   manifest. Raw Ray2 output kept in gitignored `server/data/luma/`.
2. Smoke test one claim (PD-0147), inspect frames, then run three more
   (PD-0236, PD-0219, PD-0226) for day / impact / rain / night variety.
3. Document the tool in README; do not rewire the app's claim footage.

## Files and impact

- Planned files: `server/tools/luma_videos.py` (new), `poodle/media/luma/*`
  (new clips + manifest), `.gitignore` (raw clips), `.env.example`
  (`LUMA_S3_URI`), README (tool usage).
- Expected impact: additive only; existing incident clips and app untouched.

## Validation

- Checks to run: py_compile + ReadLints on the tool; one paid smoke test;
  ffprobe the outputs (duration, size, codec); view extracted frames.
- Spend cap: about 5 generations (~$37.50) unless the user asks for more.

## Results so far

- Shipped: `poodle/media/luma/PD-0147.mp4` (red car runs the red light into
  the blue car; trim 0.5 s) and `PD-0226.mp4` (night, red car rolls over the
  give-way lines; trim 0.2 s). Manifest records prompt, ARN, S3 output, trim.
- What Ray2 does (7 takes, ~$52.80 incl. erase): end frame only sweeps the
  camera in; start frame only dives in like a drone; erased start + evidence
  still end is the only setup that keeps the CCTV fixed, but Ray2 rushes the
  cars in (pop-in) and holds. About 1 in 3 takes usable; timing words and
  "drives in from the edge of the frame" made takes chaotic.
- Rejected takes kept locally in `server/data/luma/` (gitignored).
- Stability Image Services agreement accepted ($0.07/image) for Erase Object.

## Handoff checkpoint

- Last completed: Task registered; implementation has not started.
- Current state: Planning.
- Next action: Complete this plan, then log a checkpoint before editing.
- Blockers: None known.
- Validation state: Not started.

## Plan changes and decisions

- 2026-10-17T13:10:40Z — Task created. Fill this plan before modifying scoped files.
