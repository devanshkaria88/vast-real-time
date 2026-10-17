---
name: jev-decisions
description: This skill should be used when a step in an agent, pipeline or app is a decision rather than text generation - classify, route, triage, score, verify, gate a tool call, or locate something in an image or video frame - and the answer comes from a closed set. It covers TypeSafe's Jev "System One" decision model (jev-1.14.0, released 14 Oct 2026, with experimental image input, a Box bounding-box type and 262k long context), the exact HTTP API and SDKs, confidence rules, and how to wire Jev into this repo's video agent and into the Claude Code / Codex / Cursor agent loop (jev-use MCP tools and PreToolUse gate). Do not use it for steps that must produce new prose or code.
---

# Jev typed decisions (TypeSafe System One)

Jev is TypeSafe AI's hosted decision model. It does not generate text. It takes a
`state` (string, JSON object or array, optionally with images) and a map of typed
`questions`, and returns one typed answer per question with calibrated probabilities,
in about 70-500 ms, at $0.042 per million input tokens and free output tokens.

Treat Jev as a programming primitive: code owns the workflow, hard rules, arithmetic
and side effects; Jev supplies the semantic judgment where code needs it; an LLM
writes any prose. Jev is **not** a replacement for the LLM behind a coding agent.

## Jev 1.14.0 (14 Oct 2026): what changed

- `jev-1.14.0` ships under the `jev-preview` alias. `jev-latest` still pointed to
  `jev-1.13.0` on 15 Oct 2026 and moves to 1.14.0 about one week after release.
  Pin a versioned id in production; log `response.model`.
- Core change is "small, subtle improvements to everything"; biggest expected gain is
  multilingual. Price and default limits unchanged (64k tokens per request, 32k for
  state plus any one question).
- Experimental "danger zone" features, opt-in by header and not production-certified:
  - Images: header `TypeSafe-Danger-Zone-Images: true`; works on 1.13 and 1.14.
  - `box` question type: returns one bounding box; **requires `jev-1.14.0` / `jev-preview`**.
  - Long context: header `TypeSafe-Danger-Zone-Long-Context: true`; raises both
    limits to 262k tokens; slower and less accurate.
- Deprecation: at least 60 days notice before `jev-1.13.0` is deprecated, 30 days for `jev-1.14.0`.

## Access

| Route | Base URL | Env var | Model ids |
| --- | --- | --- | --- |
| TypeSafe direct | `https://api.typesafe.ai` | `TYPESAFE_API_KEY` | `jev-latest`, `jev-preview`, `jev-1.13.0`, `jev-1.14.0` |
| OpenRouter | `https://openrouter.ai/api` (same `/v1/systemone` path) | `OPENROUTER_API_KEY` | `typesafe/jev-1.14`, `typesafe/jev-1.13`, `~typesafe/jev-latest` |
| Vercel AI Gateway / AI SDK | `@ai-sdk/typesafe-ai`, `experimental_evaluate` | `AI_GATEWAY_API_KEY` | `typesafe-ai/jev` |

Keys: https://console.typesafe.ai/keys (signups were paused for a period in late
Sept 2026; OpenRouter needs no TypeSafe account). Keep keys server-side. No key in
this repo's environment as of 17 Oct 2026, so run scripts with `--dry-run` first.

## Decide whether a step is Jev-shaped

Route a step to Jev only when both hold:

1. It produces **no new text or code** (a label, a pick, a number, a yes/no, a box).
2. Its answers can be **enumerated in advance** (options, levels, true/false, one target).

Otherwise it belongs to the LLM (writing, open-ended planning) or to code (math,
dates, counting, exact lookups, permissions, execution). If the answer is already
known, do not call Jev at all.

## Core API in one screen

`POST https://api.typesafe.ai/v1/systemone`, `Authorization: Bearer <key>`, JSON body:

```json
{
  "model": "jev-1.14.0",
  "state": {"frame_note": "worker on scaffold, no visible harness", "site": "crane bay"},
  "questions": {
    "unsafe":   {"type": "noul",   "instructions": "Does `frame_note` describe a worker at height without fall protection?"},
    "category": {"type": "choice", "instructions": "What kind of event is `frame_note`?",
                 "criteria": {"fall_risk": "work at height without protection", "ppe_missing": "missing helmet or vest", "other": "anything else"}},
    "severity": {"type": "score",  "instructions": "How severe is the situation in `frame_note`?",
                 "criteria": ["routine, nothing to act on", "worth a supervisor's look", "stop work now"]}
  }
}
```

Response: `model`, `answers` keyed by your ids (`noul` -> `noul` 0-1; `choice` -> `choice`,
`probabilities`, `confidence`; `score` -> `score`, `legend`, `probabilities`, `confidence`;
`box` -> `box{top,bottom,left,right}` 0-1 fractions, `confidence`) and `usage`.
Full schemas, SDK signatures, limits and errors: `references/api.md`.

## Rules that keep Jev correct

- **One judgment per question.** Write the exact condition; Jev reads literally.
  Boundary cases go in `criteria`. Split "what you meant" into two literal questions.
- **Batch.** Ask every independent question about one state in **one** request;
  they run in parallel (13 questions in one call: 12x cheaper, 10x faster than sequential).
- **Filter state in code.** Send only what the questions need. Irrelevant state lowers accuracy.
- **Give every Choice an exit** (`other`, `not_stated`, `none`). Add a presence Noul
  next to any Box. A Noul at 0.5 means "cannot tell", not "medium".
- **Keep math in code.** No counting, dates, arithmetic or hex colours in Jev. Count
  by asking one Noul per item and summing in code.
- **Own the thresholds.** `confidence` is distribution concentration, not permission.
  Typical bands: floor ~0.5 to catch uncertainty, ~0.9 before destructive actions.
  Scale thresholds with the cost of a wrong answer. Calibrate on labelled examples.
- **Put all questions and thresholds in one reviewable file.** Log the versioned
  model id, full distribution, chosen branch and outcome. Shadow mode before enforcement.
- **State is an attack surface.** Jev does not treat state as hostile. Keep
  least-privilege underneath any guardrail; test with adversarial inputs.
- **Pin the version** (`jev-1.14.0`), never `jev-latest` in production. Re-evaluate on upgrade.

## Images, video frames and Box

- Send `TypeSafe-Danger-Zone-Images: true` on every request with an image or a Box question.
- Each image goes once in top-level `assets` keyed by a reference string (use a UUID);
  write the reference inside `state`, `instructions` or `criteria`. Every asset must be
  referenced; each use adds the image's tokens again.
- Limits: PNG or JPEG stills; 280-1568 px per side; 78,400-2,458,624 total pixels;
  16 MiB per file; 32 MiB per request. Out-of-range images are rejected, not resized.
- Prepare frames: rotate pixels upright, longest side <= 1568, baseline JPEG quality ~90.
- Prefer multipart (`part`) over base64 for size. SDKs do this for you.
- Box: one target per question; pair with a presence Noul; crop large images before
  looking for small targets; multiply edges by width/height to get pixels.
- Jev performs worse on images than text. Decompose into the simplest questions.

## Using Jev in this repo

Two surfaces, detailed in `references/agent-system.md`:

1. **Inside the hack's video agent.** Jev is the fast, cheap, calibrated decision layer
   between frame sampling / YOLO and the heavy models: per-frame triage (Noul/Choice/
   Score/Box batched per frame), "what changed" over consecutive frames, confidence-gated
   escalation of uncertain windows to NVIDIA Cosmos, and gating of agent actions.
   Jev is **not a hackathon sponsor tool**: still use at least three of Cosmos, VAST
   semantic search, YOLO, W&B, VAST AI OS, CoreWeave and Cursor.
2. **Inside the coding-agent loop** (Claude Code, Codex, Cursor). Install `jev-use`
   for `jev_judge` / `jev_gate` MCP tools and an optional zero-token PreToolUse gate
   that composes with the taskboard hooks already in `.claude/settings.json`.

Patterns, anti-patterns and the video-frame loop: `references/patterns.md`.

## Scripts

Both scripts are stdlib-only Python 3.10+. They read `TYPESAFE_API_KEY` (direct) or
`OPENROUTER_API_KEY` (OpenRouter), honour `JEV_MODEL` and `JEV_BASE_URL`, retry 429/529
with backoff, and print the request without sending it when `--dry-run` is set.

```bash
# One System One call: text state, optional images, Noul/Choice/Score/Box questions
python3 scripts/jev_call.py --state-json '{"note": "..."}' --questions questions.json
python3 scripts/jev_call.py --image frame=frame.jpg --questions assets/video-questions.example.json --dry-run

# Sample a video at N fps with ffmpeg, judge every frame, write a JSONL timeline + events
python3 scripts/jev_video_triage.py --video clip.mp4 --fps 1 --questions assets/video-questions.example.json --out timeline.jsonl
```

Edit `assets/video-questions.example.json` to the demo's own questions; keep it as the
single reviewable file of questions and thresholds.

## Live docs

The live docs are the source of truth for version-dependent details. Index:
https://docs.typesafe.ai/llms.txt (append `.md` to any docs path for Markdown).
Key pages: `/api`, `/models`, `/images`, `/primitives/box`, `/confidence`,
`/patterns/confidence-routing`, `/model-jaggedness/jev-1.13`, `/cookbooks`.
Release post: https://typesafe.ai/blog/jev-1-14 . Official skill:
https://github.com/typesafe-ai/skills . Agent-loop plugin: https://github.com/shitianfang/jev-use .
