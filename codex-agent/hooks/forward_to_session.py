#!/usr/bin/env python3
"""Forward a thread reply to the active Codex tmux session bound to that thread."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from route_context import log_route_decision, resolve_route, route_trace_id  # noqa: E402

READY_TIMEOUT_SECONDS = 20.0
READY_POLL_INTERVAL_SECONDS = 0.5
CAPTURE_LINES = 80
READY_PATTERNS = (
    " codex",
    "›",
    "❯",
    " > ",
    " Do you want to proceed?",
    "Allow once",
    "Allow always",
)


def run(cmd: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, check=check)


def tmux_has_session(session_name: str) -> bool:
    proc = run(["tmux", "has-session", "-t", session_name])
    return proc.returncode == 0


def resolve_tmux_target(session_name: str) -> str:
    proc = run(
        [
            "tmux",
            "list-panes",
            "-t",
            session_name,
            "-F",
            "#{session_name}:#{window_index}.#{pane_index} #{pane_active} #{pane_title} #{pane_current_command}",
        ],
        check=True,
    )
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError(f"No tmux panes found for session: {session_name}")

    active_target = ""
    fallback_target = ""
    for line in lines:
        target, *rest = line.split(" ", 1)
        fields = rest[0].split(" ") if rest else []
        pane_active = fields[0] if fields else "0"
        if not fallback_target:
            fallback_target = target
        if pane_active == "1":
            active_target = target
            break
    return active_target or fallback_target


def capture_pane(target: str, *, lines: int = CAPTURE_LINES) -> str:
    proc = run(["tmux", "capture-pane", "-t", target, "-p", "-S", f"-{lines}"])
    return proc.stdout if proc.returncode == 0 else ""


def pane_looks_ready(output: str) -> bool:
    text = output or ""
    return any(pattern in text for pattern in READY_PATTERNS)


def wait_until_ready(target: str, *, timeout_seconds: float = READY_TIMEOUT_SECONDS) -> tuple[bool, str]:
    deadline = time.monotonic() + timeout_seconds
    last_output = ""
    while time.monotonic() < deadline:
        last_output = capture_pane(target)
        if pane_looks_ready(last_output):
            return True, last_output
        time.sleep(READY_POLL_INTERVAL_SECONDS)
    return False, last_output


def send_prompt(target: str, text: str) -> None:
    subprocess.run(["tmux", "send-keys", "-t", target, "-l", text], check=True)
    time.sleep(0.2)
    subprocess.run(["tmux", "send-keys", "-t", target, "Enter"], check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Forward Discord thread reply to Codex session")
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
        print(f"No active Codex session is bound to {args.channel}:{args.chat_id}", file=sys.stderr)
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
        print(f"Bound Codex tmux session not found: {session_name}", file=sys.stderr)
        return 3

    try:
        target = resolve_tmux_target(session_name)
    except Exception as exc:
        log_route_decision(
            "forward-target-resolution-failed",
            trace_id=trace_id,
            channel=args.channel,
            chat_id=args.chat_id,
            session_name=session_name,
            error=str(exc),
        )
        print(f"Failed to resolve tmux target for {session_name}: {exc}", file=sys.stderr)
        return 4

    ready, last_output = wait_until_ready(target)
    if not ready:
        log_route_decision(
            "forward-not-ready-timeout",
            trace_id=trace_id,
            channel=args.channel,
            chat_id=args.chat_id,
            session_name=session_name,
            target=target,
            preview=(last_output or "")[-400:],
        )
        print(f"Codex session not ready for input yet: {session_name}", file=sys.stderr)
        return 5

    send_prompt(target, args.message)
    log_route_decision(
        "forward-success",
        trace_id=trace_id,
        channel=args.channel,
        chat_id=args.chat_id,
        session_name=session_name,
        route_file=route.get("route_file") or "",
        target=target,
    )
    print(f"已转发到 {session_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
