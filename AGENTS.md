# vast-real-time

Hackathon project bootstrapped with `hackathon-init`. Several coding agents
(Claude Code, Cursor, Codex, and any other agent that reads `AGENTS.md`) and
people work in this repository at the same time. They coordinate through one
shared taskboard, and every commit is pushed to GitHub.

## Project notes

<!-- Fill in as the project takes shape: stack, how to run it, demo script. -->

## Shared taskboard (mandatory)

The source of truth for work in progress is
[`agent-coordination/taskboard.md`](agent-coordination/taskboard.md). It is
generated; never edit it by hand. Each task has a `plan.md` and an append-only
`activity.md` under `agent-coordination/tasks/<task-id>/`, so any agent can
pick up where another stopped.

Run every command with **your own agent name**: `claude-code`, `cursor`,
`codex`, `gemini`, `copilot`, `opencode`, `amp`, `aider`, ... (lowercase
letters, numbers, hyphens). Use the same name for the whole session.

**Before inspecting or changing files for a request:**

1. See what is going on:

   ```bash
   ./scripts/agent-taskboard.sh context --agent <your-name>
   ```

2. If an unfinished task already covers the request, take over that **same
   task**, even if another agent created it. The command prints its plan, last
   checkpoint and next action. Do not create a duplicate task.

   ```bash
   ./scripts/agent-taskboard.sh take-over --agent <your-name> --task "<task-id>"
   ```

3. Only when no task covers the work, register a new one. This is how the team
   sees that you started building something.

   ```bash
   ./scripts/agent-taskboard.sh start --agent <your-name> \
     --title "<concise task title>" --scope "<relative paths>"
   ```

4. Fill in the generated `plan.md` before making task-scoped changes.

**While working**, checkpoint before a long or risky step, after each
milestone, and whenever you are blocked (`--status blocked`):

```bash
./scripts/agent-taskboard.sh checkpoint --agent <your-name> --task "<task-id>" \
  --summary "<what is now true>" --next "<single next action>"
```

**When done**, after validating, close the task. Use `handoff` instead to
release unfinished work for another agent.

```bash
./scripts/agent-taskboard.sh complete --agent <your-name> --task "<task-id>" \
  --summary "<what changed and how it was validated>"
```

End every response with exactly one line in this form. Agents with hooks
(Claude Code, Codex, Cursor) record it on the taskboard and use it as the
commit message automatically:

```text
Taskboard checkpoint: <what changed, key result, or blocker> | Next: <single next action>
```

Never overwrite another task's plan or rewrite its activity log. Taking over
extends the same record; that is expected whenever another agent stops.

## Git: every commit is pushed

- `origin` is the GitHub repository. `.githooks/post-commit` pushes each commit
  in the background, so the remote always mirrors your work.
- Claude Code, Codex and Cursor commit automatically at the end of each turn.
  Any other agent commits after each meaningful step, with a message that
  starts with its agent name: `git commit -m "<your-name>: <what changed>"`.
- Never force-push or rewrite pushed history. If the taskboard context reports
  a failed push, run `git pull --rebase && git push`. If
  `agent-coordination/taskboard.md` conflicts, keep either side and run
  `./scripts/agent-taskboard.sh render` to regenerate it.
- After a fresh clone, run `./scripts/agent-taskboard.sh setup` once to enable
  push-on-commit.
- Per-clone switches: `git config taskboard.autocommit false`,
  `git config taskboard.autopush false`, and `git config taskboard.enforce false`
  (stops hooks from blocking edits when no task is registered).

## Project skills

Installed in `.agents/skills/` (Codex and other AGENTS.md agents), `.claude/skills/`
and `.cursor/skills/`. When a task matches a skill, read its `SKILL.md` first.

- `gsap-scrolltrigger` (`.agents/skills/gsap-scrolltrigger/SKILL.md`): Comprehensive skill for GSAP (GreenSock Animation Platform) and ScrollTrigger plugin. Use this skill when creating web animations, scroll-driven experiences,...
- `react-three-fiber` (`.agents/skills/react-three-fiber/SKILL.md`): Build declarative 3D scenes with React Three Fiber (R3F) - a React renderer for Three.js. Use when building interactive 3D experiences in React applications ...
- `skill-creator` (`.agents/skills/skill-creator/SKILL.md`): Guide for creating effective skills. This skill should be used when users want to create a new skill (or update an existing skill) that extends Claude's capa...
- `substance-3d-texturing` (`.agents/skills/substance-3d-texturing/SKILL.md`): Comprehensive skill for Adobe Substance 3D Painter texturing and material creation workflow. Use this skill when creating PBR materials, exporting textures f...
- `threejs-webgl` (`.agents/skills/threejs-webgl/SKILL.md`): Comprehensive skill for Three.js 3D web development. Use this skill when building interactive 3D scenes, WebGL/WebGPU applications, product configurators, 3D...
- `web3d-integration-patterns` (`.agents/skills/web3d-integration-patterns/SKILL.md`): Meta-skill for combining Three.js, GSAP ScrollTrigger, React Three Fiber, Motion, and React Spring for complex 3D web experiences. Use when building applicat...
- `hackathon-prep` (`.agents/skills/hackathon-prep/SKILL.md`): Structured hackathon preparation workflow for researching, ideating, and building winning projects. Use when the user mentions a specific hackathon by name, ...
- `mcp-builder` (`.agents/skills/mcp-builder/SKILL.md`): Guide for creating high-quality MCP (Model Context Protocol) servers that enable LLMs to interact with external services through well-designed tools. Use whe...
- `remotion` (`.agents/skills/remotion/SKILL.md`): Best practices for Remotion - Video creation in React
- `ui-ux-pro-max` (`.agents/skills/ui-ux-pro-max/SKILL.md`): UI/UX Pro Max design intelligence, installed with the uipro CLI
