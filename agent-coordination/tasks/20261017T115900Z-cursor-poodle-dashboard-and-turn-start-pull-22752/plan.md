# Plan: Poodle dashboard and turn-start pull

| Field | Value |
| --- | --- |
| Task ID | `20261017T115900Z-cursor-poodle-dashboard-and-turn-start-pull-22752` |
| Created by | cursor |
| Scope | `scripts/taskboard-hook.sh,.cursor/hooks.json,.claude/settings.json,.codex/hooks.json,AGENTS.md,CLAUDE.md,README.md,agent-coordination/README.md,docs/IDEA.md,poodle` |
| Created | 2026-10-17T11:59:00Z |
| Initial status | planned |

## Goal

Two outcomes:

1. Every agent turn starts with a pull from `origin`, so another person's push is in the checkout before work starts. Push-on-commit stays as it is.
2. The idea in `docs/IDEA.md` is named Poodle. The claims desk at `poodle/index.html` is clear at a glance, and a cute poodle sits on top of it and moves.

Success: a turn-start hook pulls and exits cleanly on a dirty tree; a conflict aborts the rebase instead of leaving one in progress; the desk opens in a browser and each claim changes the decision, the clips, and the poodle's mood.

## Plan

1. Pull `origin` now (done: already up to date).
2. Add `pull` to `scripts/taskboard-hook.sh` and call it from Claude/Codex prompt hooks and a Cursor `beforeSubmitPrompt` hook. Leave `.githooks/post-commit` alone.
3. Rename Claim Witness to Poodle in `docs/IDEA.md` and point at the desk.
4. Build `poodle/index.html` from the design-system result below.
5. Run the pull hook against this dirty checkout, then open the desk and click through the claims.

## Design decisions

ui-ux-pro-max, first pass (`insurance claims operations dashboard`): Trust & Authority, palette primary `#0369A1`, secondary `#0EA5E9`, CTA `#22C55E`, background `#F0F9FF`, text `#0C4A6E`, type Fira Code + Fira Sans. The pattern it returned was a marketing hero. That does not fit a desk.

Second pass (`dashboard saas analytics` plus the executive-dashboard style): at-a-glance KPIs, one open claim, traffic-light outcomes, whitespace. Data-dense widgets were the other recommendation. The request is a clear desk, so the executive layout wins and the insurance palette stays.

- Fira Sans for the name, the decision, and labels. Fira Code only for claim ids and timestamps, so the decision stays easy to read.
- No purple gradients, no emoji icons, no chat thread.
- The poodle is the one continuous animation, and it also signals mood. `prefers-reduced-motion` freezes it. The mood is always written in text as well.
- Four KPIs only: open claims, needs a person, ready to settle, fraud flags.

## Files and impact

- `scripts/taskboard-hook.sh` — pull at the start of the context hook, plus a `pull` event.
- `scripts/agent-taskboard.sh` — context prints a failed or just-updated pull. Not in the original scope string; needed so agents see the result.
- `.cursor/hooks.json`, `.cursor/hooks/pull-on-turn.sh` — Cursor turn start.
- `.claude/settings.json`, `.codex/hooks.json` — longer timeout so a pull can finish.
- `AGENTS.md`, `CLAUDE.md`, `README.md`, `agent-coordination/README.md`, `.cursor/rules/agent-taskboard.mdc` — document pull-on-turn. Push-on-commit unchanged.
- `docs/IDEA.md` — product name Poodle.
- `poodle/index.html` — the desk.

## Validation

- `scripts/taskboard-hook.sh cursor pull` exits 0 with local edits present, writes `ok` or `updated`, and does not start a rebase.
- `.githooks/post-commit` still only pushes.
- Browser: load the desk, select each claim, confirm the sentence, clips, and mood line change. Check a narrow viewport and a wide one.

## Handoff checkpoint

- Last completed: Remote is already up to date. Design system chosen.
- Current state: Plan written. Hook and desk not built yet.
- Next action: Add the pull hook, then build the desk.
- Blockers: None known.
- Validation state: Not started.

## Plan changes and decisions

- 2026-10-17T11:59:00Z — Task created.
- 2026-10-17T12:00:00Z — Plan filled. Product name is Poodle, the Claim Witness write-up. Lone Job and Return Stop stay parked in their own task.
