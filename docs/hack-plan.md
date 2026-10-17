# Hack plan: VAST Builders Challenge London, 17 October 2026

Written at 12:00 BST. Build ends at 16:30 BST. Demos start at 16:30. Awards at 18:30.
Status: the research is complete. The idea panel and the adversarial novelty check are still running. This file will be updated when they report.

## 1. Decision now

Build **RackWitness**: a camera agent that watches a technician install a GPU or storage node against the vendor runbook, flags a wrong cable or a skipped step within seconds, and writes a timestamped commissioning record with evidence clips into VastDB.

Why this one:

- The sponsors in the room are the customers. CoreWeave racks tens of thousands of GPU nodes and runs VAST AI OS. VAST ships CNode and DNode hardware. NVIDIA deploys DGX SuperPODs.
- It reuses the PC-build demo from your second inspiration. A PC case on the bench plays a 1U node.
- It hits all four judges: temporal step tracking (NVIDIA), one data platform for clips, events and search (VAST x2), a Weave eval with numbers (W&B).
- No team in San Francisco or New York built it.

Runner-up: **ClearTray**, a security-lane divest coach. It keeps the airport spirit of your first inspiration. See section 5.

## 2. How the room scores

The only published criteria are **creativity, technical implementation and real-world impact** (Ram Bansal, VAST blog, 18 Aug 2026). The first round is a table walkthrough with each team. The 3-minute demo and the recorded video are the product.

| Judge | What they ship or study | Show them | Do not show them |
| --- | --- | --- | --- |
| Abubakr Karali, NVIDIA Senior Solutions Architect | Computer-vision researcher: action recognition, tracking, multi-camera. Ex Metropolis EMEA and Smart Spaces. Reshared VSS 3 "agentic search for actions and temporal events". | State tracked across frames, YOLO track IDs that gate the VLM, Cosmos 2D points on the frame, honest precision and latency. | Per-frame captions sold as "video understanding", one cherry-picked clip, no false-positive handling. |
| Ram Bansal, VAST Sr Developer Advocate | Wrote the reference pipeline the lab runs. Ships open-source repos and MCP servers. | A clean repo that reproduces the demo, the agent exposed as an MCP tool, own rows in VastDB. | A search box. He has seen it at two cities. |
| Brian Verkley, VAST Director AI Data Platform (keynote) | AgentEngine author. Thesis: keep all data in one place, let agents observe, reason, act, evaluate. | Clips, detections, verdicts and search in one platform. An action with a cost or safety value. "In production this is a DataEngine trigger." | A laptop frontend that calls one API with no data layer. Sponsor tools bolted on. |
| Junaid Butt, W&B AI Solutions Engineer | Evals person. Judged the Mistral London hack for W&B. Promotes AI-evals courses. | Weave traces with the frame attached, a 20-item labelled eval, a leaderboard, before-and-after numbers. | "It works" with no numbers. W&B used only as a token endpoint. |

Winning mechanics at sibling video hacks (Neo4j and TwelveLabs hack, July 2026; NVIDIA Cosmos Cookoff): finished live demo, answers linked to timestamps and clips, deterministic verification around the VLM, typed outputs, a reframed domain.

## 3. Stack facts you need today

- Lab pipeline: S3 chunks -> Segmenter (5 s) -> YOLO11s detector -> Cosmos3-Reason reasoner -> Cosmos Embed1 (256-dim) -> VastDB. Only Detector -> Reasoner -> Embedder re-runs during the day. Do not redeploy the DataEngine graph.
- Direct model calls from the team VM: Cosmos3-Reason at `$COSMOS3_REASON_URL/v1/chat/completions` (OpenAI format, clip as `data:video/mp4;base64`, 4 fps default, ask for `<think>` and `<answer>` JSON, `max_tokens` small). YOLO at `$YOLO_URL/v1/infer` with `video_base64`. Cosmos Embed1 at `$COSMOS_EMBED1_URL/v1/embeddings`. Canary-1B ASR at `$CANARY_1B_URL/v1/audio/transcriptions`. Check `/config/<team>.config` for a bearer token. The docs disagree on auth.
- VSS API (JWT from `/api/v1/auth/login`): `POST /api/v1/search` (hybrid, `metadata_filters`, `time_filter`), `POST /api/v1/agent/ask`, `POST /api/v1/videos/upload` (own `.mp4` or `.webm`, `scenario`, `custom_prompt` <= 800 chars), `POST /api/v1/dashboard/reingest`, `POST /api/v1/videos/synthesize`.
- VastDB: `vastdb` Python SDK with PyArrow. Make your own schema and table, for example `commissioning.events`. Never drop `vss-collection`.
- W&B serverless inference: `https://api.inference.wandb.ai/v1`, OpenAI client with `project=`. Text models: `openai/gpt-oss-120b`, `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B`, `meta-llama/Llama-3.3-70B-Instruct`. Vision models exist too (Gemma 4, Nemotron 3.5 Super VL). Weave: `weave.init`, `@weave.op`, `weave.Evaluation`, leaderboards.
- Corpus: highway I-24, Toronto dashcam, neighborhood cam, SF streets, warehouse (~178 clips), indoor smart space (~102 clips). Internet video is banned. Own local recordings are allowed by the upload skill. Confirm with Ram before you rely on it.
- Deploy: Python or Node app under 1 MiB of code, port 8080, team namespace, open from the App button. A laptop-only app does not count.
- Known risks from NYC and SF: re-ingest stalls for 40 minutes or more, pods restart, the shared GPU adds seconds. Keep local copies of every clip. Build a replay mode.
- Cosmos Reason2-8B accepts about 42 percent of non-events (PERJURY team benchmark). Put a deterministic check around every VLM verdict.

## 4. The two inspirations

### Airport X-ray or lidar detection

Verdict: **crowded and no data**. SeeTrue holds ECAC certification since January 2026. Smiths iCMORE, Rapiscan and Leidos ship the same product. STING-BEE (CVPR 2025) already does VLM reasoning on X-ray images. The lab corpus has no X-ray or lidar footage. Cosmos was not trained on X-ray. Do not build this.

Keep the spirit: point the agent at the security lane, not the scanner. That is ClearTray in section 5.

### Smart-glasses "expert eyes"

Verdict: **partially taken**. Meta Live AI, Gemini Live and ChatGPT voice-and-video answer questions about what the camera sees. Factory systems (Retrocausal, PTC Step Check, iFactory) verify steps from fixed station cameras. Understudy (SF team 39) coached a person live from expert clips on this exact stack.

Open ground: proactive interruption only on a mistake, grounding in a written runbook with no expert video, retrofit onto wearable or archived footage, and a searchable evidence record. RackWitness takes that ground for the buyer with the most money in the room.

## 5. Candidate ideas

| Idea | Source | Buyer tomorrow | Demo moment | Real problem | Sellable | Novel | Sponsor pain | Score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RackWitness | Claude panel | Vendor professional services, neocloud build teams, install contractors | Orange cable goes into FABRIC-1 instead of MGMT. Flag within 5 s with the port circled. Search all install footage for the same error. | yes | yes | likely, check pending | yes, CoreWeave and VAST | 8.5 |
| ClearTray | Claude panel | Airport screening operators, lane vendors | Judge drops a bag with the laptop inside. "Please take your laptop out of the bag." Then: every tray this morning that failed divest. | yes | yes, slow procurement | likely, check pending | NVIDIA Smart Spaces | 8 |
| Lone Job | Cursor | Facilities operations director | Tool left on the frame before the panel closes. One sentence. The old job video plays at the same second. | yes | yes | partial | VAST archive thesis | 7.5 |
| Return Stop | Cursor | Head of returns at a hardware company | 16 of 20 return videos show open memory clips. Live build stops before power-on. | yes | yes | partial | VAST archive thesis | 7 |
| QuietHands | Claude panel | No clear buyer | Grandmother builds a PC. The coach speaks only on a mistake. | yes | no | partial | NVIDIA, W&B | 6.5 |

The Cursor ideas are in `docs/cursor-hack-ideas.md`. Lone Job and RackWitness share the same loop. RackWitness has the richer buyer and the judges' own employers as customers.

## 6. Build plan for RackWitness (4.5 hours)

Team: two people. Web demo only. No accounts, no mobile app, no second agent.

### Props

- One PC case or motherboard on the bench. Print large port labels: MGMT, FABRIC-1, PSU-A, PSU-B.
- Three cable colours. One ESD strap. One RAM stick or drive.
- An 8-step runbook as text. Example: strap on, rails, drives in order, PSU-A, PSU-B, orange cable to MGMT, blue cable to FABRIC-1, scan label.

### Schedule

| Time | Who | Do this |
| --- | --- | --- |
| 12:00-12:30 | Both | Set up props. Write the runbook. Send it to W&B inference to get a JSON step graph: step id, expected visible evidence, cable colour to port map, known mistakes. Confirm own-footage upload with Ram. |
| 12:30-13:15 | A | Record 8 takes on a phone from above: 4 correct, 4 with one planted error. Keep local copies. Upload them with `scenario: egocentric`, `camera_id: headcam_tech1` and a custom prompt that names the labels, cable colours and parts. |
| 12:30-14:00 | B | Backend (FastAPI, port 8080). Browser posts 4-second webm clips. YOLO gates on person or hands present. Cosmos3-Reason gets the clip, the current step, the next step and the cable map. It returns JSON: step id, status (done, not done, deviation), evidence timestamp, 2D point, explanation. Advance the state only when two consecutive windows agree. Write each event to `commissioning.events` in VastDB. |
| 14:00-15:00 | A | UI: live camera with the circled point, runbook checklist, commissioning record, "sign-off and punch list" button (W&B LLM), search panel on `POST /api/v1/search` with `metadata_filters {camera_id: headcam_tech1}`. |
| 14:00-15:00 | B | Weave: `@weave.op` on YOLO, Cosmos and LLM calls with the frame attached. Label 20 windows. Run `weave.Evaluation` with gate on and off. Publish a leaderboard. |
| 15:00-15:45 | Both | Deploy with `/deploy-app-no-registry`. Record the 3-minute video with replay mode. Write the README with the architecture and the five sponsor tools. |
| 15:45-16:15 | Both | Rehearse the pitch twice out loud. Fix one thing only. |
| 16:15-16:30 | A | Submit: repo, video link, description, tools, names, emails. |

### Cuts

- No voice input unless everything else works by 15:00. Canary ASR is a stretch.
- No Cosmos critic second pass unless the deviation flag misfires in tests.
- No consumer framing. Say "grandmother" only as a one-line origin story.

### Fallbacks

- If upload or re-ingest stalls: compute Cosmos Embed1 vectors yourself and run kNN over `commissioning.events` in Python.
- If the GPU is slow: shorter clips, `max_tokens` 256, a visible "verifying step 6" state, replay mode.
- If Cosmos cannot tell the ports apart: make the rule "orange cable goes to the port with the big MGMT label". Use large labels and a static camera.

## 7. Where Jev fits (stretch, not required)

Jev is TypeSafe's typed decision model (see the `jev-decisions` skill). It is not a sponsor tool. Use it only if a key is available, and only in these spots:

- Verifier vote: send the frame still and the Cosmos explanation. Ask one Noul: "Does the frame show the orange cable in the MGMT port?" Combine it with the YOLO gate and the two-window rule into a quorum. This counters the Cosmos yes-bias at about 100 ms.
- Action gate: one Choice, allow / deny / escalate, before the agent writes a red flag or a sign-off.
- Box: locate "the orange cable end" when Cosmos returns no point.

Script: `.agents/skills/jev-decisions/scripts/jev_video_triage.py`. No TypeSafe or OpenRouter key is in the environment yet.

## 8. Pitch (3 minutes)

1. Problem (30 s): "Every GPU node goes in by hand. One swapped port costs hours at bring-up. The head-cam footage exists and nobody watches it." Name CoreWeave and VAST field services as the people who have this problem.
2. Live moment (90 s): the judge plugs the orange cable into the wrong port. The flag appears with the port circled. The judge fixes it. The record shows "corrected 00:58".
3. The archive (30 s): search "cable inserted into wrong port" across the day's takes. Show the Weave leaderboard: precision with and without the gate.
4. Why now and ask (30 s): "Same loop, swap the webcam for the tech's head-cam, same runbook format. It runs on a DGX Spark on the build cart." Ask for a pilot on one build cart.

Map each beat to a criterion out loud: creativity (a witness, not a search box), technical implementation (gate, verify, two-window rule, VastDB, Weave), real-world impact (rework hours and outages).

## 9. Sanity checks

1. Who pays tomorrow: vendor professional-services arms and neocloud build teams.
2. Sellable Monday: yes, as per-node commissioning records on one build cart.
3. Exact match exists: no. Two web searches at 12:05 ("AI camera verifies data center technician rack installation cabling steps runbook commissioning record video" and "wearable camera vision language model step verification technician procedure deviation alert product") found no product. Closest: ACSETRA validates commissioning photos and tags, not video or steps (https://acsetra.com/solutions/ai-data-center-commissioning). Factory systems are fixed-station. The adversarial check in the workflow is still pending.
4. Whose pain: CoreWeave (W&B's parent), VAST, NVIDIA.
5. 30-second moment: the wrong port flagged and circled.
6. Cut if 2 hours are lost: voice, critic pass, leaderboard. Keep gate, verdict, record, search.
7. Headline: "A witness for every node you rack."
8. The winner in the room probably builds another warehouse or traffic agent. This is more defensible.
9. Picked to win, not to build.

## 10. Key sources

- Hack page and rules: https://tokensand.com/vastlondon , https://luma.com/vastlondon
- Criteria: https://www.vastdata.com/blog/lets-build-introducing-the-vast-builders-challenge
- Lab docs: https://github.com/vast-data/vast-builders-challenge (ARCHITECTURE_REFERENCE.md, BUILD_DAY.md, `.cursor/skills/`)
- Reference pipeline: https://github.com/vast-data/vss-blueprint
- VAST and NVIDIA City Watch pattern: https://www.vastdata.com/blog/vast-nvidia-cosmos-reason-smart-cities
- Prior projects: https://tokensand.com/vastsf/projects , https://tokensand.com/vastnyc/projects , Understudy https://github.com/ToukoUrsin/vast-video-agents-hack , PERJURY https://github.com/charliegillet/perjury-vast-builders-challenge
- Cosmos Reason 2: https://huggingface.co/nvidia/Cosmos-Reason2-8B ; NIM API: https://docs.nvidia.com/nim/vision-language-models/1.7.0/examples/cosmos-reason2/api.html
- W&B inference and Weave: https://docs.coreweave.com/inference/models , https://docs.coreweave.com/weave/guides/core-types/evaluations
- Judges: https://se.linkedin.com/in/abubakr-karali-8988486b , https://ca.linkedin.com/in/ram-bansal , https://www.vastdata.com/blog/introducing-agentengine , https://uk.linkedin.com/in/junaid-butt-23a18314a
- Novelty, X-ray: https://www.airportsinternational.com/article/seetrue-wins-historic-ecac-certification , STING-BEE https://arxiv.org/html/2504.02823v1
- Novelty, glasses: https://www.retrocausal.ai/ , https://ifactoryapp.com/ai-vision-camera/ai-work-instruction-compliance-checking-vlms , https://ptc.com/en/products/vuforia/vuforia-expert-capture
