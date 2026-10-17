# Plan: Hackathon submission form copy for Poodle

| Field | Value |
| --- | --- |
| Task ID | `20261017T150518Z-claude-code-hackathon-submission-form-copy-for-poodle-20981` |
| Created by | claude-code |
| Scope | `docs/submission.md` |
| Created | 2026-10-17T15:05:18Z |
| Initial status | planned |

## Goal

Give the builder the two texts the submission form asks for: a one-sentence description (300 characters max) and a project description (1,500 characters max) that says what we built, how it works and how each sponsor technology is used. Every claim must match the code as it is now, not the IDEA.md ambitions.

## Plan

1. Read README, IDEA.md, hack-plan.md, server/ and poodle/ to map what is built, what is live and what is replay.
2. Check the hackathon page for the technology list the form offers.
3. Workflow: parallel subsystem readers, five drafts from different angles, judge panel, synthesis, adversarial fact-check against the code.
4. Write `docs/submission.md` with both texts, character counts and the technology mapping.
5. Report in plain English.

## Files and impact

- Planned files: `docs/submission.md` (new).
- Expected impact: documentation only.

## Validation

- Character counts under 300 and 1,500.
- Each technology sentence points to a file in `server/` or `poodle/`.
- No claim about Cosmos, W&B or VastDB says "tested" (README says they are untested).

## Handoff checkpoint

- Last completed: Task registered, sources read.
- Current state: Workflow about to start.
- Next action: Run the draft and verify workflow.
- Blockers: None.
- Validation state: Not started.

## Plan changes and decisions

- 2026-10-17T15:05:18Z — Task created.
