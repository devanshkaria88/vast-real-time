#!/usr/bin/env bash
# Shared agent taskboard. Claude Code, Cursor, Codex and any agent that follows
# AGENTS.md record their work here. A task belongs to the work, not to one
# agent: when an agent stops (usage limit, crash, switch), another agent takes
# over the same task from its plan and activity log.
#
# Dependency free on purpose (bash 3.2+, sed, find) so every agent can run it.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COORD_DIR="$ROOT_DIR/agent-coordination"
TASKS_DIR="$COORD_DIR/tasks"
ACTIVE_DIR="$COORD_DIR/active"
LOCK_DIR="$COORD_DIR/.write-lock"
SELF="./scripts/agent-taskboard.sh"

usage() {
  cat <<'EOF'
Usage:
  agent-taskboard.sh context    --agent <agent>
  agent-taskboard.sh start      --agent <agent> --title <title> --scope <paths>
  agent-taskboard.sh checkpoint --agent <agent> --task <id> --summary <text> --next <action> [--status <status>]
  agent-taskboard.sh handoff    --agent <agent> --task <id> --summary <text> --next <action>
  agent-taskboard.sh take-over  --agent <agent> --task <id> [--reason <text>]
  agent-taskboard.sh complete   --agent <agent> --task <id> --summary <text>
  agent-taskboard.sh log        --agent <agent> --task <id> --status <status> --summary <text> [--next <action>]
  agent-taskboard.sh current    --agent <agent>
  agent-taskboard.sh require    --agent <agent>     (exit 2 when the agent has no active task)
  agent-taskboard.sh auto-log   --agent <agent> [--status <status>] < response.txt
  agent-taskboard.sh render
  agent-taskboard.sh setup                          (enable push-on-commit in a fresh clone)

Statuses: planned, in-progress, ready-for-handoff, blocked, completed.
Agent names: lowercase letters, numbers and hyphens (claude-code, cursor, codex, gemini, ...).
EOF
}

die() { echo "agent-taskboard: $*" >&2; exit 1; }
now() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
ensure_layout() { mkdir -p "$TASKS_DIR" "$ACTIVE_DIR"; }

lock() {
  local attempts=0 reclaimed=0
  while ! mkdir "$LOCK_DIR" 2>/dev/null; do
    attempts=$((attempts + 1))
    if [[ $attempts -ge 200 ]]; then
      # A writer that was killed mid-update leaves the lock behind; reclaim it once.
      if [[ $reclaimed -eq 0 && -n "$(find "$LOCK_DIR" -maxdepth 0 -mmin +1 2>/dev/null)" ]]; then
        rmdir "$LOCK_DIR" 2>/dev/null || true
        reclaimed=1; attempts=0; continue
      fi
      die "timed out waiting for the taskboard lock ($LOCK_DIR)"
    fi
    sleep 0.05
  done
  trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT
}

unlock() { rmdir "$LOCK_DIR" 2>/dev/null || true; trap - EXIT; }

atom() {
  local label="$1" value="$2"
  [[ -n "$value" && "$value" != *$'\n'* && "$value" != *$'\r'* ]] || die "$label must be a single non-empty line"
}

agent_name() {
  atom agent "$1"
  [[ "$1" =~ ^[a-z0-9][a-z0-9-]*$ ]] || die "agent must use lowercase letters, numbers, or hyphens"
}

status() {
  case "$1" in
    planned|in-progress|ready-for-handoff|blocked|completed) ;;
    *) die "unknown status '$1'" ;;
  esac
}

slug() {
  local value
  value=$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-')
  value=${value#-}; value=${value%-}
  printf '%s' "${value:0:48}"
}

oneline() {
  local value="$1"
  value=$(printf '%s' "$value" | tr '\r\n' ' ' | tr '|' '/')
  value=$(printf '%s' "$value" | sed 's/[[:space:]][[:space:]]*/ /g; s/^ //; s/ $//')
  printf '%s' "${value:0:180}"
}

task_dir() { printf '%s' "$TASKS_DIR/$1"; }
field() { sed -n "s/^$2: //p" "$(task_dir "$1")/task.md" | head -n 1; }

write_record() {
  local task="$1" title="$2" created_by="$3" task_status="$4" scope="$5" created="$6" updated="$7" executor="$8" last_agent="$9" last_summary="${10}" next_action="${11}"
  cat > "$(task_dir "$task")/task.md" <<EOF
# Task record

id: $task
title: $title
created_by: $created_by
status: $task_status
scope: $scope
created_at: $created
updated_at: $updated
current_executor: $executor
last_agent: $last_agent
last_summary: $last_summary
next_action: $next_action
plan: plan.md
activity: activity.md
EOF
}

append_event() {
  local task="$1" agent="$2" task_status="$3" summary="$4" next_action="$5" event_time="$6"
  cat >> "$(task_dir "$task")/activity.md" <<EOF

## $event_time · $agent · $task_status

$summary

**Next action:** $next_action
EOF
}

active() {
  local file="$ACTIVE_DIR/$1"
  [[ -f "$file" ]] || return 1
  tr -d '\r\n' < "$file"
}

set_active() { printf '%s\n' "$2" > "$ACTIVE_DIR/$1"; }

clear_active_for_task() {
  local task="$1" file
  for file in "$ACTIVE_DIR"/*; do
    [[ -f "$file" ]] || continue
    [[ "$(tr -d '\r\n' < "$file")" == "$task" ]] && rm -f "$file"
  done
  return 0
}

require_task() { [[ -d "$(task_dir "$1")" ]] || die "task '$1' does not exist"; }

require_executor() {
  local executor
  executor=$(field "$1" current_executor)
  [[ "$executor" == "$2" ]] || die "task '$1' is assigned to '$executor'; use take-over to continue it"
}

# Prints "<updated_at>\t<task-id>" for every task, newest first.
tasks_by_update() {
  local path task
  [[ -d "$TASKS_DIR" ]] || return 0
  while IFS= read -r path; do
    [[ -f "$path/task.md" ]] || continue
    task=$(basename "$path")
    printf '%s\t%s\n' "$(field "$task" updated_at)" "$task"
  done < <(find "$TASKS_DIR" -mindepth 1 -maxdepth 1 -type d -print) | LC_ALL=C sort -r
}

render() {
  local temp
  temp=$(mktemp "$COORD_DIR/.taskboard.XXXXXX")
  {
    cat <<'EOF'
# Agent Taskboard

Generated by `scripts/agent-taskboard.sh`; do not edit it directly.
A task belongs to the work, not to one agent. To continue after another agent
stops, read its plan and activity log, then take over the **same task**.

## Tasks

| Status | Task | Created by | Current executor | Last agent | Scope | Last activity | Next action | Plan | Log |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
EOF
    local updated task found=0
    while IFS=$'\t' read -r updated task; do
      [[ -n "$task" ]] || continue
      printf '| %s | %s | %s | %s | %s | `%s` | %s | %s | [plan](tasks/%s/plan.md) | [activity](tasks/%s/activity.md) |\n' \
        "$(oneline "$(field "$task" status)")" "$(oneline "$(field "$task" title)")" \
        "$(oneline "$(field "$task" created_by)")" "$(oneline "$(field "$task" current_executor)")" \
        "$(oneline "$(field "$task" last_agent)")" "$(oneline "$(field "$task" scope)")" \
        "$(oneline "$updated")" "$(oneline "$(field "$task" next_action)")" "$task" "$task"
      found=1
    done < <(tasks_by_update)
    [[ $found -eq 1 ]] || echo '| — | No tasks registered yet | — | — | — | — | — | — | — | — |'
    cat <<'EOF'

## Failover rule

An agent change is a continuation, not a new task. Preserve the plan and full
activity history; update the same task's checkpoint and next action.
EOF
  } > "$temp"
  mv "$temp" "$COORD_DIR/taskboard.md"
}

start() {
  local agent="" title="" scope=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --agent) agent="${2:-}"; shift 2 ;;
      --title) title="${2:-}"; shift 2 ;;
      --scope) scope="${2:-}"; shift 2 ;;
      *) die "unknown start option '$1'" ;;
    esac
  done
  agent_name "$agent"; atom title "$title"; atom scope "$scope"
  ensure_layout; lock
  local event_time task task_slug dir next_action
  event_time=$(now); task_slug=$(slug "$title")
  [[ -n "$task_slug" ]] || die "title must contain letters or numbers"
  task="$(date -u +%Y%m%dT%H%M%SZ)-$agent-$task_slug-$RANDOM"; dir="$(task_dir "$task")"
  next_action="Complete the linked plan before changing task-scoped files."
  mkdir -p "$dir"
  write_record "$task" "$title" "$agent" "planned" "$scope" "$event_time" "$event_time" "$agent" "$agent" "Task created and awaiting a completed plan." "$next_action"
  cat > "$dir/plan.md" <<EOF
# Plan: $title

| Field | Value |
| --- | --- |
| Task ID | \`$task\` |
| Created by | $agent |
| Scope | \`$scope\` |
| Created | $event_time |
| Initial status | planned |

## Goal

Describe the user outcome and success criteria.

## Plan

1. Identify relevant files, dependencies, and constraints.
2. Make the smallest scoped change that fulfils the task.
3. Validate the result with appropriate checks.

## Files and impact

- Planned files: _to be filled before implementation_
- Expected impact: _to be filled before implementation_

## Validation

- Checks to run: _to be filled before implementation_

## Handoff checkpoint

- Last completed: Task registered; implementation has not started.
- Current state: Planning.
- Next action: Complete this plan, then log a checkpoint before editing.
- Blockers: None known.
- Validation state: Not started.

## Plan changes and decisions

- $event_time — Task created. Fill this plan before modifying scoped files.
EOF
  cat > "$dir/activity.md" <<EOF
# Activity: $title

## $event_time · $agent · planned

Task registered with an agent-neutral plan. Another agent may take it over
after reading this plan and activity history.

**Next action:** $next_action
EOF
  set_active "$agent" "$task"; render; unlock
  printf 'Task started: %s\nPlan: agent-coordination/tasks/%s/plan.md\n' "$task" "$task"
}

update() {
  local agent="" task="" task_status="in-progress" summary="" next_action="" completing=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --agent) agent="${2:-}"; shift 2 ;;
      --task) task="${2:-}"; shift 2 ;;
      --status) task_status="${2:-}"; shift 2 ;;
      --summary) summary="${2:-}"; shift 2 ;;
      --next) next_action="${2:-}"; shift 2 ;;
      --complete) completing=1; task_status="completed"; shift ;;
      *) die "unknown update option '$1'" ;;
    esac
  done
  agent_name "$agent"; atom task "$task"; atom summary "$summary"; status "$task_status"
  require_task "$task"
  ensure_layout; lock; require_executor "$task" "$agent"
  local event_time executor
  event_time=$(now); executor=$(field "$task" current_executor)
  if [[ $completing -eq 1 || "$task_status" == "completed" ]]; then
    task_status="completed"; next_action="No further action; task completed."; executor="unassigned"
    clear_active_for_task "$task"
  elif [[ -z "$next_action" ]]; then
    next_action=$(field "$task" next_action)
  fi
  append_event "$task" "$agent" "$task_status" "$summary" "$next_action" "$event_time"
  write_record "$task" "$(field "$task" title)" "$(field "$task" created_by)" "$task_status" "$(field "$task" scope)" \
    "$(field "$task" created_at)" "$event_time" "$executor" "$agent" "$(oneline "$summary")" "$next_action"
  render; unlock
}

checkpoint() {
  local args=() task_status="in-progress" next_action=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --status) task_status="${2:-}"; shift 2 ;;
      --next) next_action="${2:-}"; shift 2 ;;
      *) args+=("$1" "${2:-}"); shift 2 ;;
    esac
  done
  atom next_action "$next_action"
  [[ "$task_status" != "completed" && "$task_status" != "ready-for-handoff" ]] || die "checkpoint status must be planned, in-progress, or blocked"
  update ${args[@]+"${args[@]}"} --status "$task_status" --next "$next_action"
}

handoff() {
  local agent="" task="" summary="" next_action=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --agent) agent="${2:-}"; shift 2 ;;
      --task) task="${2:-}"; shift 2 ;;
      --summary) summary="${2:-}"; shift 2 ;;
      --next) next_action="${2:-}"; shift 2 ;;
      *) die "unknown handoff option '$1'" ;;
    esac
  done
  agent_name "$agent"; atom task "$task"; atom summary "$summary"; atom next_action "$next_action"
  require_task "$task"
  ensure_layout; lock; require_executor "$task" "$agent"
  local event_time
  event_time=$(now)
  append_event "$task" "$agent" "ready-for-handoff" "$summary" "$next_action" "$event_time"
  write_record "$task" "$(field "$task" title)" "$(field "$task" created_by)" "ready-for-handoff" "$(field "$task" scope)" \
    "$(field "$task" created_at)" "$event_time" "unassigned" "$agent" "$(oneline "$summary")" "$next_action"
  clear_active_for_task "$task"; render; unlock
}

take_over() {
  local agent="" task="" reason="Agent continuation requested."
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --agent) agent="${2:-}"; shift 2 ;;
      --task) task="${2:-}"; shift 2 ;;
      --reason) reason="${2:-}"; shift 2 ;;
      *) die "unknown take-over option '$1'" ;;
    esac
  done
  agent_name "$agent"; atom task "$task"; atom reason "$reason"
  require_task "$task"
  ensure_layout; lock
  local event_time prior_executor last_agent last_summary next_action
  [[ "$(field "$task" status)" != "completed" ]] || { unlock; die "task '$task' is completed; start a follow-up task for new work"; }
  event_time=$(now); prior_executor=$(field "$task" current_executor)
  last_agent=$(field "$task" last_agent); last_summary=$(field "$task" last_summary); next_action=$(field "$task" next_action)
  clear_active_for_task "$task"; set_active "$agent" "$task"
  append_event "$task" "$agent" "in-progress" "Takeover from $prior_executor. $reason Previous checkpoint by $last_agent: $last_summary" "$next_action" "$event_time"
  write_record "$task" "$(field "$task" title)" "$(field "$task" created_by)" "in-progress" "$(field "$task" scope)" \
    "$(field "$task" created_at)" "$event_time" "$agent" "$agent" "Taken over from $prior_executor. $reason" "$next_action"
  render; unlock; handoff_context "$task"
}

# Reads the last "Taskboard checkpoint: <summary> | Next: <action>" line of a response.
extract_checkpoint() {
  local text="$1" line
  line=$(printf '%s\n' "$text" | sed -n 's/^[[:space:]]*\**Taskboard checkpoint:\**[[:space:]]*//p' | tail -n 1)
  AUTO_SUMMARY=""; AUTO_NEXT=""
  if [[ -n "$line" && "$line" == *" | Next: "* ]]; then
    AUTO_SUMMARY=$(oneline "${line%% | Next: *}"); AUTO_NEXT=$(oneline "${line#* | Next: }")
  elif [[ -n "$line" ]]; then
    AUTO_SUMMARY=$(oneline "$line")
  else
    AUTO_SUMMARY=$(oneline "$(printf '%s\n' "$text" | sed '/^[[:space:]]*$/d' | head -n 3)")
  fi
}

auto_log() {
  local agent="" task_status="in-progress"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --agent) agent="${2:-}"; shift 2 ;;
      --status) task_status="${2:-}"; shift 2 ;;
      *) die "unknown auto-log option '$1'" ;;
    esac
  done
  agent_name "$agent"; status "$task_status"
  local task message
  task=$(active "$agent" || true)
  [[ -n "$task" && -d "$(task_dir "$task")" ]] || exit 0
  # A stale hook must never write over a task another agent has taken over.
  [[ "$(field "$task" current_executor)" == "$agent" && "$(field "$task" status)" != "completed" ]] || exit 0
  message=$(cat); extract_checkpoint "$message"
  [[ -n "$AUTO_SUMMARY" ]] || AUTO_SUMMARY="Agent response completed; read the plan and activity log for details."
  if [[ -n "$AUTO_NEXT" ]]; then
    update --agent "$agent" --task "$task" --status "$task_status" --summary "$AUTO_SUMMARY" --next "$AUTO_NEXT"
  else
    update --agent "$agent" --task "$task" --status "$task_status" --summary "$AUTO_SUMMARY"
  fi
}

handoff_context() {
  local task="$1"
  echo "=== Task handoff context ==="
  echo "Task: $task"
  echo "Title: $(field "$task" title)"
  echo "Created by: $(field "$task" created_by)"
  echo "Current executor: $(field "$task" current_executor)"
  echo "Last agent: $(field "$task" last_agent)"
  echo "Status: $(field "$task" status)"
  echo "Scope: $(field "$task" scope)"
  echo "Last checkpoint: $(field "$task" last_summary)"
  echo "Next action: $(field "$task" next_action)"
  echo "Plan: agent-coordination/tasks/$task/plan.md"
  echo "Activity: agent-coordination/tasks/$task/activity.md"
  echo; echo "Recent activity:"; tail -n 18 "$(task_dir "$task")/activity.md"
  echo "=== End task handoff context ==="
}

# Prints the agent's active task id, dropping the pointer if another agent took the task over.
own_task() {
  local task
  task=$(active "$1" || true)
  [[ -n "$task" && -d "$(task_dir "$task")" ]] || return 1
  if [[ "$(field "$task" current_executor)" != "$1" ]]; then
    rm -f "$ACTIVE_DIR/$1"; return 1
  fi
  printf '%s' "$task"
}

current() {
  [[ "${1:-}" == "--agent" ]] || die "current requires --agent <agent>"
  local agent="${2:-}" task
  agent_name "$agent"
  if ! task=$(own_task "$agent"); then echo "No active task registered for $agent."; return 0; fi
  echo "Active task: $task"
  echo "Title: $(field "$task" title)"
  echo "Status: $(field "$task" status)"
  echo "Next action: $(field "$task" next_action)"
  echo "Plan: agent-coordination/tasks/$task/plan.md"
}

require() {
  [[ "${1:-}" == "--agent" ]] || die "require requires --agent <agent>"
  local agent="${2:-}"
  agent_name "$agent"
  [[ "$(git -C "$ROOT_DIR" config --bool taskboard.enforce 2>/dev/null)" != "false" ]] || return 0
  own_task "$agent" >/dev/null && return 0
  cat >&2 <<EOF
Taskboard: $agent has no active task, so this edit was blocked. Register the work on the shared taskboard, then retry the edit.
  Continue an unfinished task:  $SELF take-over --agent $agent --task "<task-id>"
  Or start a new one:           $SELF start --agent $agent --title "<concise title>" --scope "<paths>"
List unfinished tasks with:     $SELF context --agent $agent
EOF
  exit 2
}

# True when this clone will run .githooks/post-commit. Cloud Agents keep
# core.hooksPath on Cursor's dispatcher and drop a forwarder in that directory;
# git does not consult .git/hooks while core.hooksPath is set.
push_on_commit_enabled() {
  local current
  current=$(git -C "$ROOT_DIR" config core.hooksPath 2>/dev/null || true)
  if [[ "$current" == ".githooks" || "$current" == "$ROOT_DIR/.githooks" ]]; then
    return 0
  fi
  if [[ -n "$current" && -f "$current/post-commit" ]] && grep -qF '.githooks/post-commit' "$current/post-commit" 2>/dev/null; then
    return 0
  fi
  return 1
}

git_notes() {
  local gitdir state
  gitdir=$(git -C "$ROOT_DIR" rev-parse --absolute-git-dir 2>/dev/null) || return 0
  git -C "$ROOT_DIR" remote get-url origin >/dev/null 2>&1 || return 0
  if [[ -f "$ROOT_DIR/.githooks/post-commit" ]] && ! push_on_commit_enabled; then
    echo "! Push-on-commit is not enabled in this clone. Run: $SELF setup"
  fi
  [[ -f "$gitdir/autopush.status" ]] || return 0
  state=$(cat "$gitdir/autopush.status")
  if [[ "$state" == failed* ]]; then
    echo "! The last automatic push failed (${state#failed }). Run: git pull --rebase && git push"
    echo "  If agent-coordination/taskboard.md conflicts, keep either side and run: $SELF render"
  fi
}

context() {
  [[ "${1:-}" == "--agent" ]] || die "context requires --agent <agent>"
  local agent="${2:-}" task updated id found=0 shown=0
  agent_name "$agent"
  echo "=== Shared agent taskboard (you are '$agent') ==="
  if task=$(own_task "$agent"); then
    echo "Your active task: $task"
    echo "  $(field "$task" title) [$(field "$task" status)]"
    echo "  Next action: $(field "$task" next_action)"
    echo "  Plan: agent-coordination/tasks/$task/plan.md"
  else
    echo "You have no active task. Before editing files, continue an unfinished task or register a new one:"
    echo "  $SELF take-over --agent $agent --task \"<task-id>\""
    echo "  $SELF start --agent $agent --title \"<concise title>\" --scope \"<paths>\""
  fi
  echo
  echo "Unfinished tasks:"
  while IFS=$'\t' read -r updated id; do
    [[ -n "$id" && "$(field "$id" status)" != "completed" ]] || continue
    printf '  %s | %s | %s | executor: %s | next: %s\n' "$id" "$(field "$id" title)" "$(field "$id" status)" \
      "$(field "$id" current_executor)" "$(field "$id" next_action)"
    found=1
  done < <(tasks_by_update)
  [[ $found -eq 1 ]] || echo "  (none)"
  echo
  echo "Recent activity:"
  while IFS=$'\t' read -r updated id; do
    [[ -n "$id" && $shown -lt 5 ]] || continue
    printf '  %s · %s · %s: %s\n' "$updated" "$(field "$id" last_agent)" "$(field "$id" title)" "$(field "$id" last_summary)"
    shown=$((shown + 1))
  done < <(tasks_by_update)
  [[ $shown -gt 0 ]] || echo "  (nothing recorded yet)"
  git_notes
  echo
  echo "End every response with: Taskboard checkpoint: <what changed> | Next: <single next action>"
  echo "=== End shared agent taskboard ==="
}

setup() {
  git -C "$ROOT_DIR" rev-parse --git-dir >/dev/null 2>&1 || die "not inside a git repository"
  git -C "$ROOT_DIR" config core.hooksPath .githooks
  ensure_layout; lock; render; unlock
  echo "Push-on-commit enabled (core.hooksPath=.githooks). Disable with: git config taskboard.autopush false"
}

main() {
  local command="${1:-}"; [[ -n "$command" ]] || { usage; exit 1; }; shift
  case "$command" in
    start) start "$@" ;;
    checkpoint) checkpoint "$@" ;;
    handoff) handoff "$@" ;;
    take-over|resume) take_over "$@" ;;
    log) update "$@" ;;
    complete) update "$@" --complete ;;
    auto-log) auto_log "$@" ;;
    current) current "$@" ;;
    context) context "$@" ;;
    require) require "$@" ;;
    render) ensure_layout; lock; render; unlock ;;
    setup) setup ;;
    -h|--help|help) usage ;;
    *) die "unknown command '$command'" ;;
  esac
}

main "$@"
