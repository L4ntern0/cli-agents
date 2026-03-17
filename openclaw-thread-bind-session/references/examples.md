# Examples

## 极简版

```text
请在当前频道新开一个 Discord 子区并绑定新的会话，然后用 `cli-agents` 里的指定运行时在 `<project-path>` 启动 session，不要使用普通临时会话，并确认 route file、pane monitor、completion hook 和 thread 通知链路正常。
```

## Claude Code 版

```text
请在当前频道新开一个叫 `claude-demo` 的 Discord 子区，并绑定新的 `coding` 会话。然后用 `cli-agents` 里的 `claude-agent` 在 `/path/to/project` 启动一个新的 Claude Code session，不要使用普通临时会话，并确认 route file、pane monitor、completion hook 和 thread 通知链路正常。
```

## Codex 版

```text
请在当前频道新开一个叫 `codex-demo` 的 Discord 子区，并绑定新的 `coding` 会话。然后用 `cli-agents` 里的 `codex-agent` 在 `/path/to/project` 启动一个新的 Codex session，不要使用普通临时会话，并确认 route file、pane monitor、completion hook 和 thread 通知链路正常。
```

## 未指定 runtime 时的通用版

```text
请在当前频道新开一个叫 `agent-demo` 的 Discord 子区，并绑定新的会话。然后用 `cli-agents` 里的合适运行时在 `/path/to/project` 启动一个新的 session；如果需要先判断，请先确认应该使用 Claude Code 还是 Codex。不要使用普通临时会话，并确认 route file、pane monitor、completion hook 和 thread 通知链路正常。
```
