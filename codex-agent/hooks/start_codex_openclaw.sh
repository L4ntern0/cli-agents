#!/bin/bash
# OpenClaw-aware Codex launcher
# 用法:
#   ./start_codex_openclaw.sh <session-name> <workdir> [--approval|--yolo]
# 来源参数优先级：
#   1. flags: --source-chat-id / --source-channel / --source-agent-name
#   2. env:   CODEX_AGENT_SOURCE_*
#   3. env:   OPENCLAW_CHAT_ID / OPENCLAW_CHANNEL / OPENCLAW_AGENT_NAME / OPENCLAW_ACCOUNT_ID
#
# 设计目标：让 OpenClaw 在当前消息上下文里调用时，默认把“当前消息来源”传给 start_codex.sh；
# 即使手动启动时未显式传 source chat，也尽量默认挂到当前频道。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SESSION="${1:-}"
WORKDIR="${2:-}"
shift 2 || true

if [ -z "$SESSION" ] || [ -z "$WORKDIR" ]; then
  echo "Usage: $0 <session-name> <workdir> [--approval|--yolo] [--source-chat-id <id>] [--source-channel <channel>] [--source-agent-name <name>]"
  exit 1
fi

SOURCE_CHAT_ID="${CODEX_AGENT_SOURCE_CHAT_ID:-${OPENCLAW_CHAT_ID:-}}"
SOURCE_CHANNEL="${CODEX_AGENT_SOURCE_CHANNEL:-${OPENCLAW_CHANNEL:-}}"
SOURCE_AGENT_NAME="${CODEX_AGENT_SOURCE_AGENT_NAME:-${OPENCLAW_AGENT_NAME:-${CODEX_AGENT_NAME:-main}}}"
SOURCE_ACCOUNT="${CODEX_AGENT_SOURCE_ACCOUNT:-${OPENCLAW_ACCOUNT_ID:-${CODEX_AGENT_ACCOUNT:-}}}"
PASS_THROUGH_ARGS=()

while [ "$#" -gt 0 ]; do
  case "$1" in
    --source-chat-id)
      SOURCE_CHAT_ID="${2:?missing value for --source-chat-id}"
      shift 2
      ;;
    --source-channel)
      SOURCE_CHANNEL="${2:?missing value for --source-channel}"
      shift 2
      ;;
    --source-agent-name)
      SOURCE_AGENT_NAME="${2:?missing value for --source-agent-name}"
      shift 2
      ;;
    *)
      PASS_THROUGH_ARGS+=("$1")
      shift
      ;;
  esac
done

if [ -n "$SOURCE_CHAT_ID" ]; then
  export CODEX_AGENT_SOURCE_CHAT_ID="$SOURCE_CHAT_ID"
fi

if [ -n "$SOURCE_CHANNEL" ]; then
  export CODEX_AGENT_SOURCE_CHANNEL="$SOURCE_CHANNEL"
fi

export CODEX_AGENT_SOURCE_AGENT_NAME="$SOURCE_AGENT_NAME"
export CODEX_AGENT_SOURCE_ACCOUNT="$SOURCE_ACCOUNT"

exec bash "$SCRIPT_DIR/start_codex.sh" "$SESSION" "$WORKDIR" "${PASS_THROUGH_ARGS[@]}"
