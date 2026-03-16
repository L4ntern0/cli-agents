#!/bin/bash
# Claude Code 一键清理
# 用法: ./stop_claude.sh <session-name>

set -uo pipefail

SESSION="${1:?Usage: $0 <session-name>}"
MONITOR_PID_FILE="/tmp/claude_monitor_${SESSION}.pid"
ROUTE_DIR="${CLAUDE_AGENT_ROUTE_DIR:-/tmp/claude-agent-routes}"
ROUTE_FILE="$ROUTE_DIR/${SESSION}.json"

# 读取 route 配置用于通知
_notify_route() {
    if [ -f "$ROUTE_FILE" ]; then
        local channel chat_id account
        channel=$(python3 -c "import json; print(json.load(open('$ROUTE_FILE')).get('channel', 'discord'))" 2>/dev/null || echo "discord")
        chat_id=$(python3 -c "import json; print(json.load(open('$ROUTE_FILE')).get('chat_id', ''))" 2>/dev/null || echo "")
        account=$(python3 -c "import json; print(json.load(open('$ROUTE_FILE')).get('account', ''))" 2>/dev/null || echo "")
        if [ -n "$chat_id" ]; then
            local msg="🛑 Claude Code 会话已结束\n────────────────\n🧭 session: ${SESSION}"
            openclaw message send --channel "$channel" --target "$chat_id" --message "$msg" --account "$account" 2>/dev/null || true
            echo "📨 Session close notification sent"
        fi
    fi
}

# 杀 pane monitor
if [ -f "$MONITOR_PID_FILE" ]; then
    kill "$(cat "$MONITOR_PID_FILE")" 2>/dev/null || true
    rm -f "$MONITOR_PID_FILE"
    echo "✅ Monitor stopped"
else
    echo "ℹ️ Monitor PID file not found (may have already exited)"
fi
# 兜底：按精确 session 名匹配
pkill -f "pane_monitor\.sh ${SESSION}$" 2>/dev/null || true

# 杀 tmux session
if tmux has-session -t "$SESSION" 2>/dev/null; then
    tmux kill-session -t "$SESSION"
    echo "✅ Session $SESSION killed"
else
    echo "ℹ️ Session $SESSION not found"
fi

# 先发送会话结束通知，再清理 route 文件
_notify_route

if [ -f "$ROUTE_FILE" ]; then
    rm -f "$ROUTE_FILE"
    echo "✅ Route context removed"
else
    echo "ℹ️ Route context not found"
fi

# 清理日志（可选，取消注释启用）
# rm -f "/tmp/claude_monitor_${SESSION}.log"
