#!/usr/bin/env python3
"""
Skinny's Cantina Menu Scraper (nodriver edition)

Extracts menu data from skinnyscantina.com by parsing HTML DOM.
The site is a traditional HTML restaurant website with menus rendered server-side.

Usage:
    python3 skinnyscantina_menu.py --url "https://www.skinnyscantina.com/menus/" --output json
    python3 skinnyscantina_menu.py --url "..." --output markdown
    python3 skinnyscantina_menu.py --url "..." --output text
    python3 skinnyscantina_menu.py --url "..." --visible
"""
import argparse
import asyncio
import json
import os
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
    "name": "skinnyscantina_menu",
    "domains": ["skinnyscantina.com"],
    "data": "餐厅菜单：分类、菜品、价格、描述、附加项",
    "framework": "nodriver",
    "url_pattern": "https://www.skinnyscantina.com/menus/",
    "url_routes": {
        "https://www.skinnyscantina.com/": "https://www.skinnyscantina.com/menus/",
    },
    "output_formats": ["json", "text", "markdown"],
    "example": 'python3 skinnyscantina_menu.py --url "https://www.skinnyscantina.com/" --output json',
}


class SkinnyCantinaScraper:
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

        # Check if menu data exists on current page; if not, navigate to /menus/
        has_menu = await tab.evaluate("document.querySelectorAll('.menu-section').length > 0")
        if not has_menu:
            menus_url = "https://www.skinnyscantina.com/menus/"
            print(f"  [info] No menu found on {url}, navigating to {menus_url}", file=sys.stderr)
            await tab.get(menus_url)
            try:
                await tab.select("body", timeout=15)
            except Exception:
                pass
            await tab.wait(3)

        # Extract all menu data via DOM
        menu_data = await tab.evaluate("""
        (() => {
            const sections = document.querySelectorAll('.menu-section');
            const results = [];
            sections.forEach((sec) => {
                const headerEl = sec.querySelector('.menu-section__header h2');
                if (!headerEl) return;
                
                const categoryName = headerEl.innerText.trim();
                const items = [];
                
                const menuItems = sec.querySelectorAll('.menu-item');
                menuItems.forEach((item) => {
                    const nameEl = item.querySelector('.menu-item__heading--name');
                    const descEl = item.querySelector('.menu-item__details--description');
                    const priceEl = item.querySelector('.menu-item__details--price');
                    
                    // Price: combine currency span + amount
                    let price = '';
                    if (priceEl) {
                        const currencyEl = priceEl.querySelector('.menu-item__currency');
                        const currency = currencyEl ? currencyEl.innerText.trim() : '$';
                        // Get text content, remove whitespace
                        const priceText = priceEl.innerText.replace(/\\s+/g, '').trim();
                        if (priceText) {
                            price = priceText;
                        }
                    }
                    
                    // Addons
                    const addons = [];
                    const addonEls = item.querySelectorAll('.menu-item__details--addon');
                    addonEls.forEach((addon) => {
                        // Clean up addon text: remove extra whitespace and newlines
                        const text = addon.innerText.replace(/\\s+/g, ' ').trim();
                        if (text) {
                            addons.push(text);
                        }
                    });
                    
                    items.push({
                        name: nameEl ? nameEl.innerText.trim() : '',
                        description: descEl ? descEl.innerText.trim() : '',
                        price: price,
                        addons: addons
                    });
                });
                
                results.push({
                    name: categoryName,
                    items: items
                });
            });
            return JSON.stringify({
                title: document.title,
                url: window.location.href,
                categories: results
            });
        })()
        """)

        if not menu_data:
            browser.stop()
            return {"url": url, "error": "No menu data found", "categories": []}

        result = json.loads(menu_data)

        # Don't call browser.stop() — it prints "successfully removed temp profile"
        # to stdout which pollutes JSON output. Browser dies naturally with process.

        return result

    def scrape(self, url: str) -> Dict:
        return uc.loop().run_until_complete(self._scrape_async(url))


def format_text(data: Dict) -> str:
    lines = []
    lines.append(f"Restaurant: {data.get('title', 'Skinny\'s Cantina')}")
    lines.append(f"URL: {data.get('url', '')}")
    lines.append("")

    for cat in data.get("categories", []):
        lines.append(f"## {cat['name']}")
        for item in cat.get("items", []):
            line = f"  - {item['name']}"
            if item.get("price"):
                line += f"  {item['price']}"
            lines.append(line)
            if item.get("description"):
                lines.append(f"    {item['description']}")
            for addon in item.get("addons", []):
                lines.append(f"    + {addon}")
        lines.append("")

    return "\n".join(lines)


def format_markdown(data: Dict) -> str:
    lines = []
    lines.append(f"# {data.get('title', 'Skinny\'s Cantina Menu')}")
    lines.append("")

    for cat in data.get("categories", []):
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

        # Add addons info
        for item in cat.get("items", []):
            if item.get("addons"):
                lines.append(f"**{item['name']}** addons:")
                for addon in item["addons"]:
                    lines.append(f"- {addon}")
                lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="Target menu page URL")
    parser.add_argument("--output", choices=["json", "text", "markdown"], default="json")
    parser.add_argument("--visible", action="store_true", help="Show browser window (debug)")
    args = parser.parse_args()

    scraper = SkinnyCantinaScraper(headless=not args.visible)
    data = scraper.scrape(args.url)

    if args.output == "json":
        print(json.dumps(data, indent=2, ensure_ascii=False))
    elif args.output == "text":
        print(format_text(data))
    elif args.output == "markdown":
        print(format_markdown(data))

    # Flush stdout, then suppress nodriver's "successfully removed temp profile"
    # message that prints to stdout during process cleanup
    sys.stdout.flush()
    _devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(_devnull, 1)
    os.close(_devnull)


if __name__ == "__main__":
    main()
