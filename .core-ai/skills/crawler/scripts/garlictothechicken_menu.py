#!/usr/bin/env python3
"""
Garlic To the Chicken Menu Scraper (nodriver edition)

Extracts menu data from garlictothechicken.com by parsing __NEXT_DATA__ SSR data.
The site is a Next.js application that embeds menu JSON directly in the page HTML.

Usage:
    python3 garlictothechicken_menu.py --url "https://garlictothechicken.com/menu/42836629" --output json
    python3 garlictothechicken_menu.py --url "https://garlictothechicken.com/menu/42836629" --output markdown
    python3 garlictothechicken_menu.py --url "https://garlictothechicken.com/menu/42836629" --output text
    python3 garlictothechicken_menu.py --url "..." --visible
"""
import argparse
import asyncio
import json
import sys
from typing import Dict, List, Optional

try:
    import nodriver as uc
    from nodriver import cdp
except (ModuleNotFoundError, ImportError):
    import os
    _root = os.path.join(os.path.dirname(__file__), "..", "..", "..", "nodriver-main")
    sys.path.insert(0, os.path.abspath(_root))
    import nodriver as uc
    from nodriver import cdp

CRAWLER_META = {
    "name": "garlictothechicken_menu",
    "domains": ["garlictothechicken.com"],
    "data": "餐厅菜单：分类、菜品、价格、描述、选项",
    "framework": "nodriver",
    "url_pattern": "https://garlictothechicken.com/menu/{id}",
    "output_formats": ["json", "text", "markdown"],
    "example": 'python3 garlictothechicken_menu.py --url "https://garlictothechicken.com/menu/42836629" --output json',
}


class GarlicToTheChickenScraper:
    def __init__(self, headless: bool = False):
        self.headless = headless

    async def _scrape_async(self, url: str) -> Dict:
        config = uc.Config(
            headless=self.headless,
            browser_args=["--no-sandbox", "--disable-dev-shm-usage", "--window-size=1920,1080"],
        )
        browser = await uc.start(config=config)
        tab = browser.main_tab

        await tab.send(cdp.network.enable())
        await tab.get(url)

        try:
            await tab.select("body", timeout=15)
        except Exception:
            pass
        await tab.wait(3)

        menu_data = await tab.evaluate("""
        (() => {
            const d = window.__NEXT_DATA__;
            if (!d) return null;
            const menu = d.props.pageProps.menu;
            if (typeof menu === 'string') return menu;
            return JSON.stringify(menu);
        })()
        """)

        browser.stop()

        if not menu_data:
            return {"url": url, "error": "No __NEXT_DATA__ found", "items": []}

        raw = json.loads(menu_data)
        return self._build_result(url, raw)

    def _build_result(self, source_url: str, raw: Dict) -> Dict:
        location = raw.get("location", {})
        collections = raw.get("menu_collections", [])

        result = {
            "url": source_url,
            "restaurant": location.get("name", ""),
            "phone": location.get("phone", ""),
            "address": self._format_address(location),
            "collections": [],
        }

        for col in collections:
            collection = {
                "name": col.get("name", ""),
                "description": col.get("description", ""),
                "categories": [],
            }

            for cat in col.get("menu_categories", []):
                category = {
                    "name": cat.get("name", ""),
                    "items": [],
                }

                for item in cat.get("menu_items", []):
                    menu_item = self._parse_item(item)
                    category["items"].append(menu_item)

                collection["categories"].append(category)

            result["collections"].append(collection)

        return result

    def _parse_item(self, item: Dict) -> Dict:
        unit_price = item.get("unit_price", "")
        # Price is a string like "11.99" or "0.00"
        price = self._format_price(unit_price)

        # Get modifiers/options
        options = []
        for mod in item.get("menu_modifiers", []):
            mod_options = mod.get("menu_modifier_options", [])
            if mod_options:
                option_group = {
                    "name": mod.get("name", ""),
                    "required": mod.get("qty_min", 0) > 0 if mod.get("qty_min") is not None else None,
                    "options": [],
                }
                for opt in mod_options:
                    option_group["options"].append({
                        "name": opt.get("name", ""),
                        "price": self._format_price(opt.get("unit_price", "")),
                    })
                options.append(option_group)

        # Get variations (menu_item_advance)
        variations = []
        for adv in (item.get("menu_item_advance") or []):
            variations.append({
                "name": adv.get("name", ""),
                "price": self._format_price(adv.get("unit_price", "")),
            })

        return {
            "name": item.get("name", ""),
            "price": price,
            "description": item.get("description", "") or "",
            "image_url": item.get("image_url", "") or "",
            "popular": item.get("popular", False),
            "status": item.get("status", ""),
            "options": options,
            "variations": variations,
        }

    def _format_price(self, price) -> str:
        if price is None or price == "":
            return ""
        try:
            val = float(price)
            if val > 0:
                return f"${val:.2f}"
            return ""
        except (ValueError, TypeError):
            return str(price) if price else ""

    def _format_address(self, location: Dict) -> str:
        parts = []
        if location.get("address_line1"):
            parts.append(location["address_line1"])
        if location.get("city"):
            parts.append(location["city"])
        if location.get("state"):
            parts.append(location["state"])
        if location.get("zip"):
            parts.append(location["zip"])
        return ", ".join(parts) if parts else ""

    def scrape(self, url: str) -> Dict:
        return uc.loop().run_until_complete(self._scrape_async(url))


def format_text(data: Dict) -> str:
    lines = []
    lines.append(f"Restaurant: {data.get('restaurant', '')}")
    if data.get('phone'):
        lines.append(f"Phone: {data['phone']}")
    if data.get('address'):
        lines.append(f"Address: {data['address']}")
    lines.append("")

    for col in data.get("collections", []):
        if col.get("name"):
            lines.append(f"=== {col['name']} ===")
        for cat in col.get("categories", []):
            lines.append(f"\n## {cat['name']}")
            for item in cat.get("items", []):
                price = item.get("price", "")
                line = f"  - {item['name']}"
                if price:
                    line += f"  {price}"
                lines.append(line)
                if item.get("description"):
                    lines.append(f"    {item['description'][:80]}")
                for opt_group in item.get("options", []):
                    lines.append(f"    [{opt_group['name']}]")
                    for opt in opt_group.get("options", []):
                        opt_price = f" {opt['price']}" if opt['price'] else ""
                        lines.append(f"      - {opt['name']}{opt_price}")
                for var in item.get("variations", []):
                    var_price = f" {var['price']}" if var['price'] else ""
                    lines.append(f"    ~ {var['name']}{var_price}")
        lines.append("")

    return "\n".join(lines)


def format_markdown(data: Dict) -> str:
    lines = []
    lines.append(f"# {data.get('restaurant', 'Menu')}")
    if data.get('phone'):
        lines.append(f"**Phone:** {data['phone']}")
    if data.get('address'):
        lines.append(f"**Address:** {data['address']}")
    lines.append("")

    for col in data.get("collections", []):
        for cat in col.get("categories", []):
            lines.append(f"## {cat['name']}")
            lines.append("")
            lines.append("| Item | Price | Description |")
            lines.append("|------|-------|-------------|")
            for item in cat.get("items", []):
                name = item["name"]
                price = item.get("price", "")
                desc = item.get("description", "")
                lines.append(f"| {name} | {price} | {desc} |")
            lines.append("")

            # Add options/variants info
            for item in cat.get("items", []):
                if item.get("options") or item.get("variations"):
                    lines.append(f"**{item['name']}** options:")
                    for opt_group in item.get("options", []):
                        lines.append(f"- {opt_group['name']}: {', '.join(o['name'] + (' (' + o['price'] + ')' if o['price'] else '') for o in opt_group['options'])}")
                    for var in item.get("variations", []):
                        var_price = f" ({var['price']})" if var['price'] else ""
                        lines.append(f"- {var['name']}{var_price}")
                    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="Target menu page URL")
    parser.add_argument("--output", choices=["json", "text", "markdown"], default="json")
    parser.add_argument("--visible", action="store_true", help="Show browser window (debug)")
    args = parser.parse_args()

    scraper = GarlicToTheChickenScraper(headless=not args.visible)
    data = scraper.scrape(args.url)

    if args.output == "json":
        print(json.dumps(data, indent=2, ensure_ascii=False))
    elif args.output == "text":
        print(format_text(data))
    elif args.output == "markdown":
        print(format_markdown(data))


if __name__ == "__main__":
    main()
