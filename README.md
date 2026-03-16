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

## Thread Message Auto-Forward (Agent-Level Implementation)

The auto-forward is currently implemented via **AGENTS.md rules** that the OpenClaw agent follows:

**Critical Rule**: When a message arrives in a Discord thread that has an active bound `codex-agent` or `claude-agent` tmux session, the agent **MUST** first attempt to forward it via the unified router before answering itself.

### How It Works

1. Agent receives a thread message
2. Agent invokes the unified router:
   ```bash
   python3 skills/cli-agents/bridge/agent_session_router.py --chat-id <chat_id> --channel <channel> --message "<text>"
   ```
3. Based on exit code:
   - `0` → Forwarded successfully → respond `已转发到 <session-name>` only
   - `2` → No binding → answer in-thread yourself
   - `4` → Session inactive → explain and offer to start new
   - `5` → @Coder escape → answer in-thread yourself

### Reply-Target Routing

When replying to a specific agent notification (task-reply, work-start, approval), use `--reply-to-message-id` or set environment variable `OPENCLAW_REPLY_TO_MESSAGE_ID` to enable precise routing.

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CODING_AGENT_NAME` | `coding` | Only trigger hooks when `agent_name` matches this value. Prevents main/other agents from accidentally triggering Codex/Claude Code hooks and draining balance. |

```bash
# Example: customize agent name
export CODING_AGENT_NAME=coder
```

## Upstream and acknowledgements

This repository builds on the ideas and implementations from these upstream projects:

- `dztabel-happy/codex-agent` — <https://github.com/dztabel-happy/codex-agent>
- `N1nEmAn/claude-agent` — <https://github.com/N1nEmAn/claude-agent>

Many thanks to the original authors for the baseline design and implementation work that made this consolidated repository possible.

## Thread Session Routing

**Critical Rule**: When a message arrives in a Discord thread that has an active bound `codex-agent` or `claude-agent` tmux session, the agent **MUST** first attempt to forward it via the unified router before answering itself. Do not respond in-thread unless the router returns exit code 2 (no binding) or 5 (explicit @Coder escape).

### Routing Flow

1. **Always invoke the unified detector first** for any thread message:
   ```bash
   python3 skills/cli-agents/bridge/agent_session_router.py --chat-id <chat_id> --channel <channel> --message "<text>"
   ```

2. **Interpret exit codes**:
   | Exit Code | Meaning | Agent Behavior |
   |-----------|---------|----------------|
   | `0` | Forwarded successfully | Respond with `已转发到 <session-name>` only |
   | `2` | No active bound session | Answer the message yourself in-thread |
   | `4` | Bound session inactive | Explain session is gone, offer to start a new one |
   | `5` | Explicit @Coder escape (Discord native mention `<@...>`/`<@!...>`/`<@&...>`) | Answer yourself |

3. **Fallback**: If the router fails to run (missing dependency, etc.), you may answer directly but log the issue.

### Binding Source of Truth
- Route files: `/tmp/codex-agent-routes/<session>.json` or `/tmp/claude-agent-routes/<session>.json`
- If both agent types appear bound to the same thread, prefer the one with the latest `updated_at` timestamp

### Response Format
- After successful forward: respond with only `已转发到 <session-name>`
- Do not restate the forwarded content or add extra explanation

### Reply-Target Routing
When a user replies directly to a specific agent notification message (e.g., task-reply, work-start, approval), the router uses the reply-target map to forward the reply to the correct tmux session:

- Reply-target mappings are stored in `/tmp/openclaw-agent-reply-map.jsonl`
- Mappings are created automatically when agent notifications are sent
- Lookup returns the latest matching record for a given message ID

## See also

- `CHANGELOG.md` — repository-level summary of what changed relative to the upstream projects
