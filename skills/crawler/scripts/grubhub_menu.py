#!/usr/bin/env python3
"""
Grubhub Restaurant Menu Crawler (nodriver edition)
Uses nodriver (undetected CDP) to bypass WAF/anti-bot, intercepts internal API
to extract full menu: sections, items, prices, descriptions, images.

Usage:
    python3 grubhub_menu.py --url "https://www.grubhub.com/restaurant/.../ID"
    python3 grubhub_menu.py --url "..." --output markdown
    python3 grubhub_menu.py --url "..." --visible   # debug with visible browser
"""

import argparse
import asyncio
import json
import sys
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urlparse

CRAWLER_META = {
    "name": "grubhub_menu",
    "domains": ["grubhub.com"],
    "data": "餐厅完整菜单：分类、菜品名称、价格（美分转换）、描述、图片 URL",
    "framework": "nodriver",
    "url_pattern": "https://www.grubhub.com/restaurant/{slug}/{restaurant_id}",
    "output_formats": ["json", "text", "markdown"],
    "example": 'python3 grubhub_menu.py --url "https://www.grubhub.com/restaurant/.../13030928" --output json',
}

# nodriver is located in nodriver-main/ relative to project root.
# Support both: installed via pip or loaded from local source.
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

class GrubhubMenuScraper:
    def __init__(self, headless: bool = False, proxy: str | None = None):
        # headless=False: nodriver 反爬效果更佳；服务器环境传 headless=True
        self.headless = headless
        self.proxy = proxy  # 如 "http://127.0.0.1:7890" 或 "socks5://127.0.0.1:1080"

    async def _scrape_async(self, url: str) -> Dict:
        nonvolatile: Dict = {}
        feed_by_category: Dict = {}

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

        # Enable network events
        await tab.send(cdp.network.enable())

        # Two-stage interception:
        # 1. ResponseReceived  → record request_id + url for API calls we care about
        # 2. LoadingFinished   → body is guaranteed ready, safe to call get_response_body
        pending: Dict[str, str] = {}  # request_id → url

        async def on_response_received(event: cdp.network.ResponseReceived, tab=None):
            url = event.response.url
            if ("restaurant_gateway/info/nonvolatile" in url
                    or "restaurant_gateway/feed" in url):
                pending[event.request_id] = url

        async def on_loading_finished(event: cdp.network.LoadingFinished, tab=None):
            if event.request_id not in pending:
                return
            url = pending.pop(event.request_id)
            try:
                body, _ = await tab.send(cdp.network.get_response_body(event.request_id))
                data = json.loads(body)
            except Exception:
                return

            if "restaurant_gateway/info/nonvolatile" in url:
                nonvolatile["data"] = data
                print(f"  [captured] nonvolatile ({len(body)} bytes)", file=sys.stderr)
            elif "restaurant_gateway/feed" in url:
                parts = urlparse(url).path.rstrip("/").split("/")
                category_id = parts[-1]
                task = parse_qs(urlparse(url).query).get("task", [""])[0]
                feed_by_category[f"{task}:{category_id}"] = data
                print(f"  [captured] feed {task}:{category_id}", file=sys.stderr)

        tab.add_handler(cdp.network.ResponseReceived, on_response_received)
        tab.add_handler(cdp.network.LoadingFinished, on_loading_finished)

        await tab.get(url)
        # Wait for the menu nav to appear as page-ready signal
        await tab.select('[data-testid^="category_"]', timeout=15)
        await tab.wait(3)

        # Click each category nav tab to trigger lazy-loaded feed API calls
        nav_items = await tab.select_all('[data-testid^="category_"]')
        print(f"  Nav tabs found: {len(nav_items)}", file=sys.stderr)
        for nav in nav_items:
            try:
                await nav.click()
                await tab.wait(0.6)
            except Exception:
                pass

        await tab.wait(2)
        browser.stop()

        return self._build_menu(url, nonvolatile, feed_by_category)

    def scrape(self, url: str) -> Dict:
        return uc.loop().run_until_complete(self._scrape_async(url))

    # ── Menu assembly ──────────────────────────────────────────────────────────

    def _build_menu(self, source_url: str, nonvolatile: Dict, feed_by_category: Dict) -> Dict:
        if not nonvolatile:
            raise RuntimeError("No restaurant data captured — page may have been blocked or not loaded")

        obj = nonvolatile["data"].get("object", {})
        enhanced_feed = obj.get("data", {}).get("enhanced_feed", [])

        # Ordered category list (skip non-menu entries)
        categories = [e for e in enhanced_feed if e.get("data_type") == "MENU_ITEM"]

        # Restaurant name from content entities
        restaurant_name = ""
        for item in obj.get("data", {}).get("content", []):
            name = item.get("entity", {}).get("name", "")
            if name:
                restaurant_name = name
                break

        sections: Dict[str, List[Dict]] = {}
        for cat in categories:
            cat_name = cat.get("name", "Unknown")
            feed_type = cat.get("feed_type", "CATEGORY")
            cat_id = self._get_category_id(cat)

            feed = feed_by_category.get(f"{feed_type}:{cat_id}") or \
                   feed_by_category.get(f"CATEGORY:{cat_id}")

            items: List[Dict] = []
            if feed:
                for entry in feed.get("object", {}).get("data", {}).get("content", []):
                    parsed = self._parse_item(entry.get("entity", {}))
                    if parsed:
                        items.append(parsed)

            sections[cat_name] = items

        return {
            "restaurant": restaurant_name,
            "url": source_url,
            "total_sections": len(sections),
            "total_items": sum(len(v) for v in sections.values()),
            "sections": sections,
        }

    def _get_category_id(self, cat_entry: Dict) -> str:
        for p in cat_entry.get("request", {}).get("parameters", []):
            if p.get("key") in ("categoryId", "category_id", "id"):
                return str(p.get("value", "None"))
        return str(cat_entry.get("id", "None"))

    def _parse_item(self, entity: Dict) -> Optional[Dict]:
        name = entity.get("item_name", "").strip()
        if not name:
            return None

        price = None
        for channel in ("delivery", "pickup"):
            styled = entity.get("item_price", {}).get(channel, {}).get("styled_text", {})
            if styled.get("text"):
                price = styled["text"]
                break

        description = entity.get("item_description", "").strip() or None

        image_url = None
        media = entity.get("media_image", {})
        if media.get("base_url") and media.get("public_id"):
            image_url = (
                f"{media['base_url']}d_search:browse-images:default.jpg/"
                f"w_400,q_auto:low,fl_lossy,c_fill,f_auto/"
                f"{media['public_id']}.{media.get('format', 'jpg')}"
            )

        item: Dict = {"name": name, "price": price}
        if description:
            item["description"] = description
        if image_url:
            item["image"] = image_url

        tags = [k.lower() for k, v in entity.get("features_v2", {}).items() if v.get("enabled")]
        if tags:
            item["tags"] = tags

        return item


# ─── Output formatters ────────────────────────────────────────────────────────

def format_text(data: Dict) -> str:
    lines = [
        f"Restaurant : {data['restaurant']}",
        f"URL        : {data['url']}",
        f"Sections   : {data['total_sections']}",
        f"Total items: {data['total_items']}",
        "",
    ]
    for section, items in data["sections"].items():
        lines.append("=" * 60)
        lines.append(f"  {section}  ({len(items)} items)")
        lines.append("=" * 60)
        if not items:
            lines.append("  (no items loaded)")
        for item in items:
            price = item.get("price") or "N/A"
            tags = f"  [{', '.join(item['tags'])}]" if item.get("tags") else ""
            lines.append(f"  {item['name']:<45} {price}{tags}")
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
            lines.append(f"- **{item['name']}** — {price}{tags}")
            if item.get("description"):
                lines.append(f"  > {item['description']}")
        lines.append("")
    return "\n".join(lines)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Grubhub Menu Crawler — nodriver (anti-bot) + API interception"
    )
    parser.add_argument("--url", required=True, help="Grubhub restaurant page URL")
    parser.add_argument(
        "--output", choices=["json", "text", "markdown"], default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "--visible", action="store_true",
        help="Run browser in visible mode (default: headless)",
    )
    parser.add_argument(
        "--proxy", default=None,
        help="代理地址，如 http://127.0.0.1:7890 或 socks5://127.0.0.1:1080",
    )
    args = parser.parse_args()

    print(f"Scraping: {args.url}", file=sys.stderr)
    scraper = GrubhubMenuScraper(headless=not args.visible, proxy=args.proxy)

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
