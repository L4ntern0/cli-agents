#!/bin/bash
# Codex TUI pane 监控器
# 用法: ./pane_monitor.sh <tmux-session-name>
# 后台运行，检测审批等待和工作开始，按 route file 路由通知

set -uo pipefail

SESSION="${1:?Usage: $0 <tmux-session-name>}"
CHECK_INTERVAL=5
LAST_STATE=""
NOTIFIED_APPROVAL=""
CAPTURE_LINES=30
LOG_FILE="/tmp/codex_monitor_${SESSION}.log"
STATE_FILE="/tmp/codex_monitor_${SESSION}.state"

# 持久化的通知状态 (跨重启)
LAST_STATE="${LAST_STATE:-}"
NOTIFIED_APPROVAL="${NOTIFIED_APPROVAL:-}"
NOTIFIED_WORK_START="${NOTIFIED_WORK_START:-}"

load_state() {
    if [ -f "$STATE_FILE" ]; then
        LAST_STATE="$(grep '^LAST_STATE=' "$STATE_FILE" 2>/dev/null | cut -d= -f2-)"
        NOTIFIED_APPROVAL="$(grep '^NOTIFIED_APPROVAL=' "$STATE_FILE" 2>/dev/null | cut -d= -f2-)"
        NOTIFIED_WORK_START="$(grep '^NOTIFIED_WORK_START=' "$STATE_FILE" 2>/dev/null | cut -d= -f2-)"
    fi
}

save_state() {
    cat > "$STATE_FILE" <<EOF
LAST_STATE=${LAST_STATE}
NOTIFIED_APPROVAL=${NOTIFIED_APPROVAL}
NOTIFIED_WORK_START=${NOTIFIED_WORK_START}
EOF
}

# 启动时加载状态
load_state
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SEPARATOR="──────────────────"

log() { echo "[$(date '+%H:%M:%S')] $1" >> "$LOG_FILE"; }

build_work_start_message() {
    printf '%s\n🚧 Codex 开始处理任务\n🔧 session: %s\n📁 workdir: %s\n🧵 trace_id: %s\n%s' \
        "$SEPARATOR" \
        "$SESSION" \
        "${WORKDIR:-unknown}" \
        "${TRACE_ID:-unknown}" \
        "$SEPARATOR"
}

build_approval_message() {
    local cmd="$1"
    printf '%s\n⏸️ Codex 等待审批\n🔧 session: %s\n🧵 trace_id: %s\n📋 命令: %s\n%s' \
        "$SEPARATOR" \
        "$SESSION" \
        "${TRACE_ID:-unknown}" \
        "${cmd:-unknown}" \
        "$SEPARATOR"
}

store_reply_mapping() {
    local message_id="$1"
    local event_type="$2"
    [ -n "$message_id" ] || return 0
    python3 "$SKILL_DIR/../bridge/reply_route_map.py" put \
        --message-id "$message_id" \
        --kind "codex" \
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
    message_id="$(printf '%s' "$output" | python3 - <<'PY'
import json, sys
text = sys.stdin.read().strip()
if not text:
    raise SystemExit(0)
try:
    payload = json.loads(text)
except json.JSONDecodeError:
    raise SystemExit(0)
print(payload.get('messageId', '') or '')
PY
)"
    if [ -n "$message_id" ]; then
        store_reply_mapping "$message_id" "$event_type"
        log "reply-map stored: message_id=$message_id kind=codex session=$SESSION event=$event_type"
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

cleanup() {
    local pid_file="/tmp/codex_monitor_${SESSION}.pid"
    rm -f "$pid_file"
    log "Monitor exiting, cleaned up PID file"
}
trap cleanup EXIT

log "Monitor started for session: $SESSION"
log "Routing via ${CHANNEL}:${CHAT_ID} account=${ACCOUNT:-} route_file=${ROUTE_FILE:-default-env} managed=${MANAGED:-false}"

while true; do
    if ! tmux has-session -t "$SESSION" 2>/dev/null; then
        log "Session $SESSION gone, exiting"
        exit 0
    fi

    # 仅监控由 codex-agent 管理的 session
    if [ "$MANAGED" != "true" ] || [ -z "$ROUTE_FILE" ]; then
        log "Session $SESSION is unmanaged, monitor exiting"
        exit 0
    fi

    OUTPUT=$(tmux capture-pane -t "$SESSION" -p -S -"$CAPTURE_LINES" 2>/dev/null)

    # 审批检测
    if echo "$OUTPUT" | grep -q "Would you like to run\|Press enter to confirm\|approve this\|allow this"; then
        CMD=$(echo "$OUTPUT" | grep '^\s*\$' | tail -1 | sed 's/^\s*\$ //')
        STATE="approval:$CMD"

        if [ "$STATE" != "$NOTIFIED_APPROVAL" ]; then
            NOTIFIED_APPROVAL="$STATE"
            save_state
            MSG="$(build_approval_message "${CMD:-unknown}")"
            if ! notify_thread "$MSG" "approval"; then
                log "⚠️ Notify failed for approval"
            fi
            AGENT_MSG="[Codex Monitor] 审批等待，请处理。
session: $SESSION
command: ${CMD:-unknown}
请 tmux send-keys -t $SESSION '1' Enter 批准，或 '3' Enter 拒绝。"
            wake_agent "$AGENT_MSG"
            log "Approval detected: $CMD"
        fi
    # 空闲状态检测 - 当出现 › 提示符时（最可靠）
    elif echo "$OUTPUT" | grep -q "›"; then
        if [ "$LAST_STATE" = "working" ]; then
            LAST_STATE="idle"
            NOTIFIED_APPROVAL=""
            NOTIFIED_WORK_START=""
            save_state
            log "Back to idle (› prompt detected)"
        fi
    # 工作状态检测 - 使用更可靠的模式
    # 优先检测 "Working (" 模式（最可靠）
    elif echo "$OUTPUT" | grep -q "Working ("; then
        if [ "$LAST_STATE" != "working" ]; then
            LAST_STATE="working"
            log "Transitioned to working (Working pattern detected)"
            if [ -z "$NOTIFIED_WORK_START" ]; then
                NOTIFIED_WORK_START="sent"
                save_state
                if [ -n "$CHAT_ID" ] && [ -n "$CHANNEL" ]; then
                    MSG="$(build_work_start_message)"
                    if notify_thread "$MSG" "work-start"; then
                        log "Work-start notification sent"
                    else
                        log "⚠️ Work-start notification failed"
                    fi
                fi
            fi
        fi
    # 备用：关键词匹配（作为后备检测）
    elif echo "$OUTPUT" | grep -qE "Thinking|Creating|Editing|Running|Reading|Searching|Writing|Determining"; then
        if [ "$LAST_STATE" != "working" ]; then
            LAST_STATE="working"
            log "Transitioned to working (keyword fallback detected)"
            if [ -z "$NOTIFIED_WORK_START" ]; then
                NOTIFIED_WORK_START="sent"
                save_state
                if [ -n "$CHAT_ID" ] && [ -n "$CHANNEL" ]; then
                    MSG="$(build_work_start_message)"
                    if notify_thread "$MSG" "work-start"; then
                        log "Work-start notification sent"
                    else
                        log "⚠️ Work-start notification failed"
                    fi
                fi
            fi
        fi
    fi

    sleep "$CHECK_INTERVAL"
done
