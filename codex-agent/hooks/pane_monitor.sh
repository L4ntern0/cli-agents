#!/bin/bash
# Codex TUI pane 监控器
# 用法: ./pane_monitor.sh <tmux-session-name>
# 后台运行，检测审批等待并按 route file 路由通知

set -uo pipefail

SESSION="${1:?Usage: $0 <tmux-session-name>}"
CHECK_INTERVAL=5
LAST_STATE=""
NOTIFIED_APPROVAL=""
CAPTURE_LINES=30
LOG_FILE="/tmp/codex_monitor_${SESSION}.log"
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

log() { echo "[$(date '+%H:%M:%S')] $1" >> "$LOG_FILE"; }

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
ROUTE_FILE="$(resolve_route_field route_file)"
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

    if echo "$OUTPUT" | grep -q "Would you like to run\|Press enter to confirm\|approve this\|allow this"; then
        CMD=$(echo "$OUTPUT" | grep '^\s*\$' | tail -1 | sed 's/^\s*\$ //')
        STATE="approval:$CMD"

        if [ "$STATE" != "$NOTIFIED_APPROVAL" ]; then
            NOTIFIED_APPROVAL="$STATE"
            MSG="⏸️ Codex 等待审批
🧭 session: $SESSION
📋 命令: ${CMD:-unknown}"
            ACCOUNT_ARG=()
            if [ -n "$ACCOUNT" ]; then
                ACCOUNT_ARG=(--account "$ACCOUNT")
            fi
            if ! openclaw message send --channel "$CHANNEL" "${ACCOUNT_ARG[@]}" --target "$CHAT_ID" --message "$MSG" --silent 2>>"$LOG_FILE"; then
                log "⚠️ channel notify failed for approval"
            fi
            AGENT_MSG="[Codex Monitor] 审批等待，请处理。
session: $SESSION
command: ${CMD:-unknown}
请 tmux send-keys -t $SESSION '1' Enter 批准，或 '3' Enter 拒绝。"
            openclaw agent --agent "$AGENT_NAME" --message "$AGENT_MSG" --channel "$CHANNEL" --timeout 120 2>>"$LOG_FILE" &
            WAKE_PID=$!
            log "Agent wake fired (pid $WAKE_PID)"
            log "Approval detected: $CMD"
        fi
    elif echo "$OUTPUT" | grep -q "? for shortcuts"; then
        if [ "$LAST_STATE" = "working" ]; then
            LAST_STATE="idle"
            NOTIFIED_APPROVAL=""
            log "Back to idle"
        fi
    elif echo "$OUTPUT" | grep -q "esc to interrupt\|Thinking\|Creating\|Editing\|Running"; then
        LAST_STATE="working"
    fi

    sleep "$CHECK_INTERVAL"
done
