#!/usr/bin/env python3
"""
Claude Code task-start hook - sends notification when a new task begins.
Triggered via UserPromptSubmit hook in Claude Code.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from route_context import resolve_route  # noqa: E402

LOG_FILE = "/tmp/claude_task_start_log.txt"


def log(msg: str):
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def notify_user(*, channel: str, chat_id: str, account: str, msg: str, kind: str = "", session_name: str = "", trace_id: str = "", route_file: str = "", event_type: str = "task-start") -> bool:
    try:
        cmd = [
            "openclaw", "message", "send",
            "--channel", channel,
            "--target", chat_id,
            "--message", msg,
            "--json",
        ]
        if account:
            cmd.extend(["--account", account])
        
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            stdout, stderr = proc.communicate(timeout=10)
            if proc.returncode != 0:
                log(f"notify failed: {stderr[:200]}")
                return False
            log(f"notify sent to {channel}:{chat_id}")
            return True
        except subprocess.TimeoutExpired:
            log("notify timeout")
            return False
    except Exception as e:
        log(f"notify error: {e}")
        return False


def main() -> int:
    try:
        # Read JSON from stdin
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        log(f"JSON parse error: {e}")
        return 0

    # Extract session info from the hook payload
    # UserPromptSubmit hook provides: prompt, local_seq, session_id, etc.
    prompt = payload.get("prompt", "")
    session_id = payload.get("session_id", "")
    local_seq = payload.get("local_seq", 0)
    
    # Try to find the managed session
    # Check for CLAUDE_AGENT_SESSION env var or use session_id
    session_name = os.environ.get("CLAUDE_AGENT_SESSION", "")
    
    # If no session name, try to resolve from route files by checking active sessions
    if not session_name:
        log(f"No session name found, skipping")
        return 0

    # Resolve route for this session
    route = resolve_route(session_name=session_name)
    
    if not route or route.get("managed") != "true":
        log(f"Unmanaged session: {session_name}")
        return 0

    # Check if this is a fresh task start (local_seq = 0 or 1)
    # This helps avoid duplicate notifications
    if local_seq > 1:
        log(f"Already processing (local_seq={local_seq}), skipping task-start")
        return 0

    chat_id = str(route.get("chat_id", ""))
    channel = str(route.get("channel", "discord"))
    account = str(route.get("account", ""))
    route_file = str(route.get("route_file", ""))
    workdir = str(route.get("workdir", ""))
    trace_id = str(route.get("trace_id", ""))

    log(f"Task start detected: session={session_name}, prompt={prompt[:50]}...")

    # Build notification message
    prompt_preview = prompt[:100].replace("\n", " ") if prompt else "New task"
    
    msg = (
        f"🚀 Claude Code 开始处理任务\n"
        f"🧭 session: {session_name}\n"
        f"📁 {workdir}\n"
        f"📝 {prompt_preview}..."
    )

    if notify_user(
        channel=channel,
        chat_id=chat_id,
        account=account,
        msg=msg,
        kind="claude",
        session_name=session_name,
        trace_id=trace_id,
        route_file=route_file,
        event_type="task-start",
    ):
        log(f"Task-start notification sent")
    else:
        log(f"Task-start notification failed")

    return 0


if __name__ == "__main__":
    sys.exit(main())
