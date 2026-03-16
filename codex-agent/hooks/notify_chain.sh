#!/usr/bin/env bash
set -euo pipefail

OMC_HOOK="/home/lantern/.local/n/lib/node_modules/oh-my-codex/scripts/notify-hook.js"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CODEX_AGENT_HOOK="$SCRIPT_DIR/on_complete.py"

status=0

if command -v node >/dev/null 2>&1 && [ -f "$OMC_HOOK" ]; then
  node "$OMC_HOOK" "$@" || status=$?
fi

if command -v python3 >/dev/null 2>&1 && [ -f "$CODEX_AGENT_HOOK" ]; then
  python3 "$CODEX_AGENT_HOOK" "$@" || status=$?
fi

exit $status
