#!/usr/bin/env python3
"""
Napoleon's Steak & Seafood House Menu Scraper (nodriver edition)
Site: https://napoleons.ca/menu/
Tech: WordPress + Elementor (SSR) — DOM extraction via nodriver

Usage:
    python3 napoleons_menu.py --url "https://napoleons.ca/menu/" --output json
    python3 napoleons_menu.py --url "..." --output markdown
    python3 napoleons_menu.py --url "..." --visible
"""
import argparse
import json
import os
import re
import sys
from typing import Dict, List, Optional

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
        sys.exit(1)

# ★ 必须包含：crawler.py 注册表通过此字段发现脚本能力
CRAWLER_META = {
    "name": "napoleons_menu",
    "domains": ["napoleons.ca"],
    "data": "餐厅完整菜单：分类、菜品名称、价格、描述 + 餐厅信息",
    "framework": "nodriver",
    "url_pattern": "https://napoleons.ca/menu/",
    "url_routes": {
        "https://napoleons.ca/": "https://napoleons.ca/menu/",
    },
    "output_formats": ["json", "text", "markdown"],
    "example": 'python3 napoleons_menu.py --url "https://napoleons.ca/menu/" --output json',
}


class NapoleonsMenuScraper:
    def __init__(self, headless: bool = False):
        # headless=False: better anti-bot evasion; headless=True for servers
        self.headless = headless

    async def _scrape_async(self, url: str) -> Dict:
        config = uc.Config(
            headless=self.headless,
            browser_args=["--no-sandbox", "--disable-dev-shm-usage", "--window-size=1920,1080"],
        )
        browser = await uc.start(config=config)
        tab = browser.main_tab

        # URL 映射：首页 → 菜单页
        actual_url = CRAWLER_META.get("url_routes", {}).get(url, url)
        if actual_url != url:
            print(f"  [route] {url} -> {actual_url}", file=sys.stderr)

        await tab.get(actual_url)
        # Wait for Elementor content to render
        await tab.select("div.elementor-price-list", timeout=15)
        await tab.wait(2)

        # Extract all menu data via tab.evaluate()
        menu_data = await tab.evaluate("""
        (function() {
            var result = {
                restaurant: "",
                url: window.location.href,
                categories: []
            };
            
            // Try to extract restaurant name
            var titleEl = document.querySelector('h1, .site-title, .elementor-heading-title');
            if (titleEl) result.restaurant = titleEl.innerText.trim();
            
            // Find all section containers with h2 headings
            var sections = document.querySelectorAll('div.e-con.e-parent');
            sections.forEach(function(section) {
                var h2 = section.querySelector('h2.elementor-heading-title');
                if (!h2) return;
                
                var catName = h2.innerText.trim();
                if (catName.toLowerCase() === 'reservation') return;
                
                // Category description
                var descEl = section.querySelector('.elementor-widget-text-editor p');
                var catDesc = descEl ? descEl.innerText.trim() : null;
                
                // Extract price list items
                var items = [];
                var priceLists = section.querySelectorAll('ul.elementor-price-list');
                priceLists.forEach(function(pl) {
                    var listItems = pl.querySelectorAll('li');
                    listItems.forEach(function(li) {
                        var titleEl = li.querySelector('.elementor-price-list-title');
                        var descItemEl = li.querySelector('.elementor-price-list-description');
                        var priceEl = li.querySelector('.elementor-price-list-price');
                        
                        if (!titleEl) return;
                        
                        var name = titleEl.innerText.trim();
                        var itemDesc = descItemEl ? descItemEl.innerText.trim() : null;
                        var price = priceEl ? priceEl.innerText.trim() : null;
                        
                        var item = { name: name };
                        if (itemDesc) item.description = itemDesc;
                        if (price) item.price = price;
                        items.push(item);
                    });
                });
                
                if (items.length > 0) {
                    var cat = { name: catName, items: items };
                    if (catDesc) cat.description = catDesc;
                    result.categories.push(cat);
                }
            });
            
            return JSON.stringify(result);
        })()
        """)

        # 不调用 browser.stop() — cleanup 消息会污染 stdout
        data = json.loads(menu_data)
        return self._build_result(actual_url, data)

    def _build_result(self, source_url: str, raw: Dict) -> Dict:
        """Assemble standardized menu result."""
        total_items = sum(len(c.get("items", [])) for c in raw.get("categories", []))
        return {
            "restaurant": raw.get("restaurant", "Napoleon's Steak & Seafood House"),
            "url": source_url,
            "total_sections": len(raw.get("categories", [])),
            "total_items": total_items,
            "sections": {
                cat["name"]: cat.get("items", [])
                for cat in raw.get("categories", [])
            },
        }

    def scrape(self, url: str) -> Dict:
        return uc.loop().run_until_complete(self._scrape_async(url))


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
            lines.append("  (no items)")
        for item in items:
            price = item.get("price") or "N/A"
            lines.append(f"  {item['name']:<45} {price}")
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
            lines.append("_no items_")
        for item in items:
            price = item.get("price") or "N/A"
            lines.append(f"- **{item['name']}** — {price}")
            if item.get("description"):
                lines.append(f"  > {item['description']}")
        lines.append("")
    return "\n".join(lines)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Napoleon's Menu Crawler — nodriver + DOM extraction"
    )
    parser.add_argument("--url", required=True, help="Menu page URL")
    parser.add_argument(
        "--output", choices=["json", "text", "markdown"], default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "--visible", action="store_true",
        help="Run browser in visible mode (debug)",
    )
    args = parser.parse_args()

    print(f"Scraping: {args.url}", file=sys.stderr)
    scraper = NapoleonsMenuScraper(headless=not args.visible)

    try:
        data = scraper.scrape(args.url)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Done: {data['total_sections']} sections, {data['total_items']} items", file=sys.stderr)

    if args.output == "json":
        print(json.dumps(data, indent=2, ensure_ascii=False))
    elif args.output == "text":
        print(format_text(data))
    elif args.output == "markdown":
        print(format_markdown(data))

    # ★ CRITICAL: flush stdout first, then redirect fd 1 to suppress nodriver cleanup messages
    sys.stdout.flush()
    _devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(_devnull, 1)
    os.close(_devnull)


if __name__ == "__main__":
    main()
