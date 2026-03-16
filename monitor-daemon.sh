#!/bin/bash
# Monitor daemon - keeps codex/claude pane monitors running
# Usage: ./monitor-daemon.sh [start|stop|status|restart]

set -uo pipefail

CODLEX_AGENT_DIR="/home/lantern/.openclaw/workspace-coding/skills/cli-agents"
DAEMON_PID_FILE="/tmp/openclaw-agent-monitors-daemon.pid"
CHECK_INTERVAL=30

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

get_active_sessions() {
    tmux list-sessions 2>/dev/null | grep -E "^agentdeck_" | cut -d: -f1
}

start_monitors() {
    log "Scanning for active agent sessions..."
    
    for session in $(get_active_sessions); do
        # Determine if codex or claude
        if [[ "$session" == *"codex"* ]] || [[ "$session" == *"ctf"* ]] || [[ "$session" == *"astra"* ]] || [[ "$session" == *"moss-codex"* ]]; then
            MONITOR_SCRIPT="$CODLEX_AGENT_DIR/codex-agent/hooks/pane_monitor.sh"
            LOG_FILE="/tmp/codex_monitor_${session}.log"
        else
            MONITOR_SCRIPT="$CODLEX_AGENT_DIR/claude-agent/hooks/pane_monitor.sh"
            LOG_FILE="/tmp/claude_monitor_${session}.log"
        fi
        
        # Check if already running (use [p] to avoid matching grep itself)
        if ps aux | grep -q "[p]ane_monitor.sh $session"; then
            log "Monitor already running for $session"
            continue
        fi
        
        log "Starting monitor for $session..."
        nohup bash "$MONITOR_SCRIPT" "$session" > "$LOG_FILE" 2>&1 &
    done
    
    log "Monitor scan complete"
}

daemon_loop() {
    log "Monitor daemon started"
    
    while true; do
        sleep "$CHECK_INTERVAL"
        
        # Check each active session has a monitor (use [p] to avoid matching grep itself)
        for session in $(get_active_sessions); do
            if ! ps aux | grep -q "[p]ane_monitor.sh $session"; then
                log "Monitor missing for $session, restarting..."
                
                if [[ "$session" == *"codex"* ]] || [[ "$session" == *"ctf"* ]] || [[ "$session" == *"astra"* ]] || [[ "$session" == *"moss-codex"* ]]; then
                    MONITOR_SCRIPT="$CODLEX_AGENT_DIR/codex-agent/hooks/pane_monitor.sh"
                    LOG_FILE="/tmp/codex_monitor_${session}.log"
                else
                    MONITOR_SCRIPT="$CODLEX_AGENT_DIR/claude-agent/hooks/pane_monitor.sh"
                    LOG_FILE="/tmp/claude_monitor_${session}.log"
                fi
                
                nohup bash "$MONITOR_SCRIPT" "$session" > "$LOG_FILE" 2>&1 &
            fi
        done
        
        # Cleanup stale monitors (session no longer exists)
        for pid_file in /tmp/codex_monitor_*.pid /tmp/claude_monitor_*.pid; do
            [ -f "$pid_file" ] || continue
            pid=$(cat "$pid_file" 2>/dev/null)
            session=$(basename "$pid_file" .pid | sed 's/codex_monitor_//' | sed 's/claude_monitor_//')
            
            if ! ps -p "$pid" >/dev/null 2>&1; then
                rm -f "$pid_file"
                log "Cleaned up stale PID file for $session"
            fi
        done
    done
}

case "${1:-status}" in
    start)
        if [ -f "$DAEMON_PID_FILE" ] && ps -p "$(cat "$DAEMON_PID_FILE")" >/dev/null 2>&1; then
            log "Daemon already running"
            exit 0
        fi
        
        start_monitors
        daemon_loop &
        echo $! > "$DAEMON_PID_FILE"
        log "Daemon started with PID $(cat "$DAEMON_PID_FILE")"
        ;;
    stop)
        if [ -f "$DAEMON_PID_FILE" ]; then
            pid=$(cat "$DAEMON_PID_FILE")
            kill "$pid" 2>/dev/null || true
            rm -f "$DAEMON_PID_FILE"
            log "Daemon stopped"
        fi
        ;;
    restart)
        $0 stop
        sleep 2
        $0 start
        ;;
    status)
        if [ -f "$DAEMON_PID_FILE" ] && ps -p "$(cat "$DAEMON_PID_FILE")" >/dev/null 2>&1; then
            echo "Daemon running: PID $(cat "$DAEMON_PID_FILE")"
        else
            echo "Daemon not running"
        fi
        
        echo ""
        echo "Active monitors:"
        ps aux | grep -v grep | grep "pane_monitor.sh" || echo "No monitors running"
        ;;
    *)
        echo "Usage: $0 {start|stop|status|restart}"
        exit 1
        ;;
esac
