#!/usr/bin/env python3
"""Helpers for claude-agent per-session routing context."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

ROUTE_DIR = Path(os.environ.get("CLAUDE_AGENT_ROUTE_DIR", "/tmp/claude-agent-routes"))
SESSION_SAFE_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def _path_matches_workdir(cwd: str, workdir: str) -> bool:
    cwd_s = str(cwd or "").rstrip("/")
    workdir_s = str(workdir or "").rstrip("/")
    if not cwd_s or not workdir_s:
        return False
    return cwd_s == workdir_s or cwd_s.startswith(workdir_s + "/")


def _parse_timestamp(value: Any) -> float:
    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return 0.0


def _route_sort_key(payload: dict[str, Any], path: Path) -> tuple[float, float, int, str]:
    updated_at = _parse_timestamp(payload.get("updated_at"))
    try:
        mtime = path.stat().st_mtime
    except FileNotFoundError:
        mtime = 0.0
    workdir_len = len(str(payload.get("workdir") or "").rstrip("/"))
    return (updated_at, mtime, workdir_len, str(path))


def new_trace_id(prefix: str = "route") -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{prefix}-{timestamp}-{uuid4().hex[:12]}"


def route_trace_id(route: dict[str, Any] | None = None, *, prefix: str = "route") -> str:
    route_dict = route if isinstance(route, dict) else {}
    trace_id = str(route_dict.get("trace_id") or "").strip()
    return trace_id or new_trace_id(prefix=prefix)


def log_route_decision(event: str, **fields: Any) -> None:
    payload = {"event": event}
    for key, value in fields.items():
        if value is None:
            continue
        payload[key] = str(value)
    payload.setdefault("component", "claude-route-context")
    payload.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True), file=sys.stderr)


def ensure_route_dir() -> Path:
    ROUTE_DIR.mkdir(parents=True, exist_ok=True)
    return ROUTE_DIR


def sanitize_session_name(session_name: str) -> str:
    normalized = SESSION_SAFE_RE.sub("_", str(session_name or "").strip())
    return normalized or "default"


def route_file_for_session(session_name: str) -> Path:
    return ensure_route_dir() / f"{sanitize_session_name(session_name)}.json"


def route_file_candidates(*, session_name: str | None = None, cwd: str | None = None) -> list[Path]:
    candidates: list[tuple[int, float, Path]] = []
    if session_name:
        session_path = route_file_for_session(session_name)
        candidates.append((10**9, 0.0, session_path))
    if cwd:
        route_dir = ensure_route_dir()
        try:
            for path in route_dir.glob("*.json"):
                try:
                    payload = json.loads(path.read_text())
                except Exception:
                    continue
                workdir = str(payload.get("workdir") or "")
                if not _path_matches_workdir(str(cwd), workdir):
                    continue
                try:
                    mtime = path.stat().st_mtime
                except FileNotFoundError:
                    mtime = 0.0
                candidates.append((len(workdir.rstrip("/")), mtime, path))
        except FileNotFoundError:
            pass
    deduped: list[Path] = []
    seen: set[str] = set()
    for _, _, path in sorted(candidates, key=lambda item: (item[0], item[1]), reverse=True):
        key = str(path)
        if key not in seen:
            seen.add(key)
            deduped.append(path)
    return deduped


def load_route_context(*, session_name: str | None = None, cwd: str | None = None) -> dict[str, Any]:
    for candidate in route_file_candidates(session_name=session_name, cwd=cwd):
        try:
            payload = json.loads(candidate.read_text())
        except Exception:
            continue
        if isinstance(payload, dict):
            payload.setdefault("_route_file", str(candidate))
            payload.setdefault("trace_id", route_trace_id(payload))
            return payload
    return {}


def _normalize_chat_id(chat_id: str) -> str:
    """Strip channel prefix like 'channel:' or 'thread:' for comparison."""
    return chat_id.replace("channel:", "").replace("thread:", "").replace(":", "")


def find_route_by_chat(*, chat_id: str, channel: str | None = None) -> dict[str, Any]:
    if not chat_id:
        return {}
    route_dir = ensure_route_dir()
    normalized_chat_id = _normalize_chat_id(chat_id)
    candidates: list[dict[str, Any]] = []
    try:
        for path in route_dir.glob("*.json"):
            try:
                payload = json.loads(path.read_text())
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            route_chat_id = str(payload.get("chat_id") or "")
            if _normalize_chat_id(route_chat_id) != normalized_chat_id:
                continue
            if channel and str(payload.get("channel") or "") != str(channel):
                continue
            payload.setdefault("_route_file", str(path))
            payload.setdefault("trace_id", route_trace_id(payload))
            candidates.append(payload)
    except FileNotFoundError:
        return {}
    if not candidates:
        return {}
    selected = max(candidates, key=lambda item: _route_sort_key(item, Path(str(item.get("_route_file") or ""))))
    log_route_decision(
        "route-match-by-chat",
        trace_id=route_trace_id(selected),
        chat_id=chat_id,
        channel=channel or selected.get("channel") or "",
        selected_session=selected.get("session_name") or "",
        selected_route_file=selected.get("_route_file") or "",
        selected_updated_at=selected.get("updated_at") or "",
        candidate_count=len(candidates),
        strategy="latest-binding",
    )
    return selected


def resolve_route(*, session_name: str | None = None, cwd: str | None = None, chat_id: str | None = None, channel: str | None = None) -> dict[str, str]:
    route = (
        find_route_by_chat(chat_id=chat_id, channel=channel)
        if chat_id
        else load_route_context(session_name=session_name, cwd=cwd)
    )
    resolved = {
        "chat_id": str(route.get("chat_id") or os.environ.get("CLAUDE_AGENT_CHAT_ID") or os.environ.get("CODEX_AGENT_CHAT_ID") or "YOUR_CHAT_ID"),
        "channel": str(route.get("channel") or os.environ.get("CLAUDE_AGENT_CHANNEL") or os.environ.get("CODEX_AGENT_CHANNEL") or "telegram"),
        "account": str(route.get("account") or os.environ.get("CLAUDE_AGENT_ACCOUNT") or os.environ.get("CODEX_AGENT_ACCOUNT") or ""),
        "agent_name": str(route.get("agent_name") or os.environ.get("CLAUDE_AGENT_NAME") or os.environ.get("CODEX_AGENT_NAME") or "main"),
        "session_name": str(route.get("session_name") or session_name or os.environ.get("CLAUDE_AGENT_SESSION") or ""),
        "workdir": str(route.get("workdir") or cwd or ""),
        "route_file": str(route.get("_route_file") or ""),
        "trace_id": route_trace_id(route, prefix="route"),
        "updated_at": str(route.get("updated_at") or ""),
        "managed": "true" if route else "false",
    }
    log_route_decision(
        "resolve-route",
        trace_id=resolved["trace_id"],
        session_name=resolved["session_name"],
        chat_id=resolved["chat_id"],
        channel=resolved["channel"],
        route_file=resolved["route_file"],
        managed=resolved["managed"],
        source="chat" if chat_id else "context",
        cwd=cwd or "",
    )
    return resolved
