#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAP_FILE = Path("/tmp/openclaw-agent-reply-map.jsonl")


def _append(record: dict[str, Any]) -> None:
    MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
    with MAP_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def put_mapping(*, message_id: str, kind: str, session_name: str, channel: str, chat_id: str, trace_id: str = "", route_file: str = "", event_type: str = "task-reply") -> None:
    if not message_id or not kind or not session_name:
        return
    _append({
        "message_id": str(message_id),
        "kind": str(kind),
        "session_name": str(session_name),
        "channel": str(channel),
        "chat_id": str(chat_id),
        "trace_id": str(trace_id or ""),
        "route_file": str(route_file or ""),
        "event_type": str(event_type or "task-reply"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })


def get_mapping(message_id: str) -> dict[str, Any]:
    if not message_id or not MAP_FILE.exists():
        return {}
    found: dict[str, Any] = {}
    with MAP_FILE.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(obj.get("message_id") or "") == str(message_id):
                found = obj
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description="Store or lookup reply-target to agent-session mappings")
    sub = parser.add_subparsers(dest="cmd", required=True)

    put = sub.add_parser("put")
    put.add_argument("--message-id", required=True)
    put.add_argument("--kind", required=True)
    put.add_argument("--session-name", required=True)
    put.add_argument("--channel", required=True)
    put.add_argument("--chat-id", required=True)
    put.add_argument("--trace-id", default="")
    put.add_argument("--route-file", default="")
    put.add_argument("--event-type", default="task-reply")

    get = sub.add_parser("get")
    get.add_argument("--message-id", required=True)

    args = parser.parse_args()
    if args.cmd == "put":
        put_mapping(
            message_id=args.message_id,
            kind=args.kind,
            session_name=args.session_name,
            channel=args.channel,
            chat_id=args.chat_id,
            trace_id=args.trace_id,
            route_file=args.route_file,
            event_type=args.event_type,
        )
        print("OK")
        return 0

    result = get_mapping(args.message_id)
    if result:
        print(json.dumps(result, ensure_ascii=False))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
