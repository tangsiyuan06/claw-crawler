#!/usr/bin/env python3
"""
DoorDash Restaurant Menu Crawler (nodriver edition)
Uses nodriver (undetected CDP) to bypass WAF/anti-bot, intercepts
storepageFeed GraphQL API to extract full menu: sections, items,
prices, descriptions, images.

Usage:
    python3 doordash_menu.py --url "https://www.doordash.com/store/902649"
    python3 doordash_menu.py --url "..." --output markdown
    python3 doordash_menu.py --url "..."              # visible browser (default, bypasses Cloudflare)
    python3 doordash_menu.py --url "..." --headless   # headless mode (server env, may be blocked)
    python3 doordash_menu.py --url "..." --proxy "http://127.0.0.1:7890"
"""

import argparse
import asyncio
import json
import sys
from typing import Dict, List, Optional

CRAWLER_META = {
    "name": "doordash_menu",
    "domains": ["doordash.com"],
    "data": "餐厅完整菜单：分类、菜品名称、价格（字符串）、描述、图片 URL",
    "framework": "nodriver",
    "url_pattern": "https://www.doordash.com/store/{store_id}",
    "output_formats": ["json", "text", "markdown"],
    "example": 'python3 doordash_menu.py --url "https://www.doordash.com/store/902649" --output json',
    "notes": "DoorDash requires headless=False (visible browser) to bypass Cloudflare Bot Check",
}

try:
    import nodriver as uc
    from nodriver import cdp
except (ModuleNotFoundError, ImportError):
    import os
    _root = os.path.join(os.path.dirname(__file__), "..", "..", "..", "nodriver-main")
    sys.path.insert(0, os.path.abspath(_root))
    try:
        import nodriver as uc
        from nodriver import cdp
    except (ModuleNotFoundError, ImportError) as e:
        print(f"Error: nodriver not found — {e}", file=sys.stderr)
        print("Options:", file=sys.stderr)
        print("  pip install nodriver", file=sys.stderr)
        print("  or place nodriver-main/ in project root", file=sys.stderr)
        sys.exit(1)


# ─── Scraper ──────────────────────────────────────────────────────────────────

class DoorDashMenuScraper:
    def __init__(self, headless: bool = False, proxy: str | None = None):
        # headless=False: nodriver 反爬效果更佳；服务器环境传 headless=True
        self.headless = headless
        self.proxy = proxy  # 如 "http://127.0.0.1:7890" 或 "socks5://127.0.0.1:1080"

    async def _scrape_async(self, url: str) -> Dict:
        feed_data: Dict = {}

        browser_args = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--window-size=1920,1080",
        ]
        if self.proxy:
            browser_args.append(f"--proxy-server={self.proxy}")

        config = uc.Config(
            headless=self.headless,
            browser_args=browser_args,
        )
        browser = await uc.start(config=config)
        tab = browser.main_tab

        # Enable network events — must be before tab.get()
        await tab.send(cdp.network.enable())

        # Two-stage interception:
        # 1. ResponseReceived → record request_id for storepageFeed GraphQL
        # 2. LoadingFinished  → body ready, safe to read
        pending: Dict[str, str] = {}

        async def on_response_received(event: cdp.network.ResponseReceived, tab=None):
            if "storepageFeed" in event.response.url:
                pending[event.request_id] = event.response.url

        async def on_loading_finished(event: cdp.network.LoadingFinished, tab=None):
            if event.request_id not in pending:
                return
            req_url = pending.pop(event.request_id)
            try:
                body, _ = await tab.send(cdp.network.get_response_body(event.request_id))
                feed_data["raw"] = json.loads(body)
                print(f"  [captured] storepageFeed ({len(body)} bytes)", file=sys.stderr)
            except Exception:
                pass

        tab.add_handler(cdp.network.ResponseReceived, on_response_received)
        tab.add_handler(cdp.network.LoadingFinished, on_loading_finished)

        await tab.get(url)

        # DoorDash does a client-side redirect from /store/{id} to /store/{slug}/{menu_id}/
        # storepageFeed fires AFTER this SPA navigation (~13s from initial load).
        # Poll up to 25s for the feed to arrive.
        print("  [waiting] DoorDash SPA navigation + storepageFeed...", file=sys.stderr)
        for _ in range(25):
            if feed_data:
                break
            await tab.wait(1)

        if not feed_data:
            print("  [waiting] still waiting for storepageFeed...", file=sys.stderr)
            await tab.wait(5)

        browser.stop()

        if not feed_data:
            raise RuntimeError(
                "No menu data captured — page may have been blocked or storepageFeed did not fire"
            )

        return self._build_menu(url, feed_data["raw"])

    def scrape(self, url: str) -> Dict:
        return uc.loop().run_until_complete(self._scrape_async(url))

    # ── Menu assembly ──────────────────────────────────────────────────────────

    def _build_menu(self, source_url: str, raw: Dict) -> Dict:
        feed = raw.get("data", {}).get("storepageFeed", {})

        # Restaurant info
        header = feed.get("storeHeader", {})
        restaurant_name = header.get("name", "Unknown")
        restaurant_id = header.get("id", "")

        sections: Dict[str, List[Dict]] = {}

        # Featured Items carousel (first carousel)
        carousels = feed.get("carousels", [])
        for carousel in carousels:
            cat_name = carousel.get("name", "Featured")
            items = [
                self._parse_item(item, img_field="imgUrl")
                for item in carousel.get("items", [])
                if self._parse_item(item, img_field="imgUrl")
            ]
            if items:
                sections[cat_name] = items

        # Main menu categories from itemLists
        for item_list in feed.get("itemLists", []):
            cat_name = item_list.get("name", "Unknown")
            items = [
                self._parse_item(item)
                for item in item_list.get("items", [])
                if self._parse_item(item)
            ]
            sections[cat_name] = items

        return {
            "restaurant": restaurant_name,
            "restaurant_id": str(restaurant_id),
            "url": source_url,
            "total_sections": len(sections),
            "total_items": sum(len(v) for v in sections.values()),
            "sections": sections,
        }

    def _parse_item(self, item: Dict, img_field: str = "imageUrl") -> Optional[Dict]:
        name = item.get("name", "").strip()
        if not name:
            return None

        price = item.get("displayPrice") or None
        description = item.get("description", "").strip() or None
        image_url = item.get(img_field) or None

        result: Dict = {"name": name}
        if price:
            result["price"] = price
        if description:
            result["description"] = description
        if image_url:
            result["image"] = image_url

        # Dietary tags
        tags = [t.get("text", "").lower() for t in item.get("dietaryTagsList", []) if t.get("text")]
        if tags:
            result["tags"] = tags

        # Callout (e.g., "Popular")
        callout = item.get("calloutDisplayString")
        if callout:
            result["callout"] = callout

        return result


# ─── Output formatters ────────────────────────────────────────────────────────

def format_text(data: Dict) -> str:
    lines = [
        f"Restaurant  : {data['restaurant']}",
        f"Store ID    : {data['restaurant_id']}",
        f"URL         : {data['url']}",
        f"Sections    : {data['total_sections']}",
        f"Total items : {data['total_items']}",
        "",
    ]
    for section, items in data["sections"].items():
        lines.append("=" * 60)
        lines.append(f"  {section}  ({len(items)} items)")
        lines.append("=" * 60)
        if not items:
            lines.append("  (no items)")
        for item in items:
            price = item.get("price") or "N/A"
            tags = f"  [{', '.join(item['tags'])}]" if item.get("tags") else ""
            callout = f"  ★{item['callout']}" if item.get("callout") else ""
            lines.append(f"  {item['name']:<50} {price}{tags}{callout}")
            if item.get("description"):
                lines.append(f"    {item['description']}")
        lines.append("")
    return "\n".join(lines)


def format_markdown(data: Dict) -> str:
    lines = [
        f"# {data['restaurant']}",
        "",
        f"**{data['total_sections']} sections · {data['total_items']} items**",
        "",
    ]
    for section, items in data["sections"].items():
        lines.append(f"## {section}")
        if not items:
            lines.append("_items not loaded_")
        for item in items:
            price = item.get("price") or "N/A"
            tags = f" · _{', '.join(item['tags'])}_" if item.get("tags") else ""
            callout = f" · **{item['callout']}**" if item.get("callout") else ""
            lines.append(f"- **{item['name']}** — {price}{tags}{callout}")
            if item.get("description"):
                lines.append(f"  > {item['description']}")
        lines.append("")
    return "\n".join(lines)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="DoorDash Menu Crawler — nodriver (anti-bot) + GraphQL interception"
    )
    parser.add_argument("--url", required=True, help="DoorDash restaurant store URL")
    parser.add_argument(
        "--output", choices=["json", "text", "markdown"], default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="Run browser in headless mode (default: visible — DoorDash blocks headless via Cloudflare)",
    )
    parser.add_argument(
        "--proxy", default=None,
        help="代理地址，如 http://127.0.0.1:7890 或 socks5://127.0.0.1:1080",
    )
    args = parser.parse_args()

    print(f"Scraping: {args.url}", file=sys.stderr)
    scraper = DoorDashMenuScraper(headless=args.headless, proxy=args.proxy)

    try:
        data = scraper.scrape(args.url)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Done: {data['total_sections']} sections, {data['total_items']} items", file=sys.stderr)

    if args.output == "json":
        print(json.dumps(data, indent=2, ensure_ascii=False))
    elif args.output == "text":
        print(format_text(data))
    elif args.output == "markdown":
        print(format_markdown(data))


if __name__ == "__main__":
    main()
