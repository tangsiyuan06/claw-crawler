#!/usr/bin/env python3
"""
Grubhub Restaurant Menu Crawler
Intercepts Grubhub's internal API to extract full menu data:
sections, items, prices, descriptions, and images.

Usage:
    python3 grubhub_menu.py --url "https://www.grubhub.com/restaurant/.../ID" [--output json|text|markdown]
    python3 grubhub_menu.py --url "..." --output markdown > menu.md
"""

import argparse
import json
import re
import sys
import time
from typing import Dict, List, Optional
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

try:
    from playwright.sync_api import sync_playwright, Page
except ImportError as e:
    print(f"Error: Missing dependencies: {e}", file=sys.stderr)
    print("Install with: pip install playwright && playwright install chromium", file=sys.stderr)
    sys.exit(1)


# ─── API interception ─────────────────────────────────────────────────────────

class GrubhubMenuScraper:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self._nonvolatile: Optional[Dict] = None   # restaurant info + category list
        self._feed_by_category: Dict[str, Dict] = {}  # category_id → feed data

    def _on_response(self, response):
        url = response.url
        try:
            if "restaurant_gateway/info/nonvolatile" in url:
                self._nonvolatile = response.json()
            elif "restaurant_gateway/feed" in url:
                data = response.json()
                # Extract category id from URL path: /feed/RESTAURANT_ID/CATEGORY_ID?...
                path_parts = urlparse(url).path.rstrip("/").split("/")
                category_id = path_parts[-1]  # e.g. "274861897577" or "None"
                task = parse_qs(urlparse(url).query).get("task", [""])[0]
                key = f"{task}:{category_id}"
                self._feed_by_category[key] = data
        except Exception:
            pass

    def scrape(self, url: str) -> Dict:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=["--no-sandbox", "--disable-setuid-sandbox",
                      "--disable-dev-shm-usage", "--disable-gpu"],
            )
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                bypass_csp=True,
            )
            page = context.new_page()
            page.on("response", self._on_response)

            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(6000)

            # Click each nav category to trigger lazy-loaded feed API calls
            nav_items = page.query_selector_all('[data-testid^="category_"]')
            for nav in nav_items:
                try:
                    nav.click()
                    page.wait_for_timeout(500)
                except Exception:
                    pass

            page.wait_for_timeout(2000)
            browser.close()

        return self._build_menu(url)

    def _build_menu(self, source_url: str) -> Dict:
        if not self._nonvolatile:
            raise RuntimeError("No restaurant data captured — page may not have loaded correctly")

        obj = self._nonvolatile.get("object", {})
        enhanced_feed = obj.get("data", {}).get("enhanced_feed", [])

        # Build ordered category list from enhanced_feed (skip non-menu entries)
        categories = [
            entry for entry in enhanced_feed
            if entry.get("data_type") == "MENU_ITEM"
        ]

        # Restaurant name from enhanced_feed metadata or fallback
        restaurant_name = ""
        for entry in enhanced_feed:
            if entry.get("feed_type") == "POPULAR_ITEMS":
                # The restaurant name isn't here — find it from nonvolatile top-level
                break
        # Try content field
        for item in obj.get("data", {}).get("content", []):
            if item.get("entity", {}).get("name"):
                restaurant_name = item["entity"]["name"]
                break

        sections: Dict[str, List[Dict]] = {}

        for cat in categories:
            cat_name = cat.get("name", "Unknown")
            feed_type = cat.get("feed_type", "CATEGORY")
            # Determine the API key used to store this category's feed
            cat_id = self._get_category_id(cat)
            key = f"{feed_type}:{cat_id}"
            feed = self._feed_by_category.get(key)
            if not feed:
                # Try fallback: CATEGORY task with this id
                key_fallback = f"CATEGORY:{cat_id}"
                feed = self._feed_by_category.get(key_fallback)

            items: List[Dict] = []
            if feed:
                content = feed.get("object", {}).get("data", {}).get("content", [])
                for entry in content:
                    entity = entry.get("entity", {})
                    item = self._parse_item(entity)
                    if item:
                        items.append(item)

            sections[cat_name] = items

        total_items = sum(len(v) for v in sections.values())
        return {
            "restaurant": restaurant_name,
            "url": source_url,
            "total_sections": len(sections),
            "total_items": total_items,
            "sections": sections,
        }

    def _get_category_id(self, cat_entry: Dict) -> str:
        """Extract category ID from the enhanced_feed entry's request parameters."""
        params = cat_entry.get("request", {}).get("parameters", [])
        for p in params:
            if p.get("key") in ("categoryId", "category_id", "id"):
                return str(p.get("value", "None"))
        # Fallback: use the entry id
        return str(cat_entry.get("id", "None"))

    def _parse_item(self, entity: Dict) -> Optional[Dict]:
        name = entity.get("item_name", "").strip()
        if not name:
            return None

        # Price: prefer delivery price styled text
        price = None
        price_data = entity.get("item_price", {})
        for channel in ("delivery", "pickup"):
            styled = price_data.get(channel, {}).get("styled_text", {})
            if styled.get("text"):
                price = styled["text"]
                break

        description = entity.get("item_description", "").strip() or None

        # Image URL
        image_url = None
        media = entity.get("media_image", {})
        if media.get("base_url") and media.get("public_id"):
            fmt = media.get("format", "jpg")
            image_url = (
                f"{media['base_url']}d_search:browse-images:default.jpg/"
                f"w_400,q_auto:low,fl_lossy,c_fill,f_auto/"
                f"{media['public_id']}.{fmt}"
            )

        item: Dict = {"name": name, "price": price}
        if description:
            item["description"] = description
        if image_url:
            item["image"] = image_url

        features = entity.get("features_v2", {})
        tags = [k.lower() for k, v in features.items() if v.get("enabled")]
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
        lines.append(f"{'=' * 60}")
        lines.append(f"  {section}  ({len(items)} items)")
        lines.append(f"{'=' * 60}")
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
        f"",
        f"**{data['total_sections']} sections · {data['total_items']} items**",
        f"",
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
    parser = argparse.ArgumentParser(description="Grubhub Menu Crawler — intercepts API for full menu data")
    parser.add_argument("--url", required=True, help="Grubhub restaurant page URL")
    parser.add_argument("--output", choices=["json", "text", "markdown"], default="json",
                        help="Output format (default: json)")
    parser.add_argument("--visible", action="store_true", help="Run browser in visible mode (for debugging)")
    args = parser.parse_args()

    print(f"Scraping: {args.url}", file=sys.stderr)
    scraper = GrubhubMenuScraper(headless=not args.visible)
    data = scraper.scrape(args.url)

    print(
        f"Done: {data['total_sections']} sections, {data['total_items']} items",
        file=sys.stderr,
    )

    if args.output == "json":
        print(json.dumps(data, indent=2, ensure_ascii=False))
    elif args.output == "text":
        print(format_text(data))
    elif args.output == "markdown":
        print(format_markdown(data))


if __name__ == "__main__":
    main()
