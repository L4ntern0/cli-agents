# Changelog

## [2.0.1] - 2026-03-18

### Fixed
- `hooks/forward_to_session.py`
  - now resolves the active tmux pane instead of assuming window `0.0`
  - now waits for Claude Code to reach a ready prompt before sending text
  - now recognizes the `❯` prompt variant seen in current Claude Code builds
- `hooks/on_complete.py`
  - now extracts outbound `messageId` from nested `openclaw message send --json` payloads so reply-route mappings are stored reliably
- `hooks/pane_monitor.sh`
  - now uses the shared message-id extractor for monitor-generated notifications as well

### Added
- `../bridge/extract_message_id.py` helper for recursive `messageId` / `message_id` extraction from OpenClaw JSON output

### Verified
- Discord thread reply routing was re-tested end-to-end with a managed `cli-agents-demo` session:
  - forwarded thread message entered the tmux session
  - Claude completion reply returned to the same Discord thread
  - replying directly to that Claude message selected the original session via `reply-target-message-id`

## [2.0.0] - 2026-03-13

### Changed (Breaking)
- **CLI Migration**: From OpenAI Codex CLI to Anthropic Claude Code CLI
- **Config Format**: From `~/.codex/config.toml` (TOML) to `~/.claude/settings.json` (JSON)
- **Hook Mechanism**: From Codex notify hook (argv JSON) to Claude Code Stop hook (stdin JSON)
- **Models**: From GPT series to Claude series (opus / sonnet / haiku)
- **Permissions**: From sandbox + approval policy to permissions.allow/deny
- **Non-interactive Mode**: From `codex exec` to `claude -p`
- **Auto-approve**: From `--full-auto` to `--dangerously-skip-permissions`

### Added
- `hooks/start_claude.sh` — One-click launcher for Claude Code
- `hooks/stop_claude.sh` — One-click cleanup for Claude Code
- `references/claude-code-reference.md` — Claude Code CLI reference

### Removed
- `hooks/start_codex.sh` — Replaced by start_claude.sh
- `hooks/stop_codex.sh` — Replaced by stop_claude.sh
- `references/codex-cli-reference.md` — Replaced by claude-code-reference.md

### Rewritten
- `SKILL.md` — Complete rewrite for Claude Code workflow
- `hooks/on_complete.py` — Adapted for stdin JSON input
- `hooks/pane_monitor.sh` — Adapted for Claude Code permission prompts
- `knowledge/*` — All 6 files rewritten for Claude Code
- `workflows/*` — Adapted for Claude Code
- `README.md`, `README_EN.md`, `INSTALL.md` — Complete rewrite

## [0.2.0] - 2026-02-26

### Fixed
- `start_codex.sh`: Added `set -euo pipefail` and return code checks
- `pane_monitor.sh`: Fixed syntax error causing wake failure detection issue
- `on_complete.py`: Changed to DEVNULL for fire-and-forget agent wake

### Added
- `INSTALL.md`: Complete 7-step installation guide
- `README_EN.md`: Full English README
- Environment variable support: `CODEX_AGENT_CHAT_ID` and `CODEX_AGENT_NAME`

## [0.1.0] - 2026-02-25

### Added
- Initial release as codex-agent
- SKILL.md: 8-step workflow engine for OpenClaw to operate Codex CLI
- Dual-channel notification: notify hook + tmux pane monitor
- One-click start/stop scripts
- Knowledge base: 6 files
- Two approval modes: auto and OpenClaw-managed
