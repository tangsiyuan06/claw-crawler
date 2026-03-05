# Agent Coordinator - 多 Agent 协同调度

**版本**: v2.2.0
**创建日期**: 2026-03-03
**更新日期**: 2026-03-05
**维护者**: Dev Agent
**状态**: ✅ 已发布

---

## 🎯 技能目标

多 Agent 协作的**执行工具层**，提供跨 Agent 通讯和人类汇报的底层能力。

- **Agent → Agent**：通过 crontab 消息总线实现异步协调（任务委派、结果回传、状态通知）
- **Agent → Human**：创建 cron job 时配置 `delivery`，agent 执行完任务后由 OpenClaw 自动投递结果给用户
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
  │                            │                            │
  │                            │                            │
  │                            │  3. Agent B 处理并回传     │
```

**核心机制**：通过 OpenClaw 内置的 `cron.add` 工具创建定时任务：
- `agentId` 指定目标 agent
- `sessionTarget: "isolated"` + `payload.kind: "agentTurn"` 创建独立会话，agent 主动处理消息
- 支持三种调度模式（见下方参考表）

**为什么用 isolated 而不是 main？**
- Agent 通常在飞书会话中活动（如 `agent:sop:feishu:feishu-sop`），不监听 webchat main session
- `sessionTarget: "main"` 会把消息注入 webchat 会话，agent 看不到
- `sessionTarget: "isolated"` 创建独立的 agentTurn，**无论 agent 在哪个会话都能被触发处理**

参考：[OpenClaw Cron Jobs 文档](https://docs.openclaw.ai/automation/cron-jobs)

### Agent → Human 汇报（Cron Delivery）

回复 human 是 OpenClaw cron job 的内置能力。创建 cron job 时配置 `delivery`（指定 channel 和用户 open_id），agent 执行完任务后，OpenClaw 自动将结果投递给用户。`send --notify-user` 和 `reply-human` 都是生成含 delivery 配置的 cron.add JSON。

### Agent 自建定时任务（Self-Schedule）

Agent 可以为**自己**创建定时任务，执行完后通过 delivery 将结果汇报给任务创建者。典型场景：

- 用户让 agent 定期执行某项检查（如健康检查、数据统计），结果自动发回给用户
- Agent 需要延时执行某个耗时操作，完成后主动通知用户

```
User                     Agent                    OpenClaw Cron
  │                        │                            │
  │  "每30分钟检查一下服务" │                            │
  │ ──────────────────────►│                            │
  │                        │  cron.add                  │
  │                        │  (agentId=自己, delivery=User)
  │                        │ ──────────────────────────►│
  │                        │                            │
  │                        │        定时触发 agentTurn   │
  │                        │◄──────────────────────────│
  │                        │  执行任务...               │
  │  delivery announce     │                            │
  │◄───────────────────────────────────────────────────│
```

**关键点**：`agentId` 填自己的 ID，`delivery.to` 填任务创建者的 open_id。Agent 被 cron 唤醒后在 isolated session 中执行任务，执行结果由 OpenClaw 自动投递给用户。

使用 `reply-human` 或 `schedule` 命令：
```bash
# 一次性（默认 T+20s）
uv run skills/agent-cron-job/scripts/coordinator.py reply-human \
  --agent-id sop --username cyril --message "检查 SOP 文档完整性"

# 每 30 分钟周期执行
uv run skills/agent-cron-job/scripts/coordinator.py schedule \
  --agent-id sop --every "30m" --username cyril --message "执行 SOP 健康检查"

# 每天 9 点执行（cron 表达式）
uv run skills/agent-cron-job/scripts/coordinator.py schedule \
  --agent-id sop --cron "0 9 * * *" --tz Asia/Shanghai \
  --username cyril --message "生成每日 SOP 状态报告"
```

### 调度模式参考

coordinator.py 的 `send`、`reply-human`、`schedule` 命令均支持以下三种调度模式：

| 模式 | 参数 | 用途 | 示例 |
|------|------|------|------|
| `at` | `--at "2026-03-05T12:00:00Z"` | 一次性定时 | 延时投递、单次提醒 |
| `every` | `--every "30m"` | 固定间隔 | 健康检查、定期巡检 |
| `cron` | `--cron "0 9 * * *" --tz Asia/Shanghai` | Cron 表达式 | 每日晨报、工作日任务 |

- 不传调度参数时默认 `at` 模式（T+20s）
- `--every` 支持格式：`30s`、`5m`、`1h`、`2h30m`
- `--tz` 仅在 `--cron` 模式下生效
- `--at`、`--every`、`--cron` 三者互斥

等效 `openclaw cron add` CLI 对照：
```bash
# at 一次性
openclaw cron add --name "task" --at "2026-03-05T12:00:00Z" \
  --session-target isolated --agent-id sop \
  --payload '{"kind":"agentTurn","message":"..."}'

# every 周期
openclaw cron add --name "task" --every 1800000 \
  --session-target isolated --agent-id sop \
  --payload '{"kind":"agentTurn","message":"..."}' \
  --delivery '{"mode":"announce","channel":"feishu","to":"ou_xxx","bestEffort":true}'

# cron 表达式
openclaw cron add --name "task" --cron "0 9 * * *" --tz Asia/Shanghai \
  --session-target isolated --agent-id sop \
  --payload '{"kind":"agentTurn","message":"..."}' \
  --delivery '{"mode":"announce","channel":"feishu","to":"ou_xxx","bestEffort":true}'
```

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
| `notify_user` | string\|null | 任务完成后需通知的用户名（cron job 配置 delivery 自动投递） |
| `timestamp` | string | ISO 8601 格式时间戳 |

### 消息类型说明

- **request**: 任务委派——请求目标 Agent 执行操作，期望收到 response 回传结果
- **response**: 结果回传——任务执行完毕后的结果报告，应设置 `reply_to` 关联原始请求
- **notify**: 状态通知——单向告知（如"数据已就绪"、"服务已重启"），不期望回复

---

## 🔧 可用命令

### 委派任务 / 同步状态给其他 Agent（send）
```bash
# 一次性（默认 T+20s）
uv run skills/agent-cron-job/scripts/coordinator.py send \
  --from dev --to ops --message "请检查服务器 CPU 使用率"

# 每天 9 点让 ops 检查服务状态
uv run skills/agent-cron-job/scripts/coordinator.py send \
  --from dev --to ops --cron "0 9 * * *" --tz Asia/Shanghai \
  --message "检查所有服务运行状态" --notify-user cyril

# 每 30 分钟检查一次
uv run skills/agent-cron-job/scripts/coordinator.py send \
  --from dev --to ops --every "30m" --message "服务健康检查"
```

输出一段 cron.add JSON，需要将此 JSON 作为参数调用 `cron.add` 工具完成发送。

### 委托 Agent 执行任务并汇报给用户（reply-human）

与 `send` 一样创建 cron job 让 agent 执行任务，区别是**始终配置 delivery**，agent 执行完后结果自动投递给用户。

通过 `--agent-id` 指定委托 agent，`--username` 指定汇报对象，自动从 `users.json` 查找该 agent 下的 open_id 配置到 delivery 中。

```bash
# 一次性任务（默认 T+20s）
uv run skills/agent-cron-job/scripts/coordinator.py reply-human \
  --agent-id ops --username cyril \
  --message "开始 v2.1.0 上线部署任务，汇报部署结果给 cyril"

# 每天早上 9 点生成日报
uv run skills/agent-cron-job/scripts/coordinator.py reply-human \
  --agent-id sop --username cyril \
  --cron "0 9 * * *" --tz Asia/Shanghai \
  --message "生成今日工作日报并汇报"
```

输出 cron.add JSON（含 delivery 配置），需要将此 JSON 作为参数调用 `cron.add` 工具完成发送。

### 独立创建定时任务（schedule）

不包裹消息信封，直接创建 cron job。适用于 Agent 自建任务场景。

```bash
# sop 每 30 分钟执行健康检查，结果发给用户
uv run skills/agent-cron-job/scripts/coordinator.py schedule \
  --agent-id sop --every "30m" --username cyril \
  --message "执行 SOP 健康检查"

# 30 分钟后提醒用户（一次性）
uv run skills/agent-cron-job/scripts/coordinator.py schedule \
  --agent-id main --at "2026-03-05T12:30:00Z" --username cyril \
  --message "提醒：会议即将开始"

# 无 delivery 的自检任务
uv run skills/agent-cron-job/scripts/coordinator.py schedule \
  --agent-id ops --every "1h" --message "检查磁盘空间和内存使用"
```

### 用户管理

用户数据统一存储在 `/home/admin/.openclaw/data/users.json`，所有 agent 共享。
同一用户在不同 agent 下有不同的 open_id，通过 `--agent-id` 分别注册。

**添加/更新用户的某个 agent open_id**
```bash
uv run skills/agent-cron-job/scripts/coordinator.py user add \
  --username alice --name "Alice" --agent-id dev --open-id ou_xxx
```

**列出用户**
```bash
uv run skills/agent-cron-job/scripts/coordinator.py user list
```

**查看用户详情**
```bash
uv run skills/agent-cron-job/scripts/coordinator.py user get --username alice
```

**删除用户或某个 agent 的 open_id**
```bash
uv run skills/agent-cron-job/scripts/coordinator.py user remove --username alice
uv run skills/agent-cron-job/scripts/coordinator.py user remove --username alice --agent-id dev
```

### 列出可用 Agent
```bash
uv run skills/agent-cron-job/scripts/coordinator.py list-agents
```

---

## 📋 使用流程

### send 命令

1. 运行 `send` 命令生成 cron.add JSON（可选 `--every`/`--cron`/`--at` 指定调度模式）
2. 将输出的 JSON 作为参数调用 `cron.add` 工具
3. 按调度规则触发，目标 agent 在独立会话中被唤醒执行任务
4. 如设置了 `--notify-user`，cron job 已配置 delivery，agent 执行完毕后结果自动投递给用户

### reply-human 命令

1. 确保用户已通过 `user add --agent-id <委托agent>` 注册了 open_id
2. 运行 `reply-human` 生成 cron.add JSON（含 delivery，可选调度参数）
3. 将输出的 JSON 作为参数调用 `cron.add` 工具
4. 按调度规则触发，委托 agent 执行任务，结果通过 delivery 自动投递给用户

### schedule 命令

1. 运行 `schedule` 生成 cron.add JSON（不包裹消息信封，可选 `--username` 配置 delivery）
2. 将输出的 JSON 作为参数调用 `cron.add` 工具
3. 按调度规则触发，agent 在独立会话中执行任务

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
3. **Job 清理**：`at` 类型任务 `deleteAfterRun` 默认 `true`，执行后自动清理，无需手动处理。`every`/`cron` 类型任务持续运行，需要时使用 `cron.remove` 手动清理
4. **独立会话处理**：目标 agent 在 isolated session 中处理消息，无前置对话上下文，因此消息信封应包含完整的任务信息
5. **消息识别**：收到 agentTurn 消息时，检查是否包含 `agent-coordinator/v1` 协议标识来判断是否为协调消息
6. **cron.add 是内置工具**：`send` / `reply-human` / `schedule` 命令只生成 JSON 参数，需要 agent 手动调用 `cron.add` 完成投递
7. **open_id 按 agent 区分**：不同 agent 绑定不同飞书应用，同一用户有不同 open_id。用户数据统一管理在 `/home/admin/.openclaw/data/users.json`，通过 `user add --agent-id` 分别注册
8. **结果回传统一用 delivery.announce**：配置了 `delivery` 后，OpenClaw 会自动将 agent 的回复投递给用户。**不要在定时任务中使用 message 工具手动发送**，否则用户会收到重复消息。delivery.announce 已验证可靠，之前的失败是因为 open_id 被大模型传递时丢字符导致
9. **open_id 准确性**：open_id 必须使用 `users.json` 中注册的准确值，不可手动输入或让大模型推测。大模型在传递 open_id 时可能丢失部分字符导致 delivery 失败
10. **测试定时任务**：测试时消息内容应明确标注为重要任务（如"这是一条重要的反馈测试任务"），避免 agent 在 main session 中将其判断为无关消息而忽略

---

## 📁 目录结构

```
skills/agent-cron-job/
├── SKILL.md                # 技能定义（本文件）
├── scripts/
│   └── coordinator.py      # 协同调度脚本
└── data/
    └── users.json          # 用户列表（所有 agent 共享，自动创建）

/home/admin/.openclaw/data/
└── users.json              # 用户数据统一存储位置
```

---

**版本历史**:
- v2.2.0 (2026-03-05): 多调度模式支持（`at`/`every`/`cron`），新增 `schedule` 命令，delivery 添加 `bestEffort`，移除 message-cmd/get-account-id（统一用 delivery.announce 回传）
- v2.1.1 (2026-03-04): 修复 delivery 配置：移除 accountId 字段，解决 cron announce delivery failed 问题
- v2.1.0 (2026-03-03): 修复会话路由：sessionTarget 从 main 改为 isolated + agentTurn，解决 agent 不监听 webchat 会话的问题
- v2.0.0 (2026-03-03): 重命名为 Agent Coordinator，简化用户管理（每 agent 独立工作空间）
- v1.0.0 (2026-03-03): 初始版本（原 Agent Messenger）
