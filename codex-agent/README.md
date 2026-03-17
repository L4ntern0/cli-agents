# Codex Agent — 让 OpenClaw 替你操作 Codex 🧠

**[English](README_EN.md)** | 中文

> 你躺在床上说一句话，OpenClaw 帮你开 Codex、写提示词、处理审批、检查质量、汇报结果。你随时可以打开终端接管。

**这是一个 [OpenClaw](https://github.com/openclaw/openclaw) 专用 Skill。** 需要 OpenClaw 作为 AI agent 运行时，通过 OpenClaw 的 agent 唤醒、消息投递、cron 等能力驱动整个工作流。

## 上游说明

本仓库基于 [`dztabel-happy/codex-agent`](https://github.com/dztabel-happy/codex-agent) 进行二次开发，现作为**独立仓库**维护，**并非 GitHub Fork**。

原始上游仓库：
- https://github.com/dztabel-happy/codex-agent

维护说明：
- 为避免 GitHub Fork 关系带来的仓库管理限制，本项目采用普通仓库方式维护；
- 本仓库可能会根据实际需求持续演进，并逐步偏离上游实现；
- 如需引入上游更新，请通过 Git 远程 `upstream` 手动同步。

## 致谢

感谢 [`dztabel-happy/codex-agent`](https://github.com/dztabel-happy/codex-agent) 原作者提供的基础设计与实现。本仓库在其思路基础上进行了 OpenClaw thread 路由、reply-target 映射、bridge 工具与统一仓库布局等适配与扩展。

## 本仓库新增功能与变更原因

相较于上游 `codex-agent`，本仓库额外增加了以下能力：

- **线程级会话路由**：可将 Discord thread 与具体 Codex tmux session 绑定，完成通知、审批提醒与后续指令都能优先回到对应 thread；
- **thread 内继续对话转发**：在已绑定 thread 中，后续消息可以自动识别为该 session 的下一条指令并转发到 tmux 会话；
- **会话级 route file 管理**：每个 session 单独记录 `chat_id / channel / account / agent_name / workdir`，提升多 session 并行时的稳定性；
- **工作目录前缀匹配路由**：当实际运行目录是绑定 workdir 的子目录时，通知与转发仍能正确命中原 thread；
- **doctor 与 hook 自检能力**：新增 `doctor.sh`、hook preflight、自检与诊断流程，尽量把脚本错误前置到启动阶段，而不是等到运行中或 Stop hook 才暴露；
- **OpenClaw 上下文启动入口**：补充 `start_codex_openclaw.sh` 等脚本，使 OpenClaw 可以显式把当前消息来源传递给 Codex session。

之所以增加这些能力，主要是因为 **`claude-agent` 是从 `codex-agent` 演化出来的分支实现**，在给 `claude-agent` 增加 thread 绑定、自动转发、route 诊断与 hook 健康检查后，反过来也验证了这些能力对 `codex-agent` 同样必要。为了让两个 agent 的使用体验、路由行为与排障方式保持一致，本仓库也补齐了同类能力。

换句话说，这些改动一方面是为了支持更稳定的 **多 thread / 多 session 并行工作流**，另一方面也是为了让 `codex-agent` 与 `claude-agent` 在 OpenClaw 下具备一致的可维护性与可诊断性。

## 它是什么？

一句话：**OpenClaw 代替用户操作 Codex CLI**。

Codex 是 OpenAI 的终端编程工具，很强，但需要你坐在电脑前盯着它——写提示词、等输出、审批命令、检查结果。这个 skill 让 OpenClaw 替你做这些事。

本质就两样东西：**tmux + hook**。

- **tmux**：Codex 跑在 tmux session 里，OpenClaw 通过 tmux 读输出、发指令，和人在终端里操作一模一样
- **hook**：Codex 完成任务或等审批时，自动通知用户（Telegram）+ 唤醒 OpenClaw 处理

用户随时可以 `tmux attach` 接入，看 Codex 在干什么，甚至直接接管操作。

## 完全体 Codex

普通用法：你手动写提示词丢给 Codex，Codex 只知道你告诉它的东西。

OpenClaw 在发任务给 Codex 之前，会：

1. **识别本机环境**：当前装了哪些 MCP server（Exa 搜索、Chrome 控制等）、哪些 Skills、哪些模型可用
2. **根据任务选模型**：简单 bug 用快模型，架构设计用强模型，代码搜索用 code 专用模型
3. **设计提示词**：不是转发用户原话，而是基于知识库 + 提示词模式库，针对任务类型构造最优提示词——告诉 Codex 它能用什么工具、该怎么分步骤、输出什么格式
4. **开启合适的 feature flags**：比如 `multi_agent`、`web_search`、`shell_snapshot` 等，按需启用

这意味着 Codex 每次收到的都是一个**充分利用本机全部能力**的精心设计的任务，而不是用户随手写的一句话。

## 解决什么问题？

正常用 Codex 的流程：

```
你坐在电脑前 → 打开终端 → 想提示词 → 启动 Codex → 盯着输出 →
审批命令 → 不满意就重来 → 满意了收工
```

用了这个 skill：

```
你躺在床上 → 在 Telegram 里说"帮我给这个项目加个 XX 功能" →
OpenClaw 开 Codex 干活 → 中间过程自己处理 → 完事了 Telegram 通知你 →
不满意？说一句就继续改 → 想看过程？tmux attach 看直播
```

**核心价值：用户当老板，OpenClaw 当员工，Codex 当工具。**

## 工作流程

```
1. 用户下任务（Telegram / 终端 / 任何渠道）
     ↓
2. OpenClaw 理解需求，追问不清楚的地方
     ↓
3. OpenClaw 设计提示词，选择执行模式，和用户确认
     ↓
4. OpenClaw 在 tmux 里启动 Codex
     ↓
5. Codex 干活，OpenClaw 通过 hook 被唤醒：
   ├── 任务完成 → OpenClaw 检查输出质量
   │   ├── 满意 → Telegram 通知用户，汇报结果
   │   └── 不满意 → 让 Codex 继续改
   ├── 等待审批 → OpenClaw 判断批准/拒绝
   └── 方向性问题 → 立即找用户确认
     ↓
6. 用户收到最终结果
   （整个过程可以随时 tmux attach 接入）
```

中间过程 OpenClaw 全权处理，但**每一步都会同步发送到 Telegram**——任务完成、审批等待、输出内容，用户在手机上实时可见。你可以选择不管（让 OpenClaw 自主处理），也可以随时插话干预。

## 技术原理：tmux + hook

### tmux：像人一样操作终端

OpenClaw 操作 Codex 的方式和人完全一样：

```bash
# 启动 Codex（和你在终端里敲一样）
tmux send-keys -t codex-session 'codex --full-auto' Enter

# 发送提示词（和你打字一样）
tmux send-keys -t codex-session '帮我实现 XX 功能'
sleep 1
tmux send-keys -t codex-session Enter

# 查看输出（和你看屏幕一样）
tmux capture-pane -t codex-session -p
```

tmux 的好处：
- **不受 OpenClaw turn 超时限制**：Codex 跑多久都行，OpenClaw 被唤醒时再来看
- **用户可以随时接入**：`tmux attach -t codex-session` 就能看到 Codex 的实时输出
- **持久化**：OpenClaw 重启、网络断开，Codex 都不受影响

### hook：任务完成和审批等待的自动通知

两套机制覆盖两种事件：

**1. Codex notify hook（任务完成）**

Codex 自带的 `notify` 配置，任务完成时调用脚本：

```
Codex 完成 turn → on_complete.py
                  ├── 📱 Telegram / Discord thread 通知用户（Codex 完整回复内容）
                  └── 🤖 openclaw agent 唤醒（OpenClaw 自动检查输出）
```

用户在 Telegram / Discord thread 上能看到 Codex 每次回复的完整内容，相当于实时监控。

若单次回复过长，`on_complete.py` 现在会对 Discord 通知执行**自动分片发送**，而不是简单截断：
- 超过 Discord 安全长度时自动拆成多条；
- 每条都会带分片编号，如 `[1/N]`、`[2/N]`；
- 分片逻辑优先按空行、换行、空格切分；
- 对 fenced code block（```）做了代码块感知处理：若在代码块中间切开，会自动在当前分片补 closing fence，并在下一分片补回 opening fence，避免 Discord 渲染错乱。

> 兼容性说明：在部分 Codex 版本中，`agent-turn-complete` payload 可能不会稳定回传 `CODEX_AGENT_SESSION`。当前实现会优先按 session marker 识别；若缺失，则按 `cwd` 回退解析 route，从而继续把完成通知发回正确的受管 thread。

**2. tmux pane monitor（审批等待）**

Codex 的 notify 不覆盖审批场景，所以用 `pane_monitor.sh` 监控 tmux 输出：

```
Codex 弹出审批提示 → pane_monitor.sh 检测到关键词
                     ├── 📱 Telegram 通知用户（待审批的具体命令）
                     └── 🤖 openclaw agent 唤醒（OpenClaw 自主判断批准/拒绝）
```

两套机制都是**双通道同时触发**：用户和 OpenClaw 同时收到消息。用户看到后可以不管（OpenClaw 会处理），也可以直接回复干预。

### 用户随时可接管

这不是黑箱。任何时候：

- `tmux attach -t codex-session`：直接看 Codex 在干什么
- 在 tmux 里直接打字：接管操作
- `tmux detach`：看完了，还给 OpenClaw 继续

## 两种审批模式

启动前由用户选择：

| 模式 | 谁审批 | 适用场景 |
|------|--------|---------|
| **Codex 自动** (`--full-auto`) | Codex 自己判断 | 常规开发，省心 |
| **OpenClaw 审批** (`--approval`) | OpenClaw 判断批准/拒绝 | 敏感操作，需要把关 |

`start_codex.sh` 现在默认使用 **Codex 自动**（也就是默认免审批启动）；只有显式传 `--approval` 才切回人工审批模式。

两种模式下 pane monitor 都会启动（`--full-auto` 偶尔也会弹审批）。

## 知识库：OpenClaw 真正理解 Codex

OpenClaw 不是盲目转发命令。它维护一套 Codex 知识库：

| 文件 | 内容 |
|------|------|
| `features.md` | 30+ feature flags、斜杠命令、CLI 子命令 |
| `config_schema.md` | config.toml 完整字段定义 |
| `capabilities.md` | 本机 MCP/Skills/模型能力 |
| `prompting_patterns.md` | 提示词模式库（按任务类型） |
| `UPDATE_PROTOCOL.md` | 5 级数据源更新协议 |
| `changelog.md` | 版本变更 + 实测发现 |

知识库会过时，所以有更新协议：版本变更 / 超 7 天 / 手动触发时，按 CLI 自省 → Schema → GitHub → 官方文档 → 社区的优先级更新。

## 文件结构

```
codex-agent/
├── SKILL.md                    # OpenClaw 工作流指令（给 OpenClaw 读的）
├── README.md                   # 本文件（给人读的）
│
├── hooks/
│   ├── on_complete.py          # Codex 完成 → Telegram + OpenClaw 唤醒
│   ├── pane_monitor.sh         # 审批检测 → Telegram + OpenClaw 唤醒
│   ├── start_codex.sh          # 一键启动（Codex + monitor）
│   └── stop_codex.sh           # 一键清理
│
├── knowledge/                  # Codex 知识库（6 文件）
│   ├── features.md
│   ├── config_schema.md
│   ├── capabilities.md
│   ├── prompting_patterns.md
│   ├── UPDATE_PROTOCOL.md
│   └── changelog.md
│
├── workflows/
│   ├── standard_task.md        # 标准任务流程
│   └── knowledge_update.md     # 知识库更新流程
│
├── references/
│   └── codex-cli-reference.md  # CLI 命令参考
│
└── state/
    ├── version.txt             # 当前 Codex 版本
    └── last_updated.txt        # 知识库最后更新日期
```

## 快速开始

详细的安装步骤见 **[INSTALL.md](INSTALL.md)**（7 步，约 5 分钟）。

或者，把下面这段话直接发给你的 OpenClaw，它会自动帮你完成配置：

> 请帮我安装和配置 codex-agent skill。
> 先读一遍完整的安装指南 `~/.openclaw/workspace/skills/codex-agent/INSTALL.md`，然后按照步骤帮我完成配置。
> 如果还没有这个文件，先从 https://github.com/dztabel-happy/codex-agent 克隆到 `~/.openclaw/workspace/skills/codex-agent/`，再读 INSTALL.md 执行。

配置完成后，在 Telegram 里对 OpenClaw 说一句话就能用：

如果要把单个 Codex session 固定到某个 Discord thread，建议直接用：

```bash
cd ~/.openclaw/workspace/skills/codex-agent
CODEX_AGENT_SOURCE_CHAT_ID="channel:<thread_id>" \
CODEX_AGENT_SOURCE_CHANNEL="discord" \
CODEX_AGENT_SOURCE_ACCOUNT="coder" \
CODEX_AGENT_SOURCE_AGENT_NAME="coding" \
bash hooks/start_codex.sh codex-<name> /path/to/project
```

如需该 session 改回审批模式，再追加 `--approval`。

> "用 Codex 帮我在 /path/to/project 实现 XX 功能"

## 更新

已安装的用户更新到最新版本：

```bash
cd ~/.openclaw/workspace/skills/codex-agent
git pull
```

更新日志见 **[CHANGELOG.md](CHANGELOG.md)**。

## 前置条件

- [OpenClaw](https://github.com/openclaw/openclaw) 已安装并运行
- [Codex CLI](https://github.com/openai/codex) 已安装
- tmux 已安装
- Telegram 已配置为 OpenClaw 消息通道
- ⚠️ **OpenClaw session 自动重置必须关闭或调大**（默认每天重置会丢失 Codex 任务上下文，详见 [INSTALL.md](INSTALL.md#第四步配置-openclaw-session-重置)）

### 环境变量配置

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `CODING_AGENT_NAME` | `coding` | 只有 agent_name 等于此值时才触发 hook（避免 main 等其他 agent 误触发导致余额耗尽） |

```bash
# 示例：自定义 agent 名称
export CODING_AGENT_NAME=coder
```

## 踩过的坑

| 问题 | 解决 |
|------|------|
| OpenClaw 默认每天重置 session，长任务上下文丢失 | 关闭自动重置（见前置配置） |
| tmux send-keys 文本 + Enter 一起发，Codex 不响应 | 分两次发，中间 sleep 1s |
| `--full-auto` 与 shell alias 冲突报错 | 检查 `~/.bashrc` / `~/.zshrc` 是否有 codex alias，确保 tmux 里用的是原生命令 |
| Codex notify 不覆盖审批等待 | pane_monitor.sh 补齐 |
| `--full-auto` 偶尔也弹审批 | pane monitor 所有模式都启 |
| Codex memories 不工作 | `disable_response_storage = true` + custom provider 不兼容，不启用 |
| notify payload 缺少字段文档 | `turn-id` 和 `cwd` 是实测发现的 |

## 未来计划

- [ ] 复制模式到 Claude Code / OpenCode agent
- [ ] 补充更多提示词模式（代码审查、架构设计）
- [ ] pane monitor 支持更多审批模式检测
