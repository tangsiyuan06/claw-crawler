#!/usr/bin/env python3
"""
Morton's The Steakhouse Menu Scraper (BeautifulSoup edition)

Usage:
    python3 mortons_menu.py --url "https://mortons.com/location/mortons-the-steakhouse-new-york-ny-manhattan" --output json
    python3 mortons_menu.py --url "..." --output markdown
    python3 mortons_menu.py --url "..." --output text

Note: mortons.com is a BentoBox site — all menu data is server-side rendered in HTML.
No browser automation needed; requests + BeautifulSoup is the fastest approach.
"""
import argparse
import json
import re
import sys
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

CRAWLER_META = {
    "name": "mortons_menu",
    "domains": ["mortons.com"],
    "data": "餐厅菜单：分类、菜品、价格、描述、卡路里",
    "framework": "requests+bs4",
    "url_pattern": "https://mortons.com/location/{location-slug}",
    "output_formats": ["json", "text", "markdown"],
    "example": 'python3 mortons_menu.py --url "https://mortons.com/location/mortons-the-steakhouse-new-york-ny-manhattan" --output json',
}


class MortonsMenuScraper:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

    def scrape(self, url: str) -> Dict:
        """Fetch and parse menu from a Morton's location page."""
        resp = requests.get(url, headers=self.headers, timeout=30)
        resp.raise_for_status()
        return self._parse_html(resp.text, resp.url)

    def _parse_html(self, html: str, source_url: str) -> Dict:
        soup = BeautifulSoup(html, "html.parser")

        # Extract location name from h1
        h1 = soup.find("h1")
        location = h1.get_text(strip=True) if h1 else "Unknown"

        # Find the menus section
        menus_section = soup.find("section", id="menus")
        if not menus_section:
            return {"url": source_url, "location": location, "menus": []}

        result: Dict = {"url": source_url, "location": location, "menus": []}

        # Each tab panel is a <section class="tabs-panel"> or <section id="..."> inside tabs-content
        tabs_content = menus_section.find("div", class_="tabs-content")
        if not tabs_content:
            return result

        # Get tab labels from the nav
        tab_labels: Dict[str, str] = {}
        tabs_nav = menus_section.find("ul", class_="tabs-nav")
        if tabs_nav:
            for tab_link in tabs_nav.find_all("a", class_="btn-tabs"):
                panel_id = tab_link.get("href", "").lstrip("#")
                label = tab_link.get("aria-label", tab_link.get_text(strip=True))
                if panel_id:
                    tab_labels[panel_id] = label

        # Parse each tab panel
        for panel in tabs_content.find_all("section", class_="tabs-panel"):
            panel_id = panel.get("id", "")
            menu_name = tab_labels.get(panel_id, panel_id)

            menu: Dict = {
                "name": menu_name,
                "description": None,
                "sections": [],
            }

            # Extract menu description if present
            menu_desc = panel.find("div", class_="menu-description")
            if menu_desc:
                desc_text = menu_desc.get_text(strip=True)
                if desc_text:
                    menu["description"] = desc_text

            # Extract each menu section
            for section in panel.find_all("section", class_="menu-section"):
                # Check if this is a text-only section (no items)
                if "menu-section--text" in section.get("class", []):
                    text_content = section.get_text(strip=True)
                    if text_content:
                        menu["sections"].append({
                            "name": "Notes",
                            "subtitle": None,
                            "text_only": True,
                            "content": text_content,
                            "items": [],
                        })
                    continue

                header = section.find("div", class_="menu-section__header")
                section_name = ""
                section_subtitle = None
                if header:
                    h2 = header.find("h2")
                    section_name = h2.get_text(strip=True) if h2 else ""
                    # Get subtitle (text after h2, e.g. "(Choice Of)")
                    header_text = header.get_text(strip=True)
                    # Remove the h2 text to get the subtitle
                    if h2:
                        subtitle = header_text.replace(h2.get_text(strip=True), "").strip()
                        if subtitle and subtitle != section_name:
                            section_subtitle = subtitle

                items: List[Dict] = []
                for item_el in section.find_all("li", class_="menu-item"):
                    item = self._parse_menu_item(item_el)
                    if item:
                        items.append(item)

                if section_name or items:
                    menu["sections"].append({
                        "name": section_name,
                        "subtitle": section_subtitle,
                        "text_only": False,
                        "items": items,
                    })

            result["menus"].append(menu)

        return result

    def _parse_menu_item(self, item_el) -> Optional[Dict]:
        """Parse a single menu item element."""
        name_el = item_el.find("p", class_="menu-item__heading--name")
        if not name_el:
            return None

        name = name_el.get_text(strip=True)
        # Clean up whitespace in name (some have newlines)
        name = re.sub(r"\s+", " ", name).strip()

        # Description
        description = None
        desc_el = item_el.find("p", class_="menu-item__details--description")
        if desc_el:
            description = desc_el.get_text(strip=True)

        # Prices - can have multiple price elements
        prices: List[Dict[str, str]] = []
        for price_el in item_el.find_all("p", class_="menu-item__details--price"):
            price_text = self._extract_price(price_el)
            if price_text:
                prices.append(price_text)

        # Addons/modifiers (e.g., steak choices, size options)
        addons: List[Dict[str, str]] = []
        for addon_el in item_el.find_all("p", class_="menu-item__details--addon"):
            addon_text = addon_el.get_text(strip=True)
            if addon_text:
                # Split name and price if present
                addon_span = addon_el.find("span")
                addon_name = addon_text
                addon_price = None
                if addon_span:
                    addon_name = addon_el.contents[0].strip() if addon_el.contents else addon_text
                    addon_price = addon_span.get_text(strip=True)
                addons.append({"name": addon_name, "price": addon_price or None})

        # Calories
        calories = None
        cal_match = re.search(r"\((\d+)\s*cal\.\)", item_el.get_text())
        if cal_match:
            calories = int(cal_match.group(1))

        return {
            "name": name,
            "description": description,
            "prices": prices if prices else None,
            "addons": addons if addons else None,
            "calories": calories,
        }

    def _extract_price(self, price_el) -> Optional[Dict[str, str]]:
        """Extract price label and amount from a price element."""
        # Look for bold label (e.g., "Half", "Full", "Grand*", "Make it Loaded")
        label = None
        label_el = price_el.find("strong")
        if label_el:
            label_text = label_el.get_text(strip=True)
            # Check if this is just the currency symbol (skip it)
            if label_text and label_text not in ("$", ""):
                label = label_text

        # Find the price amount
        price_amount = None
        for strong in price_el.find_all("strong"):
            text = strong.get_text(strip=True)
            # Match patterns like "$85", "$12.99", "per MP", "(410 cal.)"
            if text.startswith("$") or text == "per MP":
                price_amount = text
                break

        if not price_amount:
            return None

        return {"label": label, "amount": price_amount}


def format_text(data: Dict) -> str:
    """Format menu data as readable text."""
    lines = []
    lines.append(f"{'='*60}")
    lines.append(f"  {data['location']}")
    lines.append(f"  URL: {data['url']}")
    lines.append(f"{'='*60}")

    for menu in data.get("menus", []):
        lines.append(f"\n{'─'*60}")
        lines.append(f"  📋 {menu['name']}")
        if menu.get("description"):
            lines.append(f"  {menu['description']}")
        lines.append(f"{'─'*60}")

        for section in menu.get("sections", []):
            if section.get("text_only"):
                lines.append(f"\n  📝 {section.get('content', '')}")
                continue

            section_header = section["name"]
            if section.get("subtitle"):
                section_header += f" ({section['subtitle']})"
            lines.append(f"\n  ▸ {section_header}")

            for item in section.get("items", []):
                line = f"    • {item['name']}"
                if item.get("description"):
                    line += f" — {item['description']}"
                if item.get("prices"):
                    price_strs = []
                    for p in item["prices"]:
                        if p.get("label"):
                            price_strs.append(f"{p['label']}: {p['amount']}")
                        else:
                            price_strs.append(p["amount"])
                    line += f"  [{', '.join(price_strs)}]"
                if item.get("addons"):
                    for addon in item["addons"]:
                        addon_line = f"      ├ {addon['name']}"
                        if addon.get("price"):
                            addon_line += f"  [{addon['price']}]"
                        lines.append(addon_line)
                if item.get("calories"):
                    line += f"  ({item['calories']} cal.)"
                lines.append(line)

    lines.append(f"\n{'='*60}")
    return "\n".join(lines)


def format_markdown(data: Dict) -> str:
    """Format menu data as Markdown."""
    lines = []
    lines.append(f"# {data['location']}")
    lines.append(f"\n> Source: {data['url']}\n")

    for menu in data.get("menus", []):
        lines.append(f"\n## {menu['name']}")
        if menu.get("description"):
            lines.append(f"\n{menu['description']}\n")

        for section in menu.get("sections", []):
            if section.get("text_only"):
                lines.append(f"\n> {section.get('content', '')}\n")
                continue

            section_header = section["name"]
            if section.get("subtitle"):
                section_header += f" ({section['subtitle']})"
            lines.append(f"\n### {section_header}\n")
            lines.append("| 菜品 | 描述 | 价格 | 卡路里 |")
            lines.append("|------|------|------|--------|")

            for item in section.get("items", []):
                name = item["name"]
                desc = item.get("description") or ""
                prices = ""
                if item.get("prices"):
                    price_parts = []
                    for p in item["prices"]:
                        if p.get("label"):
                            price_parts.append(f"{p['label']}: {p['amount']}")
                        else:
                            price_parts.append(p["amount"])
                    prices = ", ".join(price_parts)
                cals = str(item.get("calories") or "")
                lines.append(f"| {name} | {desc} | {prices} | {cals} |")

            # Add addons as sub-items if any
            for item in section.get("items", []):
                if item.get("addons"):
                    for addon in item["addons"]:
                        addon_price = addon.get("price") or ""
                        lines.append(f"| &nbsp;&nbsp;├ {addon['name']} | | {addon_price} | |")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Morton's The Steakhouse Menu Scraper")
    parser.add_argument("--url", required=True, help="Target location page URL")
    parser.add_argument("--output", choices=["json", "text", "markdown"], default="json")
    args = parser.parse_args()

    scraper = MortonsMenuScraper()
    data = scraper.scrape(args.url)

    if args.output == "json":
        print(json.dumps(data, indent=2, ensure_ascii=False))
    elif args.output == "text":
        print(format_text(data))
    elif args.output == "markdown":
        print(format_markdown(data))

    sys.stdout.flush()


if __name__ == "__main__":
    main()
