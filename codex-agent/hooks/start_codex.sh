#!/bin/bash
# Codex 一键启动器
# 用法: ./start_codex.sh <session-name> <workdir> [--approval|--yolo]
# 可选来源路由：
#   CODEX_AGENT_SOURCE_CHAT_ID
#   CODEX_AGENT_SOURCE_CHANNEL
#   CODEX_AGENT_SOURCE_AGENT_NAME
#   CODEX_AGENT_SOURCE_ACCOUNT
#
# 自动完成：
# 1. 创建 tmux session
# 2. 记录来源会话路由
# 3. 启动 Codex TUI
# 4. 启动 pane monitor
# 5. session 结束时自动清理 monitor

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SESSION="${1:?Usage: $0 <session-name> <workdir> [--approval|--yolo]}"
WORKDIR="${2:?Usage: $0 <session-name> <workdir> [--approval|--yolo]}"
MODE="${3:---yolo}"
ROUTE_DIR="${CODEX_AGENT_ROUTE_DIR:-/tmp/codex-agent-routes}"
ROUTE_FILE="$ROUTE_DIR/${SESSION}.json"

if ! command -v tmux &>/dev/null; then
    echo "❌ tmux not found"
    exit 1
fi

if ! command -v codex &>/dev/null; then
    echo "❌ codex not found"
    exit 1
fi

if [ ! -d "$WORKDIR" ]; then
    echo "❌ Directory not found: $WORKDIR"
    exit 1
fi

echo "🔍 Running codex-agent hook preflight..."
if ! python3 "$SKILL_DIR/../../../scripts/check_agent_hooks.py" codex; then
    echo "❌ codex-agent hook health check failed"
    echo "   Fix hook syntax/import errors before starting the session."
    exit 1
fi

mkdir -p "$ROUTE_DIR"

SOURCE_CHAT_ID="${CODEX_AGENT_SOURCE_CHAT_ID:-${OPENCLAW_CHAT_ID:-${CODEX_AGENT_CHAT_ID:-}}}"
SOURCE_CHANNEL="${CODEX_AGENT_SOURCE_CHANNEL:-${OPENCLAW_CHANNEL:-${CODEX_AGENT_CHANNEL:-discord}}}"
SOURCE_AGENT_NAME="${CODEX_AGENT_SOURCE_AGENT_NAME:-${OPENCLAW_AGENT_NAME:-${CODEX_AGENT_NAME:-main}}}"
SOURCE_ACCOUNT="${CODEX_AGENT_SOURCE_ACCOUNT:-${OPENCLAW_ACCOUNT_ID:-${CODEX_AGENT_ACCOUNT:-}}}"

if [ -n "$SOURCE_CHAT_ID" ]; then
    if ! python3 "$SKILL_DIR/../../../scripts/check_route_conflicts.py" \
        --kind codex \
        --session "$SESSION" \
        --chat-id "$SOURCE_CHAT_ID" \
        --channel "$SOURCE_CHANNEL"; then
        echo "❌ codex-agent route preflight failed"
        exit 1
    fi
fi

if [ -n "$SOURCE_CHAT_ID" ]; then
    python3 - "$ROUTE_FILE" "$SESSION" "$WORKDIR" "$SOURCE_CHAT_ID" "$SOURCE_CHANNEL" "$SOURCE_AGENT_NAME" "$SOURCE_ACCOUNT" <<'PY'
import json
import sys
from datetime import datetime, timezone
from uuid import uuid4
route_file, session_name, workdir, chat_id, channel, agent_name, account = sys.argv[1:8]
trace_id = f"route-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}-{uuid4().hex[:12]}"
payload = {
    "session_name": session_name,
    "workdir": workdir,
    "chat_id": chat_id,
    "channel": channel,
    "account": account,
    "agent_name": agent_name,
    "trace_id": trace_id,
    "updated_at": datetime.now(timezone.utc).isoformat(),
}
with open(route_file, "w") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)
print(f"[route-trace] trace_id={trace_id} route_file={route_file} session={session_name} route={channel}:{chat_id}")
PY
fi

tmux kill-session -t "$SESSION" 2>/dev/null || true
pkill -f "pane_monitor.sh $SESSION" 2>/dev/null || true

CODEX_CMD="codex --no-alt-screen --yolo"
if [ "$MODE" = "--approval" ]; then
    CODEX_CMD="codex --no-alt-screen"
elif [ "$MODE" != "--yolo" ]; then
    echo "❌ Unknown mode: $MODE"
    echo "Usage: $0 <session-name> <workdir> [--approval|--yolo]"
    exit 1
fi

if ! tmux new-session -d -s "$SESSION" -c "$WORKDIR"; then
    echo "❌ Failed to create tmux session: $SESSION"
    exit 1
fi

if ! tmux set-environment -t "$SESSION" CODEX_AGENT_SESSION "$SESSION"; then
    echo "❌ Failed to set tmux environment for session: $SESSION"
    tmux kill-session -t "$SESSION" 2>/dev/null || true
    exit 1
fi

if ! tmux send-keys -t "$SESSION" "$CODEX_CMD" Enter; then
    echo "❌ Failed to send command to tmux session: $SESSION"
    tmux kill-session -t "$SESSION" 2>/dev/null || true
    exit 1
fi

sleep 2
if ! tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "❌ tmux session died immediately, Codex may have failed to start"
    exit 1
fi

MONITOR_PID_FILE="/tmp/codex_monitor_${SESSION}.pid"
nohup bash "$SKILL_DIR/hooks/pane_monitor.sh" "$SESSION" > /dev/null 2>&1 &
echo $! > "$MONITOR_PID_FILE"

echo "✅ Codex started"
echo "   session:  $SESSION"
echo "   workdir:  $WORKDIR"
echo "   mode:     ${MODE#--}"
echo "   route:    ${SOURCE_CHANNEL}:${SOURCE_CHAT_ID:-unset}"
echo "   account:  ${SOURCE_ACCOUNT:-unset}"
echo "   routefile:$ROUTE_FILE"
echo "   monitor:  PID $(cat "$MONITOR_PID_FILE")"
echo ""
echo "📎 tmux attach -t $SESSION    # 直接查看"
echo "🔪 ./stop_codex.sh $SESSION   # 一键清理"
