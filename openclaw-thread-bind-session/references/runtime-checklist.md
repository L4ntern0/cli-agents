# Runtime Checklist

Use this checklist when creating or binding a thread-backed `cli-agents` session.

## 1. Pick the runtime explicitly

- Use `claude-agent` for Claude Code requests.
- Use `codex-agent` for Codex requests.
- If the user says only "start a coding session", ask which runtime to use.

## 2. Make the repo explicit

Always anchor the action to the `cli-agents` repository itself.

Do not silently fall back to a generic temporary session when the request is intended to use `cli-agents`.

## 3. Bind the thread and the coding session

Target outcome:

- a new or reused Discord thread exists
- a `coding` session is bound to that thread
- the managed runtime is started for the requested project path
- follow-up replies are expected to return to the same thread

## 4. Preserve startup wiring

When generating launch instructions, include source-context variables.

### Claude Code

```bash
cd ~/.openclaw/workspace-coding/skills/cli-agents/claude-agent

CLAUDE_AGENT_CHAT_ID="channel:<thread_id>" \
CLAUDE_AGENT_CHANNEL="discord" \
CLAUDE_AGENT_ACCOUNT="coder" \
CLAUDE_AGENT_NAME="coding" \
bash hooks/start_claude.sh <session-name> <project-path>
```

### Codex

```bash
cd ~/.openclaw/workspace-coding/skills/cli-agents/codex-agent

CODEX_AGENT_SOURCE_CHAT_ID="channel:<thread_id>" \
CODEX_AGENT_SOURCE_CHANNEL="discord" \
CODEX_AGENT_SOURCE_ACCOUNT="coder" \
CODEX_AGENT_SOURCE_AGENT_NAME="coding" \
bash hooks/start_codex.sh <session-name> <project-path>
```

## 5. Verify the right guarantees

Check or state explicitly that the intended runtime path preserves:

- route file generation
- pane monitor startup
- completion hook wiring
- thread-oriented notifications

## 6. Report the result clearly

At the end, report:

- thread name or identifier
- runtime chosen
- session name
- project path
- whether route file / pane monitor / completion notifications are part of the launch path
ions are part of the launch path
