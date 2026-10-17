# Patterns, anti-patterns and the video-frame loop

Sources: https://docs.typesafe.ai/patterns.md , `/patterns/confidence-routing.md`,
`/patterns/fan-out.md`, `/patterns/intent-routing.md`, `/cookbooks/llm_guardrails.md`,
`/model-jaggedness/jev-1.13.md`, https://typesafe.ai/blog/jev-1-14 .

## Pick the primitive by what the answer means

| Need | Primitive | Read the answer as |
| --- | --- | --- |
| one of a defined set | `choice` | top option + per-option probabilities + confidence |
| whether a condition holds | `noul` | probability of yes; one Noul per label when several may apply |
| degree along a described dimension | `score` | expected level index for ranking or thresholds |
| where one thing is in an image | `box` (1.14, experimental) | edges as fractions; always pair with a presence Noul |

## Three-layer division of labour

- **Code**: hard rules, permissions, arithmetic, counting, dates, exact lookups, state, side effects. Check hard policy before asking Jev.
- **Jev**: closed-set semantic judgments over the state code prepared.
- **LLM / Cosmos**: prose, summaries, open-ended reasoning, anything not enumerable.

## Writing questions

- Put the judgment in `instructions`, the possible answers in `criteria`, the facts in `state`.
- Name the state field in backticks: "Is the dog in `photo` wearing a collar?".
- One narrow judgment per question. "Is this trade safe?" is a composite; split it.
- Describe situations, not degrees, in Score levels ("stop work now", not "high").
- Add an `other` / `not_stated` / `none` option to every Choice. Selection beats generation:
  find candidates in code (regex, YOLO classes, tiles), let Jev pick.
- Align `instructions` and `criteria`; a Noul whose `true` means "no" performs badly.
- Structured instructions (objects, arrays, examples, exclusions) are allowed and help.

## Speculative fan-out (one call, many questions)

Ask every question you might need about a state in one request, including branch-specific
ones, and let code consume only the relevant answers. Questions run in parallel against the
same state and cannot see each other. A second request is only needed when an answer decides
what evidence to fetch next or what the next options are. Measured: 12 questions in one
call ~224 ms; the same 12 sequentially ~2.6 s.

## Confidence-gated routing (the pattern to copy)

```python
# All questions and thresholds live in ONE file. Calibrate on labelled data; these are examples.
FLOOR = 0.5           # below: human / LLM review
CONFIRM = 0.85        # medium band for risky actions: confirm before acting
DESTRUCTIVE = 0.9     # only act automatically above this on irreversible actions

a = resp.choices["intent"]
if a.confidence < FLOOR:
    escalate(a)                                  # reasoning model or a person
elif a.choice == "show_balance":
    show_balance()                               # low stakes: floor is enough
elif a.choice == "approve_transfer":
    approve() if a.confidence > CONFIRM else ask_user_to_confirm()
else:
    escalate(a)                                  # the "other" exit
```

Confidence formulas: Choice `(p_max - 1/n)/(1 - 1/n)`; Score penalises mass far from the
modal level; Noul has none, use `|2p - 1|` or the raw probability. Alternatives: top
probability (threshold per question) or top-to-second ratio. Three bands: act, confirm, escalate.

## Intent routing (cheapest capable handler)

Choice over handlers: `deterministic_code`, `fast_llm`, `reasoning_llm`, `human_review`
(plus `other`). Check hard rules in code first. Route uncertain items up, not down.
Routers built on an LLM-as-judge add 1-5 s per request; Jev adds ~0.1-0.3 s.

## Guardrails (input and output screening)

One request per message with several Nouls (jailbreak attempt, harmful request, medical
advice, self-harm, off-topic) plus a Score for potential harm; code applies the policy
(pass / review / block / route). Jev does not treat state as hostile: it is a filter,
not a security boundary. Keep least-privilege tool access underneath. Track false positives.

## Verify and escalate (cascade)

Cheap model or Jev first; verify specific claims with Nouls against the evidence; send
uncertain or failing items to a reasoning model or a person. Extraction cascade:
mini model -> Jev verify -> reasoning model only on failures. Citation check: one Choice
"does the quoted context support the claim?" against the source.

## Counting and numbers

Jev does not count or compute. Iterate candidates in code, ask one Noul per item in one
request, sum in code. Convert numbers to named buckets before asking. Extract date parts
as Choices (month, day, year, `not_stated`) and assemble in code.

## Video-frame loop (hack-relevant)

1. **Sample** frames with ffmpeg (1 fps is plenty for triage; 2-4 fps near events).
   Scale so the longest side <= 1568 and the shortest >= 280. Baseline JPEG, quality 85-90.
2. **Filter in code** before Jev: YOLO says "no person in this frame" -> skip the PPE questions.
   Motion/scene-change thresholds -> skip static frames.
3. **One request per frame** with every question batched: presence Nouls, a Choice for the
   event type (with `nothing_notable`), a Score for severity, Boxes for targets YOLO cannot
   name (open-vocabulary: "the person without a hard hat"). Add `previous_frame` to the
   state and ask "what changed" Nouls (arrival, departure, fall, spill) for temporal events.
4. **Build the timeline in code**: merge consecutive frames where a Noul > threshold into
   events with start/end; keep the full distribution per frame for the UI.
5. **Gate escalation**: low confidence or high severity windows go to NVIDIA Cosmos for
   reasoning over the clip; the LLM (W&B inference) writes the incident narrative; Weave
   traces both. High-confidence routine frames never reach a heavy model.
6. **Gate actions**: before the agent files a report, pages a supervisor or runs a tool,
   one `choice` allow/deny/escalate over the task + proposed action.
7. **Look closer only when needed**: on a low-confidence Box, crop with padding (0.05) and
   ask again; on "several" targets, tile the frame and ask per tile.

Budget: a 720p JPEG is a few hundred to a few thousand input tokens; at $0.042/Mtok an hour
of 1 fps footage with ten questions per frame costs cents. Latency ~100-500 ms per frame,
parallelise 4-8 requests. Respect the per-organisation rate limit.

## Jev 1.14 "danger zone" caveats

- Images, Box and long context are "dreamer-ready", not production-certified. Request and
  response shapes and limits can change between releases.
- All models, Jev included, perform worse on images than on text: decompose into the
  simplest questions; compare against a reference picture when possible.
- Long context is slower and less accurate; keep state short; use it only when needed.
- 1.14 vs 1.13 internal "overall intelligence": 60.0 vs 58.9 (TypeSafe's own, biased estimate).
  Run your own evals; the release post says the measure is not stable over time.

## Jev 1.13 jaggedness (still relevant on 1.14)

| Failure | Do instead |
| --- | --- |
| literal reading | write the exact condition; boundary cases in criteria |
| math, counting, numeric closeness | keep in code; per-item Nouls |
| date/time comparison | extract parts as Choices; compare in code |
| indirection, double negatives | reduce hops; point at the state field |
| large irrelevant state | filter first; relevance Noul if needed |
| adversarial content | precise criteria; test hostile inputs; least privilege |
| contradictory instructions vs criteria | align wording |
| Choice option order bias | reorder and check consistency |
| generation | use a generative model; turn extraction into selection |

## Anti-patterns

- One composite question ("is this safe to merge?").
- Jev for prose, code, planning or final authorisation.
- Routing every agent step through an LLM when a typed check suffices, or routing trivia
  through Jev when the answer is already known.
- Treating `confidence` as authorisation or as the probability the action succeeds.
- `jev-latest` in production; one threshold for routes with different consequences.
- Reusing English thresholds for other languages; publishing vendor speed multipliers as facts.
- Pasting bulk data into the conversation to judge it: run it from a script by reference.

## Rollout checklist

1. Shadow mode: log Jev's verdicts next to the current decision; do not act.
2. Label 50-200 examples; measure accuracy and calibration per question; set thresholds by consequence.
3. Automate the low-risk path first; keep a deterministic fallback and a rollback.
4. Log model id, input schema version, distribution, confidence, branch, outcome.
5. Re-evaluate on every model version change.
