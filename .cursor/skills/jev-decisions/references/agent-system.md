# Using Jev inside this repo's agent system

Two surfaces: (A) the video agent the team ships at the VAST Builders Challenge, and
(B) the coding-agent loop (Claude Code, Codex, Cursor) that shares the taskboard.

## A. Jev inside the video agent

### Where it earns its place

```
VAST AI OS ingest  ->  frame sampler (ffmpeg, 1 fps)  ->  YOLO detections (classes, boxes, tracks)
        |                                                        |
        v                                                        v
  semantic search (hours)                 Jev per-frame typed judgments (one request per frame,
  "find moments like X"                   all questions batched, previous frame for "what changed")
        |                                                        |
        +----------------> timeline / events (code) <------------+
                                   |
                   confidence + severity gate (code, thresholds in one file)
                     |  routine, high confidence        |  uncertain or severe window
                     v                                  v
               store event, draw box          NVIDIA Cosmos reasons over the clip window
                                                        |
                                              W&B-served LLM writes the narrative / report
                                              Weave traces every step; Jev gates the action
```

- Jev answers in ~100-500 ms with calibrated probabilities, so the agent can watch
  hours of footage and only wake the heavy models on the windows that matter.
- Jev's Box (1.14) gives open-vocabulary localisation that YOLO's fixed classes miss
  ("the person without a hard hat", "the spill nearest the forklift"). Pair every Box
  with a presence Noul; keep YOLO for tracking and counting (Jev cannot count).
- Jev gates agent actions (file report, page supervisor, run tool): one `choice`
  allow / deny / escalate with the task and the proposed action as state; act only
  above the threshold you set for that action's blast radius.
- Jev is **not a sponsor tool** for the hack. The project must still use at least three
  of: NVIDIA Cosmos, VAST semantic search, YOLO, W&B inference or Weave, VAST AI OS,
  CoreWeave, Cursor. Position Jev as the decision layer that makes those tools affordable
  at hours-of-video scale, and trace its calls in Weave so the W&B judge sees them.

### Build order

1. Write `questions.json` (per-frame Nouls, one Choice with `nothing_notable`, one Score,
   Boxes as needed) and the thresholds in the same file. Start from
   `assets/video-questions.example.json`.
2. Run `scripts/jev_video_triage.py --dry-run` to check the request shape, then on a
   30-second clip with a real key. Inspect the JSONL; tune questions, not thresholds, first.
3. Merge frames into events in code; feed only event windows to Cosmos.
4. Add the action gate last. Log `model`, distributions and the branch taken.

## B. Jev inside the coding-agent loop

Jev cannot replace the LLM behind Claude Code, Cursor or Codex (it writes nothing).
It can take over the steps that are decisions: labelling or triaging many items,
checking whether a build or test run succeeded, picking the next action from an
enumerable set, judging safety or severity, and risk-checking tool calls before they run.
The community plugin `jev-use` (MIT, v0.8.0, 13 Oct 2026) packages this for Claude Code,
Codex and pi: https://github.com/shitianfang/jev-use .

### Route each decision: where are the facts x does it block?

| Facts are... | Nothing blocked | Blocked until decided |
| --- | --- | --- |
| already in the agent's context | `jev_judge`, all questions about that state in ONE call | `jev_gate` on that one action; for every tool call wire the PreToolUse gate once |
| in a file or tool output | a script pipes them to `jev-use judge`; they never enter the context | same CLI from the script, then act on the verdicts |
| still to be written by the agent | the agent's | the agent's |

It is a **rate** win, not a token win: Jev spends more tokens per decision, so the saving
is real only when the decision leaves the conversation. Do not route trivia.

### Install (one time, per machine)

```bash
npx -y jev-use install            # wires Claude Code, Codex and pi, whichever it finds
npx -y jev-use doctor             # checks backend, key and permissions; prints missing snippets
```

Set one credential in the agent's environment: `TYPESAFE_API_KEY`, `OPENROUTER_API_KEY`
or `AI_GATEWAY_API_KEY`. `JEV_BACKEND=mock` runs keyless and local. Optional:
`JEV_MODEL=jev-1.14.0`, `JEV_GATE_THRESHOLD`, `JEV_GATE_STATE="production credentials exist in the environment"`.

Manual MCP wiring in a project's `.mcp.json` (Claude Code) or `.cursor/mcp.json` (Cursor):

```json
{"mcpServers": {"jev": {"command": "npx", "args": ["-y", "jev-use@0.8.0", "serve"]}}}
```

Allow the two tools once, or every headless `claude -p` run is refused:

```json
{"permissions": {"allow": ["mcp__jev__jev_judge", "mcp__jev__jev_gate"]}}
```

(`"mcp__jev"` allows the whole server.) The installer deliberately does not write this:
pre-authorising a tool that sends state to a third party is the user's decision.

### Optional zero-token PreToolUse gate, composed with the taskboard hooks

`jev-use hook gate` risk-checks every matched tool call through Jev before it runs, with
no LLM tokens. It only tightens: `deny` -> blocked with a reason; unsure -> ask; `allow` ->
silent, so the normal permission flow decides; Jev unreachable -> fails open. Credentials
in the action are redacted before sending (`src/redact.ts`).

`.claude/settings.json` already has a PreToolUse hook (`taskboard-hook.sh claude-code guard`
on `Edit|Write|MultiEdit|NotebookEdit`). Hooks are additive; add a second entry:

```json
{
  "hooks": {
    "PreToolUse": [
      {"matcher": "Edit|Write|MultiEdit|NotebookEdit",
       "hooks": [{"type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/scripts/taskboard-hook.sh claude-code guard", "timeout": 10}]},
      {"matcher": "Bash",
       "hooks": [{"type": "command", "command": "npx -y jev-use@0.8.0 hook gate", "timeout": 30}]}
    ]
  }
}
```

Scope the gate's matcher to tools worth ~100-300 ms each (`Bash` is the useful one here;
the taskboard guard already covers edits). Codex: the same fragment goes in
`.codex/hooks.json` with matcher `apply_patch|Edit|Write|Bash` style names. Cursor: no
`jev-use` harness exists; use the MCP server plus the routing table above.

### The verdict contract (what comes back)

`{id, type, answer, confidence, confidenceFrom: reported|estimated, escalate, reason?, hint?, distribution?, legend?}`.
Escalation reasons: `writing` / `open_ended` (structurally the LLM's), `oversized`
(state > ~30k tokens), `unsure` (answer below threshold; still present as a prior),
`unreachable` (proceed as if Jev did not exist). Thresholds: 0.5 for reported
confidence, 0.4 for estimated; an explicit `confidence_threshold` always wins.

### Good uses in this repo's workflows

- Triage: a workflow or script with many findings, candidates or frames -> one
  `jev-use judge` call per item batch from a script, verdicts back as JSON.
- CI / test outcome checks: `check("Did the run fully succeed?")` over the log tail.
- Next-action picks with enumerable options (merge / rerun / hold) before a human decides.
- Shell command gating for headless or autonomous runs.
- Not for: writing the plan, the commit message, the code, or the checkpoint line.
