#!/usr/bin/env python3
"""
Browser Session Manager — 持久浏览器会话，供 agent 反复连接探索

在脚本开发前启动一个持久会话，agent 可以多次连接同一浏览器/同一页面，
无需每次重启或重载页面。

Usage:
    # 启动会话（后台运行，浏览器保持打开）
    python3 session.py start --url "https://www.doordash.com/store/.../5188148"

    # 查看当前会话状态（连接信息、已捕获 API 列表）
    python3 session.py status

    # 关闭会话
    python3 session.py stop

Agent 连接方式（无需重新加载页面）：
    browser = await uc.start(host="127.0.0.1", port=<PORT>)
    tab = browser.main_tab   # 直接拿到已加载的页面
    # ... 交互、捕获、分析 ...
    # 不要调用 browser.stop()，否则会关闭 Chrome
"""

import argparse
import asyncio
import json
import os
import signal
import socket
import sys
from pathlib import Path

SESSION_FILE = Path(__file__).parent.parent / ".learning" / ".session.json"

try:
    import nodriver as uc
    from nodriver import cdp
except (ModuleNotFoundError, ImportError):
    _root = os.path.join(os.path.dirname(__file__), "..", "..", "..", "nodriver-main")
    sys.path.insert(0, os.path.abspath(_root))
    import nodriver as uc
    from nodriver import cdp


# ─── Port utilities ────────────────────────────────────────────────────────────

def is_port_in_use(port: int) -> bool:
    """检查端口是否被占用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


def find_process_on_port(port: int) -> int | None:
    """查找占用端口的进程 PID（仅 POSIX）"""
    try:
        import subprocess
        result = subprocess.run(
            ['lsof', '-ti', f':{port}'],
            capture_output=True, text=True, timeout=5
        )
        if result.stdout.strip():
            return int(result.stdout.strip().split('\n')[0])
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass
    return None


def cleanup_port(port: int) -> bool:
    """如果端口被残留 Chrome 占用，尝试清理"""
    if not is_port_in_use(port):
        return True

    pid = find_process_on_port(port)
    if pid:
        print(f"  ⚠️  端口 {port} 被进程 {pid} 占用，尝试终止...")
        try:
            os.kill(pid, signal.SIGTERM)
            import time
            time.sleep(1)
            if not is_port_in_use(port):
                print(f"  ✅ 端口 {port} 已释放")
                return True
            # 如果 SIGTERM 不够，用 SIGKILL
            os.kill(pid, signal.SIGKILL)
            time.sleep(0.5)
            if not is_port_in_use(port):
                print(f"  ✅ 端口 {port} 已释放 (force kill)")
                return True
        except (ProcessLookupError, PermissionError):
            pass

    print(f"  ⚠️  无法释放端口 {port}，将使用自动端口")
    return False


# ─── Session state ────────────────────────────────────────────────────────────

def save_session(port: int, url: str, pid: int):
    SESSION_FILE.parent.mkdir(exist_ok=True)
    SESSION_FILE.write_text(json.dumps({
        "host": "127.0.0.1",
        "port": port,
        "url": url,
        "pid": pid,
        "captured": [],
    }, indent=2, ensure_ascii=False))


def load_session() -> dict | None:
    if not SESSION_FILE.exists():
        return None
    try:
        return json.loads(SESSION_FILE.read_text())
    except Exception:
        return None


def update_captured(entries: list):
    s = load_session()
    if not s:
        return
    existing_urls = {e["url"] for e in s.get("captured", [])}
    for e in entries:
        if e["url"] not in existing_urls:
            s["captured"].append(e)
    SESSION_FILE.write_text(json.dumps(s, indent=2, ensure_ascii=False))


# ─── Start ────────────────────────────────────────────────────────────────────

async def _start_session(url: str, port: int, proxy: str | None = None):
    captured_log = []

    # 注意：不要把 --remote-debugging-port 放入 browser_args
    # nodriver 的 Browser.start() 会自动调用 free_port() 并添加该参数
    # 如果两边都传，Chrome 会收到两个 --remote-debugging-port，导致行为不确定
    # 正确做法：通过 uc.start(host=..., port=...) 让 nodriver 统一管理端口
    browser_args = [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--window-size=1440,900",
    ]
    if proxy:
        browser_args.append(f"--proxy-server={proxy}")

    # 端口处理方案：
    # nodriver 的 Config(host=X, port=Y) 会导致 connect_existing=True，
    # 即不会启动新 Chrome，而是连接已有实例 —— 这不是我们想要的。
    #
    # 正确做法：让 nodriver 自动分配端口（free_port），
    # 不在 browser_args 中手动传 --remote-debugging-port，
    # 这样只有一个地方设置端口，避免冲突。
    # 用户如果指定了 --port，我们只用来检查是否被占用，然后让 nodriver 自己选端口。
    config = uc.Config(
        headless=False,
        browser_args=browser_args,
    )
    browser = await uc.start(config=config)
    tab = browser.main_tab

    # CDP 网络监控（持续捕获，不过滤）
    await tab.send(cdp.network.enable())

    pending = {}

    async def on_response_received(event: cdp.network.ResponseReceived, tab=None):
        ct = (event.response.headers or {}).get("content-type", "")
        if "json" in ct:
            pending[event.request_id] = event.response.url

    async def on_loading_finished(event: cdp.network.LoadingFinished, tab=None):
        if event.request_id not in pending:
            return
        resp_url = pending.pop(event.request_id)
        try:
            body, _ = await tab.send(cdp.network.get_response_body(event.request_id))
            size = len(body)
            data = json.loads(body)
            preview = json.dumps(data, ensure_ascii=False)[:200]
            entry = {"url": resp_url, "size": size, "preview": preview}
            captured_log.append(entry)
            update_captured([entry])
            print(f"  [captured] [{size:>7}B] {resp_url}")
        except Exception:
            pass

    tab.add_handler(cdp.network.ResponseReceived, on_response_received)
    tab.add_handler(cdp.network.LoadingFinished, on_loading_finished)

    print(f"  Navigating to: {url}")
    await tab.get(url)
    await tab.select("body", timeout=15)
    await tab.wait(3)

    # 保存会话信息（真实 port 可能与请求的不同，从浏览器 info 拿）
    actual_port = browser.info.get("webSocketDebuggerUrl", f"ws://127.0.0.1:{port}").split(":")[2].split("/")[0]
    save_session(int(actual_port), url, os.getpid())

    print(f"\n✅ 会话已启动")
    print(f"   URL  : {url}")
    print(f"   Port : {actual_port}")
    print(f"   PID  : {os.getpid()}")
    if proxy:
        print(f"   Proxy: {proxy}")
    print(f"\n   Agent 连接方式：")
    print(f"   browser = await uc.start(host='127.0.0.1', port={actual_port})")
    print(f"   tab = browser.main_tab  # 页面已加载，直接使用")
    print(f"\n   Ctrl+C 或 'python3 session.py stop' 关闭")
    print(f"   持续捕获 JSON API 请求...\n")

    # 保持运行
    try:
        while True:
            await asyncio.sleep(1)
    except (asyncio.CancelledError, KeyboardInterrupt):
        print("\n  关闭会话...")
        browser.stop()
        if SESSION_FILE.exists():
            SESSION_FILE.unlink()


def cmd_start(url: str, port: int, proxy: str | None = None):
    # 启动前先检查和清理端口占用
    if is_port_in_use(port):
        print(f"  ⚠️  端口 {port} 已被占用")
        if not cleanup_port(port):
            print(f"  → 将使用 nodriver 自动分配端口")
            port = 0  # 0 表示让 nodriver 自动选端口

    try:
        uc.loop().run_until_complete(_start_session(url, port, proxy))
    except KeyboardInterrupt:
        pass


# ─── Status ───────────────────────────────────────────────────────────────────

def cmd_status():
    s = load_session()
    if not s:
        print("没有活动会话。使用 'python3 session.py start --url ...' 启动。")
        return

    print(f"\n会话状态：")
    print(f"  URL  : {s['url']}")
    print(f"  Host : {s['host']}:{s['port']}")
    print(f"  PID  : {s['pid']}")
    print(f"\n  连接方式：")
    print(f"  browser = await uc.start(host='{s['host']}', port={s['port']})")
    print(f"  tab = browser.main_tab")

    captured = s.get("captured", [])
    if captured:
        print(f"\n  已捕获 {len(captured)} 个 JSON API（按大小排序）：")
        for i, c in enumerate(sorted(captured, key=lambda x: x["size"], reverse=True)[:15], 1):
            print(f"  {i:>2}. [{c['size']:>7}B] {c['url']}")
    else:
        print(f"\n  尚未捕获到 JSON API 请求")


# ─── Stop ─────────────────────────────────────────────────────────────────────

def cmd_stop():
    s = load_session()
    if not s:
        print("没有活动会话。")
        return
    pid = s.get("pid")
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"已发送 SIGTERM 到 PID {pid}")
    except ProcessLookupError:
        print(f"进程 {pid} 已不存在")
    except PermissionError:
        print(f"无权限终止进程 {pid}")
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()
    print("会话已关闭。")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="持久浏览器会话管理 — nodriver 探索专用"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_start = sub.add_parser("start", help="启动会话并打开目标页面")
    p_start.add_argument("--url", required=True, help="目标页面 URL")
    p_start.add_argument("--port", type=int, default=9222, help="CDP 调试端口（默认 9222）")
    p_start.add_argument("--proxy", default=None, help="代理地址，如 http://127.0.0.1:7890 或 socks5://127.0.0.1:1080")

    sub.add_parser("status", help="查看当前会话状态和已捕获 API")
    sub.add_parser("stop", help="关闭当前会话")

    args = parser.parse_args()

    if args.cmd == "start":
        cmd_start(args.url, args.port, args.proxy)
    elif args.cmd == "status":
        cmd_status()
    elif args.cmd == "stop":
        cmd_stop()


if __name__ == "__main__":
    main()
