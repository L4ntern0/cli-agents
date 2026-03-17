#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from typing import Any


def _find_message_id(obj: Any) -> str:
    if isinstance(obj, dict):
        for key in ("messageId", "message_id"):
            value = obj.get(key)
            if value:
                return str(value)
        for key in ("payload", "result", "data"):
            if key in obj:
                found = _find_message_id(obj.get(key))
                if found:
                    return found
        for value in obj.values():
            found = _find_message_id(value)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_message_id(item)
            if found:
                return found
    return ""


def main() -> int:
    text = sys.stdin.read()
    if not text.strip():
        return 0

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return 0
        try:
            payload = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return 0

    message_id = _find_message_id(payload)
    if message_id:
        print(message_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
