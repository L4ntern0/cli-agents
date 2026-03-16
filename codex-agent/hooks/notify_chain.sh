#!/usr/bin/env bash
set -euo pipefail

# Try to find oh-my-codex notify-hook.js automatically
OMC_HOOK=""
if OMC_PATH="$(command -v oh-my-codex 2>/dev/null)" && [ -f "$OMC_PATH" ]; then
  OMC_HOOK="$(dirname "$OMC_PATH")/../scripts/notify-hook.js"
  [ -f "$OMC_HOOK" ] || OMC_HOOK=""
fi
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
