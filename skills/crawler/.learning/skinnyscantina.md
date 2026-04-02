---
site: skinnyscantina.com
script: TBD
date: 2026-04-01
status: completed
data_extracted: 餐厅菜单
---

## 探索阶段
### 数据来源
- [x] **DOM 解析** — 纯 HTML 渲染，菜单数据直接在页面 HTML 中
- [ ] **JSON API 拦截** — 无 JSON API（传统 HTML 网站）
- [ ] **页面内嵌（SSR）** — 无 `__NEXT_DATA__` 等

### 探索中遇到的问题（每次迭代实时追加）
| # | 问题 | 现象 | 排查过程 | 处理方式 |
|---|------|------|---------|---------|
| 1 | `evaluate` 传 Element 对象报 JSON 序列化错误 | `Object of type Element is not JSON serializable` | nodriver `tab.evaluate` 不支持传 Element 对象作为参数 | 改用纯 JS 字符串在 `evaluate` 中获取 href 和 text |
| 2 | 字体文件 body 读取失败 | `No data found for resource` | webfonts 文件可能已缓存或流式传输 | 忽略，不影响菜单数据 |
| 3 | 首页无 JSON API | session status 显示未捕获到任何 JSON | 传统 HTML 网站，非 SPA/SSR | 导航到 `/menus/` 检查 DOM 结构 |
| 4 | 价格正则只匹配到 `$40` | 价格分隔为 `<span>$</span>14.00` 两个元素 | 检查原始 HTML 发现价格分 currency 和 amount | 解析时合并 currency + amount |

### 确认的 DOM 结构
- 分类容器：`.menu-section`
- 分类名：`.menu-section__header h2`
- 菜品项：`.menu-item`（在 `<ul>` 下的 `<li>`）
- 菜名：`.menu-item__heading--name`
- 描述：`.menu-item__details--description`
- 价格：`.menu-item__details--price` → `<span class="menu-item__currency">$</span>14.00`
- 附加项：`.menu-item__details--addon`

### 菜单分类（8 个）
1. Starters
2. Brunch, Eggs & More
3. Salads
4. Skinny's Favorites
5. Fries & Sides
6. Brunch Drink Special
7. Skinny's Cocktails
8. Frozens

## 开发阶段

### 确认的 DOM 结构
| 选择器 | 用途 |
|--------|------|
| `.menu-section` | 分类容器 |
| `.menu-section__header h2` | 分类名 |
| `.menu-item` | 菜品项 (`<li>`) |
| `.menu-item__heading--name` | 菜名 |
| `.menu-item__details--description` | 描述 |
| `.menu-item__details--price` | 价格（含 `<span class="menu-item__currency">`） |
| `.menu-item__details--addon` | 附加项 |

### 开发中遇到的坑
- **nodriver evaluate 不能传 Element 对象** — 报 `Object of type Element is not JSON serializable`，必须用纯 JS 字符串操作
- **价格格式分散** — `<span class="menu-item__currency">$</span>14.00`，直接取 `innerText` 即可得到 `$14.00`
- **addon 文本含换行** — `innerText` 中有 `\n$\n4.00`，需要用 `replace(/\s+/g, ' ')` 清理
- **nodriver 退出时打印 "successfully removed temp profile" 到 stdout** — 污染 JSON 输出，在 `main()` 末尾用 `os.dup2(os.devnull, 1)` 重定向
- **空分类** — "Brunch Drink Special" 和 "Wine, Sangria & Cerveza" 有分类头但无 `.menu-item`，可能是纯文本说明区

### 价格/数字字段格式
- 价格格式：字符串 `$14.00`，直接拼接 currency + amount
- 附加项价格：同样格式 `$4.00`

## 可复用模式
- **传统 HTML 餐厅网站** — 无 API 无 SSR，直接 DOM 解析是最快方案
- **菜单结构** — `.menu-section` → `.menu-item` 是常见模式
- **nodriver 清理消息** — 在 `main()` 末尾重定向 stdout 避免污染输出
