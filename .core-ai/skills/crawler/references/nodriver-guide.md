# nodriver 爬虫开发指南

基于本项目实际开发经验（Grubhub 菜单爬虫）整理，涵盖环境配置、开发流程、
常见坑点及可复用模式。

---

## 一、环境配置

### 1.1 安装依赖

```bash
# 激活项目 conda 环境
conda activate claw-crawler

# 核心依赖
pip install nodriver beautifulsoup4 requests pytest

# nodriver 使用系统 Chrome/Chromium，无需单独安装浏览器
# 确认 Chrome 可用：
which google-chrome || which chromium-browser || which chromium
```

> **与 Playwright 的区别**：Playwright 需要 `playwright install chromium` 下载独立内核；
> nodriver 直接复用系统已安装的 Chrome/Chromium，启动更快，指纹更接近真实用户。

### 1.2 验证安装

```bash
python3 -c "import nodriver; print('nodriver OK')"
```

### 1.3 本地源码引用（不安装 pip 包）

如果使用项目内的 `nodriver-main/` 源码：

```python
import sys, os
sys.path.insert(0, os.path.abspath("nodriver-main"))
import nodriver as uc
```

---

## 二、nodriver 核心 API 速查

### 启动浏览器

```python
import nodriver as uc

# 默认：非 headless（反爬效果最佳）
browser = await uc.start()

# headless 模式（CI/服务器）
config = uc.Config(
    headless=True,
    browser_args=["--no-sandbox", "--disable-dev-shm-usage", "--window-size=1920,1080"],
)
browser = await uc.start(config=config)
```

### 导航与等待

```python
tab = browser.main_tab

# 打开页面
await tab.get("https://example.com")

# 等待元素出现（兼作页面就绪检测）
await tab.select("body")
await tab.select(".some-selector", timeout=15)   # 超时 15 秒

# 等待固定时间
await tab.wait(3)       # 3 秒
await tab.sleep(1.5)    # 同 wait
```

### 元素操作

```python
# 查找单个元素
el = await tab.select('[data-testid="submit"]')
await el.click()

# 查找多个元素
items = await tab.select_all('[data-testid^="category_"]')
for item in items:
    await item.click()
    await tab.wait(0.5)

# 文本查找（智能匹配最短文本）
btn = await tab.find("accept all", best_match=True)
await btn.click()
```

### 网络拦截（推荐两阶段模式）

```python
from nodriver import cdp

# 激活网络事件（必须在 tab.get() 之前调用）
await tab.send(cdp.network.enable())

pending = {}   # request_id → url

async def on_received(event: cdp.network.ResponseReceived, tab=None):
    """ResponseReceived：响应头到达，body 尚未就绪，只记录 ID"""
    if "api-keyword" in event.response.url:
        pending[event.request_id] = event.response.url

async def on_finished(event: cdp.network.LoadingFinished, tab=None):
    """LoadingFinished：body 完整下载，可安全读取"""
    if event.request_id not in pending:
        return
    url = pending.pop(event.request_id)
    try:
        body, _ = await tab.send(cdp.network.get_response_body(event.request_id))
        data = json.loads(body)
        # 处理 data ...
    except Exception:
        pass

tab.add_handler(cdp.network.ResponseReceived, on_received)
tab.add_handler(cdp.network.LoadingFinished, on_finished)
```

> **关键**：handler 函数必须声明 `tab=None` 参数，nodriver 会自动注入当前 tab 实例。
> 不能用 `functools.partial` 预绑定 tab，会导致注入失败。

### 运行入口

```python
# 同步入口（脚本 main）
def main():
    result = uc.loop().run_until_complete(my_async_func())

# 异步入口
async def main():
    browser = await uc.start()
    ...
```

---

## 三、Grubhub 菜单爬取开发流程（实战回顾）

### 3.1 分析阶段

**目标**：提取 Grubhub 餐厅完整菜单（分类、菜品、价格、描述）

**第一步：判断站点类型**
- 访问页面 → 标题是通用首页标题 → 确认为 React SPA
- `networkidle` 超时 → SPA 后台请求持续不断，放弃 networkidle，改用 `domcontentloaded` + 固定等待

**第二步：分析网络请求**
```python
# 拦截所有包含 "api" / "menu" 的响应，按大小排序
# → 发现关键端点：
# api-gtm.grubhub.com/restaurant_gateway/info/nonvolatile/{id}  (42KB, 菜单骨架)
# api-gtm.grubhub.com/restaurant_gateway/feed/{id}/{categoryId} (每类菜品数据)
```

**第三步：理解数据结构**
```
nonvolatile 响应：
  object.data.enhanced_feed[]         → 菜单分类列表（含分类名、ID、feed_type）

feed/{categoryId} 响应：
  object.data.content[].entity        → 菜品列表
    .item_name                        → 菜品名
    .item_price.delivery.styled_text.text  → 价格（如 "$13.99"）
    .item_description                 → 描述
    .media_image.{base_url,public_id} → 图片
    .features_v2.POPULAR.enabled      → 是否热销
```

**第四步：识别懒加载规律**
- 页面首次加载只触发 nonvolatile + 1-2 个初始分类的 feed
- 其余分类通过点击导航 Tab 触发各自的 feed 请求
- 触发方式：`select_all('[data-testid^="category_"]')` → 逐个 click

### 3.2 开发阶段

**技术选型决策**

| 方案 | 结论 |
|------|------|
| 直接 requests | ❌ 需要登录态 cookie，API 有签名验证 |
| Playwright DOM 解析 | ❌ 虚拟化渲染，滚动不累积 DOM |
| Playwright API 拦截 | ✅ 可行，但反爬能力有限 |
| **nodriver API 拦截** | ✅ 最优，反爬最强 + API 数据最完整 |

**nodriver 开发中的关键坑**

| 坑 | 原因 | 解决 |
|----|------|------|
| handler 用 `partial` 绑定 tab | nodriver 自动注入 `tab=` 参数，partial 覆盖后注入失败 | 改用闭包捕获共享变量，handler 保留 `tab=None` 声明 |
| `ResponseReceived` 时读取 body 失败 | 响应头到达时 body 尚未下载完毕 | 改为 `LoadingFinished` 事件读取 body |
| `network.enable()` 未调用 | 默认网络事件未激活，handler 不触发 | 在 `tab.get()` 之前调用 `await tab.send(cdp.network.enable())` |
| headless=True 被识别 | 部分站点检测 headless 特征 | 默认 `headless=False`；服务器环境才开启 headless |

### 3.3 测试策略

**两层测试**：

```
Layer 1 — 单元测试（无浏览器，秒级）
  test_grubhub_menu.py
  ├── TestParseItem      → 菜品解析边界情况（11 用例）
  ├── TestGetCategoryId  → 分类 ID 提取逻辑（4 用例）
  ├── TestBuildMenu      → 菜单组装 + 错误处理（6 用例）
  ├── TestFormatText     → 文本格式化（6 用例）
  └── TestFormatMarkdown → Markdown 格式化（8 用例）

Layer 2 — 集成测试（真实浏览器）
  python3 grubhub_menu.py --url "..." --output text
  验证：11 sections, 95 items
```

**单元测试原则**：
- Mock API 响应数据（`make_entity()` / `make_feed_response()` fixtures）
- 测试解析逻辑，不测试网络行为
- 覆盖：正常路径 + 缺失字段 + 空值 + 边界条件

---

## 四、新建目标站点爬虫 SOP

```
1. 打开目标页面，开启 Chrome DevTools → Network 面板
   ├── 确认是否 SPA（看 JS bundle 加载）
   └── 观察 XHR/Fetch 请求，找体积最大的 JSON 响应

2. 分析 JSON 结构
   ├── 找数据根路径（如 object.data.content[]）
   └── 记录关键字段（名称/价格/图片/分类）

3. 确认懒加载触发方式
   ├── 滚动触发？→ tab.scroll_down()
   ├── 点击 Tab 触发？→ select_all() + click()
   └── 分页参数？→ 构造 URL 循环请求

4. 用两阶段拦截模板创建脚本
   ├── ResponseReceived → 过滤目标 URL，记录 request_id
   └── LoadingFinished  → 读取 body，解析 JSON

5. 编写单元测试
   ├── 从真实响应中截取样本数据作为 fixture
   └── 覆盖 parse / build / format 三层逻辑

6. 集成测试验证
   └── 真实 URL 跑一次，确认数据完整
```

---

## 五、常用调试技巧

```python
# 查看页面当前所有可见文本（快速定位元素）
content = await tab.get_content()

# 截图（headless 调试）
await tab.save_screenshot("debug.png")

# 打印所有网络请求 URL（找 API 端点）
async def debug_response(event: cdp.network.ResponseReceived, tab=None):
    print(event.response.url, event.response.status)
tab.add_handler(cdp.network.ResponseReceived, debug_response)

# 在页面执行 JS
result = await tab.evaluate("document.title")

# 可见模式运行（最直接的调试方式）
python3 grubhub_menu.py --url "..." --visible
```

---

## 六、脚本文件规范

```
skills/crawler/scripts/
├── crawler.py              # 通用爬虫（Playwright，静态/JS 页面）
├── {site}_menu.py          # 站点专用爬虫（nodriver）
└── test_{site}_menu.py     # 对应单元测试
```

每个专用脚本必须包含：
- `--url` / `--output` / `--visible` CLI 参数
- 输出格式：`json` / `text` / `markdown`
- stderr 进度输出，stdout 仅输出数据
- `--help` 可用

---

## 七、参考资源

- nodriver 官方文档：https://ultrafunkamsterdam.github.io/nodriver
- CDP 协议参考：https://chromedevtools.github.io/devtools-protocol/
- 本项目实战脚本：`skills/crawler/scripts/grubhub_menu.py`
- 爬取经验总结：`docs/grubhub-crawling-experience.md`
