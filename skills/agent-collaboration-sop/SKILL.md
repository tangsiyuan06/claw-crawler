# Agent 协作 SOP

**版本**: v2.0.0
**创建日期**: 2026-03-02
**维护者**: SOP Agent
**状态**: ✅ 已发布

---

## 🎯 定位

本技能是多 Agent 协作的**标准操作规范（SOP）**，定义 Agent 之间协作的流程、规范和准则。

- **本技能定义**：做什么、什么时候做、怎么判断完成
- **执行工具**：`agent-coordinator` 技能提供实际的跨 Agent 通讯和人类汇报能力

---

## 📡 协作通道

所有 Agent 间交互通过 `agent-coordinator` 执行，两种通道：

| 通道 | 用途 | 执行命令 |
|------|------|----------|
| Agent → Agent | 任务委派、结果回传、状态通知 | `coordinator.py send` |
| Agent → Human | 向人类汇报任务结果 | `coordinator.py reply-human` |

详细命令用法参见 `skills/agent-coordinator/SKILL.md`。

---

## 🔄 协作生命周期

```
发起方 Agent                                     执行方 Agent
    │                                                │
    │  1. 委派任务 (send --type request)             │
    │ ─────────────────────────────────────────────► │
    │                                                │
    │                                    2. 执行任务  │
    │                                                │
    │          3a. 回传结果 (send --type response)   │
    │ ◄───────────────────────────────────────────── │
    │                                                │
    │          3b. 遇阻反馈 (send --type request)    │
    │ ◄───────────────────────────────────────────── │
    │                                                │
    │  4. 向人类汇报 (reply-human)                   │
    │ ────► Human                                    │
```

### 各阶段规范

**1. 委派任务**
- 消息中必须包含：任务描述、优先级、预期交付物
- 使用 `--type request` 发送
- 格式：`[P{0-3}] {任务描述}。交付物：{预期产出}`

**2. 执行任务**
- 收到 request 后应尽快开始执行
- 按优先级响应时间要求（见下方优先级定义）

**3a. 回传结果**
- 任务完成后，使用 `--type response` 回传
- 必须包含：执行结果摘要、交付物位置/内容
- 设置 `--reply-to` 关联原始请求

**3b. 遇阻反馈**
- 无法完成时，向发起方发送 request 说明阻塞原因
- 必须包含：阻塞原因、已尝试的方案、需要的支持

**4. 向人类汇报**
- 人类交办的任务完成后，必须通过 `reply-human` 主动汇报
- 汇报内容：执行结果摘要 + 关键产出

---

## 📊 优先级定义

| 优先级 | 响应时间 | 适用场景 | 示例 |
|--------|---------|---------|------|
| **P0** | 立即 | 系统故障、核心功能阻塞 | 生产服务宕机 |
| **P1** | 4 小时内 | 重要功能延迟、关键依赖 | API 接入阻塞开发 |
| **P2** | 24 小时内 | 一般功能开发、文档补充 | 新技能开发 |
| **P3** | 72 小时内 | 优化改进、技术债务 | 代码重构 |

---

## 📋 协作场景示例

### 场景 1：Dev 委派 Ops 部署

```bash
# Dev Agent 发起委派
uv run skills/agent-coordinator/scripts/coordinator.py send \
  --from dev --to ops --type request \
  --message "[P1] 请部署 main 分支到生产环境。交付物：部署结果 + 健康检查状态"

# Ops Agent 完成后回传
uv run skills/agent-coordinator/scripts/coordinator.py send \
  --from ops --to dev --type response \
  --message "部署完成，v2.1.0 已上线，健康检查全部通过" \
  --reply-to "2026-03-03T10:00:00+08:00"
```

### 场景 2：任务完成后向人类汇报

```bash
# 任何 Agent 完成人类交办任务后
uv run skills/agent-coordinator/scripts/coordinator.py reply-human \
  --username cyril \
  --message "部署任务已完成：v2.1.0 上线，健康检查通过"
```

### 场景 3：执行遇阻反馈

```bash
# Crawler Agent 遇阻，向 Dev Agent 请求支持
uv run skills/agent-coordinator/scripts/coordinator.py send \
  --from crawler --to dev --type request \
  --message "[P1] API 爬取遇阻：目标站点增加了反爬机制，需要技术支持。已尝试：更换 UA、降低频率。需要：分析反爬策略并提供绕过方案"
```

### 场景 4：状态通知（不期望回复）

```bash
# Crawler Agent 通知数据已就绪
uv run skills/agent-coordinator/scripts/coordinator.py send \
  --from crawler --to main --type notify \
  --message "电商 API 数据采集完成，结果已写入 data/ecommerce-apis.json"
```

---

## 🤝 Agent 职责分工

| Agent ID | 职责 | 典型委派方向 |
|----------|------|-------------|
| `main` | 日常对话 + 通用任务 | 接收人类指令，分发给专业 Agent |
| `dev` | 技能开发 + 技术方案 | 委派 ops 部署，委派 crawler 采集数据 |
| `sop` | SOP 制定 + 流程优化 | 制定标准，审查各 Agent 协作质量 |
| `ops` | 运维部署 + 监控 | 执行部署，通知相关 Agent 部署结果 |
| `crawler` | 数据爬取 + API 分析 | 完成数据采集后通知请求方 |

---

## ⚠️ 协作准则

1. **有来必有回**：收到 `request` 必须回传 `response`（完成结果或阻塞说明）
2. **按优先级响应**：严格遵守 P0-P3 响应时间
3. **主动汇报**：人类交办的任务完成后，必须通过 `reply-human` 汇报
4. **包含上下文**：委派任务时给出足够的背景信息和明确的交付物要求
5. **遇阻及时反馈**：不要等到超时才反馈，发现无法完成应立即通知发起方

---

## 📁 目录结构

```
skills/agent-collaboration-sop/
└── SKILL.md              # 协作 SOP 标准（本文件）
```

执行工具：`skills/agent-coordinator/`

---

**版本历史**:
- v2.0.0 (2026-03-03): 重构为纯 SOP 标准，执行层统一使用 agent-coordinator
- v1.0.0 (2026-03-02): 初始版本
