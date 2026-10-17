# Submission form copy

Texts for the Real-Time Video Agents Hack form (VAST London, 17 Oct 2026). Plain English, no em dashes.
Every claim matches the code as of this commit. Cosmos Reason, W&B Inference and VastDB are wired in but
were never run with credentials, and the text says so.

## One-sentence description (221/300 characters)

Poodle is a claims desk for car insurers that watches the dashcam video of a crash, checks the driver's story against what the camera saw, works out what the policy pays, and hands anything it isn't sure about to a human.

## Project description (1448/1,500 characters)

Poodle helps car insurance handlers decide claims from video. A handler opens a claim and sees the real dashcam clip with YOLO boxes on the cars, a timeline of what happened, and the driver's statement checked line by line: supported, contradicted or unverifiable. They can ask the footage questions, and every answer cites a finding or says "Not visible". The recommendation shows what's covered and what to pay, with the policy clause or Highway Code rule behind each reason. Every file gets a SHA-256 hash, and it all prints as a one-page evidence pack.

How it decides: code owns the rules, dates and money. TypeSafe Jev answers closed questions (what happened, who was at fault, fraud risk) with a confidence score. Under 50% sure, Poodle refers the claim to a person and says why.

It also watches London. It polls about 800 TfL traffic cameras and sends each new still to Jev with 12 image questions in one call. Code turns the answers into an incident library with stills, 10-second clips and review buttons, and logs road conditions per camera every few minutes. All of London costs about $0.50 an hour.

Tools: YOLO11s finds vehicles in claim footage and live stills. We built it in Cursor and Claude Code, which shared one taskboard. Cosmos Reason (video Q&A), W&B Inference (answers) and VastDB (event store) are wired in and switch on with credentials. We had none on build day, so the demo uses recorded answers and a local event log.

Optional bold in the form: the lead-ins "How it decides:", "It also watches London." and "Tools:".

## Technologies, and where each one is in the code

| Technology | How Poodle uses it | Where |
| --- | --- | --- |
| Cursor | Built the app; shared taskboard with Claude Code | `agent-coordination/`, `.cursor/` |
| TypeSafe Jev | Coverage answers on claims; 12 image questions per TfL still | `server/services.py`, `server/watch.py` |
| YOLO11s (Ultralytics) | Boxes on claim footage (precomputed) and live camera scans | `server/tools/detect_stills.py`, `server/services.py` |
| TfL JamCams | About 800 live London cameras | `server/tfl.py`, `server/watch.py` |
| NVIDIA Cosmos Reason | Video Q&A when `COSMOS3_REASON_URL` is set (not run on build day) | `server/services.py` |
| W&B Inference | Plain-English answers when `WANDB_API_KEY` is set (not run on build day) | `server/services.py` |
| VAST (VastDB) | Event store when `VASTDB_ENDPOINT` is set (not run on build day) | `server/services.py` |
