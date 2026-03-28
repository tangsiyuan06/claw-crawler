---
site: doordash.com
script: doordash_menu.py
date: 2026-03-28
status: completed
data_extracted: 餐厅完整菜单：分类、菜品名称、价格（含$字符串）、描述、图片URL
explore_file: .learning/doordash_storepagefeed.json
---

## 探索阶段

### 数据来源

#### 方案 A — JSON API 拦截（GraphQL）✅

- 目标端点关键词：`doordash.com/graphql/storepageFeed`（operation=storepageFeed）
- 数据路径：
  - 餐厅名：`data.storepageFeed.storeHeader.name`
  - 餐厅ID：`data.storepageFeed.storeHeader.id`
  - 分类+菜品：`data.storepageFeed.itemLists[]`（每项包含 id、name、items[]）
  - Featured Items：`data.storepageFeed.carousels[]`
- 触发方式：**页面加载自动触发**，无需点击导航 tab
- 响应大小：~197KB，包含全部菜单数据（单次请求）
- session status 捕获摘要（按大小排序前 5）：
  1. `197348B` — `storepageFeed?operation=storepageFeed` ← 主要数据
  2. `1039B` — `dropoffOptions?operation=dropoffOptions`（滚动后触发，非菜单）
  3. `617B` — `getBenefitReminder?operation=getBenefitReminder`（用户提醒）
  4. `356B` — `getGeoByIP?operation=getGeoByIP`（地理信息）
  5. `340B` — `paymentMethodQuery?operation=paymentMethodQuery`（支付方式）

#### 方案 B — 页面内嵌数据（SSR）❌

- `window.__NEXT_DATA__` 不存在
- `window.__PRELOADED_STATE__` 不存在
- DoorDash 纯 CSR（Client-Side Rendering），所有数据通过 GraphQL 获取

#### 方案 C — DOM 解析 ❌

- 菜品无稳定的 `data-anchor-id` 或 `data-testid` 选择器
- 样式类名为 CSS-in-JS 哈希（如 `sc-7d20bf1f-1 iABmJm`），不稳定
- 虚拟化渲染：滚动前 DOM 中菜品元素极少（itemCount=0），滚动后才渲染
- 结论：**不适合 DOM 解析，坚持 API 方案**

### Item 数据字段

```json
{
  "id": "14707443300",
  "name": "Double Sausage, Egg, & Cheese Croissan'wich",
  "description": "Two sizzling sausage patties, fluffy eggs, and two slices of melted American cheese on a toasted croissant.",
  "displayPrice": "$7.10",
  "displayStrikethroughPrice": "",
  "imageUrl": "https://img.cdn4dd.com/cdn-cgi/image/...",
  "dietaryTagsList": [],
  "calloutDisplayString": null
}
```

注意：`carousels` 里的 items 用 `imgUrl`（无 `e`），`itemLists` 里的 items 用 `imageUrl`

### 验证数据（Burger King - Niagara Falls, store 902649）

```
storeid: 902649 → redirects to /store/burger-king-niagara-falls-902649/37272546/
分类 9 个，菜品 64 个：
  popular-items / Most Ordered: 3 items
  category-125776379 / Breakfast Meals: 15 items
  category-125747675 / Breakfast Sandwiches: 15 items
  category-125758614 / Burritos: 3 items
  category-255605131 / Bundle Deals: 1 items
  category-138438315 / Limited Time Only: 2 items
  category-180430718 / Sides: 2 items
  category-125752081 / Drinks & Coffee: 20 items
  category-125828501 / Sweets: 3 items
carousels: Featured Items (4 items)
```

### 探索中遇到的问题（每次迭代实时追加）

| # | 问题 | 现象 | 排查过程 | 处理方式 |
|---|------|------|---------|---------|
| 1 | 代理 7890 未运行 | session 启动后页面 chrome-error | curl 测试代理返回 000/proxy_failed | 移除代理参数，直接访问 |
| 2 | 会话启动后页面初始加载失败 | `chrome-error://chromewebdata/` | 检查 status 发现 URL 未加载 | 在探索脚本中重新 `await tab.get()` |
| 3 | 刷新页面后 API 未捕获 | reload 后 captured=0 | 分析：reload 时 network handler 已注册，但 tab 内部 session 重置 | 用 `tab.get(url)` 代替 `tab.reload()` |
| 4 | DOM 菜品 items_count=0 | 所有 h2 分类下 items 为 0 | 检查 DOM：DoorDash 使用虚拟化渲染，滚动前不渲染菜品 | 改用 API 方案（storepageFeed 已包含全量数据）|
| 5 | menuBook.menuCategories 无菜品 | items=[] | 检查数据结构：menuCategories 只含分类骨架，真正的菜品在 itemLists | 使用 `itemLists` 而非 `menuCategories` |
| 6 | headless 模式被 Cloudflare 拦截 | title="请稍候…"，h2="执行安全验证"，storepageFeed 不触发 | debug 脚本检查 page title 发现 Bot Check | CLI 改为默认 headless=False；加 `--headless` flag 供服务器环境使用 |
| 7 | storepageFeed 在 SPA 重定向后才触发 | 初始等待不够（15s），URL 在 t=17s 才重定向，feed 在 t=20s | debug 脚本打时间戳发现 | 改为轮询等待（poll 25s），捕获到即跳出 |

## 开发阶段

### 确认的 API 端点

| 端点关键词 | 用途 | 数据路径 |
|-----------|------|---------|
| `doordash.com/graphql/storepageFeed` | 完整菜单（分类+菜品） | `data.storepageFeed.itemLists[]` |
| `doordash.com/graphql/storepageFeed` | Featured Items | `data.storepageFeed.carousels[]` |
| `doordash.com/graphql/storepageFeed` | 餐厅基本信息 | `data.storepageFeed.storeHeader` |

### 价格/数字字段格式

- 价格格式：**字符串含$符**（如 `"$7.10"`），直接使用，无需转换
- `displayStrikethroughPrice`：划线原价，通常为空字符串
- `imageUrl` vs `imgUrl`：itemLists 用 `imageUrl`，carousels 用 `imgUrl`

### URL 格式

DoorDash 商店 URL 支持两种形式：
1. `https://www.doordash.com/store/{store_id}` — 自动重定向到完整 slug URL
2. `https://www.doordash.com/store/{slug}/{menu_id}/` — 完整 URL

两种形式都可用，storepageFeed 均正常触发。

## 可复用模式

- 探索发现：DoorDash 全量菜单数据在单个 `storepageFeed` GraphQL 请求中，无需点击导航
- 探索发现：`menuBook.menuCategories` 是骨架（无 items），真正数据在 `itemLists[]`
- 开发经验：DoorDash 检测 headless 模式（Cloudflare Bot Check）→ 必须 headless=False
- 开发经验：DoorDash URL `/store/{id}` → SPA 重定向到 `/store/{slug}/{menu_id}/`，storepageFeed 在重定向后约 3s 触发（从导航开始约 20s）
- 开发经验：carousels 的 items 用 `imgUrl` 字段，itemLists 的 items 用 `imageUrl`（注意区分）
