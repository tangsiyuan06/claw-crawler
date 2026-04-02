---
site: napoleons.ca
script: scripts/napoleons_menu.py
date: 2026-04-02
status: completed
data_extracted: 餐厅菜单：7个分类、47道菜品、价格、描述
---

## 探索阶段

### 数据来源

#### 方案 B — 页面内嵌数据（SSR）✅
- 数据位置：WordPress + Elementor SSR 渲染的 HTML 页面
- 提取方式：requests + BeautifulSoup 解析
- 目标URL：`https://napoleons.ca/menu/`
- 技术栈：WordPress + Elementor Price List widget
- HTML 结构：
  - 分类：`h2.elementor-heading-title`
  - 菜品项：`ul.elementor-price-list > li > .elementor-price-list-item`
  - 菜名：`.elementor-price-list-title`
  - 描述：`.elementor-price-list-description`
  - 价格：`.elementor-price-list-price`

### 探索中遇到的问题（每次迭代实时追加）
| # | 问题 | 现象 | 排查过程 | 处理方式 |
|---|------|------|---------|---------|
| 1 | 无需浏览器 | SSR 渲染，数据在初始 HTML 中 | 直接用 requests 获取 | 使用 requests + BeautifulSoup，无需 nodriver |

## 开发阶段

### 确认的菜单数据
- **7个分类**：STEAK (12道菜), STEAK & SEAFOOD COMBINATIONS (6道菜), CHICKEN & VEAL (6道菜), APPETIZERS (6道菜), SALADS / SOUP (3道菜), ACCOMPANIMENTS (2道菜), DRESSING TO GO (1道菜)
- **总计47道菜品**
- **价格格式**：美元符号 + 整数（如 `$65`），部分有双价格（如 `$22/$39`）
- **特殊字段**：餐厅信息（地址、电话、营业时间）

### 可复用模式
- WordPress + Elementor 站点：直接 requests + BS4，无需浏览器自动化
- Elementor Price List widget 结构稳定：`.elementor-price-list-title` + `.elementor-price-list-description` + `.elementor-price-list-price`
- 菜单页在 `/menu/` 子路径，非首页
