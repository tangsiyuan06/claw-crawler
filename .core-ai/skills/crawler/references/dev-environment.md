# 开发环境说明

> 本项目爬虫脚本统一在 `claw-crawler` conda 虚拟环境中运行。
> 所有 `conda run -n claw-crawler python3 ...` 命令均依赖此环境。

---

## 一、环境概览

| 项目 | 值 |
|------|-----|
| conda 环境名 | `claw-crawler` |
| Python 版本 | 3.13.x |
| 环境路径 | `/opt/anaconda3/envs/claw-crawler` |
| conda 版本 | 24.x |

---

## 二、核心依赖

| 包 | 版本 | 用途 |
|----|------|------|
| `nodriver` | 0.48.x | CDP 浏览器自动化（主力爬虫框架） |
| `beautifulsoup4` | 4.x | 静态 HTML 解析 |
| `requests` | 2.x | 静态页面 HTTP 请求 |
| `websockets` | 16.x | nodriver 内部 CDP WebSocket 通信 |
| `playwright` | 1.x | 备用浏览器自动化（非主要，保留备用） |
| `pytest` | 9.x | 单元测试 |

---

## 三、环境搭建（首次部署）

### 3.1 安装 conda

```bash
# macOS（推荐 Miniforge，比 Anaconda 更轻量）
brew install miniforge
# 或下载安装包：https://github.com/conda-forge/miniforge/releases

# Linux
wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
bash Miniforge3-Linux-x86_64.sh
```

### 3.2 创建虚拟环境

```bash
conda create -n claw-crawler python=3.13 -y
conda activate claw-crawler
```

### 3.3 安装依赖

```bash
pip install nodriver beautifulsoup4 requests websockets pytest playwright

# 安装 Playwright 浏览器内核（备用）
playwright install chromium
```

### 3.4 验证安装

```bash
conda run -n claw-crawler python3 -c "import nodriver; print('nodriver OK:', nodriver.__version__ if hasattr(nodriver, '__version__') else 'installed')"
conda run -n claw-crawler python3 -c "import bs4; print('beautifulsoup4 OK:', bs4.__version__)"
```

---

## 四、nodriver 本地源码模式（备用）

若 pip 安装的 nodriver 版本不兼容，可使用项目根目录的 `nodriver-main` 本地源码：

```
claw-crawler/
└── nodriver-main/      ← 本地源码，优先级低于 pip 安装版本
    ├── nodriver/
    └── ...
```

各爬虫脚本已包含自动 fallback 逻辑：

```python
try:
    import nodriver as uc
    from nodriver import cdp
except (ModuleNotFoundError, ImportError):
    import os, sys
    _root = os.path.join(os.path.dirname(__file__), "..", "..", "..", "nodriver-main")
    sys.path.insert(0, os.path.abspath(_root))
    import nodriver as uc
    from nodriver import cdp
```

更新本地源码：
```bash
cd $(git rev-parse --show-toplevel)/nodriver-main
git pull
```

---

## 五、环境变量配置（`.env`）

项目根目录 `.env` 文件控制运行时行为，关键字段：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `CHROMIUM_EXECUTABLE_PATH` | `/usr/bin/chromium-browser` | Chromium 路径（Linux 服务器） |
| `HEADLESS_MODE` | `true` | 服务器上设为 true；本地调试设为 false |
| `CRAWLER_TIMEOUT` | `30` | 页面加载超时秒数 |
| `CRAWLER_USER_AGENT` | Chrome 120 UA | 默认 User-Agent |

本地开发时建议覆盖：
```bash
# 本地 .env.local（不提交到 git）
HEADLESS_MODE=false
CHROMIUM_EXECUTABLE_PATH=   # 留空，让 nodriver 自动找
```

---

## 六、运行脚本的标准方式

```bash
# 开发机（本地）
conda activate claw-crawler
python3 skills/crawler/scripts/grubhub_menu.py --url "..." --visible

# 或不激活环境（推荐在 CI / cron 中使用）
conda run -n claw-crawler python3 skills/crawler/scripts/grubhub_menu.py --url "..." --output json

# 持久会话探索
conda run -n claw-crawler python3 skills/crawler/scripts/session.py start --url "..." --proxy "http://127.0.0.1:7890"
```

---

## 七、常见环境问题

| 问题 | 原因 | 解决方式 |
|------|------|---------|
| `ModuleNotFoundError: nodriver` | 未在 claw-crawler 环境运行 | 加 `conda run -n claw-crawler` 前缀 |
| Chrome 启动失败（Linux 服务器） | 缺少 `--no-sandbox` 或 Chromium 路径错误 | 检查 `CHROMIUM_EXECUTABLE_PATH`；确保已装 chromium |
| `OSError: [Errno 98] Address already in use` | CDP 端口 9222 被占用 | `session.py stop` 或 `lsof -ti:9222 \| xargs kill` |
| `websockets.exceptions.ConnectionClosed` | 会话已断开 | 重启 session.py |
| 图形界面报错（`cannot connect to X server`） | 服务器无显示器，headless=False 失败 | 安装 `Xvfb`：`Xvfb :99 -screen 0 1440x900x24 &`，设 `DISPLAY=:99` |
