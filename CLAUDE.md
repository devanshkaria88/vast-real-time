@AGENTS.md

## Claude Code specifics

- Your agent name on the taskboard is `claude-code`.
- `.claude/settings.json` wires three hooks to `scripts/taskboard-hook.sh`:
  - **UserPromptSubmit** adds the taskboard context (your active task,
    unfinished tasks, recent activity) to every prompt.
  - **PreToolUse** blocks `Edit`/`Write` inside this repo until you have an
    active task. When it fires, run `start` or `take-over`, then retry.
  - **Stop** records your final `Taskboard checkpoint:` line on your active task
    and commits the turn; the post-commit hook pushes it.
- The Stop hook only writes while you are the task's current executor, so it
  can never overwrite a task that Cursor or Codex has taken over.
