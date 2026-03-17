---
name: openclaw-thread-bind-session
description: Create and bind a Discord thread (or similar chat sub-thread) to a managed cli-agents session, then launch a Codex or Claude Code runtime with the cli-agents repository instead of a generic temporary session. Use when asked to open a new channel thread/sub-thread, bind a coding session, start `codex-agent` or `claude-agent`, or ensure route file / pane monitor / completion hook / thread notification wiring is in place.
---

# OpenClaw Thread Bind Session

Create or reuse a chat thread, bind it to a managed coding session, and launch the runtime from the `cli-agents` repository.

## Resources

- Read `references/runtime-checklist.md` before composing or validating launch instructions.
- Read `references/examples.md` when you need a short copy-paste prompt or concrete runtime-specific examples.
- Use `scripts/render_prompt.py` when you need a standard one-shot prompt for creating a thread, binding a session, and starting either `claude-agent` or `codex-agent`.

## Workflow

1. Confirm the target runtime:
   - Prefer `claude-agent` when the user explicitly asks for Claude Code.
   - Prefer `codex-agent` when the user explicitly asks for Codex.
   - If the user does not specify, ask which runtime to start.

2. Make the repo choice explicit:
   - Use the `cli-agents` repository.
   - Do not create a generic temporary session when the request is meant to use `cli-agents`.

3. Make the thread-binding intent explicit:
   - Create the new Discord thread or sub-thread when requested.
   - Bind the new session to that thread.
   - Ensure subsequent replies are expected to return to the same thread.

4. Launch the managed runtime from the correct subdirectory:
   - Claude Code: `cli-agents/claude-agent`
   - Codex: `cli-agents/codex-agent`

5. Preserve the runtime wiring:
   - Ensure source context values are passed at startup.
   - Ensure route file output is enabled.
   - Ensure pane monitor and completion hook are part of the launch path.
   - Ensure thread notifications are expected to flow back to the bound thread.

## Default prompt pattern

Use or adapt this pattern when the user wants one-shot setup from chat.
If the values are known, prefer generating the sentence with `scripts/render_prompt.py`.
For a shorter copy-paste version, use the examples in `references/examples.md`.

```text
请在当前频道新开一个叫 `<thread-name>` 的 Discord 子区，并把一个新的会话绑定到这个子区。然后用 `cli-agents` 仓库里的 `<agent-dir>` 运行时，在 `<project-path>` 启动一个新的 <runtime-name> session，不要使用普通临时会话；同时确认 route file、pane monitor、completion hook 和 thread 通知链路都正常。
```

## Output requirements

When completing the setup, report:

- which thread was created or reused
- which runtime was started
- which session name was bound
- which project path was used
- whether route file / monitor / completion notification wiring is active
