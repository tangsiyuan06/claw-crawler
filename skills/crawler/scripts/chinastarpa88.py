#!/usr/bin/env python3
"""
China Star Restaurant Menu Crawler (nodriver edition)

Extracts the complete menu from chinastarpa88.com (BeyondMenu-powered)
by parsing embedded Next.js streaming data in the page source.

Usage:
    python3 chinastarpa88.py --url "https://www.chinastarpa88.com/" --output json
    python3 chinastarpa88.py --url "..." --output markdown
    python3 chinastarpa88.py --url "..." --visible
"""

import argparse
import asyncio
import json
import os
import re
import sys
from typing import Dict, List, Optional

try:
    import nodriver as uc
    from nodriver import cdp
except (ModuleNotFoundError, ImportError):
    _root = os.path.join(os.path.dirname(__file__), "..", "..", "..", "nodriver-main")
    sys.path.insert(0, os.path.abspath(_root))
    try:
        import nodriver as uc
        from nodriver import cdp
    except (ModuleNotFoundError, ImportError) as e:
        print(f"Error: nodriver not found — {e}", file=sys.stderr)
        sys.exit(1)

# ★ CRAWLER_META — crawler.py 注册表通过此字段发现脚本能力
CRAWLER_META = {
    "name": "chinastarpa88",
    "domains": ["chinastarpa88.com"],
    "data": "餐厅完整菜单：4 大类、27 分组、409 菜品，含名称、价格、描述",
    "framework": "nodriver",
    "url_pattern": "https://www.chinastarpa88.com/",
    "url_routes": {
        "https://www.chinastarpa88.com/": "https://www.chinastarpa88.com/ji5od7sj/china-star-blue-bell-19422/order-online#menu-section",
    },
    "output_formats": ["json", "text", "markdown"],
    "example": 'python3 chinastarpa88.py --url "https://www.chinastarpa88.com/" --output json',
}


# ─── Scraper ──────────────────────────────────────────────────────────────────

class ChinaStarScraper:
    def __init__(self, headless: bool = False, proxy: str | None = None):
        self.headless = headless
        self.proxy = proxy

    async def _scrape_async(self, url: str) -> Dict:
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

        # ★ CRITICAL: network enable before tab.get()
        await tab.send(cdp.network.enable())

        # ★ URL 映射：用户提供的首页 → 实际菜单数据 URL
        actual_url = CRAWLER_META.get("url_routes", {}).get(url, url)
        if actual_url != url:
            print(f"  [route] {url} -> {actual_url}", file=sys.stderr)

        pending: Dict[str, str] = {}

        async def on_response_received(event: cdp.network.ResponseReceived, tab=None):
            # Capture any JSON responses that might contain menu data
            ct = (event.response.headers or {}).get("content-type", "")
            if "json" in ct and ("menu" in event.response.url.lower() or "order" in event.response.url.lower()):
                pending[event.request_id] = event.response.url

        async def on_loading_finished(event: cdp.network.LoadingFinished, tab=None):
            if event.request_id not in pending:
                return
            url = pending.pop(event.request_id)
            try:
                body, _ = await tab.send(cdp.network.get_response_body(event.request_id))
                data = json.loads(body)
                print(f"  [captured] {url[:80]} ({len(body)} bytes)", file=sys.stderr)
            except Exception:
                pass

        tab.add_handler(cdp.network.ResponseReceived, on_response_received)
        tab.add_handler(cdp.network.LoadingFinished, on_loading_finished)

        await tab.get(actual_url)
        await tab.sleep(5)

        # Get page source to extract Next.js streaming data
        content = await tab.get_content()

        # ★ Don't call browser.stop() — cleanup messages pollute stdout
        # Let browser terminate naturally with the process

        return self._build_result(actual_url, content)

    def scrape(self, url: str) -> Dict:
        return uc.loop().run_until_complete(self._scrape_async(url))

    # ── Menu assembly ──────────────────────────────────────────────────────────

    def _build_result(self, source_url: str, html: str) -> Dict:
        categories = self._parse_menu_from_page(html)
        if not categories:
            raise RuntimeError("No menu data found in page source")

        total_items = sum(
            1
            for cat in categories
            for group in cat.get("groups", [])
            for item in group.get("items", [])
        )
        total_groups = sum(len(cat.get("groups", [])) for cat in categories)

        return {
            "restaurant": "China Star",
            "url": source_url,
            "total_categories": len(categories),
            "total_groups": total_groups,
            "total_items": total_items,
            "categories": categories,
        }

    def _extract_push_data(self, html: str) -> List[str]:
        """Extract data from self.__next_f.push([1,"DATA"]) calls.

        Handles escaped quotes (\\") inside the data by manual scanning
        instead of regex, which breaks on nested escapes.
        """
        results = []
        marker = 'self.__next_f.push([1,"'
        pos = 0
        while True:
            pos = html.find(marker, pos)
            if pos == -1:
                break

            data_start = pos + len(marker)

            # Scan forward, skipping escaped characters
            j = data_start
            while j < len(html) - 1:
                if html[j] == '\\' and j + 1 < len(html):
                    j += 2  # skip escaped char
                    continue
                if html[j] == '"' and j + 1 < len(html) and html[j + 1] == ']':
                    results.append(html[data_start:j])
                    j += 2
                    break
                j += 1

            pos = data_start
        return results

    def _decode_chunk(self, chunk: str) -> str:
        """Decode escaped quotes to produce valid JSON.

        The raw chunk uses \\" for quotes. We replace them with "
        to get parseable JSON. Chinese characters are already literal
        UTF-8 in the chunk, so they are preserved.
        """
        return chunk.replace('\\"', '"')

    def _parse_menu_from_page(self, html: str) -> List[Dict]:
        """Extract menu categories from Next.js __next_f streaming chunks."""
        chunks = self._extract_push_data(html)

        for chunk in chunks:
            if 'menuCatId' not in chunk and 'menuCategories' not in chunk:
                continue

            # Decode escaped quotes to get JSON-like string
            decoded = self._decode_chunk(chunk)

            # Find the menuCategories array directly (not the full JSON object)
            mc_pos = decoded.find('"menuCategories"')
            if mc_pos < 0:
                continue

            # Find the opening bracket after "menuCategories":
            arr_start = decoded.find('[', mc_pos)
            if arr_start < 0:
                continue

            # Find the matching closing bracket for the menuCategories array
            bracket_count = 0
            arr_end = 0
            for j in range(arr_start, len(decoded)):
                if decoded[j] == '[':
                    bracket_count += 1
                elif decoded[j] == ']':
                    bracket_count -= 1
                    if bracket_count == 0:
                        arr_end = j
                        break

            # Extract and parse just the menuCategories array
            arr_str = decoded[arr_start:arr_end + 1]

            try:
                categories = json.loads(arr_str)
                if categories:
                    return self._format_menu(categories)
            except json.JSONDecodeError:
                continue

        return []

    def _format_menu(self, categories: list) -> List[Dict]:
        """Format raw menu data into clean structured output."""
        result = []
        for cat in categories:
            category = {
                "name": cat.get("menuCatName", ""),
                "description": cat.get("menuCatDesc", ""),
                "groups": []
            }
            for group in cat.get("menuGroups", []):
                group_data = {
                    "name": group.get("menuGroupName", ""),
                    "description": group.get("menuGroupDesc", ""),
                    "items": []
                }
                for item in group.get("menuItems", []):
                    item_data = {
                        "name": item.get("menuItemName", ""),
                        "price": item.get("menuItemPrice", ""),
                    }
                    desc = item.get("menuItemDesc", "")
                    if desc:
                        item_data["description"] = desc
                    group_data["items"].append(item_data)
                category["groups"].append(group_data)
            result.append(category)
        return result


# ─── Output formatters ────────────────────────────────────────────────────────

def format_text(data: Dict) -> str:
    lines = [
        f"Restaurant : {data['restaurant']}",
        f"URL        : {data['url']}",
        f"Categories : {data['total_categories']}",
        f"Groups     : {data['total_groups']}",
        f"Total items: {data['total_items']}",
        "",
    ]
    for cat in data["categories"]:
        lines.append("=" * 60)
        lines.append(f"  {cat['name']}")
        lines.append("=" * 60)
        for group in cat.get("groups", []):
            lines.append(f"\n  -- {group['name']} ({len(group['items'])} items)")
            for item in group.get("items", []):
                price = item.get("price") or "N/A"
                lines.append(f"    {item['name']:<55} ${price}")
                if item.get("description"):
                    lines.append(f"      {item['description']}")
        lines.append("")
    return "\n".join(lines)


def format_markdown(data: Dict) -> str:
    lines = [
        f"# {data['restaurant']}",
        "",
        f"**{data['total_categories']} categories · {data['total_groups']} groups · {data['total_items']} items**",
        "",
    ]
    for cat in data["categories"]:
        lines.append(f"## {cat['name']}")
        lines.append("")
        for group in cat.get("groups", []):
            lines.append(f"### {group['name']}")
            lines.append("")
            for item in group.get("items", []):
                price = item.get("price") or "N/A"
                lines.append(f"- **{item['name']}** — ${price}")
                if item.get("description"):
                    lines.append(f"  > {item['description']}")
            lines.append("")
    return "\n".join(lines)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="China Star Menu Crawler — nodriver + Next.js streaming data extraction"
    )
    parser.add_argument("--url", required=True, help="China Star restaurant URL")
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
        help="Proxy address, e.g. http://127.0.0.1:7890 or socks5://127.0.0.1:1080",
    )
    args = parser.parse_args()

    print(f"Scraping: {args.url}", file=sys.stderr)
    scraper = ChinaStarScraper(headless=not args.visible, proxy=args.proxy)

    try:
        data = scraper.scrape(args.url)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Done: {data['total_categories']} categories, {data['total_groups']} groups, {data['total_items']} items", file=sys.stderr)

    if args.output == "json":
        print(json.dumps(data, indent=2, ensure_ascii=False))
    elif args.output == "text":
        print(format_text(data))
    elif args.output == "markdown":
        print(format_markdown(data))

    # ★ CRITICAL: flush stdout first, then redirect fd 1 to suppress nodriver cleanup messages
    # browser.stop() and process exit print "successfully removed temp profile" to stdout
    # Without this, JSON output gets polluted and downstream json.load() fails
    sys.stdout.flush()
    _devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(_devnull, 1)
    os.close(_devnull)


if __name__ == "__main__":
    main()
