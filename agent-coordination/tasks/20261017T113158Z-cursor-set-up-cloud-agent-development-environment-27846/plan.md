# Plan: Set up Cloud Agent development environment

| Field | Value |
| --- | --- |
| Task ID | `20261017T113158Z-cursor-set-up-cloud-agent-development-environment-27846` |
| Created by | cursor |
| Scope | `.cursor,AGENTS.md,scripts` |
| Created | 2026-10-17T11:31:58Z |
| Initial status | in-progress |

## Goal

A Cloud Agent can boot this repository, run the shared taskboard, and rely on push-on-commit without replacing Cursor's git hooks.

## Plan

1. Treat the taskboard CLI as the product. There is no application server, package manifest, or Dockerfile.
2. Keep `install` to a syntax check of the bash entry points. They are dependency-free (bash, sed, find, git).
3. On boot, `start` enables `.githooks/post-commit` without setting `core.hooksPath` when Cursor already owns that path.
4. Document that behavior in `AGENTS.md`.
5. Prove the taskboard context, checkpoint, render, and edit guard, then snapshot, draft-build, and propose the environment.

## Files and impact

- `AGENTS.md`: project notes for how to run the taskboard on a Cloud Agent.
- `scripts/agent-taskboard.sh`: unchanged. `setup` still sets `core.hooksPath=.githooks` for a normal clone. Cloud boot must not call it, because this VM's `core.hooksPath` is Cursor's dispatcher and git will not run `.git/hooks/post-commit` while that is set.
- Environment `install` / `start`: proposed to the dashboard, not committed, so they do not override a future dashboard save.

## Validation

- `bash -n` on the four entry points, twice.
- `start` twice: post-commit forwarder exists and is not duplicated.
- Taskboard: `context`, `checkpoint`, `current`, `render`.
- Hook: `context` prints the board; `guard` exits 0 for the active agent and 2 for an agent with no task.
- A commit on the feature branch reaches `ok` in `.git/autopush.status`.

## Handoff checkpoint

- Last completed: Discovery. No app server. Toolchain is bash and git.
- Current state: Plan written. Environment scripts not applied yet.
- Next action: Update AGENTS.md and validate install/start.
- Blockers: None.
- Validation state: Not started.

## Plan changes and decisions

- 2026-10-17T11:31:58Z — Task created.
- 2026-10-17T11:40:00Z — No package install. Cloud `start` writes a post-commit forwarder into the existing hooks directory instead of calling `setup`.
