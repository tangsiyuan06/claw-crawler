---
site: aldospizzeria.com
script: aldospizzeria_menu.py
date: 2026-04-02
status: completed
data_extracted: 餐厅菜单：分类、菜品、价格、描述
---

## 探索阶段
### 数据来源
- [x] **DOM 解析** — WordPress + Elementor 构建，使用 SPL (Single Product List) 插件渲染菜单
- [ ] **JSON API 拦截** — 无 JSON API
- [ ] **页面内嵌（SSR）** — 无 __NEXT_DATA__ 等

### 探索中遇到的问题（每次迭代实时追加）
| # | 问题 | 现象 | 排查过程 | 处理方式 |
|---|------|------|---------|---------|
| 1 | WordPress Elementor 站点使用 SPL 插件 | 菜单数据通过 shortcode 渲染，结构为 `.spl-item-root` | web_fetch 分析 HTML 发现 `data-style="7"` 的 SPL 菜单 | 使用 nodriver DOM 解析提取数据 |
| 2 | 菜单使用 tab 切换分类 | 分类通过点击 tab 切换，但所有分类数据已在 HTML 中 SSR 渲染 | 检查发现所有 tab content 都在 HTML 中 | 直接 DOM 解析，无需点击 tab |
| 3 | 首页 URL 与菜单 URL 不一致 | 用户给 aldospizzeria.com，实际数据在 /menu/ | 检查导航栏发现 Menu 链接 | 记录 url_routes 映射 |

### 确认的 DOM 结构
- 整体容器：`#spl_7998488223.price_wrapper`
- 分类 tab：`.df-spl-style7_cat_tab-container.tabs_spl ul li a` → `data-href` 属性
- 菜品项：`.spl-item-root`
- 菜名：`.name.a-tag span`
- 价格：`.spl-price.a-tag span[data-price]` 或 `.spl-price.a-tag span`
- 描述：`.desc.a-tag span`

### 菜单分类（13 个）
1. Pizza
2. Specialty Pizza
3. Italian Specialty
4. Soups
5. Appetizers
6. Salads
7. Hot Heros
8. Wraps & Panini
9. Pasta
10. Main Course
11. Sides
12. Desserts
13. Beverages

## 开发阶段

### 确认的 DOM 结构
| 选择器 | 用途 |
|--------|------|
| `.df-spl-style7_cat_tab-container.tabs_spl ul li` | 分类 tab |
| `.tab-content1 > .tab` | 分类内容容器 |
| `.spl-item-root` | 菜品项 |
| `.name.a-tag span` | 菜名 |
| `.spl-price.a-tag span` | 价格 |
| `.desc.a-tag span` | 描述 |

### 开发中遇到的坑
- **SPL 插件价格格式** — 价格直接在 `span[data-price]` 或 `span` 中，如 "Slice 3.95 / Pie 22.00"
- **分类 tab 切换** — 所有分类数据已 SSR 渲染，不需要点击 tab 切换

### 价格/数字字段格式
- 价格格式：字符串，如 "Slice 3.95 / Pie 22.00" 或 "$12.00"

## 可复用模式
- **WordPress + Elementor 餐厅网站** — 常见使用 SPL 等插件渲染菜单，SSR 渲染
- **SPL 插件菜单结构** — `.spl-item-root` 是菜品项的常见模式
- **Tab 切换分类** — 分类内容已全量 SSR，无需 JS 交互
