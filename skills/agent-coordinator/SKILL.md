# Agent Coordinator - 多 Agent 协同调度

**版本**: v2.1.1
**创建日期**: 2026-03-03
**更新日期**: 2026-03-04
**维护者**: Dev Agent
**状态**: ✅ 已发布

---

## 🎯 技能目标

多 Agent 协作的**执行工具层**，提供跨 Agent 通讯和人类汇报的底层能力。

- **Agent → Agent**：通过 crontab 消息总线实现异步协调（任务委派、结果回传、状态通知）
- **Agent → Human**：通过飞书 API 向人类主动汇报任务结果
- **用户管理**：每个 Agent 在自己的工作空间维护用户列表

协作的流程规范和准则定义在 `agent-collaboration-sop` 技能中，本技能负责执行。

> **为什么用 cron 而不是其他方式？**
> - `sessions_send`（含 `agentToAgent` 配置）：可跨 agent 发送消息，但消息投递到目标 agent 的**特定 session**。各 agent 日常在飞书 DM 会话中活动，消息若发到 main session 则不会被处理
> - **cron.add（isolated + agentTurn）**：为目标 agent 创建独立 agentTurn，agent 被**强制唤醒处理**，不依赖 agent 当前所在 session

---

## 📡 通讯原理

### Agent → Agent 协调（OpenClaw Cron Jobs）

```
Agent A                    OpenClaw Cron                 Agent B
  │                            │                            │
  │  1. cron.add               │                            │
  │  (agentId=B, at=T+20s)    │                            │
  │ ─────────────────────────► │                            │
  │                            │  2. 到达触发时间            │
  │                            │  agentTurn → Agent B       │
  │                            │  (isolated session)        │
  │                            │ ──────────────────────────►│
  │                            │  (deleteAfterRun: true)    │
  │                            │                            │
  │                            │  3. Agent B 处理并回传     │
```

**核心机制**：通过 OpenClaw 内置的 `cron.add` 工具创建一次性定时任务：
- `schedule.kind: "at"` + ISO 8601 时间戳，约 20 秒后触发
- `agentId` 指定目标 agent
- `sessionTarget: "isolated"` + `payload.kind: "agentTurn"` 创建独立会话，agent 主动处理消息
- `deleteAfterRun: true` 投递后自动清理

**为什么用 isolated 而不是 main？**
- Agent 通常在飞书会话中活动（如 `agent:sop:feishu:feishu-sop`），不监听 webchat main session
- `sessionTarget: "main"` 会把消息注入 webchat 会话，agent 看不到
- `sessionTarget: "isolated"` 创建独立的 agentTurn，**无论 agent 在哪个会话都能被触发处理**

参考：[OpenClaw Cron Jobs 文档](https://docs.openclaw.ai/automation/cron-jobs)

### Agent → Human 汇报（Cron Delivery）

任务完成后，Agent 通过 `reply-human` 生成 cron.add JSON（含 `delivery` 配置），由 OpenClaw 系统通过当前 agent 绑定的飞书 channel 自动发送消息。不需要飞书 app 凭证。

---

## 📨 消息信封格式

所有 Agent 间消息使用统一的 JSON 信封格式：

```json
{
  "protocol": "agent-coordinator/v1",
  "from": "dev",
  "to": "ops",
  "type": "request",
  "payload": "请部署 main 分支到生产环境",
  "reply_to": null,
  "notify_user": "cyril",
  "timestamp": "2026-03-03T10:00:00+08:00"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `protocol` | string | 固定值 `agent-coordinator/v1`，用于消息识别 |
| `from` | string | 发送方 agent ID |
| `to` | string | 接收方 agent ID |
| `type` | string | `request` / `response` / `notify` |
| `payload` | string | 消息正文内容 |
| `reply_to` | string\|null | 回复的原始消息 timestamp（可选） |
| `notify_user` | string\|null | 任务完成后需通知的用户名（目标 agent 用自己的 open_id 调 reply-human） |
| `timestamp` | string | ISO 8601 格式时间戳 |

### 消息类型说明

- **request**: 任务委派——请求目标 Agent 执行操作，期望收到 response 回传结果
- **response**: 结果回传——任务执行完毕后的结果报告，应设置 `reply_to` 关联原始请求
- **notify**: 状态通知——单向告知（如"数据已就绪"、"服务已重启"），不期望回复

---

## 🔧 可用命令

### 委派任务 / 同步状态给其他 Agent
```bash
uv run skills/agent-coordinator/scripts/coordinator.py send \
  --from dev \
  --to ops \
  --type request \
  --message "请检查服务器 CPU 使用率"
```

输出一段 crontab JSON，需要将此 JSON 作为参数调用 `cron.add` 工具完成发送。

### 向人类汇报结果（Cron Delivery）

通过 `--username` 指定目标用户，自动从当前 agent 的 `users.json` 查找 open_id，生成含 `delivery` 配置的 cron.add JSON。

```bash
uv run skills/agent-coordinator/scripts/coordinator.py reply-human \
  --username cyril \
  --message "代码审查已完成，发现 2 个问题"
```

输出 cron.add JSON，需要将此 JSON 作为参数调用 `cron.add` 工具完成发送。
OpenClaw 通过当前 agent 绑定的飞书 channel 自动投递，无需飞书 app 凭证。

### 用户管理

用户数据统一存储在 `/home/admin/.openclaw/data/users.json`，所有 agent 共享。
同一用户在不同 agent 下有不同的 open_id，通过 `--agent-id` 分别注册。

**添加/更新用户的某个 agent open_id**
```bash
uv run skills/agent-coordinator/scripts/coordinator.py user add \
  --username alice --name "Alice" --agent-id dev --open-id ou_xxx
```

**列出用户**
```bash
uv run skills/agent-coordinator/scripts/coordinator.py user list
```

**查看用户详情**
```bash
uv run skills/agent-coordinator/scripts/coordinator.py user get --username alice
```

**删除用户或某个 agent 的 open_id**
```bash
uv run skills/agent-coordinator/scripts/coordinator.py user remove --username alice
uv run skills/agent-coordinator/scripts/coordinator.py user remove --username alice --agent-id dev
```

### 列出可用 Agent
```bash
uv run skills/agent-coordinator/scripts/coordinator.py list-agents
```

---

## 📋 使用流程

### send 命令

1. 运行 `send` 命令生成 crontab JSON
2. 将输出的 JSON 作为参数调用 `cron.add` 工具
3. 约 20 秒后，目标 agent 在独立会话中被唤醒，收到 agentTurn 消息并执行任务
4. 如设置了 `--notify-user`，目标 agent 执行完毕后应调 `reply-human` 向用户汇报

### reply-human 命令

1. 确保用户已通过 `user add` 添加到当前 agent 的用户列表
2. 运行 `reply-human --username xxx --message "..."` 生成 cron delivery JSON
3. 将输出的 JSON 作为参数调用 `cron.add` 工具
4. 约 20 秒后，OpenClaw 通过当前 agent 的飞书 channel 自动发送消息给用户

协作场景示例参见 `skills/agent-collaboration-sop/SKILL.md`。

---

## 👥 用户数据结构

所有 agent 共享 `/home/admin/.openclaw/data/users.json`，按 agent 存储各飞书应用的 open_id。

不同 agent 绑定不同的飞书应用，同一用户在各 agent 下有**不同的 open_id**，通过 `--agent-id` 分别注册。

```json
{
  "cyril": {
    "name": "Cyril",
    "open_ids": {
      "main": "ou_aaa",
      "dev": "ou_bbb",
      "sop": "ou_ccc"
    }
  }
}
```

| 字段 | 说明 |
|------|------|
| key (username) | 唯一标识，跨 agent 通过 username 指代同一用户 |
| `name` | 显示名 |
| `open_ids` | 按 agent ID 分别存储各飞书应用下的 open_id |

首次使用 `user` 命令时会自动创建目录和空 JSON 文件。

---

## ⚠️ 注意事项

1. **消息延迟**：cron.add 一次性任务约 20 秒后触发，不适用于实时交互
2. **单向传递**：每次 send 只发送一条消息，双向协作需要双方各自 send
3. **自动清理**：`deleteAfterRun: true` 确保任务投递后自动删除，不会积压
4. **独立会话处理**：目标 agent 在 isolated session 中处理消息，无前置对话上下文，因此消息信封应包含完整的任务信息
5. **消息识别**：收到 agentTurn 消息时，检查是否包含 `agent-coordinator/v1` 协议标识来判断是否为协调消息
6. **cron.add 是内置工具**：`send` 命令只生成 JSON 参数，需要 agent 手动调用 `cron.add` 完成投递
7. **open_id 按 agent 区分**：不同 agent 绑定不同飞书应用，同一用户有不同 open_id。用户数据统一管理在 `/home/admin/.openclaw/data/users.json`，通过 `user add --agent-id` 分别注册

---

## 📁 目录结构

```
skills/agent-coordinator/
├── SKILL.md                # 技能定义（本文件）
└── scripts/
    └── coordinator.py      # 协同调度脚本

/home/admin/.openclaw/data/
└── users.json              # 用户列表（所有 agent 共享，自动创建）
```

---

**版本历史**:
- v2.1.1 (2026-03-04): 修复 delivery 配置：移除 accountId 字段，解决 cron announce delivery failed 问题
- v2.1.0 (2026-03-03): 修复会话路由：sessionTarget 从 main 改为 isolated + agentTurn，解决 agent 不监听 webchat 会话的问题
- v2.0.0 (2026-03-03): 重命名为 Agent Coordinator，简化用户管理（每 agent 独立工作空间）
- v1.0.0 (2026-03-03): 初始版本（原 Agent Messenger）
