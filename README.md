# REAL-TIME VIDEO AGENTS HACKATHON

# vast-real-time

Hackathon project, bootstrapped with `hackathon-init`.

## Poodle

A claims desk for road incidents. Poodle watches the incident footage, spots the vehicles and signals, checks the statement against what the camera saw, decides cover against the policy, and puts the nearest live London traffic cameras next to the evidence. Idea and agent design: [`docs/IDEA.md`](docs/IDEA.md). UI audit and redesign notes: [`docs/ui-audit.md`](docs/ui-audit.md).

![Poodle claim view](docs/audit/after-claim.jpg)

### Run it

```bash
uv run --with-requirements server/requirements.txt uvicorn server.app:app --port 8080
# open http://localhost:8080
```

To scan live TfL stills with YOLO on a laptop, run the server in an environment that also has `ultralytics` (the local fallback detector):

```bash
uv venv .venv --python 3.12 && uv pip install --python .venv/bin/python -r server/requirements.txt ultralytics
.venv/bin/python -m uvicorn server.app:app --port 8080
```

### What is real and what is replayed

| Part | Source |
| --- | --- |
| Live London cameras | TfL JamCams API, live (stills refresh every 1–3 min, 10 s clips). Powered by TfL Open Data. |
| Detection boxes on incident footage | YOLO11s, precomputed on the demo stills (`server/tools/detect_stills.py`). Signal colour from a pixel check on each traffic-light box. |
| Live camera scan | YOLO11s on the latest TfL still: `$YOLO_URL` on the event stack, else local `ultralytics`. |
| Coverage decision | Hard rules and the decision table run in code (`server/engine.py`). Typed answers come from Jev when `TYPESAFE_API_KEY` or `OPENROUTER_API_KEY` is set, otherwise from seeded answers. |
| Footage Q&A | W&B Inference when `WANDB_API_KEY` is set, otherwise rule-based answers over the findings. |
| Evidence | SHA-256 of every file, custody log, printable evidence pack (`/api/claims/<id>/pack`). |
| Events | `server/data/events.jsonl`, and VastDB when `VASTDB_ENDPOINT`, `VASTDB_ACCESS_KEY` and `VASTDB_SECRET_KEY` are set. |

Incident footage is demo footage: the team's synthetic CCTV stills (`Demo img/`) turned into 12 s clips by `server/tools/build_media.py`, with the burned-in clock set to each claim's incident time. Policies are synthetic.

Code is about 200 KB. Media is about 2 MB; to keep it out of a 1 MiB deploy, upload `poodle/media/` to a bucket and set `POODLE_MEDIA_BASE` to its URL.

### Demo in 90 seconds

1. Inbox: seven claims need a person. Open PD-0147 (J/K, Enter).
2. The footage plays with YOLO boxes; both main-road signals read red. The two nearest live TfL cameras sit beside it, 45 m and 243 m away.
3. Ask "What colour was the light?" (cites the signal finding), then "How fast was the other car going?" ("Not visible").
4. Recommendation: accept, partial. The other driver is at fault (Highway Code 175); the courtesy car is not on the policy. £1,790 payable, £2,140 recovered.
5. Open a live camera, scan the latest still, attach it as evidence: it joins the chain of custody with its hash.
6. Cmd+K, type "camden": PD-0226 settles without a handler. PD-0188 shows the fraud flag and goes to the SIU.
7. Evidence pack: one printable page with the decision, findings, statement check and hashes.

## Working on this repo with coding agents

Claude Code, Cursor, Codex and any agent that reads [`AGENTS.md`](AGENTS.md)
share one taskboard: [`agent-coordination/taskboard.md`](agent-coordination/taskboard.md).
Each agent registers what it is building, checkpoints as it goes, and can take
over a task another agent left unfinished.

Every turn starts by pulling from GitHub, in case someone else pushed.
Every commit is still pushed automatically. After cloning, enable that once:

```bash
./scripts/agent-taskboard.sh setup
```
