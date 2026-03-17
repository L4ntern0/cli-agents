# CLI Agents Installation Guide

This guide explains how to set up `cli-agents` for automated codex-agent and claude-agent session management with Discord thread binding.

## Overview

cli-agents provides:
- Session lifecycle management for Codex and Claude Code
- Discord thread binding and message forwarding
- Real-time notifications for task start/completion
- Auto-forwarding via `>>` prefix or router rules

## Prerequisites

- OpenClaw Gateway running
- Codex CLI installed (`codex`)
- Claude Code installed (`claude`)
- Discord account configured in OpenClaw

## Installation

### Step 1: Clone or Copy cli-agents

```bash
# If using as part of OpenClaw workspace:
# cli-agents should already be in your workspace at:
# skills/cli-agents/
```

### Step 2: Configure Codex Notify Hook

Edit `~/.codex/config.toml`:

```toml
notify = ["bash", "/path/to/skills/cli-agents/codex-agent/hooks/notify_chain.sh"]
```

Replace `/path/to` with your actual workspace path.

### Step 3: Configure Claude Code Hooks

Edit `~/.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 <SKILL_PATH>/hooks/on_complete.py"
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 <SKILL_PATH>/hooks/task_start.py",
            "async": true
          }
        ]
      }
    ]
  }
}
```

Replace `<SKILL_PATH>` with the path to cli-agents (e.g., `/home/user/openclaw/skills/cli-agents/claude-agent`).

### Step 4: Create Route Directories

```bash
mkdir -p /tmp/codex-agent-routes
mkdir -p /tmp/claude-agent-routes
```

### Step 5: Verify Installation

```bash
# Test Codex route resolution
python3 skills/cli-agents/bridge/agent_session_router.py --help

# Start a test Codex session
cd skills/cli-agents/codex-agent/hooks
CODEX_AGENT_SOURCE_CHAT_ID=channel:123456789 \
CODEX_AGENT_SOURCE_CHANNEL=discord \
CODEX_AGENT_SOURCE_ACCOUNT=coder \
./start_codex.sh test_session /tmp --yolo
```

## Usage

### Starting Codex Sessions

```bash
cd skills/cli-agents/codex-agent/hooks

# Start with Discord thread binding
CODEX_AGENT_SOURCE_CHAT_ID=channel:THREAD_ID \
CODEX_AGENT_SOURCE_CHANNEL=discord \
CODEX_AGENT_SOURCE_ACCOUNT=coder \
./start_codex.sh my_session /path/to/workdir --yolo
```

### Starting Claude Sessions

```bash
cd skills/cli-agents/claude-agent/hooks

CLAUDE_AGENT_SOURCE_CHAT_ID=channel:THREAD_ID \
CLAUDE_AGENT_SOURCE_CHANNEL=discord \
CLAUDE_AGENT_SOURCE_ACCOUNT=coder \
./start_claude.sh my_session /path/to/workdir
```

### Stopping Sessions

```bash
# Codex
./stop_codex.sh my_session

# Claude  
./stop_claude.sh my_session
```

## Message Forwarding

### Method 1: >> Prefix (Recommended)

Prefix your message with `>>` to have it refined and forwarded to the bound session:

```
>> 帮我检查这段代码
```

This will:
1. Strip the `>>` prefix
2. Lightly polish or expand the message so it works better as a CLI-agent prompt
3. Do **not** explain the request, answer it directly, or change the original intent
4. Forward the refined message to the bound session
5. Confirm with `已转发到 <session>`

### Method 2: Router Auto-Forward

Messages in threads with active bindings are automatically checked:
- If bound session exists: forward
- If no binding: answer directly

### Method 3: @Coder Escape

Use `@Coder` to keep message with main agent (won't forward):

```
@Coder 你好
```

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Discord      │────▶│  OpenClaw Agent  │────▶│  Router        │
│   Thread       │     │  (main session)  │     │  (check bind)  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                              │
                                                              ▼
                              ┌──────────────────┐     ┌─────────────────┐
                              │  Codex/Claude    │◀────│  Forward       │
                              │  Tmux Session    │     │  (tmux send)   │
                              └──────────────────┘     └─────────────────┘
                                       │
                                       ▼
                              ┌──────────────────┐
                              │  Notify (Discord)│
                              │  - work-start    │
                              │  - task-reply    │
                              └──────────────────┘
```

## Files

| File | Purpose |
|------|---------|
| `bridge/agent_session_router.py` | Unified routing logic |
| `bridge/reply_route_map.py` | Reply-target mapping |
| `codex-agent/hooks/start_codex.sh` | Codex session starter |
| `codex-agent/hooks/pane_monitor.sh` | Codex status monitor |
| `codex-agent/hooks/on_complete.py` | Codex task completion handler |
| `claude-agent/hooks/start_claude.sh` | Claude session starter |
| `claude-agent/hooks/pane_monitor.sh` | Claude status monitor |
| `claude-agent/hooks/on_complete.py` | Claude task completion handler |
| `claude-agent/hooks/task_start.py` | Claude task start handler |
| `monitor-daemon.sh` | Auto-restart monitors |

## Troubleshooting

### Notifications Not Working

1. Check Codex/Claude config:
   ```bash
   cat ~/.codex/config.toml | grep notify
   cat ~/.claude/settings.json | grep hooks
   ```

2. Check notify log:
   ```bash
   tail -f /tmp/codex_notify_log.txt
   tail -f /tmp/claude_notify_log.txt
   ```

3. Restart monitors:
   ```bash
   pkill -f pane_monitor.sh
   ./monitor-daemon.sh start
   ```

### Session Not Binding

1. Check route files:
   ```bash
   ls /tmp/codex-agent-routes/
   ls /tmp/claude-agent-routes/
   cat /tmp/codex-agent-routes/<session>.json
   ```

2. Verify tmux session:
   ```bash
   tmux list-sessions
   ```

## See Also

- [README.md](./README.md) - Overview and architecture
- [CHANGELOG.md](./CHANGELOG.md) - Version history
