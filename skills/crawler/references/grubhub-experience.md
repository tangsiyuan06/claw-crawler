# Grubhub 菜单爬取经验总结

**日期**: 2026-03-28
**目标**: 提取 Grubhub 餐厅完整菜单（分类、菜品、价格、描述）
**最终方案**: Playwright 拦截内部 API，点击导航栏触发分类懒加载

---

## 一、踩坑记录

### 问题 1：依赖环境未配置
**现象**: `No module named 'playwright'`
**原因**: conda 环境 `claw-crawler` 未安装 Playwright
**解决**:
```bash
conda run -n claw-crawler pip install playwright beautifulsoup4
conda run -n claw-crawler playwright install chromium
```
**经验**: 每个 conda 环境需独立安装 Playwright 及 Chromium 浏览器内核，不能共用系统级安装。

---

### 问题 2：networkidle 超时
**现象**: `Page.goto: Timeout 30000ms exceeded` (wait_until='networkidle')
**原因**: Grubhub 是重度 SPA，页面持续有后台网络请求（广告、追踪、Analytics），永远达不到 networkidle 状态
**解决**: 改用 `wait_until='domcontentloaded'` + 固定等待 `page.wait_for_timeout(8000)`
**经验**: SPA 站点（React/Vue/Angular）一律不用 `networkidle`，改用 `domcontentloaded` + 等待时间或特定 selector 出现。

---

### 问题 3：DOM 解析提取到重复数据
**现象**: 同一个菜品 "Asada Torta" 出现 8 次
**原因**: Grubhub 同一菜品有多层嵌套 div（卡片容器、图片容器、文字容器），`find_all(class_=re.compile('item'))` 每层都匹配
**解决尝试**: 改用 `article.restaurant-menu-item` 精确选择最外层容器
**遗留问题**: 依然只能拿到少量菜品（2 个），因为存在更深层问题 →

---

### 问题 4：菜单分类懒加载（Virtual Scroll）
**现象**: 滚动页面后 section 数量反而从 4 变成 1
**原因**: Grubhub 使用虚拟化渲染（Virtual DOM），只渲染当前视口内的 section，滚动时销毁旧 section、创建新 section，DOM 中永远只有少量 section
**教训**: 对 SPA 不能依赖"滚动 → DOM 累积"策略，虚拟化渲染会销毁已滚出视口的节点

---

### 问题 5：enhanced_feed results 为空
**现象**: API 返回 `enhanced_feed` 有 11 个分类，但每个分类的 `results: []`
**原因**: `enhanced_feed` 只是分类结构骨架，实际菜品数据通过独立的 `/feed/{restaurantId}/{categoryId}` 接口按需加载，不在初始响应里
**解决**: 点击每个导航分类 tab，触发对应 feed API 请求，捕获响应

---

### 问题 6：feed API 数据路径误判
**现象**: 捕获到 feed API 响应但解析出 0 个菜品
**原因**: 误以为数据在 `object.data.results[]`，实际路径是 `object.data.content[].entity`
**解决**: 打印原始 JSON 找到正确路径：
```
object.data.content[n].entity.item_name
object.data.content[n].entity.item_price.delivery.styled_text.text
object.data.content[n].entity.item_description
```

---

## 二、最终技术方案

### 核心思路：拦截内部 API > 解析 DOM
Grubhub 是典型的前后端分离架构，前端只做渲染。直接获取 API JSON 比解析 DOM 更稳定、更完整。

### API 端点结构
| 端点 | 用途 | 关键字段 |
|------|------|----------|
| `api-gtm.grubhub.com/restaurant_gateway/info/nonvolatile/{id}` | 餐厅基础信息 + 菜单分类骨架 | `object.data.enhanced_feed[]` |
| `api-gtm.grubhub.com/restaurant_gateway/feed/{id}/{categoryId}?task=CATEGORY` | 单个分类的菜品列表 | `object.data.content[].entity` |
| `api-gtm.grubhub.com/restaurant_gateway/feed/{id}/None?task=POPULAR_ITEMS` | Best Sellers 热销分类 | 同上 |

### 执行流程
```
1. 打开餐厅页面 (domcontentloaded + 6s 等待)
   → 自动触发 nonvolatile API (获取分类列表)

2. 遍历点击所有导航 tab [data-testid^="category_"]
   → 每次点击触发对应 feed API (每个分类 500ms 间隔)

3. 从 nonvolatile 的 enhanced_feed 解析分类顺序
   从每个 feed 响应的 content[].entity 解析菜品

4. 输出 JSON / 文本 / Markdown
```

### 菜品数据字段
```python
entity = {
    "item_name": str,
    "item_description": str,
    "item_price": {
        "delivery": { "styled_text": { "text": "$13.99" } },
        "pickup":   { "styled_text": { "text": "$13.99" } }
    },
    "media_image": { "base_url": str, "public_id": str, "format": str },
    "features_v2": { "POPULAR": {"enabled": bool}, "SPICY": {"enabled": bool} }
}
```

---

## 三、可复用经验（适用于其他外卖/餐饮平台）

### 判断策略的决策树
```
目标站点是否为 SPA？
├── 否 → 直接 requests + BeautifulSoup 解析 HTML
└── 是 → 先用 Playwright 打开页面，监听网络请求
          ├── 发现 JSON API 调用？ → 拦截 API（本方案）
          └── 无清晰 API？ → DOM 解析 + 等待 selector
```

### SPA 站点通用配置
```python
# ✅ 正确姿势
page.goto(url, wait_until='domcontentloaded', timeout=30000)
page.wait_for_timeout(6000)  # 给 React 渲染时间

# ❌ 避免
page.goto(url, wait_until='networkidle')  # SPA 永远不会 idle
```

### 拦截 API 模板
```python
captured = {}

def on_response(response):
    if 'target-api-keyword' in response.url:
        try:
            captured[response.url] = response.json()
        except Exception:
            pass

page.on('response', on_response)
page.goto(url, ...)
# 触发交互（点击、滚动）让更多 API 被调用
```

### 懒加载触发方式对比
| 触发方式 | 适用场景 | 注意事项 |
|---------|---------|---------|
| 点击导航 tab | 分类切换加载（本案例） | 每次点击后等 400-600ms |
| 模拟滚动 | 无限滚动列表 | 虚拟化渲染下无效 |
| 直接调用 API | 已知端点和参数结构 | 需要 session cookie / token |

### 反爬绕过配置（Grubhub 有效）
```python
context = browser.new_context(
    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    viewport={'width': 1920, 'height': 1080},
    bypass_csp=True,
)
```
- Mac UA 比 Windows UA 触发验证的概率更低
- `bypass_csp=True` 避免内容安全策略阻断脚本执行

---

## 四、脚本位置

```
skills/crawler/scripts/grubhub_menu.py
```

**运行方式**:
```bash
# Markdown 输出（交付给客户）
python3 grubhub_menu.py --url "https://www.grubhub.com/restaurant/.../ID" --output markdown

# JSON 输出（程序处理）
python3 grubhub_menu.py --url "..." --output json

# 调试模式（可视化浏览器）
python3 grubhub_menu.py --url "..." --visible
```

**实测结果**: Tacos Chano — 11 个分类，95 个菜品，含名称/价格/描述/热销标签，耗时约 20s。
