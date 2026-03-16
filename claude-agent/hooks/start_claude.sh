#!/bin/bash
# Claude Code 一键启动器
# 用法:
#   ./start_claude.sh <session-name> <workdir> [--approval|--auto] \
#     [--chat-id <id>] [--channel <channel>] [--account <account>] [--agent <agent>]
#
# 自动完成：
# 1. 创建 tmux session
# 2. 为该 session 写入独立 route file，并注入通知环境变量
# 3. 启动 Claude Code
# 4. 启动 pane monitor
# 5. session 结束时自动清理 monitor

set -euo pipefail

usage() {
    cat <<'EOF'
用法:
  ./start_claude.sh <session-name> <workdir> [--approval|--auto] \
    [--chat-id <id>] [--channel <channel>] [--account <account>] [--agent <agent>]

参数：
  --approval           使用 claude 默认权限模式（需要时再审批）
  --auto               使用 claude --dangerously-skip-permissions
  --chat-id <id>       本 session 的通知目标（如 Discord 线程 channel:123）
  --channel <channel>  通知通道（如 discord / telegram）
  --account <account>  OpenClaw 通道账号名（如 coder）
  --agent <agent>      被唤醒的 OpenClaw agent（如 coding）

说明：
  - 默认模式是 --auto，即默认免权限启动
  - 未传的参数会回退到当前 shell / ~/.zshrc / ~/.bashrc 中已有的 CLAUDE_AGENT_* 环境变量
  - 传参只对当前 session 生效，可用于多 session 独立通知
EOF
}

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SESSION="${1:-}"
WORKDIR="${2:-}"
shift 2 2>/dev/null || true

if [ -z "$SESSION" ] || [ -z "$WORKDIR" ]; then
    usage
    exit 1
fi

MODE="--auto"
SESSION_CHAT_ID="${CLAUDE_AGENT_CHAT_ID:-${CODEX_AGENT_CHAT_ID:-}}"
SESSION_CHANNEL="${CLAUDE_AGENT_CHANNEL:-${CODEX_AGENT_CHANNEL:-}}"
SESSION_ACCOUNT="${CLAUDE_AGENT_ACCOUNT:-${CODEX_AGENT_ACCOUNT:-}}"
SESSION_AGENT="${CLAUDE_AGENT_NAME:-${CODEX_AGENT_NAME:-main}}"
ROUTE_DIR="${CLAUDE_AGENT_ROUTE_DIR:-/tmp/claude-agent-routes}"
ROUTE_FILE="$ROUTE_DIR/${SESSION}.json"

while [ $# -gt 0 ]; do
    case "$1" in
        --approval)
            MODE="--approval"
            shift
            ;;
        --auto)
            MODE="--auto"
            shift
            ;;
        --chat-id)
            SESSION_CHAT_ID="${2:-}"
            shift 2
            ;;
        --channel)
            SESSION_CHANNEL="${2:-}"
            shift 2
            ;;
        --account)
            SESSION_ACCOUNT="${2:-}"
            shift 2
            ;;
        --agent)
            SESSION_AGENT="${2:-}"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "❌ Unknown argument: $1"
            echo
            usage
            exit 1
            ;;
    esac
done

if ! command -v tmux &>/dev/null; then
    echo "❌ tmux not found"
    exit 1
fi

if ! command -v claude &>/dev/null; then
    echo "❌ claude not found (Claude Code CLI)"
    exit 1
fi

if [ ! -d "$WORKDIR" ]; then
    echo "❌ Directory not found: $WORKDIR"
    exit 1
fi

echo "🔍 Running claude-agent hook preflight..."
if ! python3 "$SKILL_DIR/../../../scripts/check_agent_hooks.py" claude; then
    echo "❌ claude-agent hook health check failed"
    echo "   Fix hook syntax/import errors before starting the session."
    exit 1
fi

mkdir -p "$ROUTE_DIR"
if [ -n "$SESSION_CHAT_ID" ]; then
    if ! python3 "$SKILL_DIR/../../../scripts/check_route_conflicts.py" \
        --session "$SESSION" \
        --chat-id "$SESSION_CHAT_ID" \
        --channel "$SESSION_CHANNEL"; then
        echo "❌ claude-agent route preflight failed"
        exit 1
    fi
fi
if [ -n "$SESSION_CHAT_ID" ]; then
    python3 - "$ROUTE_FILE" "$SESSION" "$WORKDIR" "$SESSION_CHAT_ID" "$SESSION_CHANNEL" "$SESSION_AGENT" "$SESSION_ACCOUNT" <<'PY'
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

CLAUDE_CMD="unset CLAUDECODE; claude --dangerously-skip-permissions"
if [ "$MODE" = "--approval" ]; then
    CLAUDE_CMD="unset CLAUDECODE; claude"
fi

if ! tmux new-session -d -s "$SESSION" -c "$WORKDIR"; then
    echo "❌ Failed to create tmux session: $SESSION"
    exit 1
fi

if [ -n "$SESSION_CHAT_ID" ]; then
    tmux set-environment -t "$SESSION" CLAUDE_AGENT_CHAT_ID "$SESSION_CHAT_ID"
fi
if [ -n "$SESSION_CHANNEL" ]; then
    tmux set-environment -t "$SESSION" CLAUDE_AGENT_CHANNEL "$SESSION_CHANNEL"
fi
if [ -n "$SESSION_ACCOUNT" ]; then
    tmux set-environment -t "$SESSION" CLAUDE_AGENT_ACCOUNT "$SESSION_ACCOUNT"
fi
if [ -n "$SESSION_AGENT" ]; then
    tmux set-environment -t "$SESSION" CLAUDE_AGENT_NAME "$SESSION_AGENT"
fi
if ! tmux set-environment -t "$SESSION" CLAUDE_AGENT_SESSION "$SESSION"; then
    echo "❌ Failed to set tmux environment for session: $SESSION"
    tmux kill-session -t "$SESSION" 2>/dev/null || true
    exit 1
fi

if ! tmux send-keys -t "$SESSION" "$CLAUDE_CMD" Enter; then
    echo "❌ Failed to send command to tmux session: $SESSION"
    tmux kill-session -t "$SESSION" 2>/dev/null || true
    exit 1
fi

sleep 2
if ! tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "❌ tmux session died immediately, Claude Code may have failed to start"
    exit 1
fi

MONITOR_PID_FILE="/tmp/claude_monitor_${SESSION}.pid"
nohup env \
    CLAUDE_AGENT_CHAT_ID="$SESSION_CHAT_ID" \
    CLAUDE_AGENT_CHANNEL="$SESSION_CHANNEL" \
    CLAUDE_AGENT_ACCOUNT="$SESSION_ACCOUNT" \
    CLAUDE_AGENT_NAME="$SESSION_AGENT" \
    CLAUDE_AGENT_SESSION="$SESSION" \
    bash "$SKILL_DIR/hooks/pane_monitor.sh" "$SESSION" > /dev/null 2>&1 &
echo $! > "$MONITOR_PID_FILE"

echo "✅ Claude Code started"
echo "   session:  $SESSION"
echo "   workdir:  $WORKDIR"
echo "   mode:     ${MODE#--}"
echo "   notify:   ${SESSION_CHANNEL:-unset} ${SESSION_ACCOUNT:+account=$SESSION_ACCOUNT }${SESSION_CHAT_ID:-unset}"
echo "   agent:    ${SESSION_AGENT:-unset}"
echo "   route:    $ROUTE_FILE"
echo "   monitor:  PID $(cat "$MONITOR_PID_FILE")"
echo ""
echo "📎 tmux attach -t $SESSION    # 直接查看"
echo "🔪 ./stop_claude.sh $SESSION  # 一键清理"
 # 一键清理"
