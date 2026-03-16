# cli-agents

A unified repository for terminal-driven CLI agent skills used with OpenClaw and agent-deck.

## Layout

- `codex-agent/` — Codex tmux-based agent skill
- `claude-agent/` — Claude Code tmux-based agent skill
- `bridge/` — shared routing utilities
  - `agent_session_router.py`
  - `reply_route_map.py`

## Purpose

This repository consolidates the CLI agent runtime into a single versioned unit so that:

- `codex-agent` and `claude-agent` can evolve together
- shared bridge utilities live in one place
- agent-deck can integrate against a stable directory layout

## Path conventions

Prefer relative paths inside scripts where practical.

Current canonical paths inside `workspace-coding`:

- `skills/cli-agents/codex-agent/...`
- `skills/cli-agents/claude-agent/...`
- `skills/cli-agents/bridge/...`

## Notes

- Route state remains under `/tmp/codex-agent-routes` and `/tmp/claude-agent-routes`
- The bridge reply map is implemented by `bridge/reply_route_map.py`
- Nested `.git` directories from the old split repos were removed when consolidating this repository
