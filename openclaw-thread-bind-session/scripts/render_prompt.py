#!/usr/bin/env python3
import argparse


def build_prompt(thread_name: str, agent_dir: str, runtime_name: str, project_path: str) -> str:
    return (
        f"请在当前频道新开一个叫 `{thread_name}` 的 Discord 子区，并把一个新的会话绑定到这个子区。"
        f"然后用 `cli-agents` 仓库里的 `{agent_dir}` 运行时，在 `{project_path}` 启动一个新的 {runtime_name} session，"
        f"不要使用普通临时会话；同时确认 route file、pane monitor、completion hook 和 thread 通知链路都正常。"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a standard cli-agents thread-binding prompt.")
    parser.add_argument("--thread-name", required=True)
    parser.add_argument("--project-path", required=True)
    parser.add_argument("--runtime", choices=["claude", "codex"], required=True)
    args = parser.parse_args()

    if args.runtime == "claude":
        agent_dir = "claude-agent"
        runtime_name = "Claude Code"
    else:
        agent_dir = "codex-agent"
        runtime_name = "Codex"

    print(build_prompt(args.thread_name, agent_dir, runtime_name, args.project_path))


if __name__ == "__main__":
    main()
