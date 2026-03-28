---
site: grubhub.com
script: grubhub_menu.py
date: 2026-03-28
status: completed
data_extracted: 餐厅菜单（分类、菜品、价格、描述、图片）
result: 11 分类，95 菜品，耗时约 20s
---

## 探索阶段

### explore.py 运行结果
- 探索方式：Playwright 监听 `page.on('response')`（早期版本，后迁移为 nodriver）
- 数据在哪里：**JSON API**，非 SSR，非 WebSocket
- 捕获到的关键请求：`restaurant_gateway/info/nonvolatile`、`restaurant_gateway/feed`

### 探索中遇到的障碍
| 障碍 | 现象 | 处理方式 |
|------|------|---------|
| networkidle 超时 | `Timeout 30000ms`，页面有持续后台请求 | 改用 `domcontentloaded` + 固定等待 |
| 虚拟化渲染 | 滚动后 section 数量从 4 变 1 | 放弃 DOM，改为拦截 API |
| 分类数据为空（结果骨架） | feed API 返回 `results: []` | 需点击导航 tab 触发每个分类的独立 feed 请求 |

### 有效触发方式
- [x] 页面加载自动触发 nonvolatile（分类骨架）
- [x] 点击导航 tab `[data-testid^="category_"]` 触发 feed（实际菜品）

## 开发阶段

## API 端点

| 端点关键词 | 用途 | 数据路径 |
|-----------|------|---------|
| `restaurant_gateway/info/nonvolatile` | 餐厅信息 + 菜单分类骨架 | `object.data.enhanced_feed[]` |
| `restaurant_gateway/feed/{id}/{categoryId}` | 单分类菜品列表（懒加载） | `object.data.content[].entity` |

## 踩坑与解法

### networkidle 超时
- **现象**: `Timeout 30000ms exceeded (wait_until='networkidle')`
- **原因**: SPA 持续有后台请求（广告/追踪），永远不会 idle
- **解法**: 改用元素选择器 `[data-testid^="category_"]` 作为就绪信号

### DOM 重复数据
- **现象**: 同一菜品出现 8 次
- **原因**: 多层嵌套 div 都匹配了 `[class*="item"]`
- **教训**: 使用最外层语义容器 (`article`)，或直接拦截 API 避开 DOM

### Virtual Scroll（虚拟化渲染）
- **现象**: 滚动后 section 从 4 变成 1
- **原因**: SPA 只渲染视口内节点，滚出视口即销毁
- **解法**: 放弃 DOM 抓取，改为 API 拦截

### feed API 结果为空
- **现象**: feed API 返回但菜品 = 0
- **原因**: `enhanced_feed` 只是分类骨架，菜品需点击 tab 触发独立 feed 请求
- **解法**: 遍历点击 `[data-testid^="category_"]`，每次 0.6s 间隔

### nodriver handler 注入失效
- **现象**: `on_response_received` 收不到 tab
- **原因**: 用了 `functools.partial` 预绑定 tab，覆盖了 nodriver 的自动注入
- **解法**: 签名改为 `async def handler(event, tab=None)`，用闭包捕获变量

### ResponseReceived 时 body 未就绪
- **现象**: `get_response_body` 抛异常
- **原因**: header 事件触发时 body 仍在传输
- **解法**: 两阶段拦截——ResponseReceived 只记录 request_id，LoadingFinished 才读 body

## 可复用模式

- **懒加载触发**: 点击导航 tab（每项 0.6s 间隔）
- **页面就绪信号**: 等待导航元素出现，不用 networkidle
- **价格格式**: styled_text.text 已含 `$` 符号，无需转换
- **nodriver 启动**: `headless=False` 反爬效果最佳
