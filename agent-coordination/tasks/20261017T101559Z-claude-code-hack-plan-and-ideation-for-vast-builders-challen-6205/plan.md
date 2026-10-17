# Plan: Hack plan and ideation for VAST Builders Challenge London

| Field | Value |
| --- | --- |
| Task ID | `20261017T101559Z-claude-code-hack-plan-and-ideation-for-vast-builders-challen-6205` |
| Created by | claude-code |
| Scope | `docs/ agent-coordination/` |
| Created | 2026-10-17T10:15:59Z |
| Initial status | planned |

## Goal

Give the builder one validated hack idea for the VAST Builders Challenge London (17 Oct 2026, 6-hour build).
Success: `docs/hack-plan.md` holds judge and sponsor research, the two inspirations with novelty verdicts,
the ranked ideas, the selected idea, the 6-hour build plan, and the demo and pitch outline.

## Plan

1. Run a research workflow: rules, judges, VAST stack, NVIDIA and W&B stack, prior winners, novelty of the two inspirations.
2. Run an ideation panel with three angles and score the ideas with two judge lenses.
3. Run an adversarial novelty check on the top two ideas.
4. Write `docs/hack-plan.md` with the results and the selected idea.
5. Report back in ASD-STE100 Simplified Technical English.

## Files and impact

- Planned files: `docs/hack-plan.md` (new), this plan and activity log.
- Expected impact: documentation only. No application code yet.

## Validation

- Checks to run: each research claim has a source URL; the selected idea uses at least 3 sponsor tools; the build fits in 6 hours.

## Handoff checkpoint

- Last completed: Task registered; research workflow started.
- Current state: Research and ideation running.
- Next action: Write `docs/hack-plan.md` from the workflow result.
- Blockers: None known.
- Validation state: Not started.

## Plan changes and decisions

- 2026-10-17T10:15:59Z — Task created. Fill this plan before modifying scoped files.
- 2026-10-17T10:17:00Z — Plan filled. Research workflow `wf_9937e683-2fb` started with 7 researchers, 3 ideators, 2 judges, 2 verifiers.
- 2026-10-17T11:50:00Z — Scope widened at the builder's request: added the `jev-decisions` skill (TypeSafe Jev 1.14.0) under `.agents/skills/`, `.claude/skills/`, `.cursor/skills/` and listed it in `AGENTS.md`. Scripts validated with dry runs and a local mock server; no live Jev key on this machine yet.
- 2026-10-17T11:50:00Z — Research workflow failed once on a transient TLS error in 4 agents (self-signed certificate on the venue network); script patched to tolerate null judge results and resumed as `wdb0i50jk` with the 7 cached research results.
