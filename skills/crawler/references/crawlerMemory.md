# Crawler Development Memory
<!-- 由 skill 自动维护，每次完成新站点开发后从 .learning/ 汇总更新 -->
<!-- 最后更新: 2026-03-28 | 已学习站点: grubhub.com, doordash.com | 新增：Cloudflare headless 检测规律、SPA 重定向时序、GraphQL 骨架 vs 数据字段区分 -->

---

## 一、nodriver 强制规则（违反导致静默失败）

| # | 规则 | 错误现象 |
|---|------|---------|
| 1 | `cdp.network.enable()` 必须在 `tab.get()` **之前** | 网络事件一条不触发 |
| 2 | Handler 签名必须 `async def f(event, tab=None)` | tab 为 None，所有操作报错 |
| 3 | **禁止** `functools.partial` 绑定 tab | nodriver 注入被覆盖，收不到 tab |
| 4 | **禁止**在 `ResponseReceived` 读 body | body 尚未下载，必然抛异常 |
| 5 | 两阶段拦截：ResponseReceived 记录 ID → LoadingFinished 读 body | 单阶段拦截失败 |
| 6 | SPA 不用 `networkidle`，用元素 selector 作就绪信号 | 30s 超时 |

---

## 一·补充、Cloudflare Bot Check 规律（新增）

| # | 规则 | 触发条件 | 处理方式 |
|---|------|---------|---------|
| 7 | Cloudflare 检测 headless — **检查 page title** | title="请稍候…"，h2="执行安全验证" | 必须 headless=False；debug 时先打印 title 确认是否被拦 |
| 8 | nodriver headless=False 可绕过 Cloudflare | DoorDash、部分 DoorDash 系站点 | CLI 默认 headless=False；加 `--headless` 供服务器环境选用 |
| 9 | SPA 重定向 → API 在重定向后才触发 | `/store/{id}` → `/store/{slug}/{menu_id}/`（约 t=17s 重定向，t=20s API 触发） | 用**轮询等待**（`for _ in range(25): if data: break; wait(1)`）而非固定 sleep |

---

## 二、SPA 站点通用决策

```
目标站点是 SPA（React/Vue/Angular）？
├── 是 → 优先拦截 API（更稳定、更完整）
│        ├── 有清晰 JSON API → 两阶段 CDP 拦截（本项目标准方案）
│        └── 无清晰 API / GraphQL → DOM 提取 + tab.evaluate()
└── 否 → requests + BeautifulSoup（静态 HTML，最快）
```

**判断是否 SPA**：打开页面 → DevTools Network → 过滤 XHR/Fetch，看有无 JSON API 调用。

---

## 三、懒加载触发策略

| 场景 | 策略 | 注意事项 |
|------|------|---------|
| 分类/标签导航 | 遍历点击每个 tab，间隔 0.4–0.6s | 点击前等元素可交互 |
| 无限滚动 | `tab.evaluate("window.scrollBy(0, 1000)")` 循环 | 虚拟化渲染下无效 |
| 虚拟化渲染 | **放弃 DOM，改拦截 API** | DOM 滚出视口即销毁 |
| 需要登录态 | 先手动登录，保存 cookies，加载 cookies 后再爬 | — |

---

## 四、常见陷阱速查

### DOM 解析陷阱
- 多层嵌套 div 都能匹配 `[class*="item"]` → 用最外层语义容器（`article`、`li`）
- 虚拟化渲染只有视口内节点 → 滚动无效，必须拦截 API
- SPA 初始 HTML 是空壳 → 需要等 JS 执行完毕
- CSS-in-JS 哈希类名（如 `sc-7d20bf1f-1 iABmJm`）不稳定，不能依赖 class selector → 改用 API

### API 路径陷阱
- 分类骨架 ≠ 菜品数据：先有列表接口，再有详情接口（需点击触发）
- 数据路径需打印原始 JSON 确认，不要猜：`print(json.dumps(data, indent=2)[:2000])`
- GraphQL 端点通常是 `/graphql`、`/gp/graphql`，响应体内有 `data.{operationName}`
- **GraphQL 响应内多个字段，用途不同**：DoorDash `storepageFeed` 中 `menuBook.menuCategories` 是骨架（items=[]），真实菜品在 `itemLists[]` — 同一 GraphQL 响应内不同字段含义不同，需逐个验证

### 价格格式
- **美分整数**（DoorDash 常见）：`1299` → `$12.99`，需 `/ 100` 转换
- **字符串含符号**（Grubhub）：`"$13.99"`，直接使用
- **GraphQL 浮点**：`13.99`，需格式化

---

## 五、已验证的站点 API 关键词

| 站点 | API 关键词 | 数据触发方式 | 验证状态 |
|------|-----------|------------|---------|
| grubhub.com | `restaurant_gateway/info/nonvolatile`、`restaurant_gateway/feed` | 点击导航 tab | ✅ 生产验证 |
| doordash.com | `graphql/storepageFeed`（operation=storepageFeed） | **页面加载自动触发**（SPA 重定向后约 20s）| ✅ 生产验证 |
| ubereats.com | `getFeedV1`、`getStoreV1`、`getCatalogSectionsV1` | 滚动/点击 | 🔧 脚本生成，未实测 |
| yelp.com | `gp/graphql`、`biz/api` | 页面加载自动触发 | 🔧 脚本生成，未实测 |

图例：✅ 生产验证 / 🔧 脚本生成未实测 / ❌ 失效

---

## 六、调试检查清单

遇到脚本跑不出数据时，按顺序排查：

1. `cdp.network.enable()` 是否在 `tab.get()` 之前？
2. Handler 是否有 `tab=None` 签名？
3. `print(len(pending))` 在 LoadingFinished 前 —— pending 是否有记录？
4. API 关键词是否正确？用 `--visible` + DevTools Network 面板确认
5. `print(json.dumps(raw_data, indent=2)[:3000])` 确认数据路径
6. 懒加载是否已触发？点击 tab 后 pending 有新增吗？

---

## 七、探索阶段经验

### 7.1 explore.py 捕获不到数据的常见原因

| 现象 | 原因 | 处理方式 |
|------|------|---------|
| 捕获 0 个 JSON 请求 | 页面 SSR 渲染，数据在初始 HTML 里 | 改用 BeautifulSoup 解析 `<script id="__NEXT_DATA__">` 或 `window.__INITIAL_STATE__` |
| 捕获到请求但 body 为空 | 流式响应（Streaming）或压缩编码 | 在 explore.py 的 on_loading_finished 里捕获异常并打印原始 body |
| 只捕获到广告/埋点请求 | 目标数据通过 WebSocket 推送 | 需要监听 `cdp.network.WebSocketFrameReceived` 事件 |
| 数据请求有但内容是乱码 | 响应被加密（app-level encryption） | 需逆向加密逻辑，成本极高，考虑改用 DOM |
| --click-all 没触发数据 | 站点用自定义事件而非 click | 手动点击 + 增加 --wait 时间 |

### 7.2 反爬障碍识别与处理

| 障碍类型 | 识别特征 | 处理方式 |
|---------|---------|---------|
| Cloudflare Bot Check | 页面出现 "Checking your browser"；或 title="请稍候…"，h2="执行安全验证" | **debug 先打印 title 确认**；nodriver headless=False 可绕过；headless=True 必然被拦 |
| reCAPTCHA / hCaptcha | 出现验证码弹窗 | 手动完成后继续；或使用打码服务（超出本项目范围） |
| IP 频率限制 | 多次请求后 429 / 403 | 加 `--wait` 延长间隔；更换 IP |
| Token/Cookie 鉴权 | API 返回 401 / 空数据 | explore 时先手动登录，让 nodriver 持有登录 cookie |
| JS 指纹检测 | 页面加载正常但 API 返回异常数据 | 确保 nodriver headless=False；不要用 Playwright |
| Akamai / PerimeterX | 重定向到 `/ak/xxx` 验证页 | nodriver 通常可绕过；失败则尝试更慢的操作速度 |

### 7.3 数据在哪里：快速判断

```
explore.py 捕获到 JSON？
├── 是
│   ├── 数据完整 → 直接用，记录端点关键词
│   ├── 数据是骨架（results=[]）→ 需要交互触发详情接口（点击/滚动）
│   └── 单个 GraphQL 端点 → 用 operationName 字段区分不同查询
└── 否
    ├── 检查 <script id="__NEXT_DATA__"> → JSON.parse 提取
    ├── 检查 window.__INITIAL_STATE__ / __REDUX_STATE__ → 页面内嵌数据
    ├── WebSocket → 监听 WebSocketFrameReceived
    └── 真静态页面 → BeautifulSoup 直接解析 HTML
```

### 7.4 GraphQL 站点处理

GraphQL 所有查询共用同一端点（如 `/graphql`），用 `operationName` 区分：

```python
# explore 时会看到类似这样的响应结构：
# {"data": {"getMenu": {...}}, "extensions": {...}}
# operationName 通常在请求 body 里，也可以从响应的 data 键名推断

async def on_loading_finished(event, tab=None):
    ...
    data = json.loads(body)
    op_name = list(data.get("data", {}).keys())  # 如 ["getMenu"]
    if "getMenu" in op_name or "getStore" in op_name:
        result.update(data["data"])
```

### 7.5 nodriver 探索技巧

Agent 编写内联 nodriver 探索代码并通过 Bash 运行（不创建正式脚本文件）。
使用 nodriver 而非 Playwright MCP：CDP 可读 response body、反爬一致、环境与生产脚本相同。

**技巧1：按响应大小排优先级**
探索输出按 size 排序，`> 1KB` 的响应通常含实际数据，`< 200B` 多为埋点/心跳。

**技巧2：骨架 API ≠ 数据 API**
第一个大响应可能只是分类列表（`results: []`），需要点击 tab 触发后续详情接口。
看到空数组时，检查是否有更多 API 在点击后触发。

**技巧3：GraphQL 用响应体 data 键名区分**
GraphQL 所有查询共用同一端点，响应体的 `data` 顶层键名即操作名（如 `getMenu`）。
过滤时用 `list(data.get("data", {}).keys())` 判断是否目标查询。

**技巧4：捕获为空时的排查顺序**
1. 增加等待时间（`await tab.wait(8)`）— 慢网络或重 JS
2. 检查 SSR：`await tab.evaluate("JSON.stringify(window.__NEXT_DATA__ || {})")`
3. 换导航选择器，或增加点击覆盖范围
4. 仍然为空 → 可能是 WebSocket 或加密，记录到 .learning 后考虑 DOM 方案

**技巧5：迭代探索**
第一次运行发现端点后，修改代码加上精确的 `if "xxx" in url` 过滤，
第二次运行只打印目标 API 的完整 JSON，确认数据路径。

**技巧7：headless 被拦时先打印 title**
遇到 API 捕获为空时，先检查 page title 是否是 Cloudflare 验证页：
```python
title = await tab.evaluate("document.title")
h2s = await tab.evaluate("Array.from(document.querySelectorAll('h2')).map(e=>e.innerText)")
print(f"[debug] title={title}, h2s={h2s}")
# title="请稍候…" 且 h2="执行安全验证" → Cloudflare headless 检测
# 解法：headless=False（nodriver 在 visible 模式下可绕过 Cloudflare）
```

**技巧8：轮询等待 vs 固定 sleep**
SPA 重定向后 API 触发时间不确定，用轮询而非固定 sleep：
```python
for _ in range(25):
    if data:  # 检查是否已捕获目标 API
        break
    await tab.wait(1)
# 优点：捕获到即退出（更快），不会因 sleep 过短截断（更可靠）
```

**技巧6：先读 DOM 再追 API（最重要）**
探索的第一步是读取页面实际渲染的内容（导航 tab 文字、section 标题），再去追 API。
CDP 完全可以做到，无需启动 Playwright：

```python
# 拿到 nav tabs 后立即打印文字，不要只打数量
nav_items = await tab.select_all('[data-testid^="category_"]')
for nav in nav_items:
    print(await tab.evaluate(f'document.querySelector(\'[data-testid^="category_"]\').innerText'))
# 或批量读：
texts = await tab.evaluate('Array.from(document.querySelectorAll(\'[data-testid^="category_"]\')).map(e=>e.innerText)')
```

**反例**：某分类在 API schema（`enhanced_feed`）里存在，但页面实际没有渲染该 tab
→ 原因是该餐厅未配置此功能（API 返回空/报错）
→ 如果先读 DOM tab 文字，一步就能发现，不需要多轮 API 分析

规则：**API schema 有 ≠ 餐厅有数据**，以页面实际渲染为准。
