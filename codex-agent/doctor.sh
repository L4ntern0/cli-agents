#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
HOOKS_DIR="$ROOT/hooks"
ROUTE_DIR="${CODEX_AGENT_ROUTE_DIR:-/tmp/codex-agent-routes}"
SESSION_FILTER="${1:-}"

status_line() {
  local label="$1" value="$2"
  printf '%-18s %s\n' "$label" "$value"
}

echo "== codex-agent doctor =="
status_line root "$ROOT"
status_line route_dir "$ROUTE_DIR"
echo

echo "[1/5] hook preflight"
python3 "$ROOT/../../scripts/check_agent_hooks.py" codex || true
echo

echo "[2/5] route files"
if [ -d "$ROUTE_DIR" ] && find "$ROUTE_DIR" -maxdepth 1 -name '*.json' | grep -q .; then
  while IFS= read -r file; do
    python3 - "$file" <<'PY'
import json, sys
p = sys.argv[1]
with open(p) as f:
    data = json.load(f)
print(f"- {p}")
print(f"  session: {data.get('session_name','')}")
print(f"  workdir: {data.get('workdir','')}")
print(f"  route:   {data.get('channel','')}:{data.get('chat_id','')}")
print(f"  account: {data.get('account','')}")
print(f"  trace:   {data.get('trace_id','')}")
print(f"  updated: {data.get('updated_at','')}")
PY
  done < <(find "$ROUTE_DIR" -maxdepth 1 -name '*.json' | sort)
else
  echo "- no codex route files"
fi
echo

echo "[3/5] tmux sessions"
if tmux list-sessions 2>/dev/null | grep -q .; then
  tmux list-sessions | grep 'agentdeck\|codex' || echo "- no codex-like tmux sessions found"
else
  echo "- no tmux sessions"
fi
echo

echo "[4/5] codex notify log tail"
tail -n 20 /tmp/codex_notify_log.txt 2>/dev/null || echo "- no codex notify log yet"
echo

echo "[5/5] session detail"
if [ -n "$SESSION_FILTER" ]; then
  status_line session "$SESSION_FILTER"
  if tmux has-session -t "$SESSION_FILTER" 2>/dev/null; then
    status_line tmux active
    echo "--- pane tail ---"
    tmux capture-pane -t "$SESSION_FILTER" -p -S -20 || true
  else
    status_line tmux missing
  fi
  ROUTE_FILE="$ROUTE_DIR/${SESSION_FILTER}.json"
  if [ -f "$ROUTE_FILE" ]; then
    echo "--- route file ---"
    cat "$ROUTE_FILE"
  else
    echo "- no route file for $SESSION_FILTER"
  fi
else
  echo "Usage: ./doctor.sh [session-name]"
fi
