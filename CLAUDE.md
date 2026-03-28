# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Workspace Is

This is the **CrawlerBot** OpenClaw agent workspace — a revenue-focused web crawling agent that extracts structured data from websites and coordinates with other agents in a multi-agent ecosystem. The agent runs on the OpenClaw platform and communicates via Feishu (飞书).

## Running Scripts

No centralized build or test runner exists. Scripts are executed directly.

### Crawler (main skill)

```bash
# 查询注册表 — 自动判断是否有现成脚本
conda run -n claw-crawler python3 skills/crawler/scripts/crawler.py match --url "https://www.grubhub.com/restaurant/.../ID"
# → matched: true  → 直接用 run 命令
# → matched: false → 需要创建新脚本（见 skills/crawler/SKILL.md 创建模式）

# 执行已注册脚本
conda run -n claw-crawler python3 skills/crawler/scripts/crawler.py run grubhub_menu \
  --url "https://www.grubhub.com/restaurant/.../ID" --output json
conda run -n claw-crawler python3 skills/crawler/scripts/crawler.py run doordash_menu \
  --url "https://www.doordash.com/store/902649" --output markdown

# 查看所有已注册脚本
conda run -n claw-crawler python3 skills/crawler/scripts/crawler.py list

# 直接运行专用脚本
conda run -n claw-crawler python3 skills/crawler/scripts/grubhub_menu.py --url "..." --output text
conda run -n claw-crawler python3 skills/crawler/scripts/doordash_menu.py --url "..." --output json
```

Requires: `pip install nodriver beautifulsoup4 requests` (nodriver 使用系统 Chrome，无需单独安装浏览器内核)

### Agent Coordinator
```bash
# Delegate task to another agent
python3 skills/agent-cron-job/scripts/coordinator.py send --from crawler --to sop --message "Task description"

# Schedule recurring delivery to user
python3 skills/agent-cron-job/scripts/coordinator.py schedule --every 30m --message "Check moltbook" --notify-user cyril

# Manage user registry
python3 skills/agent-cron-job/scripts/coordinator.py user list
```

### SearXNG (metasearch)
```bash
uv run skills/searxng/scripts/searxng.py search "query" --output json
sh skills/searxng/scripts/run-searxng.sh   # Start local SearXNG Docker instance
```

### Operational cron scripts
```bash
bash scripts/moltbook-check.sh     # Revenue opportunity check (runs every 30 min)
bash scripts/task-processor.sh     # Process pending tasks in task-queue/
bash scripts/skill-analysis.sh     # Generate skill inventory report
```

## Architecture

### Skill-based structure
Each capability lives in `skills/<name>/` with a `SKILL.md` manifest and `scripts/` directory. The `SKILL.md` defines trigger phrases, dependencies, and usage examples for the OpenClaw harness.

### Core skills
| Skill | Purpose |
|-------|---------|
| `skills/crawler/` | nodriver (CDP) 反爬爬虫工坊，含注册表、专用脚本、记忆库 |
| `skills/agent-cron-job/` | Inter-agent coordination and scheduling |
| `skills/searxng/` | Privacy-respecting web search |
| `skills/agent-collaboration-sop/` | P0-P3 priority protocol definitions |

### Crawler Skill 架构
`skills/crawler/` 是爬虫能力的完整载体，三种工作模式：

| 模式 | 触发场景 | 入口 |
|------|---------|------|
| **执行** | 目标网站已注册 | `crawler.py match/run` |
| **创建** | 新网站 | 读 `references/crawlerMemory.md` → `session.py` 探索 → 编写脚本 |
| **总结** | 说"总结爬虫经验" | 从 `.learning/` 提取通用模式 → 更新记忆库 |

关键文件：
- `scripts/crawler.py` — 注册表管理器（match / run / list / info）
- `scripts/{site}_menu.py` — 各站点专用 nodriver 爬虫
- `scripts/session.py` — 持久浏览器会话（开发探索用）
- `references/crawlerMemory.md` — 跨站点通用经验记忆库
- `references/nodriver-guide.md` — nodriver CDP API 速查
- `references/dev-environment.md` — 服务器部署与依赖说明
- `.learning/{site}.md` — 各站点开发日志

nodriver 反爬原理：直接使用系统 Chrome（非 Playwright 独立内核），CDP 读取响应 body，headless=False 可绕过 Cloudflare Bot Check。

### Inter-agent communication
Agents communicate asynchronously via **OpenClaw cron jobs** (not direct messages):
- `sessionTarget: "isolated"` + `payload.kind: "agentTurn"` wakes the target agent regardless of its active session
- Message envelope format: `{"protocol": "agent-coordinator/v1", "from": "...", "to": "...", "type": "request|response|notify", "payload": "..."}`
- Why cron and not sessions_send: agents operate in Feishu DM sessions, not the webchat main session

### Task queue (SOP → Crawler handoff)
SOP Agent drops JSON files into `task-queue/`. Crawler polls and processes them:
```json
{
  "taskId": "unique-id",
  "from": "sop", "to": "crawler",
  "type": "research",
  "priority": "normal|high|urgent",
  "status": "pending|processing|completed|failed",
  "task": { "title": "...", "target": "URL or keyword" },
  "result": { "findings": [], "summary": "..." }
}
```

### Agent ecosystem (5 agents)
`main` (dispatcher) → `dev` (code) / `sop` (process) / `ops` (infra) / **`crawler`** (data extraction — this workspace)

## Environment & Secrets

- `.env` sets `WORKSPACE_PATH`, `SEARXNG_URL`, `CHROMIUM_EXECUTABLE_PATH`, timeouts
- `scripts/moltbook-check.sh` and `skills/dalle-image-sender/scripts/send-image.js` contain embedded API tokens — treat as sensitive, never commit new secrets
- Users registry lives at `/home/admin/.openclaw/data/users.json` (shared across agents)

## Code Conventions

- **Python**: 4-space indent, ~100 col limit, type hints on public functions, `ensure_ascii=False` for CJK JSON
- **Shell**: uppercase constants, log output to files for cron tasks
- **JS**: 2-space indent, camelCase functions, PascalCase classes
- Docs and comments mix English and Chinese — keep language consistent within the file you edit
- Scripts must be self-contained; avoid adding heavyweight dependencies

## 新站点爬虫开发流程

开发新站点爬虫时，通过 crawler skill 的**创建模式**进行，完整流程见 `skills/crawler/SKILL.md`。要点：

1. **先查注册表**：`crawler.py match --url "..."` — matched:false 才进入创建流程
2. **加载记忆库**：读 `skills/crawler/references/crawlerMemory.md`，了解已知坑点
3. **持久会话探索**：用 `session.py` 启动浏览器，编写内联代码连接并捕获 API（**不用 Playwright MCP**）
4. **写开发日志**：探索中遇到的每个问题实时记录到 `skills/crawler/.learning/{site}.md`
5. **编写生产脚本**：保存到 `skills/crawler/scripts/{site}_menu.py`，必须包含 `CRAWLER_META` 字典
6. **nodriver 强制规则**：
   - `cdp.network.enable()` 必须在 `tab.get()` 之前
   - Handler 签名必须 `async def f(event, tab=None)`
   - 禁止在 `ResponseReceived` 读 body（用 `LoadingFinished`）
   - SPA 用轮询等待而非 `networkidle`
7. **总结经验**：说"总结爬虫经验"，将本次经验写入记忆库
