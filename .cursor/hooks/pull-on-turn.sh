#!/usr/bin/env bash
# Cursor beforeSubmitPrompt: pull origin before the turn reads or edits the repo.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/scripts/taskboard-hook.sh" cursor pull
