#!/usr/bin/env python3
"""Forward a thread reply to the active Claude Code tmux session bound to that thread."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from route_context import log_route_decision, resolve_route, route_trace_id  # noqa: E402


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True)


def tmux_has_session(session_name: str) -> bool:
    proc = run(["tmux", "has-session", "-t", session_name])
    return proc.returncode == 0


def send_prompt(session_name: str, text: str) -> None:
    subprocess.run(["tmux", "send-keys", "-t", session_name, text], check=True)
    subprocess.run(["sleep", "1"], check=True)
    subprocess.run(["tmux", "send-keys", "-t", session_name, "Enter"], check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Forward Discord thread reply to Claude session")
    parser.add_argument("--chat-id", required=True)
    parser.add_argument("--channel", required=True)
    parser.add_argument("--message", required=True)
    parser.add_argument("--trace-id", default="")
    parser.add_argument("--session-name", default="")
    args = parser.parse_args()

    route = resolve_route(session_name=args.session_name) if args.session_name else resolve_route(chat_id=args.chat_id, channel=args.channel)
    trace_id = args.trace_id or route_trace_id(route, prefix="thread-route")
    log_route_decision(
        "forward-request",
        trace_id=trace_id,
        channel=args.channel,
        chat_id=args.chat_id,
        session_name=route.get("session_name") or "",
        route_file=route.get("route_file") or "",
    )
    if route.get("managed") != "true" or not route.get("session_name"):
        log_route_decision(
            "forward-missing-route",
            trace_id=trace_id,
            channel=args.channel,
            chat_id=args.chat_id,
        )
        print(f"No active Claude session is bound to {args.channel}:{args.chat_id}", file=sys.stderr)
        return 2

    session_name = route["session_name"]
    if not tmux_has_session(session_name):
        log_route_decision(
            "forward-missing-session",
            trace_id=trace_id,
            channel=args.channel,
            chat_id=args.chat_id,
            session_name=session_name,
        )
        print(f"Bound Claude tmux session not found: {session_name}", file=sys.stderr)
        return 3

    send_prompt(session_name, args.message)
    log_route_decision(
        "forward-success",
        trace_id=trace_id,
        channel=args.channel,
        chat_id=args.chat_id,
        session_name=session_name,
        route_file=route.get("route_file") or "",
    )
    print(f"已转发到 {session_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
