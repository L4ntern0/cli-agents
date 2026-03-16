#!/usr/bin/env python3
"""Detect and forward a thread reply to a bound codex-agent or claude-agent tmux session.

Exit codes:
  0: forwarded successfully
  2: no active bound session for this thread
  4: bound session missing/inactive
  5: explicit @Coder mention; keep for OpenClaw
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
CODEX_HOOKS = ROOT / "skills" / "cli-agents" / "codex-agent" / "hooks"
CLAUDE_HOOKS = ROOT / "skills" / "cli-agents" / "claude-agent" / "hooks"
REPLY_ROUTE_MAP = ROOT / "skills" / "cli-agents" / "bridge" / "reply_route_map.py"


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module {module_name} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


codex_route_context = load_module("codex_route_context", CODEX_HOOKS / "route_context.py")
claude_route_context = load_module("claude_route_context", CLAUDE_HOOKS / "route_context.py")


def log_event(event: str, **fields: Any) -> None:
    payload = {"event": event, "component": "agent-session-router", "timestamp": datetime.now(timezone.utc).isoformat()}
    for key, value in fields.items():
        if value is None:
            continue
        payload[key] = str(value)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True), file=sys.stderr)


def tmux_has_session(session_name: str) -> bool:
    proc = subprocess.run(["tmux", "has-session", "-t", session_name], text=True, capture_output=True)
    return proc.returncode == 0


def candidate_sort_key(candidate: dict[str, str]) -> tuple[float, float, str, str]:
    updated_at = candidate.get("updated_at_ts") or "0"
    mtime = candidate.get("route_mtime") or "0"
    return (float(updated_at), float(mtime), candidate.get("kind") or "", candidate.get("session_name") or "")


def lookup_reply_target(message_id: str) -> dict[str, str]:
    if not message_id:
        return {}
    proc = subprocess.run(
        [sys.executable, str(REPLY_ROUTE_MAP), "get", "--message-id", message_id],
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return {}
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {}
    result = {k: str(v) for k, v in payload.items() if v is not None}
    result["active"] = "true" if result.get("session_name") and tmux_has_session(result["session_name"]) else "false"
    return result


def resolve_candidates(chat_id: str, channel: str, trace_id: str) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []

    for kind, module in (("codex", codex_route_context), ("claude", claude_route_context)):
        route = module.resolve_route(chat_id=chat_id, channel=channel)
        active = "true" if route.get("session_name") and tmux_has_session(route["session_name"]) else "false"
        candidate = {
            "kind": kind,
            "session_name": str(route.get("session_name") or ""),
            "route_file": str(route.get("route_file") or ""),
            "trace_id": str(route.get("trace_id") or trace_id),
            "updated_at": str(route.get("updated_at") or ""),
            "updated_at_ts": str(module._parse_timestamp(route.get("updated_at"))),
            "route_mtime": "0",
            "managed": str(route.get("managed") or "false"),
            "active": active,
        }
        route_file = candidate["route_file"]
        if route_file:
            try:
                candidate["route_mtime"] = str(Path(route_file).stat().st_mtime)
            except FileNotFoundError:
                candidate["route_mtime"] = "0"
        log_event(
            "candidate-evaluated",
            trace_id=trace_id,
            candidate_kind=kind,
            candidate_session=candidate["session_name"],
            candidate_route_file=candidate["route_file"],
            candidate_route_trace_id=candidate["trace_id"],
            candidate_updated_at=candidate["updated_at"],
            candidate_managed=candidate["managed"],
            candidate_active=candidate["active"],
            channel=channel,
            chat_id=chat_id,
        )
        if candidate["managed"] == "true" and candidate["session_name"] and active == "true":
            candidates.append(candidate)

    return sorted(candidates, key=candidate_sort_key, reverse=True)


def forward(kind: str, chat_id: str, channel: str, message: str, trace_id: str, session_name: str = "") -> int:
    script = CODEX_HOOKS / "forward_to_session.py" if kind == "codex" else CLAUDE_HOOKS / "forward_to_session.py"
    cmd = [sys.executable, str(script), "--chat-id", chat_id, "--channel", channel, "--message", message, "--trace-id", trace_id]
    if session_name:
        cmd.extend(["--session-name", session_name])
    proc = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
    )
    if proc.stdout.strip():
        print(proc.stdout.strip())
    if proc.stderr.strip():
        print(proc.stderr.strip(), file=sys.stderr)
    return proc.returncode


DISCORD_MENTION_RE = re.compile(r"<@!?\d+>|<@&\d+>")


def should_keep_for_openclaw(message: str) -> bool:
    text = str(message or "")
    return bool(DISCORD_MENTION_RE.search(text))


def main() -> int:
    parser = argparse.ArgumentParser(description="Route a thread reply into a bound agent tmux session")
    parser.add_argument("--chat-id", required=True)
    parser.add_argument("--channel", required=True)
    parser.add_argument("--message", required=True)
    parser.add_argument("--trace-id", default="")
    parser.add_argument("--reply-to-message-id", default="")
    args = parser.parse_args()

    trace_id = args.trace_id or codex_route_context.new_trace_id(prefix="thread-route")
    reply_to_message_id = (
        args.reply_to_message_id
        or os.environ.get("OPENCLAW_REPLY_TO_MESSAGE_ID", "")
        or os.environ.get("OPENCLAW_REFERENCED_MESSAGE_ID", "")
        or os.environ.get("OPENCLAW_QUOTED_MESSAGE_ID", "")
    )

    if should_keep_for_openclaw(args.message):
        log_event("kept-for-openclaw", trace_id=trace_id, channel=args.channel, chat_id=args.chat_id, reason="explicit-mention")
        print("Explicit @Coder mention detected; do not forward to codex-agent/claude-agent session.", file=sys.stderr)
        return 5

    if reply_to_message_id:
        mapped = lookup_reply_target(reply_to_message_id)
        log_event(
            "reply-target-evaluated",
            trace_id=trace_id,
            channel=args.channel,
            chat_id=args.chat_id,
            reply_to_message_id=reply_to_message_id,
            mapped_kind=mapped.get("kind") or "",
            mapped_session=mapped.get("session_name") or "",
            mapped_active=mapped.get("active") or "false",
            mapped_event_type=mapped.get("event_type") or "",
        )
        if mapped and mapped.get("active") == "true" and mapped.get("kind") in {"codex", "claude"}:
            log_event(
                "selected-reply-target-binding",
                trace_id=trace_id,
                channel=args.channel,
                chat_id=args.chat_id,
                reply_to_message_id=reply_to_message_id,
                selected_kind=mapped.get("kind") or "",
                selected_session=mapped.get("session_name") or "",
                selected_route_file=mapped.get("route_file") or "",
                strategy="reply-target-message-id",
            )
            return forward(mapped["kind"], args.chat_id, args.channel, args.message, trace_id, session_name=mapped.get("session_name", ""))

    candidates = resolve_candidates(args.chat_id, args.channel, trace_id)
    if not candidates:
        log_event("no-active-binding", trace_id=trace_id, channel=args.channel, chat_id=args.chat_id)
        print(f"No active bound codex-agent or claude-agent session for {args.channel}:{args.chat_id}", file=sys.stderr)
        return 2

    candidate = candidates[0]
    loser_summary = ", ".join(
        f"{item['kind']}:{item['session_name']}@{item['updated_at'] or 'unknown'}"
        for item in candidates[1:]
    )
    log_event(
        "selected-binding",
        trace_id=trace_id,
        channel=args.channel,
        chat_id=args.chat_id,
        selected_kind=candidate["kind"],
        selected_session=candidate["session_name"],
        selected_route_file=candidate["route_file"],
        selected_route_trace_id=candidate["trace_id"],
        selected_updated_at=candidate["updated_at"],
        strategy="latest-binding",
        competing_bindings=len(candidates),
        shadowed_bindings=loser_summary,
    )
    return forward(candidate["kind"], args.chat_id, args.channel, args.message, trace_id)


if __name__ == "__main__":
    raise SystemExit(main())
