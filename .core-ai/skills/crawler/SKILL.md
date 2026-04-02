---
name: crawler
description: >
  反爬增强网络爬虫工坊——执行爬取任务，或为新网站生成 nodriver 爬虫脚本。
  当用户提到「爬取」「抓取」「crawler」「scraper」「extract data from」「生成爬虫」
  「create crawler」「scaffold scraper」，或给出一个网站 URL 并要求提取数据时，
  立即触发此 skill。即便用户没有明确说「爬虫」，只要目标是从某网站批量提取结构化数据
  （菜单、商品、评论、列表、价格等），也应使用此 skill。
author: CrawlerBot
version: 3.0.0
homepage: https://github.com/tangsiyuan06/claw-crawler
metadata: {"clawdbot":{"emoji":"🕷️","requires":{"bins":["python3"],"pip":["nodriver","beautifulsoup4","requests"]}}}
---

# Crawler Skill — nodriver 爬虫工坊

## ⚠️ 执行前必读（违反 = 任务立即失败）

**每次触发此 skill，Agent 必须严格按以下顺序执行，不可跳步、不可乱序：**

1. **先读 SKILL.md 全文** — 了解所有规范要求
2. **立即创建完整 todo 列表** — 用 `write_todos` 一次性写出**所有步骤 + 子步骤 + spec-ref**，全部标记 `pending`。**禁止只写 Step 1，禁止边做边加。**
3. **按 todo 顺序逐步执行** — 每步执行前标 `in_progress`，完成后标 `completed`。**禁止批量标记。**
4. **每步执行时对照 spec-ref** — 确认该步骤的输出符合 skill 规范要求后再进入下一步。
5. **全部完成后再给用户结果** — 禁止在流程中途提前返回结果。

**常见违规模式（历史教训）：**
- ❌ 用 `web_fetch` 拿到数据后直接给结果，跳过 exploration、learning 文件、脚本编写
- ❌ todo 只写 "Step 1: 查询注册表"，后续步骤边做边加
- ❌ 脚本写到项目根目录而非 `{baseDir}/scripts/`
- ❌ 脚本缺少 CRAWLER_META、argparse、format_text/format_markdown
- ❌ 批量标记 todo 步骤为 completed
- ❌ todo 项不标注 spec-ref，执行时不参照规范

---

## ★ 脚本编写前检查清单（生成脚本前必须逐条确认）

**每次编写或修改生产脚本前，Agent 必须逐条确认以下 7 项，缺一不可：**

| # | 检查项 | 说明 | 违反后果 |
|---|--------|------|---------|
| 1 | **存放路径** | 脚本必须保存在 `{baseDir}/scripts/` 下（即 SKILL.md 所在目录的 scripts 子目录）。`{baseDir}` = `.core-ai/skills/crawler/`。禁止写到项目根目录 `skills/` 或其他位置 | 注册表找不到脚本，用户无法复用 |
| 2 | **CRAWLER_META** | 脚本顶部必须包含 `CRAWLER_META` 字典，含 `name`/`domains`/`data`/`framework`/`url_pattern`/`url_routes`/`output_formats`/`example` | 注册表无法发现脚本能力 |
| 3 | **argparse 三参数** | `main()` 必须使用 `argparse`，包含 `--url`(required)、`--output`(choices: json/text/markdown, default: json)、`--visible`(store_true) | 无法切换输出格式，无法调试 |
| 4 | **nodriver 模板框架** | 必须使用 Scraper 类 + `_scrape_async` + `uc.start()` + `uc.loop().run_until_complete()` 结构。即使是 SSR/DOM 场景也必须走此框架 | 接口不一致，无法被 crawler.py 调度 |
| 5 | **stdout 输出 + cleanup 抑制** | 数据必须 `print()` 到 stdout，禁止 `open()` 写文件。`main()` 末尾必须 `sys.stdout.flush()` + `os.dup2(os.open(os.devnull, os.O_WRONLY), 1)` | nodriver cleanup 消息污染 JSON，下游解析失败 |
| 6 | **三种输出格式** | 必须实现 `format_text()` 和 `format_markdown()` 函数，`main()` 中根据 `--output` 参数选择输出方式 | 用户无法获取可读格式 |
| 7 | **URL 路由映射** | 如果探索发现用户 URL 与数据 URL 不一致，必须在 `CRAWLER_META["url_routes"]` 中记录映射 | 用户传入首页时无法自动跳转到菜单页 |

### 禁止行为

- ❌ **禁止写简化版/内联脚本**（如 `import urllib; print(json.dumps(...))`）—— 无论任务多简单，必须走标准模板
- ❌ **禁止因 SSR 场景跳过 nodriver 框架**—— 即使数据在 HTML 中可直接解析，也必须使用 nodriver 启动浏览器，保持接口一致性
- ❌ **禁止事后补写**—— 不能先生成简化脚本再"补上" CRAWLER_META 和 argparse
- ❌ **禁止省略 format_text/format_markdown**—— 即使暂时用不到，也必须实现

### 正确做法

- ✅ 直接复制「标准脚本模板」，替换占位符
- ✅ 以 `{baseDir}/scripts/grubhub_menu.py` 或 `{baseDir}/scripts/skinnyscantina_menu.py` 为参考
- ✅ 生成后立即用 `python3 {script} --url "..." --output json` 验证

---

## ★ 强制规则：Todo 任务跟踪

**每次触发此 skill 时，Agent 必须首先创建并维护一个 todo 列表**，跟踪所有步骤的执行状态。
这确保任务完整性，避免遗漏步骤。

### Todo 使用规范（违反 = 任务失败）

1. **触发 skill 后立即创建 todo 列表** — 使用 `write_todos` 工具，**必须一次性写出所有步骤和子步骤**，全部列为 `pending`。禁止只写 "Step 1" 然后边做边加。
2. **每个 todo 项必须包含 `spec-ref`** — 标注该步骤应遵循的 skill 规范编号（如 `检查清单#1`、`强制规则#9`、`模板:标准脚本`），确保执行时对照规范要求。
3. **执行前标记 `in_progress`** — 开始某个步骤前，将其状态更新为 `in_progress`。
4. **完成后标记 `completed`** — 步骤完成后立即标记，**禁止批量标记多个步骤为 completed**。
5. **禁止跳过步骤** — 每个步骤必须按顺序执行，不可省略。即使某步结果为"不适用"，也必须执行后记录结论。
6. **禁止直接给结果** — 即使数据已获取，也必须走完完整流程（探索、记录、脚本、注册）。
7. **步骤间 checkpoint** — 每完成一个 Step（A/B/C/D/E），必须暂停确认该步骤输出符合规范要求，再进入下一步。
8. **最终确认** — 所有步骤完成后，逐项检查 todo 列表是否全部 `completed`，如有 `pending` 或 `in_progress` 则继续执行。

### Todo 模板（创建模式）— 必须完整写出，不可省略

```
- Step 1: 查询注册表判断模式 — pending
  └─ 1.1 运行 `crawler.py match --url "<URL>"` — spec-ref: "Step 1 注册表查询"
  └─ 1.2 根据 matched true/false 判断创建/执行模式 — spec-ref: "Step 1 注册表查询"

- Step A: 加载记忆库 — pending
  └─ A.1 读取 references/crawlerMemory.md — spec-ref: "Step A 加载记忆库"
  └─ A.2 提取同类站点 API 关键词、已知坑点、懒加载策略 — spec-ref: "Step A 加载记忆库"

- Step B0: 环境检查 — pending
  └─ B0.1 检查 conda env `claw-crawler` 是否存在 — spec-ref: "强制规则:环境检查"
  └─ B0.2 检查 nodriver/beautifulsoup4/requests 依赖 — spec-ref: "强制规则:环境检查"
  └─ B0.3 如缺失则安装，禁止跳过环境检查写内联脚本 — spec-ref: "禁止行为:禁止跳过环境检查"

- Step B0.5: 创建 .learning/{site_name}.md 文件骨架 — pending
  └─ B0.5.1 在 {baseDir}/.learning/ 下创建文件 — spec-ref: "B0.5 learning 文件骨架"
  └─ B0.5.2 写入 frontmatter（site/script/date/status/data_extracted）— spec-ref: "B0.5 learning 文件骨架"
  └─ B0.5.3 写入探索阶段和开发阶段骨架模板 — spec-ref: "B0.5 learning 文件骨架"

- Step B1: 启动持久会话 session.py — pending
  └─ B1.1 运行 `session.py start --url "<URL>"` — spec-ref: "B1 启动持久会话"
  └─ B1.2 记录输出的 Port 号 — spec-ref: "B1 启动持久会话"

- Step B2: Agent 探索目标站点 (API 拦截 / SSR 数据 / DOM) — pending
  └─ B2.1 编写探索脚本连接已有页面 — spec-ref: "B2 迭代探索代码模板"
  └─ B2.2 尝试 API 拦截（ResponseReceived + LoadingFinished 两阶段）— spec-ref: "强制规则#1-5"
  └─ B2.3 如 API 为空，尝试 SSR 数据（__NEXT_DATA__ 等）— spec-ref: "B2 迭代探索"
  └─ B2.4 如 SSR 为空，尝试 DOM 解析 — spec-ref: "B4 数据来源方案C"
  └─ B2.5 每次迭代后立即更新 .learning/{site_name}.md — spec-ref: "B0.5 强制规则:每次迭代后更新"
  └─ B2.6 记录确认的数据来源类型（A/B/C）和数据路径 — spec-ref: "B4 整理完善开发日志"

- Step B3: 关闭会话 — pending
  └─ B3.1 运行 `session.py stop` — spec-ref: "B3 关闭会话"

- Step B4: 整理完善开发日志 — pending
  └─ B4.1 确认数据来源类型（JSON API / SSR / DOM）并填写 — spec-ref: "B4 数据来源模板"
  └─ B4.2 填写探索中遇到的问题表 — spec-ref: "B4 问题表"
  └─ B4.3 记录 URL 路由映射（如有）— spec-ref: "强制规则#7:URL 映射"

- Step C: 编写生产脚本 — pending
  └─ C.1 脚本保存到 {baseDir}/scripts/{site_name}_scraper.py — spec-ref: "检查清单#1:存放路径"
  └─ C.2 写入 CRAWLER_META 字典（name/domains/data/framework/url_pattern/url_routes/output_formats/example）— spec-ref: "检查清单#2:CRAWLER_META"
  └─ C.3 实现 argparse 三参数（--url/--output/--visible）— spec-ref: "检查清单#3:argparse"
  └─ C.4 使用标准 nodriver 模板框架（Scraper 类 + _scrape_async + uc.start() + uc.loop()）— spec-ref: "检查清单#4:nodriver 模板"
  └─ C.5 实现 stdout 输出 + cleanup 抑制（flush + dup2）— spec-ref: "检查清单#5:stdout+cleanup"
  └─ C.6 实现 format_text() 和 format_markdown() — spec-ref: "检查清单#6:三种输出格式"
  └─ C.7 记录 URL 路由映射到 CRAWLER_META["url_routes"] — spec-ref: "检查清单#7:URL 路由映射"
  └─ C.8 注册脚本到 crawler.py — spec-ref: "禁止跳过流程:注册脚本"

- Step D: 验证脚本输出 — pending
  └─ D.1 运行 `--output json` 验证 JSON 输出可解析 — spec-ref: "正确做法:生成后立即验证"
  └─ D.2 运行 `--output text` 验证文本输出 — spec-ref: "检查清单#6:三种输出格式"
  └─ D.3 运行 `--output markdown` 验证 Markdown 输出 — spec-ref: "检查清单#6:三种输出格式"
  └─ D.4 验证数据完整性（分类数、菜品数、价格字段）— spec-ref: "Step D 脚本开发"

- Step E: 告知用户结果 — pending
  └─ E.1 输出脚本路径、开发日志路径、验证结果 — spec-ref: "Step E 告知用户"
  └─ E.2 提供下一步验证指引 — spec-ref: "Step E 告知用户"
```

### Todo 模板（执行模式）— 必须完整写出，不可省略

```
- Step 1: 查询注册表判断模式 — pending
  └─ 1.1 运行 `crawler.py match --url "<URL>"` — spec-ref: "Step 1 注册表查询"
  └─ 1.2 确认 matched: true，获取 run 命令 — spec-ref: "Step 1 注册表查询"

- Step 2: 运行已有脚本获取数据 — pending
  └─ 2.1 使用 crawler.py run 或直接执行脚本 — spec-ref: "执行模式"
  └─ 2.2 捕获 stdout 输出 — spec-ref: "检查清单#5:stdout 输出"

- Step 3: 验证输出完整性 — pending
  └─ 3.1 验证 JSON 可解析（无 cleanup 污染）— spec-ref: "强制规则#8:cleanup 抑制"
  └─ 3.2 验证数据字段完整性 — spec-ref: "Step D 验证"

- Step 4: 告知用户结果 — pending
  └─ 4.1 格式化输出数据摘要 — spec-ref: "Step E 告知用户"
```

### Todo 格式规范

每个 todo 项的 `content` 字段必须包含：
- **动作描述**：具体要做什么
- **`spec-ref:`**：标注应遵循的 skill 规范位置（如 `检查清单#1`、`强制规则#9`、`B0.5 骨架模板`）

示例：
```
content: "C.2 写入 CRAWLER_META 字典（含 name/domains/data/framework/url_pattern/url_routes/output_formats/example 7个字段） [spec-ref: 检查清单#2]"
```

---

### 禁止跳过流程

即使 Agent 已经通过其他方式（如 `web_fetch`）获取到数据，也**必须完成以下流程**：
1. 创建 `.learning/{site_name}.md` 开发日志
2. 记录数据来源、探索过程、遇到的问题
3. 编写生产脚本保存到 `scripts/{site_name}_menu.py`
4. 注册脚本到 `crawler.py` 注册表

**禁止行为**：
- ❌ 直接解析 HTML 给结果，不创建 learning 文件
- ❌ 直接解析 HTML 给结果，不编写生产脚本
- ❌ 跳过探索步骤，直接写脚本
- ❌ 一次性补写 learning 文件（必须迭代探索、实时更新）
- ❌ 只写 "Step 1" 到 todo，边做边加后续步骤
- ❌ 批量标记多个步骤为 completed
- ❌ todo 项不标注 `spec-ref`，导致执行时不参照规范

**正确做法**：
- ✅ 触发 skill 后立即用 `write_todos` 写出**完整** todo 列表（含所有子步骤和 spec-ref）
- ✅ 即使数据已获取，也要记录到 learning 文件
- ✅ 编写可复用的生产脚本
- ✅ 按 todo 步骤逐一执行，每步完成后才进入下一步
- ✅ 每个步骤执行时对照 `spec-ref` 确认符合规范要求

---

四种工作模式，统一入口：

| 模式 | 触发场景 | 操作 |
|------|---------|------|
| **执行** | 目标网站已有现成脚本 | 直接运行，返回结果 |
| **创建** | 新网站，无对应脚本 | 加载记忆库 → **探索验证** → 编写脚本 → 写开发日志 |
| **学习** | 说「学习爬虫经验」「学习开发日志」「learn crawler」 | 将 `.learning/` 下的开发经验自动整合到记忆库 |
| **总结** | 说「总结爬虫经验」或脚本开发完成 | 从 `.learning/` 提取通用模式，更新记忆库 |

---

## Step 1 — 查询注册表，判断模式

**首先运行 match 命令**，让注册管理器自动判断是否有现成脚本：

```bash
python3 {baseDir}/scripts/crawler.py match --url "<用户提供的 URL>"
```

返回 `matched: true` → **执行模式**，使用 `run` 字段中的命令
返回 `matched: false` → **创建模式**，为该域名生成新脚本

查看所有已注册脚本：
```bash
python3 {baseDir}/scripts/crawler.py list
python3 {baseDir}/scripts/crawler.py list --format json   # 机器可读
python3 {baseDir}/scripts/crawler.py info grubhub_menu   # 某脚本详情
```

---

## 执行模式

用注册管理器代理执行，或直接用 `run` 字段的命令：

```bash
# 通过管理器执行（推荐）
python3 {baseDir}/scripts/crawler.py run grubhub_menu \
  --url "https://www.grubhub.com/restaurant/.../ID" --output json

# 或直接执行
python3 {baseDir}/scripts/grubhub_menu.py --url "..." --output text
python3 {baseDir}/scripts/grubhub_menu.py --url "..." --output markdown
python3 {baseDir}/scripts/grubhub_menu.py --url "..." --visible   # 调试
```

### 单元测试
```bash
python3 -m pytest {baseDir}/scripts/test_grubhub_menu.py -v
```

---

## 创建模式

当目标网站没有现成脚本时，**禁止直接写脚本**。Agent 必须先自行探索目标站点，验证 API 和数据结构，再编写生产脚本。

### Step A — 加载记忆库

读取 `{baseDir}/references/crawlerMemory.md`，了解：
- 同类站点已验证的 API 关键词
- 已知坑点和反爬障碍
- 适用的懒加载触发策略

### Step B — Agent 用 nodriver 持久会话探索

**使用 `session.py` 启动持久浏览器会话**，Agent 可多次连接同一页面迭代探索，无需每次重启或重载。

#### B0 — 环境检查（必须在 B1 之前执行）

```bash
# 检查 conda 环境是否存在
conda env list | grep claw-crawler
```

- **环境不存在** → 先创建环境（见 `references/dev-environment.md` 第三章），再继续
- **环境存在但依赖缺失** → `conda run -n claw-crawler pip install nodriver beautifulsoup4 requests`
- **禁止跳过环境检查直接写内联脚本** — 如果 session.py 因环境问题无法运行，必须先解决环境，而不是绕过

#### B0.5 — 创建 learning 文件骨架（探索前）

**在启动浏览器之前**，先在 `{baseDir}/.learning/{site_name}.md` 创建文件骨架：

```bash
cat > {baseDir}/.learning/{site_name}.md << 'EOF'
---
site: {site_domain}
script: TBD
date: {today}
status: exploring
data_extracted: {目标数据描述}
---

## 探索阶段
### 数据来源
<!-- 探索中实时填写 -->

### 探索中遇到的问题（每次迭代实时追加）
| # | 问题 | 现象 | 排查过程 | 处理方式 |
|---|------|------|---------|---------|

## 开发阶段
<!-- 脚本开发时填写 -->
EOF
```

**强制规则：每次探索迭代后必须立即更新此文件**，追加发现的问题、捕获的 API 信息、排查过程。
禁止等全部成功后一次性补写——事后补写会丢失关键上下文。

#### B1 — 启动持久会话

```bash
# 基本启动
conda run -n claw-crawler python3 {baseDir}/scripts/session.py start \
  --url "https://目标URL"

# 指定代理
conda run -n claw-crawler python3 {baseDir}/scripts/session.py start \
  --url "https://目标URL" --proxy "http://127.0.0.1:7890"

# 指定端口（默认 9222）
conda run -n claw-crawler python3 {baseDir}/scripts/session.py start \
  --url "https://目标URL" --port 9333
```

会话启动后浏览器保持打开，终端持续输出捕获到的 JSON API。记录输出中的 `Port`（默认 9222）。

查看已捕获的 API 列表：
```bash
conda run -n claw-crawler python3 {baseDir}/scripts/session.py status
```

#### B2 — Agent 连接会话迭代探索

会话运行期间，Agent 编写内联代码通过 Bash 连接已有页面（**不重载页面**）：

```python
import asyncio, json, sys
import nodriver as uc
from nodriver import cdp

SESSION_PORT = 9222  # session.py 启动时输出的 Port

async def explore():
    pending = {}

    # ★ 连接到已有浏览器（不会重启 Chrome）
    browser = await uc.start(host="127.0.0.1", port=SESSION_PORT)
    tab = browser.main_tab   # 页面已加载，直接使用

    async def on_response_received(event: cdp.network.ResponseReceived, tab=None):
        ct = (event.response.headers or {}).get("content-type", "")
        if "json" in ct:
            pending[event.request_id] = event.response.url

    async def on_loading_finished(event: cdp.network.LoadingFinished, tab=None):
        if event.request_id not in pending:
            return
        url = pending.pop(event.request_id)
        try:
            body, _ = await tab.send(cdp.network.get_response_body(event.request_id))
            data = json.loads(body)
            print(f"\n[{len(body):>8}B] {url}")
            print(f"  {json.dumps(data, ensure_ascii=False)[:400]}")
        except Exception:
            pass

    tab.add_handler(cdp.network.ResponseReceived, on_response_received)
    tab.add_handler(cdp.network.LoadingFinished, on_loading_finished)

    # ★ 网络监听必须在操作之前启用
    await tab.send(cdp.network.enable())

    # 点击导航 tab 触发懒加载（按需调整 selector）
    for sel in ['[role="tab"]', 'nav a', '[data-testid*="category"]', '.tab', '.nav-item']:
        items = await tab.select_all(sel)
        if items:
            print(f"[nav] 找到 {len(items)} 个 '{sel}'，开始点击...", file=sys.stderr)
            for item in items[:8]:
                try:
                    await item.click()
                    await tab.wait(0.8)
                except Exception:
                    pass
            break

    await tab.wait(3)
    # ★ 不要调用 browser.stop()，否则会关闭 Chrome 会话

uc.loop().run_until_complete(explore())
```

运行命令：
```bash
conda run -n claw-crawler python3 /tmp/explore_{site}.py 2>/dev/null
```

**迭代探索**：每次修改代码只需重新运行上面的命令，页面状态保留，无需重载。

分析输出：
- 哪个端点响应体最大且含目标数据？
- 数据的具体 JSON 路径是什么？
- 是否有"骨架"接口需要更多交互触发？

如果捕获为空：
- 调整导航选择器，或用 `tab.evaluate()` 手动触发
- 检查 SSR 数据：`await tab.evaluate("JSON.stringify(window.__NEXT_DATA__ || {})")`
- 参考 `crawlerMemory.md` 7.1 节排查清单

**每次迭代后**：立即更新 `.learning/{site_name}.md`，追加发现的问题、捕获的 API 摘要、排查过程。

#### B3 — 探索完成后关闭会话

```bash
conda run -n claw-crawler python3 {baseDir}/scripts/session.py stop
```

#### B4 — 整理完善开发日志

探索阶段 `.learning/{site_name}.md` 已实时更新，此处做最后整理：确认数据来源、补充完整 JSON 路径、清理冗余信息。

基于 Step B **实际捕获验证的**数据，确认以下模板中的字段：

```markdown
## 探索阶段

### 数据来源（三选一或组合）

#### 方案 A — JSON API 拦截
- 目标端点关键词：`{api_keyword}`（如 `restaurant_gateway/feed`）
- 数据路径：`{json.path.to.items}`（如 `object.data.content[].entity`）
- 触发方式：{页面加载自动 / 点击 `{selector}` / 滚动}
- session status 捕获摘要（按大小排序的前 5 条）：

#### 方案 B — 页面内嵌数据（SSR）
- 数据位置：{`__NEXT_DATA__` / `__INITIAL_STATE__` / `<script type="application/json">`}
- 提取方式：`tab.evaluate("JSON.stringify(window.__NEXT_DATA__)")`
- 数据路径：`{json.path}`

#### 方案 C — DOM 解析
- 原因：{无 JSON API / 数据加密 / 静态 HTML}
- 目标容器选择器：`{selector}`（如 `article.menu-item`、`li[data-item]`）
- 关键字段提取方式：{CSS selector / XPath / 正则}
- 注意事项：{虚拟化渲染 / 分页 / 懒加载}

### 探索中遇到的问题（每次迭代实时追加）
| # | 问题 | 现象 | 排查过程 | 处理方式 |
|---|------|------|---------|---------|
| 1 |      |      |          |         |
```

每次探索迭代遇到新问题，**实时追加**到该文件，不要等全部完成后再补写。

### Step C — 编写生产脚本

基于 Step B **实际捕获验证的** API 端点和数据路径，编写脚本保存到
`{baseDir}/scripts/{site_name}_scraper.py`。

### 强制规则（违反导致静默失败）

  0. **脚本存放路径 — 必须使用 `{baseDir}` 即 skill 所在目录** — 所有生产脚本、开发日志、学习文件必须存放在 `{baseDir}` 下的对应子目录中（`{baseDir}/scripts/`、`{baseDir}/.learning/`、`{baseDir}/references/`）。`{baseDir}` 是 `.core-ai/skills/crawler/`。判断方法：SKILL.md 所在目录即为 `{baseDir}`，所有路径以该目录为基准。
  1. `await tab.send(cdp.network.enable())` 必须在 `tab.get()` **之前**调用
 2. Handler 签名必须是 `async def handler(event, tab=None)` — nodriver 自动注入 `tab`
 3. **禁止** `functools.partial` 绑定 `tab`
 4. **禁止**在 `ResponseReceived` 中读取 body — body 尚未下载
 5. 必须两阶段：ResponseReceived 记录 → LoadingFinished 读 body
 6. SPA 不用 `networkidle`；用元素选择器作为页面就绪信号
 7. **URL 映射 — 原始 URL → 实际数据 URL** — 探索阶段如果发现用户提供的 URL（如首页）不包含目标数据，需要跳转或导航到另一个 URL 才能获取数据，必须记录 `原始 URL → 实际数据 URL` 的映射关系并硬编码到脚本中。脚本执行时若匹配已映射的原始 URL，直接 `tab.get()` 跳转到实际数据 URL，**禁止运行时 DOM 检测判断是否需要跳转**。映射记录到 `CRAWLER_META` 的 `url_routes` 字段：
    ```python
    CRAWLER_META = {
        "url_routes": {
            "https://www.example.com/": "https://www.example.com/menus/",
            "https://www.example.com/": "https://www.example.com/food/",
        },
    }
    ```
 8. **nodriver cleanup 消息污染 stdout** — `browser.stop()` 和进程退出时 nodriver 会向 stdout 打印 `successfully removed temp profile` 消息，导致 JSON 等结构化输出被下游 `json.load()` 拒绝。**正确做法**：_scrape_async 中**不调用** `browser.stop()`，让浏览器随进程自然终止；在 `main()` 中先 `sys.stdout.flush()` 确保数据完整写出，然后 `os.dup2(os.open(os.devnull, os.O_WRONLY), 1)` 重定向 fd 1 抑制后续 cleanup 消息。错误做法：在 `print()` 之前重定向 fd 1（block-buffered 模式下缓冲数据全部丢失）
  9. **输出规范 — 禁止写文件，必须 stdout 输出** — 生产脚本是 agent 可调用的工具，不是独立运行的批处理程序。**必须**通过 `--output` 参数控制输出格式（json/text/markdown），数据打印到 stdout 供上游 `json.load()` 或管道消费。**禁止**在脚本中 `open()` 写 `.json` 文件。**必须**包含 `CRAWLER_META` 字典（注册表发现脚本所需）和 `argparse` 三参数（`--url`/`--output`/`--visible`）。即使是 SSR 场景（无需浏览器也能获取数据），也必须走 nodriver 模板框架，保持接口一致性。
 10. **中文/UTF-8 编码 — 禁止使用 `.encode().decode('unicode_escape')`** — 当 HTML 内嵌数据（如 Next.js `__next_f.push` chunks）同时包含原始 UTF-8 字符（中文、日文等）和 `\"` 转义引号时，`unicode_escape` 会把 UTF-8 多字节重新编码为 Latin-1 码位，导致中文变乱码（如 `鸡翅` → `é¸¡ç¿**正确做法**：手动扫描提取 push 数据（跳过 `\"` 转义），然后只做 `.replace('\\"', '"')` 替换引号，保留原始 UTF-8 字符不变。详见 `.learning/chinastarpa88.md` 中文乱码修复记录。

### 标准脚本模板

参考生产实现：`{baseDir}/scripts/grubhub_menu.py`

```python
#!/usr/bin/env python3
"""
{SiteName} {DataType} Scraper (nodriver edition)

Usage:
    python3 {site_name}_scraper.py --url "https://..." --output json
    python3 {site_name}_scraper.py --url "..." --output markdown
    python3 {site_name}_scraper.py --url "..." --visible
"""
import argparse, asyncio, json, os, sys
from typing import Dict, List, Optional

try:
    import nodriver as uc
    from nodriver import cdp
except (ModuleNotFoundError, ImportError):
    import os
    _root = os.path.join(os.path.dirname(__file__), "..", "..", "..", "nodriver-main")
    sys.path.insert(0, os.path.abspath(_root))
    import nodriver as uc
    from nodriver import cdp

# ★ 必须包含：crawler.py 注册表通过此字段发现脚本能力
CRAWLER_META = {
    "name": "{site_name}_scraper",
    "domains": ["{site_domain}"],                      # 例: ["doordash.com"]
    "data": "{目标数据描述}",                             # 例: "餐厅菜单：分类、菜品、价格"
    "framework": "nodriver",
    "url_pattern": "{url_pattern}",                    # 例: "https://doordash.com/store/{id}"
    "url_routes": {                                     # 原始 URL → 实际数据 URL（探索阶段记录）
        "{user_url}": "{actual_data_url}",              # 例: "https://www.x.com/": "https://www.x.com/menus/"
    },
    "output_formats": ["json", "text", "markdown"],
    "example": 'python3 {site_name}_scraper.py --url "..." --output json',
}


class {SiteName}Scraper:
    def __init__(self, headless: bool = False):
        self.headless = headless  # False = 更好的反爬效果

    async def _scrape_async(self, url: str) -> Dict:
        result: Dict = {}
        config = uc.Config(
            headless=self.headless,
            browser_args=["--no-sandbox", "--disable-dev-shm-usage", "--window-size=1920,1080"],
        )
        browser = await uc.start(config=config)
        tab = browser.main_tab

        # ★ CRITICAL: 必须在 tab.get() 之前
        await tab.send(cdp.network.enable())

        # ★ URL 映射：用户提供的 URL 可能不包含数据，直接跳转到实际数据 URL
        # 探索阶段记录的 CRAWLER_META["url_routes"] 中查找
        actual_url = CRAWLER_META.get("url_routes", {}).get(url, url)
        if actual_url != url:
            print(f"  [route] {url} -> {actual_url}", file=sys.stderr)

        pending: Dict[str, str] = {}

        async def on_response_received(event: cdp.network.ResponseReceived, tab=None):
            if "{api_keyword}" in event.response.url:
                pending[event.request_id] = event.response.url

        async def on_loading_finished(event: cdp.network.LoadingFinished, tab=None):
            if event.request_id not in pending:
                return
            url = pending.pop(event.request_id)
            try:
                body, _ = await tab.send(cdp.network.get_response_body(event.request_id))
                result[url] = json.loads(body)
                print(f"  [captured] {url[:80]}", file=sys.stderr)
            except Exception:
                pass

        tab.add_handler(cdp.network.ResponseReceived, on_response_received)
        tab.add_handler(cdp.network.LoadingFinished, on_loading_finished)

        await tab.get(actual_url)
        await tab.select("body", timeout=15)  # ★ 不用 networkidle
        await tab.wait(3)

        # ★ 如有懒加载导航栏，点击每项触发 API 调用
        # nav_items = await tab.select_all(".nav-selector")
        # for nav in nav_items:
        #     await nav.click(); await tab.wait(0.6)

        # ★ 不调用 browser.stop() — 它输出的 cleanup 消息会污染 stdout
        # 让浏览器随进程退出自然终止

        await tab.wait(2)
        return self._build_result(actual_url, result)

    def _build_result(self, source_url: str, raw: Dict) -> Dict:
        # TODO: 解析 raw JSON，组装结构化数据
        return {"url": source_url, "items": [], "_raw_keys": list(raw.keys())}

    def scrape(self, url: str) -> Dict:
        return uc.loop().run_until_complete(self._scrape_async(url))


def format_text(data: Dict) -> str:
    lines = [f"URL: {data['url']}", f"Items: {len(data.get('items', []))}"]
    for item in data.get("items", []):
        lines.append(f"  - {item.get('name', '?')}")
    return "\n".join(lines)


def format_markdown(data: Dict) -> str:
    lines = [f"# {data['url']}\n"]
    for item in data.get("items", []):
        lines.append(f"- **{item.get('name', '?')}**")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="Target page URL")
    parser.add_argument("--output", choices=["json", "text", "markdown"], default="json")
    parser.add_argument("--visible", action="store_true", help="Show browser window (debug)")
    args = parser.parse_args()

    scraper = {SiteName}Scraper(headless=not args.visible)
    data = scraper.scrape(args.url)

    if args.output == "json":
        print(json.dumps(data, indent=2, ensure_ascii=False))
    elif args.output == "text":
        print(format_text(data))
    elif args.output == "markdown":
        print(format_markdown(data))

    # ★ CRITICAL: 先 flush stdout，再重定向 fd 1 抑制 nodriver cleanup 消息
    # browser.stop() 和进程退出时会向 stdout 打印 "successfully removed temp profile"
    # 如果不处理，JSON 输出末尾会多出非 JSON 文本，下游 json.load() 必然失败
    sys.stdout.flush()
    _devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(_devnull, 1)
    os.close(_devnull)


if __name__ == "__main__":
    main()
```

### 占位符

| 占位符 | 替换为 |
|--------|--------|
| `{SiteName}` | PascalCase（如 `DoorDash`） |
| `{site_name}` | snake_case（如 `doordash`） |
| `{DataType}` | 目标数据类型（如 `Menu`） |
| `{api_keyword}` | 推断的 API 路径关键词 |

### Step D — 脚本开发 & 更新开发日志

脚本开发过程中，**每次遇到问题立即更新** `.learning/{site_name}.md` 的开发阶段部分。
该文件在 B0.5 已创建探索阶段骨架，此处追加开发阶段内容：

```markdown
---
site: {site_domain}
script: {site_name}_scraper.py
date: {today}
status: in_progress       # in_progress | completed
data_extracted: {目标数据描述}
explore_file: .learning/{site_name}_explore.json   # explore.py 保存的原始捕获
---

## 探索阶段

### 数据来源
<!-- 根据实际探索结果填写，可多选 -->
- [ ] **JSON API 拦截** — 端点：`{api_keyword}`，数据路径：`{json.path}`，触发：{自动/点击/滚动}
- [ ] **页面内嵌（SSR）** — 位置：`{__NEXT_DATA__ / __INITIAL_STATE__}`，路径：`{json.path}`
- [ ] **DOM 解析** — 原因：{无 API/加密/静态}，容器：`{selector}`，提取方式：{CSS/XPath/正则}

### 探索中遇到的问题（每次迭代实时追加）
<!-- 反爬拦截、捕获为空、骨架 API、数据加密、代理问题、需要登录、DOM 虚拟化等 -->
| # | 问题 | 现象 | 排查过程 | 处理方式 |
|---|------|------|---------|---------|
| 1 |      |      |          |         |

## 开发阶段

### 确认的 API 端点
| 端点关键词 | 用途 | 数据路径 |
|-----------|------|---------|
|           |      |         |

### 开发中遇到的坑
<!-- 每次遇到问题记录：现象 → 原因 → 解法 -->

### 价格/数字字段格式
- 价格格式：{美分整数 | 字符串$符 | 浮点}
- 其他特殊字段：

## 可复用模式
<!-- 完成后填写，供总结时提取通用经验 -->
- 探索发现：
- 开发经验：
```

### Step E — 告知用户

```
✅ 已生成：skills/crawler/scripts/{site_name}_scraper.py
📝 开发日志：skills/crawler/.learning/{site_name}.md

下一步（验证脚本）：
1. 运行脚本验证输出：
   conda activate claw-crawler
   python3 skills/crawler/scripts/{site_name}_scraper.py --url "..." --visible
2. 如果数据不对，对照 .learning/{site_name}_explore.json 检查 API 路径
3. 脚本验证通过后：告诉我「总结爬虫经验」，将本次经验写入记忆库
```

---

## 学习模式

**触发词**：「学习爬虫经验」/ 「学习开发日志」/ 「learn crawler」/ 「consolidate learning」

当用户触发学习模式时，Agent **自主阅读** `.learning/` 目录下的开发日志，理解后提取通用经验并整合到 `crawlerMemory.md` 记忆库中。

### 执行步骤

#### 1. 查看未学习文件

```bash
python3 {baseDir}/scripts/learning.py list-unlearned
```

#### 2. Agent 自主阅读

```bash
# 逐个阅读未学习文件的完整内容
python3 {baseDir}/scripts/learning.py get grubhub
python3 {baseDir}/scripts/learning.py get doordash
```

#### 3. Agent 理解并整合

Agent **自行决定**从每个文件中提取什么经验，重点关注：
- **通用开发模式**（可复用到其他站点的策略）
- **常见陷阱**（问题 → 原因 → 解法，去除站点特定细节）
- **数据源识别经验**（不同类型站点的数据位置规律）
- **反爬处理**（通用反爬对策，非站点特定）
- **探索技巧**（有效的调试/探索方法）

**不要**：
- ❌ 堆砌特定站点的 URL、API 端点、域名
- ❌ 复制原始文件内容到记忆库
- ❌ 记录只适用于单一站点的细节

**要**：
- ✅ 泛化为通用规律（如 "Wix 站点的菜单常托管于外部平台"）
- ✅ 记录可复用的策略（如 "Next.js 站点优先检查 __NEXT_DATA__"）
- ✅ 保持记忆库精简、通用、可检索

#### 4. 标记已学习

```bash
# Agent 整合完成后，标记为已学习
python3 {baseDir}/scripts/learning.py mark grubhub
```

### 学习规则

- **只增不减**：已有条目不覆盖，新内容追加
- **去重检查**：相同经验不重复添加
- **标注来源**：每条经验保留原始站点信息
- **保持精简**：每条经验一句话，具体示例保留在 `.learning/` 原文件
- **Agent 自主**：脚本只提供工具，理解/提取/泛化由 Agent 完成

### 整合内容

Agent 应从开发日志中提取以下通用经验：

| 提取内容 | 整合到记忆库位置 |
|---------|----------------|
| 新站点的数据源类型规律 | 五、已验证的站点 |
| 反爬障碍及通用处理 | 7.2 反爬障碍识别与处理 |
| 常见问题及解法（泛化后） | 四、常见陷阱 |
| 懒加载触发模式 | 三、懒加载触发策略 |
| 价格格式规律 | 四、价格格式 |
| 有效的探索/调试技巧 | 7.5 nodriver 探索技巧 |

---

## 总结模式

**触发词**：「总结爬虫经验」/ 「consolidate crawler memory」/ 「更新记忆库」

### 执行步骤

1. **读取所有开发日志**：扫描 `{baseDir}/.learning/*.md`（跳过 `*_explore.json`）
2. **读取当前记忆库**：`{baseDir}/references/crawlerMemory.md`
3. **提取探索阶段新经验**（第七章）：
   - 遇到的反爬障碍及处理方式 → 更新"7.2 反爬障碍识别与处理"表
   - explore.py 捕获失败的原因及解决 → 更新"7.1 捕获不到数据"表
   - 新发现的数据位置模式（SSR/WebSocket/GraphQL）→ 更新"7.3 数据在哪里"
   - 有效的探索技巧 → 更新"7.5 使用技巧"
4. **提取开发阶段新经验**：
   - 新站点已验证 API 关键词 → 更新"五、已验证站点"表（状态改为 ✅）
   - 新发现的坑/解法 → 归类到"四、常见陷阱"对应小节
   - 新懒加载触发模式 → 更新"三、懒加载触发策略"
   - 新价格格式 → 更新"四、价格格式"
5. **更新记忆库文件**，顶部注释更新"已学习站点"和"最后更新日期"
6. **更新开发日志状态**：将处理过的 `.learning/{site}.md` 的 `status` 改为 `completed`

### 更新规则

- **探索经验和开发经验都要提取**——探索阶段的障碍比开发阶段更有通用价值
- **只增不减**：已有条目不覆盖，新内容追加
- **标注验证状态**：实测通过 ✅ / 脚本生成未实测 🔧 / 已知失效 ❌
- **保持精简**：每条经验一句话，具体示例保留在 `.learning/` 原文件

---

## 参考资料

需要时读取以下文件（按需加载，不要一次全读）：

| 文件 | 内容 | 何时读取 |
|------|------|---------|
| `{baseDir}/references/crawlerMemory.md` | 通用经验记忆库（**创建脚本必读**） | 每次创建新脚本前 |
| `{baseDir}/references/dev-environment.md` | 开发环境搭建与依赖说明 | 首次部署或环境报错时 |
| `{baseDir}/references/nodriver-guide.md` | nodriver 完整 API 速查 | 不确定 API 用法时 |
| `{baseDir}/references/grubhub-experience.md` | Grubhub 完整开发日志 | 遇到复杂 bug 时 |
| `{baseDir}/scripts/grubhub_menu.py` | 生产级参考实现 | 需要代码示例时 |
| `{baseDir}/.learning/*.md` | 各站点开发日志 | 总结经验时读取 |
| `{baseDir}/scripts/learning.py` | 学习管理器 | 整合开发经验到记忆库 |
| `nodriver-main/` （项目根目录） | nodriver 完整源码（`nodriver/` 核心包 + `docs/`） | nodriver 行为异常、API 用法存疑、排查底层 bug 时；`nodriver-main/nodriver/` 是权威实现，优先于文档 |
