# cli-agents — 让 OpenClaw 稳定驱动终端 CLI Agent

**[English](README.md)** | 中文

> 这是一个面向 OpenClaw / agent-deck 的统一 CLI agent 仓库。它把 `codex-agent`、`claude-agent` 和共享 bridge 工具整合到同一个版本化目录里，用来解决终端 agent 在真实运行环境中的**启动、监控、通知、thread 路由、reply-target 映射与多 session 并行协作**问题。

## 它是什么？

一句话：**`cli-agents` 是一套让 OpenClaw 能稳定接管 CLI 编码代理的运行时技能集合。**

当你不想一直坐在终端前盯着 Codex / Claude Code 时，这个仓库提供了一套统一方案，让上层 agent 可以：

- 在 `tmux` 中启动和托管 CLI agent
- 监听任务开始、任务完成、审批等待等关键事件
- 把通知精确发回 Discord / Telegram / thread
- 在用户回复某条通知时，把消息自动路由回原来的 tmux session
- 在多 session / 多 thread / 多 workdir 并行时维持稳定的路由关系

这不是“单个 agent 的 README”，而是一个**统一运行时仓库**：

- `codex-agent/` —— 面向 Codex CLI 的 tmux + hook 工作流
- `claude-agent/` —— 面向 Claude Code 的 tmux + hook 工作流
- `bridge/` —— 两者共享的 thread 路由、reply-target 映射与转发工具

## 为什么需要它？

如果只是手动使用 CLI agent，正常流程通常是：

```text
打开终端 → 写 prompt → 启动 CLI agent → 盯着输出 → 审批命令/工具调用 → 继续追问 → 收工
```

而 `cli-agents` 想实现的是：

```text
用户在聊天里下任务 → OpenClaw 理解并组织执行 →
CLI agent 在 tmux 里持续工作 → 关键事件自动通知 →
用户可随时回复、接管、续做
```

它的目标不是取代 Codex 或 Claude Code，而是让这些 CLI 工具真正融入一个**可观测、可路由、可异步管理**的 agent 工作流。

## 仓库解决的核心问题

### 1. 统一 CLI agent 运行时

将 `codex-agent` 与 `claude-agent` 放进一个统一仓库中，减少：

- 路径漂移
- 共享脚本重复维护
- 多仓库升级不一致
- bridge 工具四处分散的问题

### 2. thread / session 精确路由

在 Discord thread、Telegram、其他消息面上，最常见的问题是：

- 通知发到了错误线程
- 回复回不到原 session
- session 重启后 route 失效
- 多个 agent 抢同一个 thread

本仓库提供 route file + bridge + reply-target map 机制，用来增强这种路由稳定性。

### 3. tmux 持久化执行

CLI agent 运行时间可能远超单轮 agent turn。使用 `tmux` 后可以：

- 让长任务持续运行
- 让用户随时 attach 接管
- 让 OpenClaw 在关键事件时再被唤醒
- 降低对“当前会话必须一直在线”的依赖

### 4. 可观测通知系统

仓库把通知拆成几个关键事件：

- 任务开始
- 任务完成
- 审批等待
- reply-target 回复路由

其中：
- Claude Code 更多依赖原生 hook
- Codex 则结合 `on_complete.py` + `pane_monitor.sh`

### 5. 长消息平台适配

Discord 等平台有消息长度限制。当前仓库已经为 agent 通知补充：

- 超长消息自动分片发送
- 分片编号 `[1/N]`
- fenced code block 感知分片

这样长日志 / 长回复不会被简单截断，也不容易把 Markdown 代码块渲染弄坏。

## 工作原理

整个体系本质上由三层构成：

### 1）Agent Runtime 层

每个 CLI agent 都运行在独立的 `tmux session` 中。

例如：
- `codex-agent/hooks/start_codex.sh`
- `claude-agent/hooks/start_claude.sh`

这些启动器负责：
- 创建 session
- 写入 route file
- 启动 monitor
- 注入上下文环境

### 2）Hook / Monitor 层

用于检测关键状态变化：

- `on_complete.py`：任务完成通知
- `pane_monitor.sh`：审批等待 / 工作开始等状态检测
- `task_start.py`：Claude Code 的任务开始事件

这层负责“什么时候通知、通知什么、通知发去哪里”。

### 3）Bridge Routing 层

位于：
- `bridge/agent_session_router.py`
- `bridge/reply_route_map.py`

负责：
- 根据 thread 或 reply-target 找到目标 session
- 根据 route file 做多 session 选择
- 将用户消息转发到正确 tmux session

## 仓库结构

```text
cli-agents/
├── README.md                  # 英文说明
├── README_zh.md               # 中文说明
├── CHANGELOG.md               # 仓库级变更记录
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

## 安装步骤

> 更详细的安装与环境接入说明，请优先查看各子项目自己的 `INSTALL.md`。

### 1. 克隆仓库

```bash
git clone git@github.com:L4ntern0/cli-agents.git
cd cli-agents
```

### 2. 放入你的 OpenClaw / workspace-coding 技能目录

推荐目录结构示例：

```bash
~/.openclaw/workspace-coding/skills/cli-agents
```

### 3. 准备依赖

请确认至少具备：

- `bash`
- `python3`
- `git`
- `tmux`
- 对应 CLI agent 本体（如 `codex`、`claude`）

示例：

```bash
bash --version
python3 --version
git --version
tmux -V
```

### 4. 选择要启用的 agent

按你的需求，分别阅读：

- `codex-agent/README.md`
- `codex-agent/INSTALL.md`
- `claude-agent/README.md`
- `claude-agent/INSTALL.md`

`cli-agents` 是统一仓库，但具体启用哪一个 agent，仍取决于你实际使用的 CLI 工具。

### 5. 校验脚本

建议每次修改 hook / monitor / bridge 后都执行：

```bash
bash -n codex-agent/hooks/*.sh
bash -n claude-agent/hooks/*.sh
python3 -m py_compile bridge/*.py codex-agent/hooks/*.py claude-agent/hooks/*.py
```

### 6. 开始集成

完成后即可将其接入：

- OpenClaw agent 工作流
- agent-deck thread/session 管理
- Discord / Telegram 通知回流
- tmux 驱动的长任务执行

## 通知与路由能力

### 任务完成通知

- Codex：`on_complete.py`
- Claude Code：`on_complete.py`

支持：
- 回复内容通知
- reply-target 映射
- 超长消息自动分片
- fenced code block 感知分片

### 任务开始 / 审批等待

- Claude Code：更多依赖原生 hook + monitor
- Codex：主要通过 pane monitor 检测状态

### 线程消息自动转发

当某个 Discord thread 已绑定到活跃 tmux session 时，OpenClaw agent 应优先调用统一路由器：

```bash
python3 skills/cli-agents/bridge/agent_session_router.py \
  --chat-id <chat_id> \
  --channel <channel> \
  --message "<text>"
```

### `>>` 前缀整理后转发

如果消息以 `>> ` 开头，则应：

1. 去掉前缀
2. 可以对内容做轻量的扩写与润色，使其更适合作为发给绑定 CLI agent 的 prompt
3. 不要解释消息内容，不要自行回答，也不要改变原始意图
4. 将整理后的内容转发到绑定 session

这条规则对于 CLI agent 场景非常重要，因为很多时候用户希望主 agent 先做轻量提示词整理，再交给 tmux 中的 agent 继续执行。

## 注意事项

### 1. 这是运行时仓库，不只是文档仓库

这里面的脚本会真正参与：

- session 启动
- route 绑定
- monitor 监控
- completion hook
- 消息通知

因此修改时应把它视作**生产运行组件**，而不是普通示例代码。

### 2. 请保持 route file 与 session 生命周期一致

如果 session 手工重启、名称变化、workdir 改变，而 route file 没同步更新，就容易出现：

- 通知发错线程
- 回复路由失效
- thread 表面绑定但实际已失联

### 3. 长消息平台限制是现实问题

Discord 等平台对消息长度有限制，因此仓库当前采用分片发送策略；如果你后续再扩展通知格式，请注意不要重新引入“超长直接截断”的问题。

### 4. 转发规则依赖 AGENTS.md 约束，必要时需要重复确认

当前项目主要在 **GPT-5.4** 环境下测试。

由于 OpenClaw 目前**没有 Discord 消息级 hook / 拦截器**，因此线程消息自动转发并不是由网关层强制完成，而主要依赖在 `AGENTS.md` 中写明规则，让主 agent 在收到消息后先调用路由器再决定是否自行回复。

这套方式可以工作，但实测中 agent 有时会忘记或偏离这些规则。因此在关键线程、关键任务、或你怀疑没有正确转发时，最好再次明确确认一次当前转发规则，必要时重新强调：

- 先尝试路由
- 已绑定 session 优先转发
- `>> ` 前缀按约定整理后转发
- 只有在无绑定或显式转义时才由主 agent 自己回答

### 5. 多主题改动请拆分提交

建议分别提交：

- monitor 行为修复
- route matching 修复
- 消息分片增强
- 文档更新

这样更便于排查、回滚与 review。

## 上游说明与致谢

本仓库并不是凭空从零开始设计的。它在多个上游项目的基础思路之上，结合 OpenClaw / agent-deck 的实际工作流逐步演化而来。

特别感谢以下原仓库与作者：

- [`dztabel-happy/codex-agent`](https://github.com/dztabel-happy/codex-agent)
- [`N1nEmAn/claude-agent`](https://github.com/N1nEmAn/claude-agent)

感谢原作者提供的基础设计与实现。本仓库在这些思路之上，进一步补充了：

- 统一仓库布局
- bridge 路由工具
- reply-target 映射
- thread/session 自动转发
- monitor 稳定性改进
- Discord 长消息分片发送
- 代码块感知分片

换句话说，`cli-agents` 既是对原有项目思路的继承，也是一个围绕真实 agent 运维场景继续演进的统一运行时仓库。

## 相关文档

- [INSTALL.md](INSTALL.md) — 仓库级安装与接入说明
- [CHANGELOG.md](CHANGELOG.md) — 仓库级变更说明
- [codex-agent/README.md](codex-agent/README.md) — Codex Agent 中文说明
- [codex-agent/README_EN.md](codex-agent/README_EN.md) — Codex Agent 英文说明
- [codex-agent/INSTALL.md](codex-agent/INSTALL.md) — Codex Agent 安装指南
- [claude-agent/README.md](claude-agent/README.md) — Claude Agent 中文说明
- [claude-agent/README_EN.md](claude-agent/README_EN.md) — Claude Agent 英文说明
- [claude-agent/INSTALL.md](claude-agent/INSTALL.md) — Claude Agent 安装指南

## License / 使用说明

如需明确开源许可证，请在仓库根目录补充 `LICENSE` 文件。
当前 README 主要描述仓库用途、结构与运维方式，不替代正式许可证文本。
