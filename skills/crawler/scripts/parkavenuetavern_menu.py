#!/usr/bin/env python3
"""
Park Avenue Tavern Menu Scraper (nodriver edition)

Extracts menu data from parkavenuetavern.com by parsing HTML DOM.
The site is a WordPress + Enfold theme with SSR-rendered tabbed menu sections.

Usage:
    python3 parkavenuetavern_menu.py --url "https://parkavenuetavern.com/nyc/menu/" --output json
    python3 parkavenuetavern_menu.py --url "..." --output markdown
    python3 parkavenuetavern_menu.py --url "..." --output text
    python3 parkavenuetavern_menu.py --url "..." --visible
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
    "name": "parkavenuetavern_menu",
    "domains": ["parkavenuetavern.com"],
    "data": "餐厅菜单：6大菜单区域（All Day/Brunch/Beverages/Desserts/Kids/Late Night），分类、菜品、价格、描述",
    "framework": "nodriver",
    "url_pattern": "https://parkavenuetavern.com/nyc/menu/",
    "url_routes": {
        "https://parkavenuetavern.com/": "https://parkavenuetavern.com/nyc/menu/",
    },
    "output_formats": ["json", "text", "markdown"],
    "example": 'python3 parkavenuetavern_menu.py --url "https://parkavenuetavern.com/nyc/menu/" --output json',
}


class ParkAvenueTavernScraper:
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

        # URL mapping: homepage -> actual menu page
        actual_url = CRAWLER_META.get("url_routes", {}).get(url, url)
        if actual_url != url:
            print(f"  [route] {url} -> {actual_url}", file=sys.stderr)

        await tab.get(actual_url)

        try:
            await tab.select("body", timeout=15)
        except Exception:
            pass
        await tab.wait(3)

        # Extract all menu data via DOM parsing in browser
        menu_data = await tab.evaluate("""
        (() => {
            const tabs = document.querySelectorAll('.av-layout-tab');
            const result = { restaurant: 'Park Avenue Tavern', url: window.location.href, sections: [] };
            
            tabs.forEach((tab) => {
                const tabId = tab.getAttribute('data-tab-section-id') || '';
                const tabName = tabId ? tabId.replace(/-/g, ' ').toUpperCase() : 'MENU';
                
                const section = { name: tabName, subsections: [] };
                const itemsBySubsection = {};
                let currentSubsection = null;
                
                const headings = tab.querySelectorAll('h2.av-special-heading-tag, h3.av-special-heading-tag, h6.av-special-heading-tag');
                headings.forEach((el) => {
                    const text = el.innerText.trim();
                    if (!text) return;
                    
                    const priceSpan = el.querySelector('span.menu-price');
                    
                    // Section/subsection headings (h2, h3 without price)
                    if ((el.tagName === 'H2' || el.tagName === 'H3') && !priceSpan) {
                        currentSubsection = text;
                        if (!itemsBySubsection[currentSubsection]) {
                            itemsBySubsection[currentSubsection] = [];
                        }
                        return;
                    }
                    
                    // Menu items (h6 with price)
                    if (el.tagName === 'H6' && priceSpan) {
                        const price = priceSpan.innerText.trim();
                        // Replace special_amp spans inline to avoid line breaks
                        const clone = el.cloneNode(true);
                        const ampSpans = clone.querySelectorAll('.special_amp');
                        ampSpans.forEach(s => {
                            const txt = document.createTextNode(s.innerText);
                            s.parentNode.replaceChild(txt, s);
                        });
                        const fullText = clone.innerText.trim();
                        const itemName = fullText.replace(price, '').trim();
                        
                        // Get description from sibling subheading
                        let desc = '';
                        const parent = el.closest('.av-special-heading') || el.parentElement;
                        if (parent) {
                            const subheading = parent.querySelector('.av-subheading');
                            if (subheading) {
                                desc = subheading.innerText.replace(/\\s+/g, ' ').trim();
                            }
                        }
                        
                        const item = { name: itemName, price: price };
                        if (desc) item.description = desc;
                        
                        if (currentSubsection) {
                            itemsBySubsection[currentSubsection].push(item);
                        }
                    }
                });
                
                for (const [subName, items] of Object.entries(itemsBySubsection)) {
                    if (items.length > 0) {
                        section.subsections.push({ name: subName, items: items });
                    }
                }
                
                if (section.subsections.length > 0) {
                    result.sections.push(section);
                }
            });
            
            return JSON.stringify(result);
        })()
        """)

        if not menu_data:
            return {"url": actual_url, "error": "No menu data found", "sections": []}

        result = json.loads(menu_data)
        return result

    def scrape(self, url: str) -> Dict:
        return uc.loop().run_until_complete(self._scrape_async(url))


def format_text(data: Dict) -> str:
    lines = []
    lines.append(f"Restaurant: {data.get('restaurant', 'Park Avenue Tavern')}")
    lines.append(f"URL: {data.get('url', '')}")
    lines.append("")

    for section in data.get("sections", []):
        lines.append(f"=== {section['name']} ===")
        for sub in section.get("subsections", []):
            lines.append(f"\n--- {sub['name']} ---")
            for item in sub.get("items", []):
                line = f"  {item['name']}  ${item['price']}"
                lines.append(line)
                if item.get("description"):
                    lines.append(f"    {item['description']}")
        lines.append("")

    return "\n".join(lines)


def format_markdown(data: Dict) -> str:
    lines = []
    lines.append(f"# {data.get('restaurant', 'Park Avenue Tavern')} Menu\n")

    for section in data.get("sections", []):
        lines.append(f"## {section['name']}\n")
        for sub in section.get("subsections", []):
            lines.append(f"### {sub['name']}\n")
            lines.append("| Item | Price | Description |")
            lines.append("|------|-------|-------------|")
            for item in sub.get("items", []):
                name = item["name"]
                price = f"${item['price']}"
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

    scraper = ParkAvenueTavernScraper(headless=not args.visible)
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
