#!/usr/bin/env bash
# Cursor afterAgentResponse hook: checkpoint Cursor's active task and commit the turn.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/scripts/taskboard-hook.sh" cursor turn
