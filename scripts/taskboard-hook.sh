#!/usr/bin/env bash
# Hook adapter shared by Claude Code, Codex and Cursor. Each agent's hook
# config calls it with its agent name and the event:
#
#   taskboard-hook.sh <agent> pull      turn start: git pull --rebase --autostash
#   taskboard-hook.sh <agent> context   prompt submit: pull, then print the taskboard
#   taskboard-hook.sh <agent> guard     before a file edit: block until a task is registered
#   taskboard-hook.sh <agent> turn      end of turn: checkpoint the active task, then commit
#
# The hook payload (JSON) arrives on stdin. A hook must never break the agent,
# so every unexpected failure exits 0 quietly. Only `guard` may exit 2.
set -uo pipefail

AGENT="${1:-}"
EVENT="${2:-}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BOARD="$ROOT/scripts/agent-taskboard.sh"
PAYLOAD=$(cat 2>/dev/null || true)
[[ -n "$AGENT" && -x "$BOARD" ]] || exit 0

json() { command -v jq >/dev/null 2>&1 && printf '%s' "$PAYLOAD" | jq -r "$1" 2>/dev/null; }

guard() {
  local path
  # Edits outside this repository (agent memory, ~/.config, ...) are not project work.
  path=$(json '.tool_input.file_path // .tool_input.notebook_path // .tool_input.path // empty')
  if [[ -n "$path" && "$path" == /* ]]; then
    [[ "$path" == "$ROOT"/* || "$path" == "$(cd "$ROOT" && pwd -P)"/* ]] || exit 0
  fi
  "$BOARD" require --agent "$AGENT"
  [[ $? -eq 2 ]] && exit 2
  exit 0
}

last_response() {
  local text transcript
  # Codex and Claude Code send last_assistant_message; Cursor sends text.
  text=$(json '.last_assistant_message // .text // empty')
  if [[ -z "$text" ]]; then
    transcript=$(json '.transcript_path // empty')
    [[ -n "$transcript" && -f "$transcript" ]] && text=$(jq -rs '
      [ .[] | select(.message.role? == "assistant") | .message.content
        | if type == "array" then map(select(.type == "text") | .text) | join("\n") else . end
        | select(type == "string" and length > 0) ] | last // empty' "$transcript" 2>/dev/null)
  fi
  printf '%s' "$text"
}

commit_turn() {
  local text="$1" gitdir marker summary
  cd "$ROOT" || return 0
  git rev-parse --git-dir >/dev/null 2>&1 || return 0
  [[ "$(git config --bool taskboard.autocommit 2>/dev/null)" != "false" ]] || return 0
  gitdir=$(git rev-parse --absolute-git-dir) || return 0
  # Never commit in the middle of a merge, rebase, cherry-pick or revert.
  for marker in MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD rebase-merge rebase-apply; do
    [[ -e "$gitdir/$marker" ]] && return 0
  done
  git add -A >/dev/null 2>&1 || return 0
  git diff --cached --quiet 2>/dev/null && return 0
  summary=$(printf '%s\n' "$text" | sed -n 's/^[[:space:]]*\**Taskboard checkpoint:\**[[:space:]]*//p' | tail -n 1)
  summary="${summary%% | Next: *}"
  summary=$(printf '%s' "$summary" | tr '\r\n' '  ' | sed 's/[[:space:]][[:space:]]*/ /g; s/^ //; s/ $//')
  [[ -n "$summary" ]] || summary="turn @ $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  [[ ${#summary} -le 72 ]] || summary="${summary:0:69}..."
  # The post-commit hook pushes this commit to GitHub.
  git commit -q -m "$AGENT: $summary" >/dev/null 2>&1 || true
}

file_mtime() {
  stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null || echo 0
}

# Pull origin at turn start. Never leave a rebase in progress, and never
# fail the agent hook. Push-on-commit stays in .githooks/post-commit.
pull_remote() {
  local branch gitdir state lock before after out rc reason now mtime prev age
  cd "$ROOT" || return 0
  [[ "$(git config --bool taskboard.autopull 2>/dev/null)" != "false" ]] || return 0
  git remote get-url origin >/dev/null 2>&1 || return 0
  branch=$(git symbolic-ref --short -q HEAD) || return 0
  gitdir=$(git rev-parse --absolute-git-dir) || return 0
  state="$gitdir/autopull.status"
  lock="$gitdir/autopull.lock"

  for marker in MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD rebase-merge rebase-apply; do
    if [[ -e "$gitdir/$marker" ]]; then
      printf 'skipped %s: rebase or merge already in progress\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$state"
      return 0
    fi
  done
  if [[ -d "$gitdir/autopush.lock" ]]; then
    printf 'skipped %s: push still in flight\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$state"
    return 0
  fi

  if [[ -f "$state" ]]; then
    prev=$(cat "$state" 2>/dev/null || true)
    now=$(date +%s)
    mtime=$(file_mtime "$state")
    age=$((now - mtime))
    case "$prev" in
      ok*|updated*)
        [[ "$age" -lt 8 ]] && return 0
        ;;
    esac
  fi

  if [[ -d "$lock" ]]; then
    now=$(date +%s)
    mtime=$(file_mtime "$lock")
    age=$((now - mtime))
    [[ "$age" -gt 120 ]] && rmdir "$lock" 2>/dev/null || true
  fi
  mkdir "$lock" 2>/dev/null || return 0

  before=$(git rev-parse HEAD 2>/dev/null || true)
  export GIT_TERMINAL_PROMPT=0
  if command -v perl >/dev/null 2>&1; then
    out=$(perl -e 'alarm shift; exec @ARGV' 25 git pull --rebase --autostash origin "$branch" 2>&1) || rc=$?
  else
    out=$(git pull --rebase --autostash origin "$branch" 2>&1) || rc=$?
  fi
  rc=${rc:-0}

  if [[ -d "$gitdir/rebase-merge" || -d "$gitdir/rebase-apply" ]]; then
    git rebase --abort >/dev/null 2>&1 || true
    printf 'failed %s: pull hit a conflict and the rebase was aborted\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$state"
    rmdir "$lock" 2>/dev/null || true
    return 0
  fi

  if [[ "$rc" -ne 0 ]]; then
    reason=$(printf '%s\n' "$out" | grep -E '^[Ee]rror:|^fatal:|CONFLICT|Timed out' | head -n 1 || true)
    [[ -n "$reason" ]] || reason=$(printf '%s\n' "$out" | tail -n 1)
    printf 'failed %s: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${reason:-pull failed}" > "$state"
    rmdir "$lock" 2>/dev/null || true
    return 0
  fi

  after=$(git rev-parse HEAD 2>/dev/null || true)
  if [[ -n "$before" && "$before" != "$after" ]]; then
    printf 'updated %s %s..%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${before:0:7}" "${after:0:7}" > "$state"
  else
    printf 'ok %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${after:0:7}" > "$state"
  fi
  rmdir "$lock" 2>/dev/null || true
  return 0
}

case "$EVENT" in
  pull)
    pull_remote
    exit 0
    ;;
  context)
    pull_remote
    "$BOARD" context --agent "$AGENT" 2>/dev/null
    exit 0
    ;;
  guard)
    guard
    ;;
  turn)
    text=$(last_response)
    [[ -n "$text" ]] && printf '%s' "$text" | "$BOARD" auto-log --agent "$AGENT" >/dev/null 2>&1
    commit_turn "$text"
    exit 0
    ;;
esac
exit 0
