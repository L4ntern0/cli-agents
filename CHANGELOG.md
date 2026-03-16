# Changelog

All notable changes to `cli-agents` are documented in this file.

## [0.1.0] - 2026-03-16

Initial consolidated `cli-agents` repository release.

### Added
- Consolidated repository layout:
  - `codex-agent/`
  - `claude-agent/`
  - `bridge/`
- Shared bridge utilities:
  - `bridge/agent_session_router.py`
  - `bridge/reply_route_map.py`
  - `bridge/check_agent_hooks.py`
  - `bridge/check_route_conflicts.py`
- Repository-level `README.md`
- Repository-level `.gitignore`
- Repository-level acknowledgements to upstream projects

### Changed vs upstream `dztabel-happy/codex-agent`
Source: <https://github.com/dztabel-happy/codex-agent>

- Added session route context support via per-session route files
- Added reply-target mapping so outbound message IDs can route future thread replies back to the correct tmux session
- Added thread-aware forwarding helper: `hooks/forward_to_session.py`
- Added `start_codex_openclaw.sh` for explicit OpenClaw source-context startup
- Added `doctor.sh` and bridge-level hook preflight / route conflict checks
- `start_codex.sh`
  - now writes route metadata (`chat_id`, `channel`, `account`, `agent_name`, `workdir`, `trace_id`)
  - now performs hook preflight and cross-agent route conflict checks before launch
  - now supports managed source routing through environment variables
  - now defaults to yolo/auto mode unless `--approval` is specified
- `on_complete.py`
  - now ignores unmanaged sessions
  - now resolves route context dynamically
  - now stores reply-route mappings for completion notifications
  - now supports channel/account-aware delivery instead of a single hardcoded target model
- `pane_monitor.sh`
  - now routes approval notifications through per-session context
  - now exits early for unmanaged sessions
  - now supports account-aware outbound messaging
- `stop_codex.sh`
  - now sends session-close notifications using route context
  - now removes per-session route files on cleanup
- Documentation updated for `workspace-coding/skills/cli-agents/...` layout and managed thread routing workflow

### Changed vs upstream `N1nEmAn/claude-agent`
Source: <https://github.com/N1nEmAn/claude-agent>

- Added shared bridge integration with codex-agent-compatible routing model
- Added thread-aware forwarding helper: `hooks/forward_to_session.py`
- Added per-session route file support via `hooks/route_context.py`
- Added bridge-level hook preflight / route conflict checks
- Added `doctor.sh`
- `start_claude.sh`
  - now supports explicit per-session flags for `--chat-id`, `--channel`, `--account`, `--agent`
  - now writes per-session route metadata
  - now performs preflight and conflict detection before launch
  - now defaults to auto mode unless `--approval` is specified
- `on_complete.py`
  - now resolves route context dynamically instead of relying only on global env
  - now stores reply-route mappings for completion notifications
  - now supports account-aware delivery and cleaner thread-targeted wake behavior
- `pane_monitor.sh`
  - now detects work-start transitions and can proactively notify the bound thread
  - now stores reply-route mappings for monitor-generated messages
  - now uses bridge-local `reply_route_map.py`
- `stop_claude.sh`
  - now sends session-close notifications using route context
  - now removes per-session route files on cleanup
- Documentation updated for the consolidated repository layout and multi-session thread routing workflow

### Repository maintenance
- Removed nested `.git` directories from the old split repos
- Created a single standalone Git repository for `cli-agents`
- Cleaned `__pycache__` / `*.pyc` from version control and added ignore rules
