---
site: superpollo.nyc
script: superpollo_menu.py
date: 2026-04-01
status: in_progress
data_extracted: Restaurant menu data (via getsauce.com ordering links)
---

## 探索阶段

### 数据来源

#### 方案 B — 页面内嵌数据（SSR）+ 外部链接追踪
- **superpollo.nyc**: Wix 站点，不直接托管菜单
  - 数据位置：`wix-viewer-model` SSR payload
  - 提取方式：nodriver 解析页面，获取 getsauce.com 订单链接
  - 两个门店链接：
    - Ridgewood: `https://www.getsauce.com/order/super-pollo/menu`
    - Brooklyn: `https://www.getsauce.com/order/super-pollo-brooklyn/menu`

- **getsauce.com**: 菜单托管平台，JSON-LD 结构化数据
  - 数据位置：`<script type="application/ld+json">` 标签
  - 数据路径：`@graph[1].hasMenuSection[].hasMenuItem[]`
  - 每个 MenuItem 包含：name, description, price, url, image
  - 也可从 `__NEXT_DATA__` 获取完整菜单 JSON

### 探索中遇到的问题（每次迭代实时追加）
| # | 问题 | 现象 | 排查过程 | 处理方式 |
|---|------|------|---------|---------|
| 1 | superpollo.nyc 无直接菜单 | 页面只显示门店信息和外部订单链接 | web_fetch 分析 Wix SSR 数据 | 追踪到 getsauce.com 平台获取菜单 |

## 开发阶段

### 确认的 API 端点
| 端点关键词 | 用途 | 数据路径 |
|-----------|------|---------|
| getsauce.com/order/*/menu | 菜单页面 HTML + JSON-LD | `@graph[1].hasMenuSection[].hasMenuItem[]` |
| __NEXT_DATA__ | Next.js SSR 数据 | `props.pageProps.menuDetails.menus/sections/items` |

### 开发中遇到的坑
- superpollo.nyc 是 Wix 站点，菜单数据不在本站
- 需要提取 getsauce.com 链接后爬取外部平台
- getsauce.com 使用 Next.js SSR，数据在 JSON-LD 和 __NEXT_DATA__ 中

### 价格/数字字段格式
- 价格格式：浮点数（如 `55.00`, `23.00`），美元单位
