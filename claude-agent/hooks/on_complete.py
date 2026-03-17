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
                log(f"notify failed (exit {proc.returncode}): {stderr[:200]}")
                return False, ""
            message_id = ""
            if stdout.strip():
                try:
                    payload: dict[str, Any] = json.loads(stdout)
                    message_id = str(payload.get("messageId") or "")
                except json.JSONDecodeError:
                    pass
            return True, message_id
        except subprocess.TimeoutExpired:
            log("notify timeout (10s), process still running")
            return False, ""
    except Exception as e:
        log(f"notify error: {e}")
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
    first_message_id = ""

    for idx, chunk in enumerate(chunks):
        ok, message_id = _send_message(channel=channel, chat_id=chat_id, account=account, msg=chunk)
        if not ok:
            return False
        ok_any = True
        if idx == 0:
            first_message_id = message_id

    if first_message_id and kind and session_name:
        _store_reply_mapping(
            message_id=first_message_id,
            kind=kind,
            session_name=session_name,
            channel=channel,
            chat_id=chat_id,
            trace_id=trace_id,
            route_file=route_file,
            event_type=event_type,
        )
        log(f"reply-map stored: message_id={first_message_id} kind={kind} session={session_name} event={event_type}")

    log(f"notify sent to {channel}:{chat_id} chunks={len(chunks)}")
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
            return str(val)[:12000]

    transcript = notification.get("transcript", [])
    if isinstance(transcript, list) and transcript:
        last = transcript[-1]
        if isinstance(last, dict):
            for k in ("content", "text", "message"):
                if k in last:
                    return str(last[k])[:12000]
            return str(last)[:12000]
        return str(last)[:12000]

    return "Turn Complete!"


def build_message(header: str, body: str) -> str:
    return f"{header.rstrip()}\n{body.strip()}" if body.strip() else header.rstrip()


def build_task_reply_message(*, session_name: str, cwd: str, trace_id: str, summary: str) -> str:
    header = (
        f"{SEPARATOR}\n"
        f"🔔 Claude Code 任务回复\n"
        f"🧭 session: {session_name}\n"
        f"📁 workdir: {cwd}\n"
        f"🧵 trace_id: {trace_id}\n"
        f"{SEPARATOR}\n"
        f"💬"
    )
    return build_message(header, summary)


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

    allowed_agent = os.environ.get("CODING_AGENT_NAME", "coding")
    if route.get("agent_name") != allowed_agent:
        log(f"Ignoring non-coding agent trigger: agent_name={route.get('agent_name')}, expected={allowed_agent}, cwd={cwd}")
        return 0

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
