#!/usr/bin/env python3
"""Check for cross-agent thread route conflicts before starting a managed Claude session."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

CODEX_ROUTE_DIR = Path("/tmp/codex-agent-routes")
CLAUDE_ROUTE_DIR = Path("/tmp/claude-agent-routes")


def tmux_has_session(session_name: str) -> bool:
    if not session_name:
        return False
    proc = subprocess.run(["tmux", "has-session", "-t", session_name], text=True, capture_output=True)
    return proc.returncode == 0


def load_matches(route_dir: Path, *, chat_id: str, channel: str) -> list[dict[str, str]]:
    matches: list[dict[str, str]] = []
    if not route_dir.exists():
        return matches
    for path in sorted(route_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text())
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        if str(payload.get("chat_id") or "") != str(chat_id):
            continue
        if str(payload.get("channel") or "") != str(channel):
            continue
        session_name = str(payload.get("session_name") or "")
        matches.append({
            "route_file": str(path),
            "session_name": session_name,
            "account": str(payload.get("account") or ""),
            "agent_name": str(payload.get("agent_name") or ""),
            "active": "true" if tmux_has_session(session_name) else "false",
        })
    return matches


def main() -> int:
    parser = argparse.ArgumentParser(description="Check cross-agent thread route conflicts")
    parser.add_argument("--session", required=True)
    parser.add_argument("--chat-id", required=True)
    parser.add_argument("--channel", required=True)
    args = parser.parse_args()

    conflicts = [m for m in load_matches(CODEX_ROUTE_DIR, chat_id=args.chat_id, channel=args.channel) if m["active"] == "true"]
    if not conflicts:
        print(f"OK: no active codex-agent route conflicts for {args.channel}:{args.chat_id}")
        return 0

    print(f"CONFLICT: active codex-agent route already bound to {args.channel}:{args.chat_id}")
    for item in conflicts:
        print(
            " - "
            f"session={item['session_name']} account={item['account'] or 'unset'} "
            f"agent={item['agent_name'] or 'unset'} route={item['route_file']}"
        )
    print(f"Refusing to start claude-agent session {args.session} to avoid dual binding.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
