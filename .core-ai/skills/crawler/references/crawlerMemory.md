<!-- learned: doordash.md, garlictothechicken.md, grubhub.md, mortons.md, skinnyscantina.md, superpollo.md, aldospizzeria.md, parkavenuetavern.md, chinastarpa88.md -->
# Crawler Development Memory
<!-- 由 skill 自动维护，每次完成新站点开发后从 .learning/ 汇总更新 -->
<!-- 最后更新: 2026-04-02 | 已学习站点: grubhub.com, doordash.com, superpollo.nyc, skinnyscantina.com, garlictothechicken.com, mortons.com, aldospizzeria.com, parkavenuetavern.com, chinastarpa88.com | 新增：WordPress SPL 插件规律、Enfold 主题规律、Tab 切换但 SSR 全量渲染经验、BeyondMenu 平台规律、Next.js __next_f.push 中文编码修复 -->

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

## 一·补充、nodriver stdout 污染问题（新增）

| # | 规则 | 错误现象 | 处理方式 |
|---|------|---------|---------|
| 10 | `browser.stop()` 输出 cleanup 消息到 stdout | JSON 末尾多出 `successfully removed temp profile`，下游 `json.load()` 抛 Extra data | **不在脚本中调 `browser.stop()`**，让浏览器随进程退出自然终止；或在 `main()` 中先 `sys.stdout.flush()` 再 `os.dup2(devnull, 1)` 重定向 fd 1 |
| 11 | **不要**在 `print()` 前用 `os.dup2` 重定向 fd 1 | `os.dup2` 劫持 fd 1 后，block-buffered 的 stdout 缓冲数据全部丢失 | 正确顺序：先 `print()` → `sys.stdout.flush()` → 再 `os.dup2(devnull, 1)`；只在 `main()` 末尾做，不在 `_scrape_async` 里做 |

---

## 二、SPA 站点通用决策

```
目标站点是 SPA（React/Vue/Angular）？
├── 否（传统 HTML/SSR）→ requests + BeautifulSoup（静态 HTML，最快）
│                         判断方法：web_fetch 后搜索 `<script id="__NEXT_DATA__">` 或检查菜品数据是否已在 HTML 中
│                         典型平台：BentoBox（mortons.com）、传统 WordPress 餐厅站
└── 是 → 优先拦截 API（更稳定、更完整）
          ├── 有清晰 JSON API → 两阶段 CDP 拦截（本项目标准方案）
          └── 无清晰 API / GraphQL → DOM 提取 + tab.evaluate()
```

**判断是否 SPA**：打开页面 → DevTools Network → 过滤 XHR/Fetch，看有无 JSON API 调用。
或直接用 `web_fetch` 获取 HTML 搜索 `menu-item`、`menu-section` 等关键词，如果找到 → SSR 渲染，直接用 BS4。

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
- **首页和菜单页不同 URL** — 传统餐厅站首页可能没有菜单 DOM 元素 → 脚本应先检测目标选择器是否存在（`document.querySelectorAll('.menu-section').length > 0`），不存在时自动导航到 `/menus/` 等子页面

### 建站平台特征
- **Wix 站点**：餐厅菜单通常不直接托管，页面只显示门店信息和外部订单入口 → 需追踪外部托管平台（如 getsauce.com）
- **外部平台追踪**：页面无直接菜单时，解析页面中的订单链接 → 追踪到实际托管平台提取数据
- **BentoBox 平台**（mortons.com）：传统 SSR 渲染，所有菜单数据在初始 HTML 中完整渲染
  - 识别特征：URL 模式 `*.com/location/{slug}`，菜单 HTML 结构 `section#menus > .tabs-content > .tabs-panel`
  - 方案：直接 `web_fetch` + BeautifulSoup，**跳过浏览器自动化**（快 10 倍以上）
  - 价格格式：`<span class="menu-item__currency">$</span>` + `<strong>数字</strong>`，需跳过货币符号 span
  - 卡路里：嵌入价格文本，格式 `(XXX cal.)`，正则提取
  - 多规格价格：同一菜品多个 `p.menu-item__details--price` 元素（如 Half/Full）
- **Next.js 站点**（garlictothechicken.com）：`<script id="__NEXT_DATA__">` 包含完整 SSR 数据
- **WordPress + SPL 插件**（aldospizzeria.com）：传统 SSR 渲染，使用 Single Product List 插件渲染菜单
  - 识别特征：`.price_wrapper` 容器，`data-style` 属性，`.spl-item-root` 菜品项
  - HTML 结构：`.df-spl-style7_cat_tab-container` (tabs) + `.tab-content1 > .tab` (content)
  - 菜品项：`.spl-item-root` → `.name.a-tag span` + `.spl-price.a-tag span` + `.desc.a-tag span`
  - 所有 tab 内容已 SSR 渲染，无需点击切换
  - 价格格式多样："Slice 3.95 / Pie 22.00"、"$12.00" 等
- **WordPress + Enfold 主题**（parkavenuetavern.com）：传统 SSR 渲染，使用 Enfold Tab Section 元素
  - 识别特征：`av-tab-section` 容器，`av-special-heading` 元素
  - DOM 模式：`h2.av-special-heading-tag` (分类) + `h6.av-special-heading-tag` (菜品+价格) + `.av-subheading` (描述)
  - 价格嵌入菜品标题内：`<span class="menu-price">`
  - 所有 tab 内容已 SSR 渲染，无需浏览器交互
- **传统 HTML 站点**（skinnyscantina.com）：无 API 无 SSR 内嵌数据，直接 DOM 解析

### API 路径陷阱
- 分类骨架 ≠ 菜品数据：先有列表接口，再有详情接口（需点击触发）
- 数据路径需打印原始 JSON 确认，不要猜：`print(json.dumps(data, indent=2)[:2000])`
- GraphQL 端点通常是 `/graphql`、`/gp/graphql`，响应体内有 `data.{operationName}`
- **GraphQL 响应内多个字段，用途不同**：DoorDash `storepageFeed` 中 `menuBook.menuCategories` 是骨架（items=[]），真实菜品在 `itemLists[]` — 同一 GraphQL 响应内不同字段含义不同，需逐个验证

### 价格格式
- **美分整数**（DoorDash 常见）：`1299` → `$12.99`，需 `/ 100` 转换
- **字符串含符号**（Grubhub）：`"$13.99"`，直接使用
- **浮点数**（getsauce.com 等 Next.js 站点）：`55.00`、`23.00`，需格式化为 `$55.00`
- **字符串浮点**（garlictothechicken.com）：`"11.99"`、`"0.00"`
  - `0.00` 表示价格由选项决定
  - modifier 选项价格同样是字符串浮点
- **附加项价格**：与主菜品同格式

---

## 五、已验证的站点

| 站点 | API 关键词 | 数据触发方式 | 验证状态 |
|------|-----------|------------|---------|
| superpollo.nyc | SSR/内嵌数据 | Restaurant menu data (via getsauce.com ordering links) | ✅ 生产验证 |

| 站点 | API 关键词 | 数据触发方式 | 验证状态 |
|------|-----------|------------|---------|
| skinnyscantina.com | JSON API | 餐厅菜单 | ✅ 生产验证 |

| 站点 | API 关键词 | 数据触发方式 | 验证状态 |
|------|-----------|------------|---------|
| garlictothechicken.com | JSON API | 餐厅菜单：分类、菜品、价格、描述、选项 | ✅ 生产验证 | API 关键词

| 站点 | API 关键词 | 数据触发方式 | 验证状态 |
|------|-----------|------------|---------|
| grubhub.com | `restaurant_gateway/info/nonvolatile`、`restaurant_gateway/feed` | 点击导航 tab | ✅ 生产验证 |
| doordash.com | `graphql/storepageFeed`（operation=storepageFeed） | **页面加载自动触发**（SPA 重定向后约 20s）| ✅ 生产验证 |
| 站点 | API 关键词 | 数据触发方式 | 验证状态 |
|------|-----------|------------|---------|
| aldospizzeria.com | **无 API — WordPress SSR**（SPL 插件） | **nodriver DOM 解析**，所有 tab 内容已 SSR 渲染 | ✅ 生产验证 |
| mortons.com | **无 API — 传统 HTML SSR**（BentoBox 平台） | **直接 requests+BS4**，无需浏览器 | ✅ 生产验证 |
| chinastarpa88.com | **Next.js `__next_f.push` 内嵌数据**（BeyondMenu 平台） | **解析 streaming chunks**，`menuCategories[].menuGroups[].menuItems[]` | ✅ 生产验证 |
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
    ├── 先用 web_fetch 检查 HTML 中是否有菜单数据（BentoBox 等 SSR 平台）→ 直接 BS4 解析
    ├── 检查 <script type="application/ld+json"> → JSON-LD schema.org 结构化数据
    │   └── Menu 结构：`@graph[].hasMenuSection[].hasMenuItem[]`
    ├── 检查 <script id="__NEXT_DATA__"> → JSON.parse 提取
    ├── 检查 `self.__next_f.push([1,"..."])` → Next.js streaming chunks（BeyondMenu 等平台）
    │   └── 数据结构：`menuCategories[].menuGroups[].menuItems[]`
    │   └── 编码注意：中文以 UTF-8 存储，引号以 `\"` 转义，禁止用 unicode_escape
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

**技巧16：WordPress Tab 类插件 — 内容已 SSR 渲染，无需点击切换**
- aldospizzeria.com 使用 SPL (Single Product List) 插件，parkavenuetavern.com 使用 Enfold Tab Section
- 共同特征：页面有 tab 切换导航，但**所有 tab 的内容已在初始 HTML 中 SSR 渲染**
- 判断方法：`web_fetch` 获取 HTML 后搜索所有分类名称，如果都在 HTML 中 → 无需浏览器交互
- 解法：直接 DOM 解析或 BS4 解析，不需要点击 tab 触发懒加载
- 这比 SPA 站点简单得多：数据已在 HTML 中，只需找到正确的选择器

**技巧17：WordPress 餐厅站识别特征**
- 检查 HTML 中是否有 WordPress 特征：`wp-content`、`wp-includes`、`elementor`、`av-tab-section`
- 常见菜单插件：SPL (Single Product List)、Five Star Restaurant Menu、WP Food Menu
- 这些插件通常 SSR 渲染菜单数据，可直接用 BS4 解析（如果不需要处理 JS 交互）
- 如果菜单在 `/menu/` 或 `/menus/` 子页面，先检查首页是否有菜单链接

**技巧18：BeyondMenu 平台规律（chinastarpa88.com）**
- BeyondMenu 是一个餐厅外卖托管平台，餐厅站点通过 iframe 或链接嵌入订单页面
- 识别特征：URL 中包含 BeyondMenu 实体 ID（如 `/ji5od7sj/restaurant-name-12345/order-online`）
- 菜单数据嵌入在 Next.js streaming chunks（`self.__next_f.push([1,"DATA"])`）中
- 数据结构：`menuCategories[].menuGroups[].menuItems[]`，每个 item 含 `menuItemName`、`menuItemPrice`、`menuItemDesc`
- **编码注意**：chunk 中中文以原始 UTF-8 存储，引号以 `\"` 转义。**禁止使用 `.encode().decode('unicode_escape')`**，会破坏 UTF-8 中文字符
- 正确做法：手动扫描提取 push 数据（跳过 `\"` 转义），然后只做 `.replace('\\"', '"')` 替换引号
- 首页通常不包含菜单数据，需要从 JSON-LD `hasMenu` 字段或 "View Menu" 链接找到实际订单页 URL

**技巧19：Next.js `__next_f.push` 中文编码修复**
- 当 HTML 内嵌数据同时包含原始 UTF-8 字符（中文、日文等）和 `\"` 转义引号时，`unicode_escape` 会把 UTF-8 多字节重新编码为 Latin-1 码位
- 症状：`鸡翅` 变成 `é¸¡ç¿` 等乱码字符
- 根因：`unicode_escape` 设计用于纯 ASCII 文本，会把每个字节当作独立码位处理
- 正确做法：只替换转义引号 `.replace('\\"', '"')`，或使用正则 `re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), s)` 仅处理 `\uXXXX` 序列

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

**技巧9：skinnyscantina.com 经验**
**菜单结构** — `.menu-section` → `.menu-item` 是常见模式

**技巧9：grubhub.com 经验**
**页面就绪信号**: 等待导航元素出现，不用 networkidle

**技巧9：garlictothechicken.com 经验**
**价格为 0 的菜品**：检查 modifier options 获取实际价格

**技巧9：doordash.com 经验**
探索发现：`menuBook.menuCategories` 是骨架（无 items），真正数据在 `itemLists[]`

**技巧9：skinnyscantina.com 经验**
**传统 HTML 餐厅网站** — 无 API 无 SSR，直接 DOM 解析是最快方案

**技巧9：grubhub.com 经验**
**懒加载触发**: 点击导航 tab（每项 0.6s 间隔）

**技巧9：garlictothechicken.com 经验**
**Next.js SSR 站点**：直接读取 `__NEXT_DATA__` 比拦截 API 更高效，一步到位

**技巧9：doordash.com 经验**
探索发现：DoorDash 全量菜单数据在单个 `storepageFeed` GraphQL 请求中，无需点击导航

**技巧10：Next.js SSR 站点数据提取策略**
- 优先读取 `__NEXT_DATA__`：`props.pageProps` 通常包含完整数据
- 同时检查 JSON-LD（`<script type="application/ld+json">`）：部分站点使用 schema.org Menu 结构
- 两者数据路径不同但内容一致，可互为验证
- JSON-LD 路径示例：`@graph[1].hasMenuSection[].hasMenuItem[]`
- `__NEXT_DATA__` 路径示例：`props.pageProps.menuDetails.menus/sections/items`
- 直接读取 SSR 数据比拦截 API 更高效，一步到位

**技巧12：先用 HTTP 探测 SSR，避免不必要的浏览器自动化**
- 在启动 session.py 之前，先用 `web_fetch` 获取页面 HTML
- 检查 HTML 中是否已包含目标数据（搜索关键词如 "menu-item"、"price" 等）
- 如果数据已渲染 → 直接用 BeautifulSoup 解析，无需浏览器
- 如果是空壳 HTML → 才需要 nodriver 浏览器自动化
- 好处：避免端口冲突、进程循环等 Chrome 相关问题，大幅节省时间

**技巧13：session.py 端口冲突处理**
- 如果端口 9222 被占用，用 `--port 9333` 指定其他端口
- 启动前用 `lsof -i :9222` 检查端口占用
- 多个 session.py 实例同时运行会导致 Chrome 反复重启

**技巧14：mortons.com 经验 — BentoBox 平台 SSR 渲染**
- 探索发现：BentoBox 平台（mortons.com）采用传统 HTML 渲染，所有菜单数据在服务端完整输出
- 开发经验：对于传统 HTML 餐厅网站，优先用 `web_fetch` 探测，如果数据已渲染则直接用 requests + BeautifulSoup，无需浏览器自动化
- 可复用技能树：BentoBox 站点 → requests + BS4；Wix 站点 → 追踪外部平台；Next.js 站点 → __NEXT_DATA__
- HTML 结构：`section#menus > .tabs-content > .tabs-panel > section.menu-section > li.menu-item`
- 价格解析：`$` 在单独 `<span class="menu-item__currency">` 中，需跳过只取 `<strong>` 数字
- 卡路里：`(XXX cal.)` 格式嵌入价格文本，正则提取
- 多规格：同一菜品多个 `p.menu-item__details--price` 元素（如 Half/Full）

**技巧15：skinnyscantina.com 经验 — 传统 HTML 无框架站点**
- 与 BentoBox 不同，skinnyscantina.com 是独立建站的传统 HTML 站点，无 `__NEXT_DATA__`、无 API
- 菜单 DOM 结构：`.menu-section` → `.menu-item` → `.menu-item__heading--name` + `.menu-item__details--price` + `.menu-item__details--description`
- 价格格式：`<span class="menu-item__currency">$</span>` + 金额在同一元素内，需 `.innerText.replace(/\s+/g, '')` 合并
- 首页（`/`）无菜单 DOM，菜单页在 `/menus/` — 脚本需自动检测并导航
- 方案：nodriver 加载页面后用 `tab.evaluate()` 执行 DOM 提取


---

