#!/bin/bash
# Claude Code TUI pane 监控器 - 基于 prompt 状态检测
# 用法: ./pane_monitor.sh <tmux-session-name>
# 检测 prompt 消失 = 任务开始, prompt 出现 = 任务结束

set -uo pipefail

SESSION="${1:?Usage: $0 <tmux-session-name>}"
CHECK_INTERVAL=2
LAST_STATE=""
HAS_WORKING=0
HAS_PROMPT=0
INITIAL_DETECT_DONE="false"
LAST_WORKING_END=0  # 上次 working 结束的时间戳
QUIET_PERIOD_SECONDS=10  # 静默期：工作结束后多久内不重复发送通知
CAPTURE_LINES=30
LOG_FILE="/tmp/claude_monitor_${SESSION}.log"
STATE_FILE="/tmp/claude_monitor_${SESSION}.state"
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SEPARATOR="──────────────────"

load_state() {
    if [ -f "$STATE_FILE" ]; then
        LAST_STATE="$(grep '^LAST_STATE=' "$STATE_FILE" 2>/dev/null | cut -d= -f2-)"
        NOTIFIED_APPROVAL="$(grep '^NOTIFIED_APPROVAL=' "$STATE_FILE" 2>/dev/null | cut -d= -f2-)"
        LAST_WORKING_END="$(grep '^LAST_WORKING_END=' "$STATE_FILE" 2>/dev/null | cut -d= -f2-)"
    fi
    if [ -z "$LAST_STATE" ]; then
        LAST_STATE="unknown"
    fi
    NOTIFIED_APPROVAL="${NOTIFIED_APPROVAL:-}"
    LAST_WORKING_END="${LAST_WORKING_END:-0}"
}

save_state() {
    cat > "$STATE_FILE" <<EOF
LAST_STATE=${LAST_STATE}
NOTIFIED_APPROVAL=${NOTIFIED_APPROVAL}
LAST_WORKING_END=${LAST_WORKING_END:-0}
EOF
}

load_state

log() { echo "[$(date '+%H:%M:%S')] $1" >> "$LOG_FILE"; }

is_approval_prompt() {
    local output="$1"
    echo "$output" | grep -qE "Do you want to proceed\?|Allow once|Allow always" || return 1
    echo "$output" | grep -qE "Allow (Bash|Read|Write|Edit|Glob|Grep|WebFetch|WebSearch|Agent|NotebookEdit)" || return 1
}

extract_approval_tool() {
    local output="$1"
    echo "$output" | grep -oE "Allow (Bash|Read|Write|Edit|Glob|Grep|WebFetch|WebSearch|Agent|NotebookEdit)" | tail -1 | sed 's/Allow //'
}

extract_approval_command() {
    local output="$1"
    python3 - "$output" <<'PY'
import re
import sys
text = sys.argv[1]
seen = False
for raw_line in text.splitlines():
    line = raw_line.rstrip("\n")
    if re.search(r"Allow (Bash|Read|Write|Edit|Glob|Grep|WebFetch|WebSearch|Agent|NotebookEdit)", line):
        seen = True
        continue
    if not seen:
        continue
    if re.search(r"Do you want to proceed\?|Allow once|Allow always", line):
        continue
    stripped = line.strip()
    if stripped:
        print(stripped)
        break
PY
}

build_work_start_message() {
    printf '%s\n🚧 Claude Code 开始处理任务\n🔧 session: %s\n📁 workdir: %s\n🧵 trace_id: %s\n%s' \
        "$SEPARATOR" \
        "$SESSION" \
        "${WORKDIR:-unknown}" \
        "${TRACE_ID:-unknown}" \
        "$SEPARATOR"
}

build_approval_message() {
    local tool="$1"
    local cmd="$2"
    printf '%s\n⏸️ Claude Code 等待审批\n🔧 session: %s\n🧵 trace_id: %s\n📋 工具: %s\n%s\n📝 命令: %s' \
        "$SEPARATOR" \
        "$SESSION" \
        "${TRACE_ID:-unknown}" \
        "${tool:-unknown}" \
        "$SEPARATOR" \
        "${cmd:-unknown}"
}

store_reply_mapping() {
    local message_id="$1"
    local event_type="$2"
    [ -n "$message_id" ] || return 0
    python3 "$SKILL_DIR/../bridge/reply_route_map.py" put \
        --message-id "$message_id" \
        --kind "claude" \
        --session-name "$SESSION" \
        --channel "$CHANNEL" \
        --chat-id "$CHAT_ID" \
        --trace-id "${TRACE_ID:-}" \
        --route-file "${ROUTE_FILE:-}" \
        --event-type "$event_type" >/dev/null 2>&1 || true
}

notify_thread() {
    local msg="$1"
    local event_type="${2:-task-reply}"
    local -a cmd=(openclaw message send --channel "$CHANNEL" --target "$CHAT_ID" --message "$msg" --silent --json)
    if [ -n "$ACCOUNT" ]; then
        cmd+=(--account "$ACCOUNT")
    fi
    local output
    output="$("${cmd[@]}" 2>>"$LOG_FILE")"
    local message_id
    message_id="$(printf '%s' "$output" | python3 "$SKILL_DIR/../bridge/extract_message_id.py")"
    if [ -n "$message_id" ]; then
        store_reply_mapping "$message_id" "$event_type"
        log "reply-map stored: message_id=$message_id kind=claude session=$SESSION event=$event_type"
    fi
}

wake_agent() {
    local msg="$1"
    openclaw agent --agent "$AGENT_NAME" --message "$msg" --channel "$CHANNEL" --timeout 120 2>>"$LOG_FILE" &
    WAKE_PID=$!
    log "Agent wake fired (pid $WAKE_PID)"
}

resolve_route_field() {
    local field="$1"
    python3 - "$SESSION" "$field" "$SKILL_DIR/hooks/route_context.py" <<'PY'
import importlib.util
import sys
session_name, field_name, module_path = sys.argv[1:4]
spec = importlib.util.spec_from_file_location("route_context", module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
route = module.resolve_route(session_name=session_name)
print(route.get(field_name, ""))
PY
}

CHAT_ID="$(resolve_route_field chat_id)"
CHANNEL="$(resolve_route_field channel)"
ACCOUNT="$(resolve_route_field account)"
AGENT_NAME="$(resolve_route_field agent_name)"
WORKDIR="$(resolve_route_field workdir)"
ROUTE_FILE="$(resolve_route_field route_file)"
TRACE_ID="$(resolve_route_field trace_id)"
MANAGED="$(resolve_route_field managed)"
NOTIFY="$(resolve_route_field notify)"
if [ "${NOTIFY:-true}" = "false" ]; then
    log "Notifications explicitly disabled for session $SESSION (notify=false)"
fi

cleanup() {
    local pid_file="/tmp/claude_monitor_${SESSION}.pid"
    rm -f "$pid_file"
    log "Monitor exiting, cleaned up PID file"
}
trap cleanup EXIT

log "Monitor started for session: $SESSION"
log "Routing via ${CHANNEL}:${CHAT_ID} account=${ACCOUNT:-} route_file=${ROUTE_FILE:-default-env} managed=${MANAGED:-false}"

# 初始内容捕获用于状态检测
INITIAL_OUTPUT="$(tmux capture-pane -t "$SESSION" -p -S -"$CAPTURE_LINES" 2>/dev/null)"

# 检测初始状态并同步 LAST_STATE（不发送通知）
if [ "$LAST_STATE" = "unknown" ]; then
    if echo "$INITIAL_OUTPUT" | grep -qE '(❯|›|>)'; then
        LAST_STATE="idle"
        log "Initial state detected: idle"
    else
        LAST_STATE="working"
        log "Initial state detected: working"
    fi
    save_state
    INITIAL_DETECT_DONE="true"
fi

log "Initial state: $LAST_STATE"

while true; do
    if ! tmux has-session -t "$SESSION" 2>/dev/null; then
        log "Session $SESSION gone, exiting"
        exit 0
    fi

    if [ "${MANAGED:-false}" != "true" ] || [ -z "$ROUTE_FILE" ]; then
        log "Session $SESSION is unmanaged, monitor exiting"
        exit 0
    fi

    OUTPUT="$(tmux capture-pane -t "$SESSION" -p -S -"$CAPTURE_LINES" 2>/dev/null)"

    # 检测 prompt 状态: Claude 当前常见 prompt 为 ❯ / › / >
    HAS_PROMPT=0
    if echo "$OUTPUT" | grep -qE '(❯|›|>)'; then
        HAS_PROMPT=1
    fi

    # 审批检测 - 最高优先级
    if is_approval_prompt "$OUTPUT"; then
        TOOL="$(extract_approval_tool "$OUTPUT")"
        CMD="$(extract_approval_command "$OUTPUT")"
        STATE="approval:${TOOL:-unknown}:${CMD:-unknown}"

        if [ "$STATE" != "$NOTIFIED_APPROVAL" ] && [ "${NOTIFY:-true}" != "false" ]; then
            NOTIFIED_APPROVAL="$STATE"
            MSG="$(build_approval_message "${TOOL:-unknown}" "${CMD:-unknown}")"
            if ! notify_thread "$MSG" "approval"; then
                log "⚠️ Notify failed for approval"
            fi
            AGENT_MSG="[Claude Monitor] 审批等待，请处理。
session: $SESSION
tool: ${TOOL:-unknown}
command: ${CMD:-unknown}
请在 tmux 中输入 y + Enter 批准，或 n + Enter 拒绝。"
            wake_agent "$AGENT_MSG"
            log "Approval detected: ${TOOL:-unknown} - ${CMD:-unknown}"
        fi
    # Prompt 消失 = 任务开始 (从 idle -> working)
    # 只有在静默期过后才发送通知
    elif [ "$INITIAL_DETECT_DONE" != "true" ] && [ "$HAS_PROMPT" -eq 0 ] && [ "$LAST_STATE" = "idle" ]; then
        CURRENT_TIME=$(date +%s)
        TIME_SINCE_LAST_WORKING=$((CURRENT_TIME - LAST_WORKING_END))
        
        LAST_STATE="working"
        save_state
        log "Prompt disappeared, transitioned to working (last working ended ${TIME_SINCE_LAST_WORKING}s ago)"
        
        # 只有静默期超过阈值时才发送通知
        if [ "$TIME_SINCE_LAST_WORKING" -ge "$QUIET_PERIOD_SECONDS" ] && [ "${NOTIFY:-true}" != "false" ]; then
            MSG="$(build_work_start_message)"
            if notify_thread "$MSG" "work-start"; then
                log "Work-start notification sent (quiet period: ${TIME_SINCE_LAST_WORKING}s)"
            else
                log "⚠️ Work-start notification failed"
            fi
        else
            log "Notification skipped (quiet period only ${TIME_SINCE_LAST_WORKING}s, need ${QUIET_PERIOD_SECONDS}s)"
        fi
    # Prompt 出现 = 任务结束 (从 working -> idle)
    elif [ "$HAS_PROMPT" -eq 1 ] && [ "$LAST_STATE" = "working" ]; then
        LAST_WORKING_END=$(date +%s)
        LAST_STATE="idle"
        NOTIFIED_APPROVAL=""
        save_state
        log "Prompt appeared, back to idle (working ended at ${LAST_WORKING_END})"
    fi

    sleep "$CHECK_INTERVAL"
done
