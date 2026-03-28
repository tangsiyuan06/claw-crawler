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

三种工作模式，统一入口：

| 模式 | 触发场景 | 操作 |
|------|---------|------|
| **执行** | 目标网站已有现成脚本 | 直接运行，返回结果 |
| **创建** | 新网站，无对应脚本 | 加载记忆库 → **探索验证** → 编写脚本 → 写开发日志 |
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

使用 nodriver 而非 Playwright MCP 的原因：
- CDP 可以直接读取响应 body，探索时就能看到真实 JSON 内容
- 探索环境与生产脚本完全一致（同一框架），避免"探索能通、脚本被拦"
- nodriver 的反爬能力在探索阶段同样生效

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

    # 连接到已有浏览器（不会重启 Chrome）
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

#### B3 — 探索完成后关闭会话

```bash
conda run -n claw-crawler python3 {baseDir}/scripts/session.py stop
```

#### B4 — 记录探索发现到 `.learning/{site_name}.md`

在开始写脚本前先写入开发日志，**探索过程中遇到的每个问题都要记录**。
探索结果可能是以下三种之一，按实际情况填写对应小节：

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

1. `await tab.send(cdp.network.enable())` 必须在 `tab.get()` **之前**调用
2. Handler 签名必须是 `async def handler(event, tab=None)` — nodriver 自动注入 `tab`
3. **禁止** `functools.partial` 绑定 `tab`
4. **禁止**在 `ResponseReceived` 中读取 body — body 尚未下载
5. 必须两阶段：ResponseReceived 记录 → LoadingFinished 读 body
6. SPA 不用 `networkidle`；用元素选择器作为页面就绪信号

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
import argparse, asyncio, json, sys
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

        await tab.get(url)
        await tab.select("body", timeout=15)  # ★ 不用 networkidle
        await tab.wait(3)

        # ★ 如有懒加载导航栏，点击每项触发 API 调用
        # nav_items = await tab.select_all(".nav-selector")
        # for nav in nav_items:
        #     await nav.click(); await tab.wait(0.6)

        await tab.wait(2)
        browser.stop()
        return self._build_result(url, result)

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

### Step D — 创建后写开发日志

脚本生成后，立即在 `{baseDir}/.learning/{site_name}.md` 创建开发日志（将探索发现固化）：

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
| `nodriver-main/` （项目根目录） | nodriver 完整源码（`nodriver/` 核心包 + `docs/`） | nodriver 行为异常、API 用法存疑、排查底层 bug 时；`nodriver-main/nodriver/` 是权威实现，优先于文档 |
