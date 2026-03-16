#!/usr/bin/env python3
"""
Claude Code Stop hook — Claude Code 完成 turn 时：
1. 给用户发通知（Telegram/Discord 等）
2. 唤醒 OpenClaw agent（去检查输出）
3. 记录 outbound task-reply messageId -> session 映射，供 reply-target 路由复用
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

LOG_FILE = "/tmp/claude_notify_log.txt"
SEPARATOR = "──────────────────"
REPLY_ROUTE_MAP = CURRENT_DIR.parent.parent / "bridge" / "reply_route_map.py"


def log(msg: str):
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def _store_reply_mapping(*, message_id: str, kind: str, session_name: str, channel: str, chat_id: str, trace_id: str = "", route_file: str = "", event_type: str = "task-reply") -> None:
    try:
        subprocess.run([
            sys.executable,
            str(REPLY_ROUTE_MAP),
            "put",
            "--message-id", message_id,
            "--kind", kind,
            "--session-name", session_name,
            "--channel", channel,
            "--chat-id", chat_id,
            "--trace-id", trace_id,
            "--route-file", route_file,
            "--event-type", event_type,
        ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        log(f"reply-map store error: {e}")


def notify_user(*, channel: str, chat_id: str, account: str, msg: str, kind: str = "", session_name: str = "", trace_id: str = "", route_file: str = "", event_type: str = "task-reply") -> bool:
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
                log(f"notify failed (exit {proc.returncode}): {stderr[:200]}")
                return False
            message_id = ""
            if stdout.strip():
                try:
                    payload: dict[str, Any] = json.loads(stdout)
                    message_id = str(payload.get("messageId") or "")
                except json.JSONDecodeError:
                    pass
            if message_id and kind and session_name:
                _store_reply_mapping(
                    message_id=message_id,
                    kind=kind,
                    session_name=session_name,
                    channel=channel,
                    chat_id=chat_id,
                    trace_id=trace_id,
                    route_file=route_file,
                    event_type=event_type,
                )
                log(f"reply-map stored: message_id={message_id} kind={kind} session={session_name} event={event_type}")
        except subprocess.TimeoutExpired:
            log("notify timeout (10s), process still running")
        log(f"notify sent to {channel}:{chat_id}")
        return True
    except Exception as e:
        log(f"notify error: {e}")
        return False


def wake_agent(*, channel: str, account: str, agent_name: str, msg: str) -> bool:
    try:
        cmd = [
            "openclaw", "agent",
            "--agent", agent_name,
            "--message", msg,
            "--channel", channel,
            "--timeout", "120",
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log(f"agent wake fired (pid {proc.pid})")
        return True
    except Exception as e:
        log(f"agent wake error: {e}")
        return False


def extract_summary(notification: dict[str, Any]) -> str:
    log(f"Payload keys: {list(notification.keys())}")
    for key in (
        "last_assistant_message",
        "last_message",
        "message",
        "summary",
        "transcript_summary",
        "result",
    ):
        val = notification.get(key)
        if val and isinstance(val, str) and val not in ("end_turn", "unknown"):
            return str(val)[:1000]

    transcript = notification.get("transcript", [])
    if isinstance(transcript, list) and transcript:
        last = transcript[-1]
        if isinstance(last, dict):
            for k in ("content", "text", "message"):
                if k in last:
                    return str(last[k])[:1000]
            return str(last)[:1000]
        return str(last)[:1000]

    return "Turn Complete!"


def build_task_reply_message(*, session_name: str, cwd: str, trace_id: str, summary: str) -> str:
    return (
        f"{SEPARATOR}\n"
        f"🔔 Claude Code 任务回复\n"
        f"🧭 session: {session_name}\n"
        f"📁 workdir: {cwd}\n"
        f"🧵 trace_id: {trace_id}\n"
        f"{SEPARATOR}\n"
        f"💬 {summary}"
    )


def main() -> int:
    try:
        raw = sys.stdin.read()
    except Exception:
        raw = ""

    if not raw.strip():
        log("Empty stdin, skipping")
        return 0

    try:
        notification = json.loads(raw)
    except json.JSONDecodeError as e:
        log(f"JSON parse error: {e}")
        return 1

    session_id = str(notification.get("session_id", "unknown"))
    hook_event = str(notification.get("hook_event_name", "Stop"))
    cwd = str(notification.get("cwd", os.getcwd()))
    summary = extract_summary(notification)
    route = resolve_route(cwd=cwd)
    chat_id = str(route["chat_id"])
    channel = str(route["channel"])
    account = str(route["account"])
    agent_name = str(route["agent_name"])
    trace_id = str(route["trace_id"])
    route_file = str(route.get("route_file") or "")
    session_name = str(route.get("session_name") or os.path.basename(cwd) or "unknown")

    log(f"Claude Code {hook_event}: session={session_id}, cwd={cwd}")
    log(f"Routing via {channel}:{chat_id} account={account or '-'} route_file={route_file or 'default-env'} trace_id={trace_id}")
    log(f"Summary: {summary[:200]}")

    msg = build_task_reply_message(session_name=session_name, cwd=cwd, trace_id=trace_id, summary=summary)
    notify_ok = notify_user(
        channel=channel,
        chat_id=chat_id,
        account=account,
        msg=msg,
        kind="claude",
        session_name=session_name,
        trace_id=trace_id,
        route_file=route_file,
        event_type="task-reply",
    )

    agent_msg = (
        f"[Claude Hook] 任务完成，请检查输出并汇报。\n"
        f"cwd: {cwd}\n"
        f"session: {session_id}\n"
        f"summary: {summary}"
    )
    agent_ok = wake_agent(channel=channel, account=account, agent_name=agent_name, msg=agent_msg)

    if not notify_ok and not agent_ok:
        log("⚠️ Both notify and agent wake failed!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
