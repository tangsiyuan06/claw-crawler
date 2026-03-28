# SETUP.md — Crawler Agent 环境初始化

本文档用于在 OpenClaw 服务器上从零完成 Crawler Agent 的环境安装。

**目标系统**: Linux (Ubuntu/Debian)
**工作目录**: `/home/admin/.openclaw/workspace-crawler`
**运行用户**: `admin`

---

## 前置要求

| 依赖 | 最低版本 | 用途 |
|------|---------|------|
| Python | 3.11+ | 爬虫脚本、协调器 |
| conda / miniconda | 任意 | Python 环境隔离 |
| Node.js | 18+ | DALL-E 图片发送 |
| Docker | 20+ | SearXNG 搜索服务 |
| Git | 任意 | 拉取代码 |

---

## 第一步：拉取代码

```bash
cd /home/admin/.openclaw
git clone <repo-url> workspace-crawler
cd workspace-crawler
```

---

## 第二步：Python 环境（conda）

### 2.1 创建 conda 环境

```bash
conda create -n claw-crawler python=3.11 -y
conda activate claw-crawler
```

### 2.2 安装 Python 依赖

```bash
pip install nodriver beautifulsoup4 requests websockets httpx rich pytest
```

各依赖用途：

| 包 | 使用脚本 | 用途 |
|----|---------|------|
| `nodriver` | `grubhub_menu.py`, `doordash_menu.py`, `session.py` | CDP 浏览器自动化（反爬主力） |
| `websockets` | nodriver 内部依赖 | CDP WebSocket 通信 |
| `beautifulsoup4` | `crawler.py` | 静态 HTML 解析 |
| `requests` | `crawler.py` | 静态页面 HTTP 请求 |
| `httpx` | `searxng.py` | 异步 HTTP 客户端 |
| `rich` | `searxng.py` | 终端格式化输出 |
| `pytest` | `test_*.py` | 单元测试 |

### 2.3 安装系统 Chrome/Chromium

nodriver 使用系统已安装的 Chrome/Chromium，**无需单独下载浏览器内核**。

```bash
# Ubuntu/Debian
sudo apt-get install -y chromium-browser
# 或安装 Google Chrome
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
sudo apt-get install -y google-chrome-stable

# 验证
which chromium-browser || which google-chrome
```

> **与 Playwright 的区别**：Playwright 需要 `playwright install chromium` 下载独立内核（约 200MB）；
> nodriver 复用系统 Chrome，启动更快，浏览器指纹更接近真实用户，反爬效果更好。

### 2.4 安装系统级浏览器依赖（无头模式如遇报错）

```bash
sudo apt-get install -y libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 libgbm1 \
  libxss1 libasound2 libx11-xcb1
```

> 服务器上 headless=True 运行时需要这些依赖；headless=False 需额外安装 Xvfb：
> `sudo apt-get install -y xvfb && Xvfb :99 -screen 0 1440x900x24 &`，设 `DISPLAY=:99`

### 2.5 验证安装

```bash
conda run -n claw-crawler python3 -c "import nodriver; print('nodriver OK')"
conda run -n claw-crawler python3 skills/crawler/scripts/crawler.py list
conda run -n claw-crawler python3 skills/crawler/scripts/grubhub_menu.py --help
conda run -n claw-crawler python3 skills/crawler/scripts/doordash_menu.py --help
```

---

## 第三步：配置环境变量

复制模板并填写实际值：

```bash
cp .env.example .env   # 如无模板，直接创建 .env
```

`.env` 文件内容（按实际填写）：

```bash
# OpenClaw 路径配置
WORKSPACE_PATH=/home/admin/.openclaw/workspace-crawler
MEMORY_PATH=/home/admin/.openclaw/workspace-crawler/memory
SKILLS_PATH=/home/admin/.openclaw/workspace-crawler/skills
OPENCLAW_WORKSPACE=/home/admin/.openclaw/workspace-crawler

# 爬虫行为配置
CRAWLER_TIMEOUT=30
CRAWLER_MAX_RETRIES=3
CRAWLER_RESPECT_ROBOTS=true
HEADLESS_MODE=true

# 浏览器路径（可选，Playwright 会自动找到自己安装的 Chromium）
# CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium-browser

# SearXNG 搜索服务地址
SEARXNG_URL=http://localhost:8080

# Azure DALL-E（图片生成功能）
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_API_KEY=your-api-key-here

# 飞书（Feishu）配置（图片发送 + Agent 通知）
FEISHU_APP_ID=your-app-id
FEISHU_APP_SECRET=your-app-secret
```

---

## 第四步：启动 SearXNG（搜索服务）

SearXNG 提供隐私搜索能力，通过 Docker 运行。

```bash
sh skills/searxng/scripts/run-searxng.sh
```

验证服务：

```bash
curl http://localhost:8080/search?q=test&format=json | python3 -m json.tool | head -20
```

> SearXNG 容器配置了 `--restart always`，服务器重启后自动恢复。

---

## 第五步：Node.js 环境（DALL-E 图片发送）

`send-image.js` 仅使用 Node.js 内置模块（`fs`, `path`, `https`, `http`），无需 `npm install`。

验证：

```bash
node skills/dalle-image-sender/scripts/send-image.js --help
```

---

## 第六步：创建目录结构

```bash
cd /home/admin/.openclaw/workspace-crawler
mkdir -p memory logs reports task-queue docs knowledge-base
```

---

## 第七步：验证全部技能

```bash
# 爬虫注册表
conda run -n claw-crawler python3 skills/crawler/scripts/crawler.py list

# 查询注册表（判断目标站点是否有现成脚本）
conda run -n claw-crawler python3 skills/crawler/scripts/crawler.py match \
  --url "https://www.grubhub.com/restaurant/tacos-chano-2251-south-monaco-street-parkway-denver/13030928"

# Grubhub 专用爬虫（通过注册表执行）
conda run -n claw-crawler python3 skills/crawler/scripts/crawler.py run grubhub_menu \
  --url "https://www.grubhub.com/restaurant/tacos-chano-2251-south-monaco-street-parkway-denver/13030928" \
  --output text

# DoorDash 专用爬虫
conda run -n claw-crawler python3 skills/crawler/scripts/doordash_menu.py \
  --url "https://www.doordash.com/store/902649" --output text

# SearXNG 搜索
conda run -n claw-crawler uv run skills/searxng/scripts/searxng.py search "python web scraping"

# Agent 协调器
conda run -n claw-crawler python3 skills/agent-cron-job/scripts/coordinator.py user list
```

---

## OpenClaw 技能注册

在 OpenClaw 管理后台，将以下路径配置为 Agent 工作空间：

```
workspace: /home/admin/.openclaw/workspace-crawler
identity:  IDENTITY.md
soul:      SOUL.md
```

技能目录 `skills/` 中每个子目录的 `SKILL.md` 会被 OpenClaw 自动读取，无需手动注册。

---

## 常见问题

### Playwright 启动报错 `libgbm.so.1 not found`
```bash
sudo apt-get install -y libgbm1
```

### SearXNG 无法访问
```bash
docker ps | grep searxng          # 检查容器状态
docker logs searxng --tail 20     # 查看启动日志
docker restart searxng            # 重启容器
```

### conda 环境中 playwright 找不到 Chromium
```bash
# 确认是在 claw-crawler 环境下安装的
conda run -n claw-crawler playwright install chromium
```

### 脚本执行权限问题
```bash
chmod +x scripts/*.sh
chmod +x skills/searxng/scripts/run-searxng.sh
```

---

## 快速重置（完全重装）

```bash
# 删除 conda 环境重建
conda deactivate
conda env remove -n claw-crawler -y
conda create -n claw-crawler python=3.11 -y
pip install nodriver beautifulsoup4 requests websockets httpx rich pytest

# 重启 SearXNG
docker stop searxng && docker rm searxng
sh skills/searxng/scripts/run-searxng.sh
```
