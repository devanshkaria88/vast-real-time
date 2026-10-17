# Claim Witness — Video Agent for Incident & Insurance Claims

> Real-Time Video Agents Hack · VAST London · 17 Oct 2026
> Theme fit: an agent that **searches footage, answers questions, spots events, and takes action**.

## One-liner

When a road incident happens, Claim Witness takes every piece of footage (dashcam, CCTV, phone clips), the GPS track and the location context, reconstructs what happened on one synced timeline, answers an adjuster's questions with timestamped clip proof, checks the events against the road rules, flags contradictions and fraud signals, and exports a tamper-evident evidence pack fit to share with lawyers or a court.

## Problem

- Motor claims depend on "he said / she said". Video exists more often than ever (dashcams, doorbells, shop CCTV, phones), but adjusters still scrub through it by hand.
- Clips arrive from different devices, with different clocks, angles and quality. Nobody lines them up.
- Liability depends on context the video alone doesn't show: junction layout, signal phases, speed limits, give-way lines, the Highway Code.
- Fraud (staged "crash-for-cash" collisions) costs insurers heavily and is hard to spot without frame-level review.
- Evidence used in disputes or court needs proof it hasn't been altered, plus a clear trail of how conclusions were reached.

## Users

| User | What they get |
|------|---------------|
| Claims adjuster | Minutes instead of hours per claim; answers with clip proof |
| Fraud / SIU team | Automatic contradiction and staged-crash signals |
| Solicitor / court | Hashed, audited evidence pack with timeline and rule citations |
| Fleet operator | Fast first-notice-of-loss from their own dashcams |
| Driver / claimant | Faster, fairer settlement when the footage backs them |

## Positioning

Claim Witness **assists** the human decision-maker. It produces an evidence-backed assessment of contributing factors with confidence scores. It never issues a final liability decision. Every claim it makes links to a clip, a frame or a rule.

---

## Features

### 1. Multi-source ingest with chain of custody
- Accepts dashcam, CCTV, phone and bodycam video, plus GPS/IMU tracks and the written claim statements.
- Every file is hashed (SHA-256) at the moment of upload. Hash, uploader, time and device metadata go into a chain-of-custody log.
- Any later processing works on copies. The original hash proves the source was never altered.

### 2. Multi-camera sync
- Places every clip on one shared incident timeline, even when device clocks disagree.
- Aligns on shared "anchor events" that several cameras see: the impact itself, a traffic light change, a horn or crash sound, a vehicle crossing a stop line.

### 3. Event timeline
- An ordered list of key moments, each with clip, timestamp, camera and confidence:
  `00:12.4 blue hatchback enters junction (CCTV-1, 0.91)` → `00:13.0 signal for blue car: red (CCTV-1, 0.87)` → `00:13.8 impact (dashcam + CCTV-1 + audio, 0.98)`.

### 4. Scene reconstruction (bird's-eye replay)
- A 2D top-down animation of every tracked vehicle, cyclist and pedestrian, drawn on the real junction map.
- Lets a non-technical reader (adjuster, judge) see the incident in seconds.

### 5. Speed and distance estimates
- Per-vehicle speed at key moments, with the method shown (GPS-based, or visual estimate labelled "approx").
- Gap and stopping-distance checks against the speed limit at that location.

### 6. Location & road-rule context
- From the GPS point: junction type, signal control, lanes, give-way / stop lines, speed limit, crossings.
- Street-level imagery to confirm signage and road markings at that spot.
- Highway Code retrieval: events are matched to the relevant rules, and the rule number and text are cited.

### 7. Video Q&A
- Plain-language questions answered from the footage, with the clip as proof:
  - "What colour was the light when the blue car crossed the stop line?"
  - "Did the van indicate before turning?"
  - "Was the pedestrian on the crossing at impact?"
  - "Show every moment the red car braked."
- If the footage can't answer, the agent says "not visible" rather than guessing.

### 8. Statement contradiction check
- Each party's written statement is split into individual claims ("I had a green light", "I was doing 20 mph", "he didn't indicate").
- Each claim is marked **supported**, **contradicted** or **unverifiable**, with the clip that decides it.

### 9. Fraud and tamper signals
- Staged-crash patterns: sudden braking with no hazard ahead, a slow rear-end shunt right after a lane cut-in, a vehicle waiting then pulling out into traffic, the same vehicles or people across past claims.
- Tamper signals: timestamp jumps, dropped or duplicated frames, metadata that disagrees with GPS, re-encoding traces, a hash mismatch with a previously submitted copy.
- Output is a risk flag with reasons for a human investigator, not an accusation.

### 10. Contributing-factor assessment
- Combines the timeline, rules and statements into a structured assessment: which party's actions contributed, which rule each relates to, confidence, and the evidence links.
- Shows what would change the assessment ("no footage of the van's indicator from the left side").

### 11. Court-ready evidence pack
- Exportable report: incident summary, synced timeline, key frames, bird's-eye replay snapshots, Q&A log, statement check, rule citations, confidence scores.
- Appendix: source file hashes, chain-of-custody log, and the full agent trace showing how each conclusion was reached.

### 12. Incident search across claims
- Search all past incidents in plain language: "rear-end collisions at roundabouts in the rain", "claims where the claimant said green but the footage showed red".
- Supports fraud-ring detection and portfolio-level risk insight.

---

## How the agents detect things

The system is a small team of specialised agents coordinated by an orchestrator. Each agent writes structured facts (with timestamps, confidence and evidence links) into a shared incident record.

### Orchestrator
Receives the claim, routes work to the specialist agents, merges their facts into the incident record, and answers the adjuster.

### Ingest & Integrity Agent
- **Hashing:** SHA-256 of each original file at upload; stored with metadata in the chain-of-custody log.
- **Metadata:** reads container metadata (creation time, device, frame rate, embedded GPS where present).
- **Tamper detection:** looks for frame-timestamp discontinuities, irregular frame intervals, duplicated frames, metadata vs GPS mismatches, and signs of re-encoding.

### Perception Agent
- **Object detection & tracking:** YOLO (Ultralytics) detects vehicles, cyclists, pedestrians, traffic lights and signs in each frame. Its built-in multi-object tracker gives each road user a persistent ID across frames.
- **Impact detection:** combines three signals: a sudden spike in visual motion between frames, a loud transient in the audio track, and a sharp deceleration in GPS/IMU data. A collision-anticipation model trained on real dashcam collisions (Nexar BADAS-Open) adds a collision probability per moment.
- **Traffic-light state:** the detected light is cropped and its lit lamp classified (red / amber / green) frame by frame, giving the signal phase over time.
- **Indicator use:** the tail-light or side-light region of a tracked vehicle is watched for a regular on/off blink (about 1–2 flashes per second). It's labelled "likely indicating" with a confidence, because angle and lighting limit it.
- **Braking:** brake-light brightening on the vehicle ahead, plus sudden drops in that vehicle's tracked speed.
- **Scene understanding:** NVIDIA VSS with Cosmos turns each video segment into a text description and an embedding ("a white van turns right across the path of an oncoming cyclist"). These feed search and Q&A.

### Sync Agent
- Finds anchor events seen by more than one camera (impact, light change, a vehicle crossing a line) and the matching audio peaks.
- Solves for each camera's time offset so the anchors line up, then maps every clip onto one incident clock.
- Reports the sync confidence per camera.

### Context Agent
- **Map geometry:** looks up the GPS point in OpenStreetMap for junction shape, lanes, signals, give-way/stop lines, crossings and the speed limit.
- **Street-level imagery:** fetches Mapillary (or Google Street View) imagery at that spot to confirm signage and markings.
- **Rules retrieval:** the Highway Code is indexed for retrieval. Events from the timeline ("entered junction on red", "turned right across oncoming traffic") retrieve the matching rules, which are cited by number.

### Reconstruction Agent
- Maps each camera's view of the road surface onto the map using known reference points (lane markings, stop lines, kerb corners from the map and street imagery). This gives every tracked road user a real-world position over time.
- Draws the bird's-eye replay and computes speeds and distances from those positions. GPS tracks, where present, override visual estimates.

### Q&A Agent
- Searches the VAST vector store for the video segments most relevant to the question, using the VSS/Cosmos embeddings and the structured incident record.
- A vision-language model looks at the retrieved segments and answers, always returning the timestamp and camera as proof.
- Answers "not visible / unclear" when the evidence doesn't support an answer.

### Statement & Fraud Agent
- Splits each statement into atomic claims and checks each against the incident record → supported / contradicted / unverifiable.
- Scores staged-crash patterns from the timeline (braking with no hazard, cut-in followed by sudden stop) and compares people, plates and locations against past incidents in VAST.
- Combines these with the tamper signals into a fraud-risk flag with reasons.

### Assessment & Report Agent
- Reasons over the timeline, rule citations and statement checks to produce the contributing-factor assessment with confidence and evidence links.
- Builds the evidence pack, including hashes, custody log and the agent trace.

---

## How everything ties together

```
                  ┌──────────────────── Claim submitted ───────────────────┐
                  │  videos · GPS/IMU · statements · location               │
                  └──────────────────────────┬─────────────────────────────┘
                                             ▼
                              Ingest & Integrity Agent
                     (SHA-256, metadata, tamper checks, custody log)
                                             │
                                             ▼
                         VAST AI OS — single store for video,
                     vectors, metadata, incident records, past claims
                                             │
              ┌──────────────────────────────┼──────────────────────────────┐
              ▼                              ▼                              ▼
      Perception Agent                  Sync Agent                    Context Agent
  YOLO detect + track,           anchor events + audio →         OpenStreetMap, Mapillary /
  impact, lights, indicators,    one incident clock              Street View, Highway Code
  NVIDIA VSS + Cosmos captions                                     retrieval
              └──────────────────────────────┼──────────────────────────────┘
                                             ▼
                                Reconstruction Agent
                       (map positions, speeds, bird's-eye replay)
                                             │
              ┌──────────────────────────────┼──────────────────────────────┐
              ▼                              ▼                              ▼
          Q&A Agent                Statement & Fraud Agent       Assessment & Report Agent
   grounded answers with        supported / contradicted,       contributing factors,
   timestamped clips            staged-crash + tamper flags     court-ready evidence pack
              └──────────────────────────────┼──────────────────────────────┘
                                             ▼
                                  Adjuster / court UI

   W&B Weave traces every agent step (audit trail + evals) · models served on CoreWeave via W&B Inference
```

### Sponsor stack map

| Sponsor tool | Role in Claim Witness |
|--------------|-----------------------|
| **VAST AI OS** | One store for raw video, segment embeddings, metadata, incident records and past claims. Powers Q&A retrieval and cross-claim search. |
| **NVIDIA VSS Blueprint + Cosmos** | Turns video segments into searchable descriptions and embeddings; scene understanding for Q&A. |
| **Ultralytics YOLO** | Real-time detection and tracking of road users, traffic lights and signs. |
| **W&B Weave** | Traces every agent call: the audit trail in the evidence pack, plus evals (Q&A accuracy, impact-detection precision/recall, sync error). |
| **CoreWeave / W&B Inference** | GPU serving for the vision-language and reasoning models. |
| **Cursor** | Build environment. |

### Why Weave matters twice
1. **Engineering:** measures how often the agent is right (answer accuracy on labelled questions, impact timing error, light-state accuracy).
2. **Legal:** the same traces become the "how we reached this" appendix. Every conclusion links back to the inputs, model calls and clips that produced it.

---

## Data sources

### Incident video
| Source | What | Licence / access | Use |
|--------|------|------------------|-----|
| [Nexar Dashcam Collision Prediction Dataset](https://huggingface.co/nexar-ai) | 1,500 dashcam clips (~40 s each), labelled collision / near-collision / normal | Custom "Nexar Dataset License 2025": attribution, no resale, no re-identification of people or vehicles | Primary real crash footage; impact-detection evals |
| [Nexar paper (arXiv 2503.03848)](https://arxiv.org/abs/2503.03848) | Dataset description | — | Reference |
| [BADAS-Open (arXiv 2510.14876)](https://arxiv.org/pdf/2510.14876) | Collision-anticipation model trained on the Nexar dataset | APSv2 licence | Collision probability signal |
| [MM-AU (CVPR 2024)](https://arxiv.org/pdf/2403.00436) | 11,727 accident videos with text on cause, prevention, category | Non-commercial; ~364 GB full set ([mirror listing](https://hyper.ai/en/datasets/38267)) | Sample clips as Q&A / cause ground truth |
| Team-staged incident | Toy-car junction filmed from 2–3 phones (dashcam, CCTV, bystander angles) with a synthetic GPS track | Own footage | The only multi-angle footage of a single incident; full control of ground truth |

No public dataset was found with several camera angles of the same real crash, which is why the staged incident exists.

### Location & rules context
| Source | What | Notes |
|--------|------|-------|
| [The Highway Code (gov.uk)](https://www.gov.uk/guidance/the-highway-code) | UK road rules | Crown copyright, Open Government Licence; indexed for rule citations |
| [OpenStreetMap](https://www.openstreetmap.org) | Junction geometry, lanes, signals, speed limits, crossings | ODbL, free |
| [Mapillary](https://www.mapillary.com/developer) | Street-level imagery | Free API |
| [Google Street View Static API](https://developers.google.com/maps/documentation/streetview) | Street-level imagery | Needs API key and billing; terms limit storage and reuse |

### Tools & platforms
- [Ultralytics YOLO tracking](https://docs.ultralytics.com/modes/track/)
- [W&B Weave](https://weave-docs.wandb.ai)
- Hackathon page and sponsor list: [tokensand.com/vastlondon](https://tokensand.com/vastlondon)

---

## Demo story (90 seconds)

1. The claimant states: "I had a green light; the other driver hit me."
2. The adjuster uploads three clips (dashcam, CCTV, bystander phone) and the GPS track. The agent hashes them and syncs them onto one timeline.
3. The bird's-eye replay shows both cars entering the junction.
4. Question: "What colour was the light when the blue car crossed the stop line?" → "Red, at 00:13.0 on CCTV-1", with the clip.
5. The statement check marks "I had a green light" as **contradicted** and cites the relevant Highway Code rule on traffic signals.
6. One click exports the evidence pack: timeline, key frames, rule citations, hashes, and the Weave trace.

## Why it can win

- Hits every word of the brief: searches footage, answers questions, spots events, takes action.
- Uses each sponsor tool for something it is genuinely good at, and Weave plays a dual engineering/legal role.
- Clear buyer (insurers, fleets, legal), clear money (claims cost, fraud).
- A live, controlled multi-camera demo instead of a canned video.

## Limits & responsible use

- Assists human adjusters; never issues a final liability or fraud decision.
- Visual speed estimates and indicator detection are approximate and labelled as such.
- Faces and plates are blurred in exported packs unless legally required; no re-identification across datasets (also a Nexar licence term).
- Rule citations cover UK law (Highway Code); other jurisdictions need their own rule sets.
- Dataset licences (Nexar custom, MM-AU non-commercial) allow research/hackathon use; commercial use needs separate agreements.

## Not yet verified

- Exact text of the Nexar LICENSE file on Hugging Face.
- MM-AU official download page and per-sample availability.
- Mapillary API rate limits and current Google Street View terms.
- NVIDIA VSS / Cosmos access details for build day (check the event's Cosmos Community resources).
