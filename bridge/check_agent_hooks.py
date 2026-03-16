#!/usr/bin/env python3
"""Preflight syntax/import health checks for codex-agent and claude-agent hooks."""

from __future__ import annotations

import argparse
import importlib.util
import py_compile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {
    "codex": {
        "hooks_dir": ROOT / "codex-agent" / "hooks",
        "files": [
            "route_context.py",
            "on_complete.py",
            "forward_to_session.py",
            "start_codex.sh",
            "stop_codex.sh",
            "pane_monitor.sh",
            "start_codex_openclaw.sh",
        ],
    },
    "claude": {
        "hooks_dir": ROOT / "claude-agent" / "hooks",
        "files": [
            "route_context.py",
            "on_complete.py",
            "forward_to_session.py",
            "start_claude.sh",
            "stop_claude.sh",
            "pane_monitor.sh",
        ],
    },
}


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


def check_target(name: str) -> int:
    cfg = TARGETS[name]
    hooks_dir: Path = cfg["hooks_dir"]
    failures: list[str] = []
    for rel in cfg["files"]:
        path = hooks_dir / rel
        if not path.exists():
            failures.append(f"missing: {path}")
            continue
        if path.suffix == ".py":
            errs = check_python_file(path)
        elif path.suffix == ".sh":
            errs = check_shell_file(path)
        else:
            errs = []
        for err in errs:
            failures.append(f"{path}: {err}")
    if failures:
        print(f"[{name}] FAILED")
        for item in failures:
            print(f" - {item}")
        return 1
    print(f"[{name}] OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Check agent hook files before launch")
    parser.add_argument("target", choices=["codex", "claude", "all"])
    args = parser.parse_args()

    targets = [args.target] if args.target != "all" else ["codex", "claude"]
    rc = 0
    for target in targets:
        rc |= check_target(target)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
