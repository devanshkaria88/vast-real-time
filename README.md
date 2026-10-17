# REAL-TIME VIDEO AGENTS HACKATHON

# vast-real-time

Hackathon project, bootstrapped with `hackathon-init`.

## Working on this repo with coding agents

Claude Code, Cursor, Codex and any agent that reads [`AGENTS.md`](AGENTS.md)
share one taskboard: [`agent-coordination/taskboard.md`](agent-coordination/taskboard.md).
Each agent registers what it is building, checkpoints as it goes, and can take
over a task another agent left unfinished.

Every turn starts by pulling from GitHub, in case someone else pushed.
Every commit is still pushed automatically. After cloning, enable that once:

```bash
./scripts/agent-taskboard.sh setup
```
