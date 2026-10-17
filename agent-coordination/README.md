# Agent coordination

The shared record of work in this repo. Claude Code, Cursor, Codex and any
agent that reads `AGENTS.md` post their work here, so when one agent stops
(usage limit, crash, or you switch tools) another continues the same task
without losing the plan, latest checkpoint, or history.

```text
find or create task → plan → checkpoint work → hand off or take over → validate → complete
```

[`taskboard.md`](taskboard.md) is the generated overview. Each task under
`tasks/<task-id>/` owns:

- `task.md` — machine-readable record (status, current executor, next action).
- `plan.md` — the living plan and any later decisions.
- `activity.md` — append-only, timestamped checkpoints: which agent did what,
  and the concrete next action.

`active/` holds each agent's current task on this machine and is not committed.

## Commands

```bash
./scripts/agent-taskboard.sh context    --agent codex
./scripts/agent-taskboard.sh start      --agent codex --title "Add login" --scope "app/auth"
./scripts/agent-taskboard.sh checkpoint --agent codex --task "<id>" --summary "API done" --next "Wire the form"
./scripts/agent-taskboard.sh take-over  --agent cursor --task "<id>" --reason "Codex hit its usage limit"
./scripts/agent-taskboard.sh handoff    --agent cursor --task "<id>" --summary "Form wired" --next "Add tests"
./scripts/agent-taskboard.sh complete   --agent cursor --task "<id>" --summary "Login works; tests pass"
./scripts/agent-taskboard.sh render     # rebuild taskboard.md (e.g. after a merge conflict)
```

## Agent integrations

| Agent | Instructions | Hooks |
| --- | --- | --- |
| Claude Code | `CLAUDE.md` (imports `AGENTS.md`) | `.claude/settings.json`: context on prompt, edit guard, checkpoint + commit on stop |
| Codex | `AGENTS.md` | `.codex/hooks.json`: same three hooks (loads once the project is trusted and the hooks are approved) |
| Cursor | `.cursor/rules/agent-taskboard.mdc`, `AGENTS.md` | `.cursor/hooks.json`: checkpoint + commit after each response |
| Any other agent | `AGENTS.md` | none; it calls the helper and commits explicitly |

All hooks go through `scripts/taskboard-hook.sh`. A hook only writes to a task
while its agent is the task's current executor, so a stale hook cannot
overwrite work another agent has taken over. Every commit is pushed by
`.githooks/post-commit`.
