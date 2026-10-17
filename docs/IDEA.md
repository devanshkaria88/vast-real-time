# Poodle — Video Agent for Incident & Insurance Claims

> Real-Time Video Agents Hack · VAST London · 17 Oct 2026
> Theme fit: an agent that **searches footage, answers questions, spots events, and takes action**.
> Judging criteria (VAST blog): **creativity, technical implementation, real-world impact**.

Poodle is the name of this idea. The claims desk is [`poodle/index.html`](../poodle/index.html). A small apricot poodle sits on top of that desk and moves with the open claim: steady while you read, brighter when a decision is ready for a person to confirm. The desk writes that same mood in words, so the motion is not the only signal.

## One-liner

When a road incident happens, Poodle takes every piece of footage (dashcam, CCTV, phone clips), the GPS track, the location context and the claimant's insurance policy. It reconstructs what happened on one synced timeline, answers an adjuster's questions with timestamped clip proof, checks the events against the road rules, flags contradictions and fraud signals, **decides whether the claim is covered and which benefits apply** (accept, partial, reject or refer to a human), and exports a tamper-evident evidence pack fit to share with lawyers or a court.

## Problem

- Motor claims depend on "he said / she said". Video exists more often than ever (dashcams, doorbells, shop CCTV, phones), but adjusters still scrub through it by hand.
- Clips arrive from different devices, with different clocks, angles and quality. Nobody lines them up.
- Liability depends on context the video alone doesn't show: junction layout, signal phases, speed limits, give-way lines, the Highway Code.
- Even once fault is clear, the adjuster still has to read the policy: is this peril covered under the customer's cover level, does an exclusion apply, which benefits (courtesy car, windscreen, legal expenses, personal injury) kick in, what is the excess. This is slow, inconsistent between handlers, and hard to explain to the customer.
- Fraud (staged "crash-for-cash" collisions) costs insurers heavily and is hard to spot without frame-level review.
- Evidence used in disputes or court needs proof it hasn't been altered, plus a clear trail of how conclusions were reached.

## Users

| User | What they get |
|------|---------------|
| Claims adjuster | Minutes instead of hours per claim; answers with clip proof; a pre-filled coverage decision to confirm |
| Customer / claimant | A fast, explained decision: what is covered, which benefits apply, what they pay |
| Fraud / SIU team | Automatic contradiction and staged-crash signals |
| Solicitor / court | Hashed, audited evidence pack with timeline and rule citations |
| Fleet operator | Fast first-notice-of-loss from their own dashcams |

## Positioning

Poodle **assists** the human decision-maker. It produces an evidence-backed assessment of contributing factors and a coverage recommendation, each with confidence scores. Only simple, low-value, high-confidence acceptances can be settled automatically; **every rejection, partial decision and uncertain case goes to a human handler**. Every claim the system makes links to a clip, a frame, a road rule or a policy clause.

---

## Features

### 1. Multi-source ingest with chain of custody
- Accepts dashcam, CCTV, phone and bodycam video, plus GPS/IMU tracks, written or spoken claim statements, and the claimant's policy schedule and wording.
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
- Each party's statement (typed, or spoken and transcribed) is split into individual claims ("I had a green light", "I was doing 20 mph", "he didn't indicate").
- Each claim is marked **supported**, **contradicted** or **unverifiable**, with the clip that decides it.

### 9. Fraud and tamper signals
- Staged-crash patterns: sudden braking with no hazard ahead, a slow rear-end shunt right after a lane cut-in, a vehicle waiting then pulling out into traffic, the same vehicles or people across past claims.
- Tamper signals: timestamp jumps, dropped or duplicated frames, metadata that disagrees with GPS, re-encoding traces, a hash mismatch with a previously submitted copy.
- Output is a risk flag with reasons for a human investigator, not an accusation.

### 10. Contributing-factor assessment
- Combines the timeline, rules and statements into a structured assessment: which party's actions contributed, which rule each relates to, a fault band, confidence, and the evidence links.
- Shows what would change the assessment ("no footage of the van's indicator from the left side").

### 11. Coverage & benefits decision (accept / partial / reject / refer)
- Reads the claimant's **policy schedule** (cover level, excess, named drivers, vehicle, territory, add-ons) and **policy wording** (sections, benefits, exclusions, limits).
- Combines them with the video-derived facts (peril, fault band, driver, location, time, fraud flags) to decide:
  - **Is the incident covered?** Which policy section applies to this peril under this cover level.
  - **Does any exclusion apply?** E.g. unlisted driver, driving outside the permitted use, policy not in force on the incident date, outside the territory, vehicle not roadworthy, racing or speed testing.
  - **Which benefits apply?** E.g. own-damage repair, courtesy car, windscreen, personal-injury benefit, legal-expenses cover, and whether the no-claims discount is protected.
  - **What the claimant pays and receives**: excess, limits and the settlement range, computed exactly in code.
- Outcome: **ACCEPT**, **ACCEPT – PARTIAL**, **REJECT** or **REFER TO HANDLER**, with every reason linked to a policy clause and a clip.
- The typed, calibrated decision layer for this step is **TypeSafe Jev** (see "Where Jev fits").

### 12. Court-ready evidence pack & decision letter
- Exportable report: incident summary, synced timeline, key frames, bird's-eye replay snapshots, Q&A log, statement check, rule citations, coverage decision with clause citations, confidence scores.
- A plain-English decision letter for the customer: what is covered, which benefits apply, what they pay, and why.
- Appendix: source file hashes, chain-of-custody log, the full agent trace, and the logged Jev decision record (model version, full probability distributions, thresholds, chosen branch).

### 13. Incident search across claims
- Search all past incidents in plain language: "rear-end collisions at roundabouts in the rain", "claims where the claimant said green but the footage showed red", "rejected claims that cited the unlisted-driver exclusion".
- Supports fraud-ring detection, consistency audits across handlers, and portfolio-level risk insight.

---

## How the agents detect things

The system is a small team of specialised agents coordinated by an orchestrator. Each agent writes structured facts (with timestamps, confidence and evidence links) into a shared incident record in VastDB.

A three-layer rule runs through every agent:

| Layer | Owns |
|-------|------|
| **Code** | Hard rules, dates, arithmetic, counting, exact lookups, thresholds, side effects |
| **Jev (typed decisions)** | Closed-set judgments: yes/no, pick one of a set, a severity level, locate one target in a frame |
| **Cosmos / LLM** | Open-ended video reasoning, captions, summaries, the decision letter |

### Orchestrator
Receives the claim, routes work to the specialist agents, merges their facts into the incident record, and answers the adjuster.

### Ingest & Integrity Agent
- **Hashing:** SHA-256 of each original file at upload; stored with metadata in the chain-of-custody log.
- **Metadata:** reads container metadata (creation time, device, frame rate, embedded GPS where present).
- **Tamper detection:** looks for frame-timestamp discontinuities, irregular frame intervals, duplicated frames, metadata vs GPS mismatches, and signs of re-encoding.
- **Spoken statements:** Canary-1B ASR transcribes voice statements so they can be checked like written ones.

### Perception Agent
- **Object detection & tracking:** YOLO (YOLO11s in the event pipeline) detects vehicles, cyclists, pedestrians, traffic lights and signs. A multi-object tracker gives each road user a persistent ID across frames.
- **Impact detection:** combines three signals: a sudden spike in visual motion between frames, a loud transient in the audio track, and a sharp deceleration in GPS/IMU data.
- **Frame-level typed checks (Jev):** for frames YOLO marks as relevant, one batched Jev request asks every question about that frame at once:
  - Choice: traffic-light state for the approach (`red`, `amber`, `green`, `not_visible`).
  - Noul: "Is the tracked vehicle's indicator lit in `frame`?" (compared over consecutive frames to see a blink).
  - Noul: "Are the brake lights of the vehicle ahead lit?"
  - Noul: "Is a pedestrian on the crossing in `frame`?"
  - Box (paired with a presence Noul): locate a target YOLO has no class for, e.g. "the cyclist's front wheel" or "the give-way line".
  - "What changed" Nouls against the previous frame: vehicle entered junction, impact, vehicle stopped.
- **Scene understanding:** NVIDIA VSS with Cosmos3-Reason describes each 5-second segment, and Cosmos Embed1 turns it into an embedding ("a white van turns right across the path of an oncoming cyclist"). These feed search and Q&A.
- **Verification around Cosmos:** VLMs are biased towards saying "yes" to events that didn't happen. Every Cosmos verdict that matters (impact, red light, no indicator) must be confirmed by a deterministic check (YOLO track, motion/audio spike) and a Jev verifier Noul on the key frame before it enters the timeline. Uncertain windows are escalated, never silently accepted.

### Sync Agent
- Finds anchor events seen by more than one camera (impact, light change, a vehicle crossing a line) and the matching audio peaks.
- Solves for each camera's time offset so the anchors line up, then maps every clip onto one incident clock.
- Reports the sync confidence per camera.

### Context Agent
- **Map geometry:** looks up the GPS point in OpenStreetMap for junction shape, lanes, signals, give-way/stop lines, crossings and the speed limit.
- **Street-level imagery:** fetches Mapillary (or Google Street View) imagery at that spot to confirm signage and markings.
- **Rules retrieval:** the Highway Code is indexed for retrieval. Events from the timeline ("entered junction on red", "turned right across oncoming traffic") retrieve candidate rules; a Jev Choice picks which candidate rule applies (with a `none` exit), so citations are selected, not invented.

### Reconstruction Agent
- Maps each camera's view of the road surface onto the map using known reference points (lane markings, stop lines, kerb corners from the map and street imagery). This gives every tracked road user a real-world position over time.
- Draws the bird's-eye replay and computes speeds and distances from those positions. GPS tracks, where present, override visual estimates.

### Q&A Agent
- Searches the VAST store for the video segments most relevant to the question, using the Cosmos embeddings (VSS hybrid search) and the structured incident record.
- Cosmos3-Reason looks at the retrieved segments and answers, always returning the timestamp and camera as proof.
- A Jev citation check ("does this clip support this answer?") runs before the answer is shown. Answers "not visible / unclear" when the evidence doesn't support an answer.

### Statement & Fraud Agent
- Splits each statement into atomic claims; for each claim a Jev Choice against the incident record returns `supported`, `contradicted` or `unverifiable`.
- A Jev Score rates staged-crash risk from the timeline (braking with no hazard, cut-in followed by sudden stop); code compares people, vehicles and locations against past incidents in VAST.
- Combines these with the tamper signals into a fraud-risk flag with reasons.

### Liability Agent
- Reasons over the timeline, rule citations and statement checks.
- A Jev Score places the claimant in a **fault band**: `not at fault`, `shared fault`, `mostly at fault`, `fully at fault`, plus `cannot determine`.
- Cosmos / the LLM writes the contributing-factor explanation; every sentence links to evidence.

### Coverage & Benefits Agent (Jev decision layer)
Detailed in the next section. Turns facts + policy into ACCEPT / PARTIAL / REJECT / REFER.

### Report Agent
- Builds the evidence pack and the customer decision letter (LLM via W&B Inference), including hashes, custody log, the agent trace and the Jev decision record.
- A final Jev action gate (`allow` / `deny` / `escalate`) runs before any decision letter is released or any settlement is triggered.

---

## Coverage & benefits decision: how the claim is accepted or rejected

### Inputs
| Input | Source |
|-------|--------|
| **Policy schedule** | Cover level (comprehensive / third party, fire & theft / third party only), excess (compulsory + voluntary), named drivers, insured vehicle, permitted use, territory, start and end dates, add-ons (protected NCD, courtesy car, legal expenses, breakdown) |
| **Policy wording** | Sections and what each covers, benefits and their limits, general exclusions, conditions |
| **Incident facts** | From the agents above: date/time, GPS location, peril type, fault band, who was driving, vehicle involved, damage severity band, fraud flags, evidence sufficiency |
| **Repair estimate** | From a garage or engineer (the system does not price repairs from video) |

### Who decides what

**Code (hard rules, exact, no model):**
- Policy in force on the incident date and time (date comparison).
- Insured vehicle matches the claimed vehicle (registration from the claim form, exact match).
- Driver is on the named-driver list (exact lookup).
- Incident location inside the policy territory (GPS geofence).
- Excess, limits and settlement arithmetic: `payable = min(repair estimate, section limit) − excess`, plus benefit limits.
- Applying the thresholds and the decision table below.

**Jev (typed judgments over the facts and the retrieved policy clauses, all batched in one request):**

| Question id | Type | What it asks |
|-------------|------|--------------|
| `peril` | Choice | What happened: `collision_with_vehicle`, `collision_with_object`, `collision_with_pedestrian_or_cyclist`, `theft`, `vandalism`, `fire`, `weather`, `glass_only`, `other` |
| `section_covers_peril` | Noul | Does the retrieved policy section cover this peril under this cover level? |
| `exclusion` | Choice | Which exclusion clause, if any, the facts trigger: one option per clause in the wording, plus `none` |
| `exclusion_<id>` | Noul (one per clause) | Does the evidence show this specific exclusion applies? (e.g. vehicle used for paid delivery when the policy covers social use only) |
| `fault_band` | Score | Claimant's fault: not at fault → fully at fault (from the Liability Agent's facts) |
| `benefit_<id>` | Noul (one per benefit) | Is the claimant eligible for this benefit given the facts? (courtesy car, windscreen, personal injury, legal expenses, NCD protection) |
| `severity` | Score | Damage severity band, for triage only: cosmetic → repairable → major → likely write-off |
| `evidence_sufficient` | Noul | Do the facts contain enough evidence to decide coverage without more information? |
| `fraud_risk` | Score | From the Statement & Fraud Agent's signals |

**Cosmos / LLM:** retrieves and summarises the relevant policy clauses as Jev `state`, and writes the decision letter. It never makes the decision.

### Decision table (applied in code)

| Condition | Outcome |
|-----------|---------|
| A hard-rule check fails (policy not in force, vehicle mismatch, driver not named, outside territory) | **REJECT** (recommended) → human review |
| `exclusion` ≠ `none` with confidence ≥ 0.9 | **REJECT** citing the clause → human review |
| `section_covers_peril` is no, with confidence ≥ 0.9 (e.g. own damage under third-party-only cover, claimant at fault) | **REJECT** for own damage; third-party liability still handled → human review |
| Covered, but some benefits not eligible, or `fault_band` = shared | **ACCEPT – PARTIAL** (e.g. repair covered, courtesy car not included; shared-fault recovery) → human review |
| Covered, no exclusion, all checks confident, `fraud_risk` low, repair estimate under the auto-settle limit | **ACCEPT** (eligible for straight-through settlement) |
| Any key answer below the confidence floor (0.5), `evidence_sufficient` is no, `fault_band` = cannot determine, or `fraud_risk` high | **REFER TO HANDLER** |

Thresholds are examples, calibrated on labelled claims. Higher thresholds guard more costly or adverse outcomes: a wrong rejection harms the customer, so rejections need ≥ 0.9 confidence **and** a human sign-off.

### What the customer sees

```
Decision: ACCEPT – PARTIAL                                   ref PD-0147
Cover: Comprehensive · Excess £350
Incident: collision at signal-controlled junction, 17 Oct 2026 09:42
Fault: other driver entered on red (CCTV-1 00:13.0) — you are not at fault

Covered
  ✓ Repair to your vehicle (Section 1)            estimate £2,140 − £350 excess
  ✓ Excess recoverable from other insurer        (not-at-fault claim)
  ✓ No-claims discount unaffected                 (not-at-fault claim)
  ✓ Legal expenses cover (add-on)                 to pursue the other driver
Not covered
  ✗ Courtesy car — add-on not on your policy (Schedule, Add-ons)

Evidence: 3 clips · hashes in evidence pack · reviewed by a claims handler
```

### Why Jev for this step
- Every coverage question is a **closed set** (covered or not, which exclusion, which band), so it is decision-shaped, not text-shaped.
- **Calibrated probabilities and confidence** per answer drive the accept / review / refer bands, rather than an LLM's free-text "I think it's covered".
- **Fast and cheap**: all coverage questions run in one batched request (roughly 70–500 ms), so the decision updates live as new footage or answers arrive.
- **Auditable**: questions and thresholds live in one reviewable file, and every decision logs the pinned model version (`jev-1.14.0`), the full distributions and the branch taken. That record goes straight into the evidence pack and Weave.
- **Selection, not generation**: Jev picks an exclusion from the clauses actually in the policy, so it can't invent a clause.

---

## Where Jev fits (summary)

TypeSafe Jev ("System One") is a hosted decision model: it takes a `state` and a map of typed questions (Noul, Choice, Score, Box) and returns one typed answer per question with calibrated probabilities. It does not write text.

| Where | Jev role |
|-------|----------|
| Perception | Batched per-frame typed checks: light state, indicator, brake lights, pedestrian on crossing, "what changed", Box for open-vocabulary targets |
| Verification | Verifier vote on the key frame for every Cosmos event verdict (counters VLM yes-bias) |
| Context | Pick which retrieved Highway Code rule applies |
| Q&A | Citation check: does this clip support this answer? |
| Statements | supported / contradicted / unverifiable per claim |
| Fraud | Staged-crash risk score |
| Liability | Fault band |
| **Coverage** | Peril, section covers peril, exclusions, benefit eligibility, evidence sufficiency |
| Actions | allow / deny / escalate gate before a decision letter or settlement |

Jev is **not** a hackathon sponsor tool. It sits alongside the sponsor stack, which still carries the core video work (YOLO, Cosmos, VSS, VAST, W&B). Its image input and Box type are experimental ("danger zone") features in 1.14, so the core coverage decision runs on text facts, where Jev is strongest.

---

## How everything ties together

```
          ┌─────────────────────────── Claim submitted ────────────────────────────┐
          │  videos · GPS/IMU · statements (text/voice) · policy schedule + wording │
          └─────────────────────────────────┬──────────────────────────────────────┘
                                            ▼
                             Ingest & Integrity Agent
                (SHA-256, metadata, tamper checks, custody log, Canary ASR)
                                            │
                                            ▼
                      VAST AI OS / VastDB — one store for video, vectors,
                  metadata, incident records, policy clauses, past claims
                                            │
            ┌───────────────────────────────┼───────────────────────────────┐
            ▼                               ▼                               ▼
    Perception Agent                    Sync Agent                    Context Agent
 YOLO11s detect + track,          anchor events + audio →        OpenStreetMap, Mapillary /
 impact, Jev frame checks,        one incident clock             Street View, Highway Code
 VSS + Cosmos3-Reason + Embed1                                    (Jev picks rule)
            └───────────────────────────────┼───────────────────────────────┘
                                            ▼
                               Reconstruction Agent
                      (map positions, speeds, bird's-eye replay)
                                            │
       ┌──────────────────┬─────────────────┼──────────────────┬──────────────────┐
       ▼                  ▼                 ▼                  ▼                  ▼
   Q&A Agent      Statement & Fraud    Liability Agent   Coverage & Benefits   Report Agent
 Cosmos answers   Jev supported /      Jev fault band    code hard rules +    evidence pack,
 + Jev citation   contradicted,                          Jev typed decisions  decision letter,
 check            Jev fraud score                        → ACCEPT / PARTIAL / Jev action gate
                                                           REJECT / REFER
       └──────────────────┴─────────────────┼──────────────────┴──────────────────┘
                                            ▼
                         Adjuster UI  ·  customer decision letter  ·  court pack

   W&B Weave traces every agent step and every Jev decision (audit trail + evals)
   LLM + VLM serving on CoreWeave via W&B Inference
```

### Sponsor stack map

| Tool | Role in Poodle |
|------|-----------------------|
| **VAST AI OS / VastDB** | One store for raw video, segment embeddings, metadata, incident records, policy clauses and past claims. Powers Q&A retrieval, cross-claim search and consistency audits. |
| **NVIDIA VSS Blueprint + Cosmos** | Cosmos3-Reason for segment reasoning and Q&A; Cosmos Embed1 for searchable embeddings; VSS search and ask APIs. |
| **YOLO (Ultralytics)** | Real-time detection and tracking of road users, traffic lights and signs; gates which frames reach heavier models. |
| **NVIDIA Canary-1B ASR** | Transcribes spoken statements for the contradiction check. |
| **W&B Weave** | Traces every agent call and Jev decision: the audit trail in the evidence pack, plus evals (Q&A accuracy, impact-detection precision/recall, sync error, coverage-decision agreement with labelled outcomes). |
| **CoreWeave / W&B Inference** | GPU serving for the reasoning LLM that writes explanations and the decision letter. |
| **Cursor** | Build environment. |
| **TypeSafe Jev** (not a sponsor) | Typed, calibrated decision layer for frame checks, verification, liability band and the coverage decision. |

### Why Weave matters twice
1. **Engineering:** measures how often the agent is right (answer accuracy on labelled questions, impact timing error, light-state accuracy, coverage-decision accuracy against handler-labelled claims).
2. **Legal and regulatory:** the same traces become the "how we reached this" appendix. Every conclusion and every coverage decision links back to the inputs, model calls, Jev distributions and clips that produced it.

---

## Data sources

### Build-day video
Per the event's lab docs, the shared corpus includes **I-24 highway footage, Toronto dashcam, a neighbourhood camera and San Francisco streets** (plus warehouse and indoor clips). Traffic and dashcam clips fit Poodle directly. Internet video is banned on build day; own local recordings are allowed by the upload skill (confirm with the VAST organisers).

| Source | What | Use |
|--------|------|-----|
| Event corpus: I-24, Toronto dashcam, neighbourhood cam, SF streets | Real road footage on the event stack | Primary incident footage, Q&A and search |
| Team-staged incident | Toy-car junction filmed from 2–3 phones (dashcam, CCTV, bystander angles) with a synthetic GPS track | The only multi-angle footage of a single incident; full control of ground truth for evals |

No public dataset was found with several camera angles of the same real crash, which is why the staged incident exists.

### Off-event references (not usable on build day: internet video)
| Source | What | Licence / access |
|--------|------|------------------|
| [Nexar Dashcam Collision Prediction Dataset](https://huggingface.co/nexar-ai) ([paper](https://arxiv.org/abs/2503.03848)) | 1,500 dashcam clips (~40 s), labelled collision / near-collision / normal | Custom "Nexar Dataset License 2025": attribution, no resale, no re-identification ([licence record](https://scancode-licensedb.aboutcode.org/nexar-dataset-2025.html)) |
| [BADAS-Open](https://arxiv.org/pdf/2510.14876) | Collision-anticipation model trained on Nexar data | APSv2 licence |
| [MM-AU (CVPR 2024)](https://arxiv.org/pdf/2403.00436) | 11,727 accident videos with text on cause, prevention, category | Non-commercial; ~364 GB ([mirror listing](https://hyper.ai/en/datasets/38267)) |

### Policy data
| Source | Notes |
|--------|-------|
| Synthetic demo motor policies | A small set of sample schedules (comprehensive, third party fire & theft, third party only; with and without add-ons) and one sample policy wording with sections, benefits, limits and exclusions. Written by the team, so no real insurer's branding or wording is reproduced. |
| Handler-labelled demo claims | 20 or so claims labelled ACCEPT / PARTIAL / REJECT / REFER, used to calibrate Jev thresholds and as the Weave coverage eval. |

### Location & rules context
| Source | What | Notes |
|--------|------|-------|
| [The Highway Code (gov.uk)](https://www.gov.uk/guidance/the-highway-code) | UK road rules | Crown copyright, Open Government Licence; indexed for rule citations |
| [OpenStreetMap](https://www.openstreetmap.org) | Junction geometry, lanes, signals, speed limits, crossings | ODbL, free |
| [Mapillary](https://www.mapillary.com/developer) | Street-level imagery | Free API |
| [Google Street View Static API](https://developers.google.com/maps/documentation/streetview) | Street-level imagery | Needs API key and billing; terms limit storage and reuse |

### Tools, platforms & event docs
- Hackathon page: [tokensand.com/vastlondon](https://tokensand.com/vastlondon) · [luma.com/vastlondon](https://luma.com/vastlondon)
- Judging criteria: [VAST Builders Challenge blog](https://www.vastdata.com/blog/lets-build-introducing-the-vast-builders-challenge)
- Lab docs: [vast-data/vast-builders-challenge](https://github.com/vast-data/vast-builders-challenge) · reference pipeline [vast-data/vss-blueprint](https://github.com/vast-data/vss-blueprint)
- VAST + NVIDIA smart-city pattern: [vastdata.com blog](https://www.vastdata.com/blog/vast-nvidia-cosmos-reason-smart-cities)
- Cosmos Reason: [nvidia/Cosmos-Reason2-8B](https://huggingface.co/nvidia/Cosmos-Reason2-8B) · [NIM API](https://docs.nvidia.com/nim/vision-language-models/1.7.0/examples/cosmos-reason2/api.html)
- W&B Inference & Weave: [models](https://docs.coreweave.com/inference/models) · [evaluations](https://docs.coreweave.com/weave/guides/core-types/evaluations) · [Weave docs](https://weave-docs.wandb.ai)
- [Ultralytics YOLO tracking](https://docs.ultralytics.com/modes/track/)
- TypeSafe Jev: [docs index](https://docs.typesafe.ai/llms.txt) · [confidence routing](https://docs.typesafe.ai/patterns/confidence-routing.md) · [Jev 1.14 release](https://typesafe.ai/blog/jev-1-14) · [official skill](https://github.com/typesafe-ai/skills) · repo skill `.agents/skills/jev-decisions/SKILL.md`

---

## Demo story (90 seconds)

Open `poodle/index.html` first. The poodle is already sitting on the desk, and PD-0147 is the open claim.

1. The claimant states: "I had a green light; the other driver hit me." Their policy: comprehensive, £350 excess, legal-expenses add-on, no courtesy-car add-on.
2. The adjuster uploads three clips (dashcam, CCTV, bystander phone) and the GPS track. The agent hashes them and syncs them onto one timeline.
3. The bird's-eye replay shows both cars entering the junction.
4. Question: "What colour was the light when the blue car crossed the stop line?" → "Red, at 00:13.0 on CCTV-1", with the clip.
5. The statement check marks the other driver's "I had green" as **contradicted** and cites the relevant Highway Code rule on traffic signals. Fault band: claimant not at fault.
6. The coverage panel fills in live: **ACCEPT – PARTIAL**. Repair covered minus excess, excess recoverable, NCD unaffected, legal expenses applies, courtesy car not included. Each line cites a policy clause and a clip.
7. Swap the policy to third party only, with the claimant at fault in a second staged clip → own damage **REJECTED** with the clause cited, routed to a handler for sign-off.
8. One click exports the evidence pack and decision letter, with hashes, Weave trace and Jev decision record.

## Why it can win

- Hits every word of the brief: searches footage, answers questions, spots events, takes action — and the action has money attached (a claim decision).
- Uses each sponsor tool for something it is genuinely good at; Weave plays a dual engineering/legal role.
- A deterministic + typed verification layer around the VLM answers the known weakness judges look for (VLM yes-bias, no numbers).
- Clear buyer (insurers, fleets, legal), clear money (claims handling cost, fraud, consistency).
- A live, controlled multi-camera demo instead of a canned video.

## Limits & responsible use

- Assists human adjusters. Only low-value, high-confidence acceptances can settle automatically; every rejection, partial decision, fraud flag and uncertain case is reviewed by a human handler before the customer is told.
- Coverage logic uses synthetic demo policies; real policy wordings and jurisdictions need their own clause sets and legal review.
- Visual speed estimates and indicator detection are approximate and labelled as such.
- Faces and plates are blurred in exported packs unless legally required; no re-identification across datasets.
- Rule citations cover UK law (Highway Code); other jurisdictions need their own rule sets.
- Jev image input and Box are experimental in 1.14; coverage decisions rely on text facts.
- Dataset licences (Nexar custom, MM-AU non-commercial) allow research use only; neither is used on build day.

## Not yet verified

- Whether the event corpus clips contain a usable collision or near-miss (otherwise rely on the staged incident).
- Own-footage upload rules on build day (confirm with VAST organisers).
- A TypeSafe or OpenRouter key for Jev (none in the repo environment as of 17 Oct 2026).
- Exact text of the Nexar LICENSE file; Mapillary API limits; current Google Street View terms.
- Some reference links (gov.uk Highway Code, Mapillary, Street View, Ultralytics, Weave docs) were written from memory and not opened in this session.
