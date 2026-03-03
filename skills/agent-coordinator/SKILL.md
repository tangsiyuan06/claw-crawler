# Agent Coordinator - 多 Agent 协同调度

**版本**: v2.0.0
**创建日期**: 2026-03-03
**维护者**: Dev Agent
**状态**: ✅ 已发布

---

## 🎯 技能目标

多 Agent 协作的**执行工具层**，提供跨 Agent 通讯和人类汇报的底层能力。

- **Agent → Agent**：通过 crontab 消息总线实现异步协调（任务委派、结果回传、状态通知）
- **Agent → Human**：通过飞书 API 向人类主动汇报任务结果
- **用户管理**：每个 Agent 在自己的工作空间维护用户列表

协作的流程规范和准则定义在 `agent-collaboration-sop` 技能中，本技能负责执行。

> 由于 `sessions_send` 受 session 隔离限制无法跨 agent 通讯，本技能利用 **crontab 一次性定时任务**作为消息总线。

---

## 📡 通讯原理

### Agent → Agent 协调（crontab 消息总线）

```
Agent A                    Crontab 服务                  Agent B
  │                            │                            │
  │  1. 调用 cron.add          │                            │
  │  (agentId=B, +20s)        │                            │
  │ ─────────────────────────► │                            │
  │                            │  2. 定时触发               │
  │                            │  systemEvent → Agent B     │
  │                            │ ──────────────────────────►│
  │                            │                            │
  │                            │  3. Agent B 处理消息       │
  │                            │  可通过同样方式回复        │
```

**核心机制**：通过 `cron.add` 创建一次性定时任务（`deleteAfterRun: true`），任务携带 `agentId` 字段指定目标 agent，`payload` 中包含结构化消息信封。定时任务触发时，消息作为 `systemEvent` 送达目标 agent 的 `main` session。

### Agent → Human 汇报（飞书 API）

任务完成后，Agent 通过飞书 Open API 主动向人类汇报结果，使用用户的 `open_id` 发送消息。

---

## 📨 消息信封格式

所有 Agent 间消息使用统一的 JSON 信封格式：

```json
{
  "protocol": "agent-coordinator/v1",
  "from": "dev",
  "to": "ops",
  "type": "request",
  "payload": "请帮忙检查服务器状态",
  "reply_to": null,
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

### 向人类汇报结果（飞书）

通过 `--username` 指定目标用户，自动从当前 agent 的 `users.json` 查找 open_id。

```bash
uv run skills/agent-coordinator/scripts/coordinator.py reply-human \
  --username cyril \
  --message "代码审查已完成，发现 2 个问题"
```

### 用户管理

管理当前 agent 工作空间中的用户列表。每个 agent 独立维护自己的 `users.json`。

**添加/更新用户**
```bash
uv run skills/agent-coordinator/scripts/coordinator.py user add \
  --username alice --name "Alice" --open-id ou_xxx
```

**列出用户**
```bash
uv run skills/agent-coordinator/scripts/coordinator.py user list
```

**查看用户详情**
```bash
uv run skills/agent-coordinator/scripts/coordinator.py user get --username alice
```

**删除用户**
```bash
uv run skills/agent-coordinator/scripts/coordinator.py user remove --username alice
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
3. 约 20 秒后，目标 agent 收到 systemEvent，payload.text 中包含消息信封

### reply-human 命令

1. 确保用户已通过 `user add` 添加到当前 agent 的用户列表
2. 运行 `reply-human --username xxx --message "..."` 发送飞书消息

协作场景示例参见 `skills/agent-collaboration-sop/SKILL.md`。

---

## 👥 用户数据结构

每个 agent 在自己的工作空间中维护 `skills/agent-coordinator/data/users.json`。由于不同 agent 绑定不同的飞书应用，同一用户的 open_id 在各 agent 之间不同，因此各自独立管理。

```json
{
  "cyril": {
    "name": "Cyril",
    "open_id": "ou_xxx"
  }
}
```

| 字段 | 说明 |
|------|------|
| key (username) | 唯一标识，跨 agent 通过 username 指代同一用户 |
| `name` | 显示名 |
| `open_id` | 当前 agent 飞书应用下该用户的 open_id |

首次使用 `user` 命令时会自动创建 `data/` 目录和空 JSON 文件。

---

## ⚠️ 注意事项

1. **消息延迟**：crontab 消息有约 20 秒延迟，不适用于实时交互
2. **单向传递**：每次 send 只发送一条消息，双向通讯需要双方各自 send
3. **deleteAfterRun**：所有消息任务执行后自动删除，不会积压
4. **消息识别**：收到 systemEvent 时，检查是否包含 `agent-coordinator/v1` 协议标识来判断是否为 agent 消息
5. **open_id 不可跨 agent 复用**：不同 agent 绑定不同的飞书应用，同一用户在各 agent 下有不同的 open_id。每个 agent 在自己的工作空间维护用户列表，通过 `--username` 查找

---

## 📁 目录结构

```
skills/agent-coordinator/
├── SKILL.md              # 技能定义（本文件）
├── data/
│   └── users.json        # 用户列表（自动创建）
└── scripts/
    └── coordinator.py      # 协同调度脚本
```

---

**版本历史**:
- v2.0.0 (2026-03-03): 重命名为 Agent Coordinator，简化用户管理（每 agent 独立工作空间）
- v1.0.0 (2026-03-03): 初始版本（原 Agent Messenger）
