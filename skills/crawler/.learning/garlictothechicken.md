---
site: garlictothechicken.com
script: garlictothechicken_menu.py
date: 2026-04-01
status: completed
data_extracted: 餐厅菜单：分类、菜品、价格、描述、选项
explore_file: /tmp/garlic_explore_v2_capture.json
---

## 探索阶段

### 数据来源

- [x] **页面内嵌（SSR）** — 位置：`window.__NEXT_DATA__.props.pageProps.menu`，路径：`menu_collections[].menu_categories[].menu_items[]`
- [ ] **JSON API 拦截** — 无独立菜单 API，数据直接嵌入 SSR 页面
- [ ] **DOM 解析** — 不需要

### 探索中遇到的问题

| # | 问题 | 现象 | 排查过程 | 处理方式 |
|---|------|------|---------|---------|
| 1 | 无 conda 环境 `claw-crawler` | `conda run -n claw-crawler` 报 `EnvironmentLocationNotFound` | `conda env list` 确认环境不存在；但系统 Python 已有 nodriver | 先用系统 Python 探索，后续补建环境 |
| 2 | `session.py` 启动失败 | 依赖 conda 环境 | 环境不存在，session.py 无法运行 | 改用内联探索脚本直接启动，但导致后续多次重复启浏览器 |
| 3 | 首页探索未捕获菜单 API JSON | 只捕获到 Google Tag Manager 的 409KB JS | 检查 `__NEXT_DATA__`，发现 `pageProps.menu` 是一个 JSON 字符串，包含完整菜单数据 | 直接访问 `/menu/42836629` 菜单页，从 `__NEXT_DATA__` 提取 |
| 4 | 价格为 0.00 的菜品 | Signature Fried Chicken 的 Wings/Strips/Drums 的 `unit_price` 为 `"0.00"` | 检查 `menu_modifiers`，发现选项不在 `modifier_items` 而是在 `menu_modifier_options` 中，每个 option 有独立的 `unit_price`（如 6 Pieces=$9.99, 20 Pieces=$28.99） | 价格显示为空字符串，选项单独列出 |
| 5 | `menu_item_advance` 为 None 导致 TypeError | 生产脚本运行报 `'NoneType' object is not iterable` | 原始数据中该字段为 `null`（None），不是空数组 | 改用 `item.get("menu_item_advance") or []` 防御 |
| 6 | 探索过程未实时记录 learning | 等全部成功后一次性补写 | 探索了 4 次浏览器启动，中间排查过程未记录 | 本文档为事后补记，部分细节可能遗漏 |

### 探索迭代记录

**迭代 1 — 首页探索** (`/tmp/explore_garlic.py`)
- 目标：判断数据来源（API vs SSR）
- 发现：页面 title = "Home - Garlic To the Chicken"，无 Cloudflare 拦截
- 发现：`__NEXT_DATA__` 存在，`pageProps.menu` 包含 JSON 字符串
- 发现：DOM 中有 `<a href="/menu/42836629">` 菜单链接
- 结论：Next.js SSR 站点，数据在 `__NEXT_DATA__` 中，无需拦截 API

**迭代 2 — 菜单页探索** (`/tmp/explore_garlic_v2.py`)
- 目标：直接访问 `/menu/42836629` 提取完整结构
- 发现：`pageProps.menu` 是 JSON 字符串，需要 `JSON.parse`
- 发现：`pagePropsKeys` = `["menu", "mid", "canonicalUrl", "initialState"]`
- 发现：DOM 中 `[class*="category"]` 匹配到 6 个分类：Signature Fried Chicken, Combo, Rice Box, Extras, Sides, Drinks
- 发现：价格格式为字符串浮点 `$9.99`, `$11.99` 等

**迭代 3 — 完整数据提取** (`/tmp/extract_menu.py`)
- 目标：解析 `menu` JSON 字符串，理解完整结构
- 发现：顶层结构 = `{location, menu_collections}`（不是 `categories`）
- 发现：`menu_collections[0].menu_categories[]` 是分类列表
- 发现：每个 item 的字段：`name`, `unit_price`(string), `description`, `menu_modifiers`, `menu_item_advance`
- 保存完整数据到 `/tmp/garlic_menu_full.json`（24KB）

**迭代 4 — 价格与 modifiers 深挖**
- 发现：Wings/Strips/Drums 的 `unit_price` = `"0.00"`，价格实际在 modifier options 中
- 发现：modifier 结构是 `menu_modifiers[].menu_modifier_options[]`（不是 `modifier_items`）
- 发现：每个 option 有 `name`（如 "6 Pieces"）和 `unit_price`（如 "9.99"）

## 开发阶段

### 确认的 API 端点
| 端点关键词 | 用途 | 数据路径 |
|-----------|------|---------|
| `__NEXT_DATA__` | 完整菜单数据（SSR） | `props.pageProps.menu` → `menu_collections[].menu_categories[].menu_items[]` |

### 开发中遇到的坑
- `menu_item_advance` 为 `null` 而非 `[]`，导致 `for adv in item.get(...)` 报错 → 改用 `or []`
- `unit_price` 是字符串 `"11.99"` 而非整数，不需要除以 100
- 价格为 `"0.00"` 表示价格由 modifier 决定，不应显示 `$0.00`

### 价格/数字字段格式
- 价格格式：字符串浮点，如 `"11.99"`、`"0.00"`、`"1.50"`
- 0.00 表示价格由选项决定（如不同数量不同价格）
- modifier 选项价格同样是字符串浮点

## 可复用模式
- **Next.js SSR 站点**：直接读取 `__NEXT_DATA__` 比拦截 API 更高效，一步到位
- **价格为 0 的菜品**：检查 modifier options 获取实际价格
- **Rushable 平台**：`menu_collections` → `menu_categories` → `menu_items` 是其标准数据结构
- **探索过程教训**：应先记录 learning 再迭代，事后补记会丢失排查细节
