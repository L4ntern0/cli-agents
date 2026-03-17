# cli-agents — A unified runtime for terminal CLI agents in OpenClaw

English | **[中文](README_zh.md)**

> 2026-03-18 update: Discord thread routing has been re-validated end-to-end. Managed `claude-agent` / `codex-agent` sessions now use active-pane + ready-state forwarding, completion/monitor notifications extract nested `messageId` values reliably, and replying directly to an agent's thread message can route back through `reply-target-message-id` to the original tmux session.

> `cli-agents` is a consolidated repository for OpenClaw / agent-deck terminal agent workflows. It brings together `codex-agent`, `claude-agent`, and shared bridge utilities into a single versioned runtime that handles **session startup, monitoring, notifications, thread routing, reply-target mapping, and multi-session coordination**.

## What is this?

In one sentence: **`cli-agents` is a runtime toolkit that helps OpenClaw operate CLI coding agents reliably in real terminal environments.**

Instead of treating Codex or Claude Code as isolated command-line tools, this repository provides the runtime glue that lets higher-level agents:

- launch and manage CLI agents inside `tmux`
- detect important lifecycle events such as task start, task completion, and approval prompts
- send notifications back to Discord / Telegram / bound threads
- route user replies back to the original tmux session
- keep multi-session / multi-thread / multi-workdir workflows stable

This is not just the README for a single agent. It is a **unified runtime repository** that contains:

- `codex-agent/` — tmux + hook workflow for Codex
- `claude-agent/` — tmux + hook workflow for Claude Code
- `bridge/` — shared routing, reply-target mapping, and forwarding utilities

## Why this repository exists

If you use CLI agents manually, the flow usually looks like this:

```text
Open terminal → write prompt → launch CLI agent → watch output → approve commands/tools → iterate → finish
```

`cli-agents` aims to make the flow look more like this:

```text
User assigns a task in chat → OpenClaw prepares and orchestrates execution →
CLI agent keeps running in tmux → key events trigger notifications →
user can reply, intervene, or take over at any time
```

The goal is not to replace Codex or Claude Code. The goal is to make them fit into a **stable, observable, routable, asynchronously managed** agent workflow.

## Core problems it solves

### 1. A unified CLI agent runtime

This repository puts `codex-agent` and `claude-agent` under one roof so that:

- shared bridge tools live in one place
- path conventions stay stable
- updates are easier to coordinate
- the runtime is versioned as one deployable unit

### 2. Thread / session routing

In real chat-driven workflows, common failures include:

- notifications going to the wrong thread
- replies not returning to the original session
- route bindings drifting after session restarts
- multiple agents competing for the same thread

This repository uses route files, bridge scripts, and reply-target maps to make routing more robust.

### 3. Persistent tmux execution

CLI agent tasks often outlive a single agent turn. Running them in `tmux` provides:

- persistent execution for long-running tasks
- manual takeover via `tmux attach`
- event-driven wakeups instead of constant polling by the parent agent
- less dependence on one foreground chat turn remaining alive forever

### 4. Observable notification flows

The runtime splits notifications into meaningful event classes:

- task start
- task completion
- approval wait
- reply-target routing

In practice:
- Claude Code relies more on native hooks
- Codex combines completion hooks with `pane_monitor.sh`

### 5. Platform-safe long message delivery

Discord and similar platforms impose message length limits. The current runtime already supports:

- automatic chunking for long notifications
- chunk numbering such as `[1/N]`
- fenced code block aware chunk splitting

That means long logs and long assistant replies are not simply truncated, and Markdown code fences are much less likely to break mid-message.

## How it works

The runtime is built around three layers.

### 1) Agent runtime layer

Each CLI agent runs inside its own `tmux session`.

Examples:
- `codex-agent/hooks/start_codex.sh`
- `claude-agent/hooks/start_claude.sh`

These launchers are responsible for:
- creating sessions
- writing route files
- starting monitors
- injecting runtime context
- sending one extra empty `Enter` on first startup to help unblock trust-directory / continue prompts in newly entered workdirs

### 2) Hook / monitor layer

This layer detects important lifecycle changes:

- `on_complete.py` — task completion notifications
- `pane_monitor.sh` — approval wait / task start state detection
- `task_start.py` — Claude Code task start event handling

This is the layer that decides *when* to notify, *what* to notify, and *where* the notification should go.

### 3) Bridge routing layer

Located in:
- `bridge/agent_session_router.py`
- `bridge/reply_route_map.py`

This layer is responsible for:
- mapping threads or reply-targets to sessions
- selecting the correct session from route files
- forwarding user messages into the right tmux session

## Repository layout

```text
cli-agents/
├── README.md                  # English overview
├── README_zh.md               # Chinese overview
├── CHANGELOG.md               # Repository-level changelog
│
├── bridge/
│   ├── agent_session_router.py
│   └── reply_route_map.py
│
├── codex-agent/
│   ├── README.md
│   ├── README_EN.md
│   ├── INSTALL.md
│   ├── SKILL.md
│   └── hooks/
│       ├── start_codex.sh
│       ├── pane_monitor.sh
│       └── on_complete.py
│
└── claude-agent/
    ├── README.md
    ├── README_EN.md
    ├── INSTALL.md
    ├── SKILL.md
    └── hooks/
        ├── start_claude.sh
        ├── task_start.py
        ├── pane_monitor.sh
        └── on_complete.py
```

## Installation

> For detailed setup, read each subproject’s own `INSTALL.md` first.

### 1. Clone the repository

```bash
git clone git@github.com:L4ntern0/cli-agents.git
cd cli-agents
```

### 2. Put it into your OpenClaw / workspace-coding skills directory

A typical location would be:

```bash
~/.openclaw/workspace-coding/skills/cli-agents
```

### 3. Prepare dependencies

You should have at least:

- `bash`
- `python3`
- `git`
- `tmux`
- the actual CLI agents you want to use (for example `codex` and/or `claude`)

Example checks:

```bash
bash --version
python3 --version
git --version
tmux -V
```

### 4. Choose which agent(s) to enable

Read the corresponding docs:

- `codex-agent/README.md`
- `codex-agent/INSTALL.md`
- `claude-agent/README.md`
- `claude-agent/INSTALL.md`

`cli-agents` is a unified repository, but each runtime still depends on the specific CLI tool you actually want to run.

### 5. Validate scripts after changes

Whenever you modify hooks, monitors, or bridge logic, it is strongly recommended to run:

```bash
bash -n codex-agent/hooks/*.sh
bash -n claude-agent/hooks/*.sh
python3 -m py_compile bridge/*.py codex-agent/hooks/*.py claude-agent/hooks/*.py
```

### 6. Integrate into your runtime

After setup, the repository can be integrated into:

- OpenClaw agent workflows
- agent-deck thread / session management
- Discord / Telegram notification routing
- tmux-driven long-running task execution

## Notification and routing features

### Task completion notifications

- Codex: `on_complete.py`
- Claude Code: `on_complete.py`

Supported features include:
- response notifications
- reply-target mapping
- automatic long-message chunking
- fenced code block aware chunking

### Task start / approval wait

- Claude Code uses more native hooks plus monitor logic
- Codex relies more heavily on pane monitor state detection

### Thread auto-forwarding

When a Discord thread is already bound to a live tmux session, the OpenClaw agent should first invoke the unified router:

```bash
python3 skills/cli-agents/bridge/agent_session_router.py \
  --chat-id <chat_id> \
  --channel <channel> \
  --message "<text>"
```

### Refined forwarding with `>>`

If a message starts with `>> `, the intended behavior is:

1. strip the prefix
2. lightly polish or expand the message so it works better as a prompt for the bound CLI agent
3. do **not** explain it, do **not** answer it yourself, and do **not** change the original intent
4. forward the refined message to the bound session

This matters because in CLI-agent workflows, users often want the main agent to act as a lightweight prompt organizer before handing the task to the tmux-managed agent.

## Notes and operational cautions

### 1. This is a runtime repository, not just a docs repository

The scripts here directly participate in:

- session startup
- route binding
- monitor execution
- completion hooks
- user notifications

That means changes here should be treated as changes to **production runtime components**, not just examples.

### 2. Keep route files aligned with session lifecycle

If a session is manually restarted, renamed, or moved to a different workdir without refreshing route files, you can easily end up with:

- notifications going to the wrong thread
- reply routing failing
- threads that look bound but are actually stale

### 3. Message length limits are real

Discord and similar platforms impose practical message limits. If you extend the notification format later, avoid reintroducing “send one huge message and let the platform truncate it” behavior.

### 4. Forwarding rules currently depend on AGENTS.md and may need re-confirmation

This project has primarily been tested under **GPT-5.4**.

At the moment, OpenClaw does **not** provide a Discord message-level hook / interceptor that can enforce thread forwarding at the gateway layer. Because of that, message forwarding is currently implemented mainly through rules written in `AGENTS.md`, instructing the main agent to invoke the router first before deciding whether to answer directly.

This approach works, but in practice the agent may occasionally forget or drift away from those rules. So for important threads, important tasks, or any situation where forwarding looks suspicious, it is wise to restate and re-confirm the forwarding rules explicitly.

In practice, that usually means reminding the agent that:

- routing should be attempted first
- bound sessions should be forwarded to by default
- `>> ` messages should be refined and then forwarded according to the documented convention
- the main agent should only answer directly when there is no binding or an explicit escape applies

### 5. Split unrelated topics into separate commits

A good commit split usually looks like:

- monitor behavior fixes
- route matching fixes
- notification chunking improvements
- documentation updates

That makes troubleshooting, rollback, and review much easier.

## Upstream credits and acknowledgements

This repository did not emerge from a vacuum. It builds on ideas and implementations from upstream projects, then adapts them to real OpenClaw / agent-deck workflows.

Special thanks to the original repositories and authors:

- [`dztabel-happy/codex-agent`](https://github.com/dztabel-happy/codex-agent)
- [`N1nEmAn/claude-agent`](https://github.com/N1nEmAn/claude-agent)

Their work provided the baseline concepts and implementation patterns that made this consolidated runtime possible.

On top of those foundations, `cli-agents` extends the system with:

- unified repository layout
- shared bridge routing tools
- reply-target mapping
- thread/session auto-forwarding
- monitor stability improvements
- Discord long-message chunking
- fenced code block aware chunk splitting

In short, `cli-agents` is both a continuation of those upstream ideas and a runtime-focused evolution shaped by real operational needs.

## Related documentation

- [INSTALL.md](INSTALL.md) — repository-level installation and setup notes
- [CHANGELOG.md](CHANGELOG.md) — repository-level change history
- [codex-agent/README.md](codex-agent/README.md) — detailed Codex agent documentation
- [codex-agent/README_EN.md](codex-agent/README_EN.md) — Codex agent English README
- [codex-agent/INSTALL.md](codex-agent/INSTALL.md) — Codex agent setup guide
- [claude-agent/README.md](claude-agent/README.md) — detailed Claude Code agent documentation
- [claude-agent/README_EN.md](claude-agent/README_EN.md) — Claude agent English README
- [claude-agent/INSTALL.md](claude-agent/INSTALL.md) — Claude agent setup guide

## License

If you want the repository to be explicitly open source, add a `LICENSE` file at the repository root.
This README describes purpose, structure, and operations, but it is not a substitute for a formal license file.
