---
site: mortons.com
script: mortons_menu.py
date: 2026-04-01
status: completed
data_extracted: Mortons 牛排餐厅菜单（6个分类：Easter 3-Course Dinner, Steak & Sushi, Lunch, Dinner, Bar 12-21 & After Dinner, Power Hour）
explore_file: .learning/mortons_explore.json
---

## 探索阶段

### 数据来源
- [x] **DOM 解析 / requests+BS4** — 原因：BentoBox 建站平台，所有菜单数据在服务端完整渲染为 HTML
- [ ] **JSON API 拦截** — 不需要，数据已在 HTML 中
- [ ] **页面内嵌（SSR）** — 不适用

### 数据来源详情

#### 方案 C — DOM 解析（实际采用方案）
- 原因：BentoBox 平台传统 HTML 渲染，数据直接在 HTML 中
- 目标容器选择器：`section#menus` → `.tabs-content` → `.tabs-panel` → `section.menu-section` → `li.menu-item`
- 关键字段提取方式：CSS selector
- 价格格式：`<strong>$XX</strong>` 带 `<span class="menu-item__currency">$</span>` 前缀
- 卡路里信息：嵌入在价格文本中，格式 `(XXX cal.)`
- 多规格价格：`<p class="menu-item__details--price">` 内含多个 `<strong>` 元素（如 Half/Full）
- 附加选项：`<p class="menu-item__details--addon">` 元素

### 探索中遇到的问题（每次迭代实时追加）
| # | 问题 | 现象 | 排查过程 | 处理方式 |
|---|------|------|---------|---------|
| 1 | 无需浏览器自动化 | web_fetch 直接获取到完整 HTML | 检查 HTML 中发现所有菜单数据已渲染 | 采用 requests + BeautifulSoup 方案，跳过 session.py |

## 开发阶段

### 确认的 HTML 结构
| 元素 | 选择器 | 用途 |
|------|--------|------|
| 菜单区域 | `section#menus` | 包含所有菜单 tab |
| Tab 导航 | `ul.tabs-nav > a.btn-tabs` | 获取菜单分类名称 |
| Tab 面板 | `section.tabs-panel` | 每个独立菜单（如 Lunch, Dinner） |
| 菜单分区 | `section.menu-section` | 菜品分类（如 Chilled, Hot, Prime Steaks） |
| 分区标题 | `div.menu-section__header > h2` | 分类名称 |
| 分区副标题 | `div.menu-section__header` 中 h2 后的文本 | 如 "(Choice Of)" |
| 菜品 | `li.menu-item` | 单个菜品项 |
| 菜品名称 | `p.menu-item__heading--name` | 菜名 |
| 菜品描述 | `p.menu-item__details--description` | 描述文字 |
| 价格 | `p.menu-item__details--price` | 价格（可多个） |
| 附加选项 | `p.menu-item__details--addon` | 如牛排尺寸选择 |
| 文字分区 | `section.menu-section--text` | 纯文字说明（无菜品列表） |

### 开发中遇到的坑
- 菜品名称中可能含换行符（如 "Prime\nSteaks\n&\nChops"），需要 `re.sub(r"\s+", " ", name)` 清理
- 价格元素中 `$` 符号在单独的 `<span class="menu-item__currency">` 中，需要跳过只取数字部分
- 多规格菜品（如 Half/Full）有多个 price 元素，需要全部提取
- 卡路里信息嵌入在价格文本中，用正则 `\((\d+)\s*cal\.\)` 提取

### 价格/数字字段格式
- 价格格式：字符串含 `$` 符号，如 `"$85"`, `"$7.75"`, `"per MP"` (Market Price)
- 多规格价格：同一菜品多个 `<p class="menu-item__details--price">` 元素（如 Half: $25, Full: $46）
- 附加项价格：在 `<span>` 元素中
- 卡路里：`(XXX cal.)` 格式，附加在价格文本后面

## 可复用模式
<!-- 完成后填写，供总结时提取通用经验 -->
- 探索发现：BentoBox 建站平台（mortons.com、skinnyscantina.com 同类型）采用传统 HTML 渲染，所有菜单数据在服务端完整输出
- 开发经验：对于传统 HTML 餐厅网站，优先用 `web_fetch` 探测，如果数据已渲染则直接用 requests + BeautifulSoup，无需浏览器自动化
- 可复用技能树：BentoBox 站点 → requests + BS4；Wix 站点 → 追踪外部平台；Next.js 站点 → __NEXT_DATA__
