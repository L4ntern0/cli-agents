# cli-agents

用于 OpenClaw 和 agent-deck 的终端驱动 CLI agent 技能统一仓库。

## 快速开始

详细安装说明请查看 [INSTALL.md](./INSTALL.md)。

## 目录结构

- `codex-agent/` — 基于 tmux 的 Codex agent 技能
- `claude-agent/` — 基于 tmux 的 Claude Code agent 技能
- `bridge/` — 共享路由工具
  - `agent_session_router.py`
  - `reply_route_map.py`

## 目的

本仓库将 CLI agent 运行时统一为一个版本化单元，以便：

- `codex-agent` 和 `claude-agent` 可以同步演进
- 共享的桥接工具存放在同一位置
- agent-deck 可以基于稳定的目录结构进行集成

## 路径约定

在脚本中优先使用相对路径。

当前 `workspace-coding` 中的规范路径：

- `skills/cli-agents/codex-agent/...`
- `skills/cli-agents/claude-agent/...`
- `skills/cli-agents/bridge/...`

## 说明

- 路由状态保存在 `/tmp/codex-agent-routes` 和 `/tmp/claude-agent-routes`
- 桥接回复映射由 `bridge/reply_route_map.py` 实现
- 合并时已移除旧拆分仓库中的嵌套 `.git` 目录

## 线程消息自动转发（Agent 级实现）

自动转发通过 **AGENTS.md 规则**实现，OpenClaw agent 遵循以下规则：

### 关键规则

当消息到达已绑定 `codex-agent` 或 `claude-agent` tmux 会话的 Discord 线程时，**必须**先通过统一路由转发，再自行回复。除非路由返回退出码 2（无绑定）或 5（显式 @Coder 转义）。

### 路由流程

1. **始终先调用统一检测器**：
   ```bash
   python3 skills/cli-agents/bridge/agent_session_router.py --chat-id <chat_id> --channel <channel> --message "<text>"
   ```

2. **解析退出码**：
   - `0`: 转发成功 → 仅回复 `已转发到 <session-name>`
   - `2`: 无绑定 session → 在线程内自行回复
   - `4`: Session 不存在 → 说明情况，提供新建
   - `5`: 显式 @Coder 转义 → 在线程内自行回复

3. **后备**：如果路由执行失败（缺少依赖等），可直接回复但需记录问题

### 绑定源
- 路由文件：`/tmp/codex-agent-routes/<session>.json` 或 `/tmp/claude-agent-routes/<session>.json`
- 如果同一线程绑定多个 agent 类型，优先使用最新 `updated_at` 时间戳

### 回复格式
- 转发成功后：仅回复 `已转发到 <session-name>`
- 不要重复转发内容或添加额外说明

### 基于前缀的转发

当消息以 `>> ` 开头时，处理后转发到绑定 session：

1. 如果消息以 `>> ` 开头，去掉前缀并处理请求
2. **改进/扩展请求** - 如需要，添加上下文、澄清意图
3. 转发处理后的请求到绑定 session
4. 转发成功则回复 `已转发到 <session-name>`

**注意**：`>>` 前缀表示"让我先处理，然后转发到 CLI agent"

### 示例
- `>> 帮我检查这段代码` → 处理并转发
- `@Coder 你好` → 留在主 agent（转义）
- 普通消息 → 先尝试路由

## 通知系统

### Claude Code 通知（事件驱动）

Claude Code 使用原生 hooks 实现精确通知：

| 事件 | Hook | 触发时机 | 可靠性 |
|------|------|---------|---------|
| 任务开始 | `UserPromptSubmit` hook → `task_start.py` | 用户提交 prompt 时 | ✅ 事件驱动 |
| 任务完成 | `Stop` hook → `on_complete.py` | Claude 完成响应时 | ✅ 事件驱动 |

### Codex 通知（轮询）

Codex 没有原生 hooks，使用 pane 监控：

| 事件 | 方式 | 触发时机 | 可靠性 |
|------|------|---------|---------|
| 工作开始 | `pane_monitor.sh` | 检测 pane 中的 `Working (` 模式 | ⚠️ 轮询 |
| 任务完成 | `on_complete.py` | Codex `agent-turn-complete` 事件 | ✅ 事件驱动 |

### 对比

- **Claude Code**：开始和完成通知都是事件驱动的（精确）
- **Codex**：只有任务完成是事件驱动的；工作开始使用轮询

## 环境变量

### 启动脚本环境变量

| 变量 | 说明 |
|------|------|
| `CODEX_AGENT_SOURCE_CHAT_ID` | Discord 频道/线程 ID |
| `CODEX_AGENT_SOURCE_CHANNEL` | 频道类型（如 discord） |
| `CODEX_AGENT_SOURCE_ACCOUNT` | 发送通知的账号 |
| `CODEX_AGENT_SOURCE_AGENT_NAME` | agent 名称（默认 coding） |

### 路由脚本环境变量

| 变量 | 说明 |
|------|------|
| `OPENCLAW_REPLY_TO_MESSAGE_ID` | 被回复的消息 ID |
| `OPENCLAW_REFERENCED_MESSAGE_ID` | 引用的消息 ID |
| `OPENCLAW_QUOTED_MESSAGE_ID` | 引用（_quoted）的消息 ID |

## 相关文件

| 文件 | 用途 |
|------|------|
| `bridge/agent_session_router.py` | 统一路由逻辑 |
| `bridge/reply_route_map.py` | 回复目标映射 |
| `codex-agent/hooks/start_codex.sh` | Codex 会话启动器 |
| `codex-agent/hooks/pane_monitor.sh` | Codex 状态监控器 |
| `codex-agent/hooks/on_complete.py` | Codex 任务完成处理器 |
| `claude-agent/hooks/start_claude.sh` | Claude 会话启动器 |
| `claude-agent/hooks/pane_monitor.sh` | Claude 状态监控器 |
| `claude-agent/hooks/on_complete.py` | Claude 任务完成处理器 |
| `claude-agent/hooks/task_start.py` | Claude 任务开始处理器 |
| `monitor-daemon.sh` | 自动重启监控进程 |

## 另见

- [INSTALL.md](./INSTALL.md) — 详细安装指南
- [CHANGELOG.md](./CHANGELOG.md) — 版本历史
