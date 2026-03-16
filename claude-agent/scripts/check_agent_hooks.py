#!/usr/bin/env python3
"""Preflight syntax/import health checks for claude-agent hooks."""

from __future__ import annotations

import argparse
import importlib.util
import py_compile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOKS_DIR = ROOT / "hooks"
FILES = [
    "route_context.py",
    "on_complete.py",
    "forward_to_session.py",
    "start_claude.sh",
    "stop_claude.sh",
    "pane_monitor.sh",
]


def load_module(path: Path) -> None:
    spec = importlib.util.spec_from_file_location(f"check_{path.stem}_{abs(hash(path))}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load spec: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)


def check_python_file(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        py_compile.compile(str(path), doraise=True)
    except Exception as e:
        errors.append(f"py_compile failed: {e}")
        return errors
    try:
        load_module(path)
    except Exception as e:
        errors.append(f"import failed: {e}")
    return errors


def check_shell_file(path: Path) -> list[str]:
    import subprocess

    proc = subprocess.run(["bash", "-n", str(path)], text=True, capture_output=True)
    if proc.returncode == 0:
        return []
    msg = proc.stderr.strip() or proc.stdout.strip() or f"bash -n failed ({proc.returncode})"
    return [msg]


def main() -> int:
    parser = argparse.ArgumentParser(description="Check claude-agent hook files before launch")
    parser.parse_args()

    failures: list[str] = []
    for rel in FILES:
        path = HOOKS_DIR / rel
        if not path.exists():
            failures.append(f"missing: {path}")
            continue
        errs = check_python_file(path) if path.suffix == ".py" else check_shell_file(path)
        for err in errs:
            failures.append(f"{path}: {err}")
    if failures:
        print("[claude] FAILED")
        for item in failures:
            print(f" - {item}")
        return 1
    print("[claude] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
