#!/usr/bin/env python3
"""
Aldo's Pizzeria Menu Scraper (nodriver edition)

Extracts menu data from aldospizzeria.com by parsing HTML DOM.
The site is a WordPress + Elementor website with SPL (Single Product List) plugin
rendering the menu server-side.

Usage:
    python3 aldospizzeria_menu.py --url "https://aldospizzeria.com/menu/" --output json
    python3 aldospizzeria_menu.py --url "..." --output markdown
    python3 aldospizzeria_menu.py --url "..." --output text
    python3 aldospizzeria_menu.py --url "..." --visible
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
    "name": "aldospizzeria_menu",
    "domains": ["aldospizzeria.com"],
    "data": "餐厅菜单：分类、菜品、价格、描述",
    "framework": "nodriver",
    "url_pattern": "https://aldospizzeria.com/menu/",
    "url_routes": {
        "https://aldospizzeria.com/": "https://aldospizzeria.com/menu/",
    },
    "output_formats": ["json", "text", "markdown"],
    "example": 'python3 aldospizzeria_menu.py --url "https://aldospizzeria.com/" --output json',
}


class AldosPizzeriaScraper:
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

        # Check if menu data exists on current page; if not, navigate to /menu/
        has_menu = await tab.evaluate("document.querySelectorAll('.spl-item-root').length > 0")
        if not has_menu:
            menus_url = "https://aldospizzeria.com/menu/"
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
            const results = [];
            
            // Get all category tabs
            const tabContainer = document.querySelector('.df-spl-style7_cat_tab-container.tabs_spl ul');
            if (!tabContainer) {
                return JSON.stringify({ title: document.title, url: window.location.href, categories: [] });
            }
            
            const tabs = tabContainer.querySelectorAll('li');
            
            tabs.forEach((tab) => {
                const link = tab.querySelector('a');
                if (!link) return;
                
                const categoryName = link.innerText.trim();
                const dataHref = link.getAttribute('data-href');
                
                // Find the corresponding tab content
                let tabContent = null;
                if (dataHref) {
                    const tabId = dataHref.replace('#', '');
                    tabContent = document.getElementById(tabId);
                }
                
                if (!tabContent) return;
                
                const items = [];
                const menuItems = tabContent.querySelectorAll('.spl-item-root');
                
                menuItems.forEach((item) => {
                    const nameEl = item.querySelector('.name.a-tag span');
                    const priceEl = item.querySelector('.spl-price.a-tag span');
                    const descEl = item.querySelector('.desc.a-tag span');
                    
                    const name = nameEl ? nameEl.innerText.trim() : '';
                    const price = priceEl ? priceEl.innerText.trim() : '';
                    const description = descEl ? descEl.innerText.trim() : '';
                    
                    if (name) {
                        items.push({
                            name: name,
                            price: price,
                            description: description
                        });
                    }
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
            return {"url": url, "error": "No menu data found", "categories": []}

        result = json.loads(menu_data)
        return result

    def scrape(self, url: str) -> Dict:
        return uc.loop().run_until_complete(self._scrape_async(url))


def format_text(data: Dict) -> str:
    lines = []
    lines.append(f'Restaurant: {data.get("title", "Aldo\'s Pizzeria")}')
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
        lines.append("")

    return "\n".join(lines)


def format_markdown(data: Dict) -> str:
    lines = []
    lines.append(f'# {data.get("title", "Aldo\'s Pizzeria Menu")}')
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

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="Target menu page URL")
    parser.add_argument("--output", choices=["json", "text", "markdown"], default="json")
    parser.add_argument("--visible", action="store_true", help="Show browser window (debug)")
    args = parser.parse_args()

    scraper = AldosPizzeriaScraper(headless=not args.visible)
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
