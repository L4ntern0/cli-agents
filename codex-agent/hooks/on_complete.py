#!/usr/bin/env python3
"""
Codex notify hook — 只接管由 codex-agent 管理的 Codex 会话。
手动启动的 codex 也会命中全局 notify，但这里必须忽略，避免误把通知发到已有 route（如 ctf）。
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from route_context import resolve_route  # noqa: E402

LOG_FILE = "/tmp/codex_notify_log.txt"
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
                log(f"channel notify failed (exit {proc.returncode}): {stderr[:200]}")
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
            log("channel notify timeout (10s), process still running")
        log(f"channel notify sent to {channel}:{chat_id} account={account or '-'}")
        return True
    except Exception as e:
        log(f"channel notify error: {e}")
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


def extract_session_name(notification: dict[str, Any]) -> str:
    session_name = str(notification.get("session_name") or "").strip()
    if session_name:
        return session_name
    input_messages = notification.get("input-messages") or []
    if isinstance(input_messages, list):
        for message in reversed(input_messages):
            if not isinstance(message, str):
                continue
            if "CODEX_AGENT_SESSION=" in message:
                tail = message.split("CODEX_AGENT_SESSION=", 1)[1]
                return tail.split()[0].strip()
    return ""


def main() -> int:
    if len(sys.argv) < 2:
        return 0

    try:
        notification = json.loads(sys.argv[1])
    except json.JSONDecodeError as e:
        log(f"JSON parse error: {e}")
        return 1

    if notification.get("type") != "agent-turn-complete":
        return 0

    summary = notification.get("last-assistant-message", "Turn Complete!")
    cwd = notification.get("cwd", "unknown")
    thread_id = notification.get("thread-id", "unknown")
    session_name = extract_session_name(notification)

    route: dict[str, Any] = {}
    if session_name:
        route = resolve_route(session_name=session_name)
    else:
        route = resolve_route(cwd=cwd)
        session_name = str(route.get("session_name") or "").strip()
        if route.get("managed") == "true" and route.get("route_file"):
            log(f"Recovered managed Codex session by cwd fallback: session={session_name}, cwd={cwd}, thread={thread_id}")

    if not session_name or route.get("managed") != "true" or not route.get("route_file"):
        log(f"Ignoring unmanaged Codex turn: missing session marker, cwd={cwd}, thread={thread_id}")
        return 0

    chat_id = str(route["chat_id"])
    channel = str(route["channel"])
    account = str(route["account"])
    agent_name = str(route["agent_name"])
    trace_id = str(route.get("trace_id") or "")
    route_file = str(route.get("route_file") or "")

    log(f"Codex turn complete: thread={thread_id}, cwd={cwd}, session={session_name}")
    log(f"Routing via {channel}:{chat_id} account={account or '-'} route_file={route_file or 'default-env'}")
    log(f"Summary: {summary[:200]}")

    msg = (
        f"🔔 Codex 任务回复\n"
        f"🧭 session: {session_name}\n"
        f"📁 {cwd}\n"
        f"💬 {summary}"
    )
    notify_ok = notify_user(
        channel=channel,
        chat_id=chat_id,
        account=account,
        msg=msg,
        kind="codex",
        session_name=session_name,
        trace_id=trace_id,
        route_file=route_file,
        event_type="task-reply",
    )

    agent_msg = (
        f"[Codex Hook] 任务完成，请检查输出并汇报。\n"
        f"session: {session_name}\n"
        f"cwd: {cwd}\n"
        f"thread: {thread_id}\n"
        f"summary: {summary}"
    )
    agent_ok = wake_agent(channel=channel, account=account, agent_name=agent_name, msg=agent_msg)

    if not notify_ok and not agent_ok:
        log("⚠️ Both channel notify and agent wake failed!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
