#!/usr/bin/env python3
"""
Codex notify hook — 只接管由 codex-agent 管理的 Codex 会话。
手动启动的 codex 也会命中全局 notify，但这里必须忽略，避免误把通知发到已有 route（如 ctf）。
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

LOG_FILE = "/tmp/codex_notify_log.txt"
REPLY_ROUTE_MAP = CURRENT_DIR.parent.parent / "bridge" / "reply_route_map.py"
EXTRACT_MESSAGE_ID = CURRENT_DIR.parent.parent / "bridge" / "extract_message_id.py"
DISCORD_MESSAGE_LIMIT = 1900


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


def _send_message(*, channel: str, chat_id: str, account: str, msg: str) -> tuple[bool, str]:
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
                return False, ""
            message_id = ""
            if stdout.strip():
                extract = subprocess.run(
                    [sys.executable, str(EXTRACT_MESSAGE_ID)],
                    input=stdout,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                message_id = extract.stdout.strip()
            return True, message_id
        except subprocess.TimeoutExpired:
            log("channel notify timeout (10s), process still running")
            return False, ""
    except Exception as e:
        log(f"channel notify error: {e}")
        return False, ""


def _find_split_at(text: str, available: int) -> int:
    part = text[:available]
    if len(text) <= available:
        return len(part)
    candidates = [part.rfind("\n```"), part.rfind("\n\n"), part.rfind("\n"), part.rfind(" ")]
    split_at = max(candidates)
    return split_at if split_at > available // 3 else len(part)


def _extract_open_fence(text: str) -> str:
    open_fence = "```"
    in_fence = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_fence:
                in_fence = False
                open_fence = "```"
            else:
                in_fence = True
                open_fence = stripped
    return open_fence if in_fence else ""


def split_discord_message(header: str, body: str, limit: int = DISCORD_MESSAGE_LIMIT) -> list[str]:
    header = header.rstrip()
    body = body.strip()

    if not body:
        return [header[:limit] if header else ""]

    raw_chunks: list[tuple[str, str]] = []
    remaining = body
    carry_fence = ""
    while remaining:
        current_prefix = ""
        if carry_fence:
            current_prefix += f"{carry_fence}\n"
        closing_reserve = 4 if carry_fence else 0
        available = max(1, limit - closing_reserve)

        split_at = _find_split_at(remaining, available)
        part = remaining[:split_at].rstrip()
        if not part:
            part = remaining[:available]

        open_fence = _extract_open_fence(part)
        chunk_body = part
        next_carry_fence = ""
        if open_fence:
            chunk_body = f"{part}\n```"
            next_carry_fence = open_fence

        raw_chunks.append((current_prefix, chunk_body))
        remaining = remaining[len(part):].lstrip()
        carry_fence = next_carry_fence

    total = len(raw_chunks)
    chunks: list[str] = []
    for idx, (prefix, chunk_body) in enumerate(raw_chunks, start=1):
        number_tag = f"[{idx}/{total}]"
        numbered_header = f"{header}\n{number_tag}" if header else number_tag
        current_prefix = f"{numbered_header}\n"
        if prefix:
            current_prefix += prefix
        chunks.append(f"{current_prefix}{chunk_body}"[:limit])

    return chunks


def notify_user(*, channel: str, chat_id: str, account: str, msg: str, kind: str = "", session_name: str = "", trace_id: str = "", route_file: str = "", event_type: str = "task-reply") -> bool:
    chunks = [msg] if len(msg) <= DISCORD_MESSAGE_LIMIT else split_discord_message("", msg, DISCORD_MESSAGE_LIMIT)
    ok_any = False
    mapped_message_ids: list[str] = []

    for chunk in chunks:
        ok, message_id = _send_message(channel=channel, chat_id=chat_id, account=account, msg=chunk)
        if not ok:
            return False
        ok_any = True
        if message_id:
            mapped_message_ids.append(message_id)

    if mapped_message_ids and kind and session_name:
        for message_id in mapped_message_ids:
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
        log(
            f"reply-map stored: count={len(mapped_message_ids)} first={mapped_message_ids[0]} "
            f"kind={kind} session={session_name} event={event_type}"
        )

    log(f"channel notify sent to {channel}:{chat_id} account={account or '-'} chunks={len(chunks)}")
    return ok_any


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


def build_message(header: str, body: str) -> str:
    return f"{header.rstrip()}\n{body.strip()}" if body.strip() else header.rstrip()


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

    summary = str(notification.get("last-assistant-message", "Turn Complete!"))
    cwd = str(notification.get("cwd", "unknown"))
    thread_id = str(notification.get("thread-id", "unknown"))
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

    allowed_agent = os.environ.get("CODING_AGENT_NAME", "coding")
    if route.get("agent_name") != allowed_agent:
        log(f"Ignoring non-coding agent trigger: agent_name={route.get('agent_name')}, expected={allowed_agent}, session={session_name}")
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

    header = (
        f"🔔 Codex 任务回复\n"
        f"🧭 session: {session_name}\n"
        f"📁 {cwd}\n"
        f"💬"
    )
    msg = build_message(header, summary)
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
