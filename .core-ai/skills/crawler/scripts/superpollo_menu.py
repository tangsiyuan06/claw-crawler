#!/usr/bin/env python3
"""
Super Pollo Menu Scraper (requests + BeautifulSoup edition)

Extracts menu data from superpollo.nyc by following ordering links to getsauce.com.
The superpollo.nyc site (Wix-based) doesn't host menus directly - it links to
getsauce.com for ordering. This script:
1. Fetches superpollo.nyc to extract getsauce.com ordering URLs
2. Fetches each getsauce.com menu page
3. Extracts menu data from JSON-LD structured data

Usage:
    python3 superpollo_menu.py --url "https://www.superpollo.nyc" --output json
    python3 superpollo_menu.py --url "..." --output markdown
"""
import argparse
import json
import re
import sys
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

CRAWLER_META = {
    "name": "superpollo_menu",
    "domains": ["superpollo.nyc", "getsauce.com"],
    "data": "Restaurant menu: categories, items, prices, descriptions (via getsauce.com)",
    "framework": "requests+bs4",
    "url_pattern": "https://www.superpollo.nyc",
    "output_formats": ["json", "text", "markdown"],
    "example": 'python3 superpollo_menu.py --url "https://www.superpollo.nyc" --output json',
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class SuperPolloMenuScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _extract_ordering_urls(self, html: str) -> List[str]:
        """Extract getsauce.com ordering URLs from superpollo.nyc HTML."""
        soup = BeautifulSoup(html, "html.parser")
        urls = []
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "getsauce.com" in href and "super-pollo" in href and href not in seen:
                seen.add(href)
                urls.append(href)
        
        # Fallback: known URLs if none found
        if not urls:
            urls = [
                "https://www.getsauce.com/order/super-pollo/menu",
                "https://www.getsauce.com/order/super-pollo-brooklyn/menu",
            ]
        
        return urls

    def _extract_menu_from_jsonld(self, soup: BeautifulSoup) -> Optional[Dict]:
        """Extract menu data from JSON-LD structured data."""
        jsonld_blocks = soup.find_all("script", type="application/ld+json")
        if not jsonld_blocks:
            return None
        
        for block in jsonld_blocks:
            try:
                data = json.loads(block.string)
                if isinstance(data, dict):
                    graph = data.get("@graph", [])
                    # Find Menu object in graph
                    for item in graph:
                        if isinstance(item, dict) and item.get("@type") == "Menu":
                            return data  # Return full graph for parsing
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get("@type") == "Menu":
                            return {"@graph": data}
            except (json.JSONDecodeError, AttributeError):
                continue
        return None

    def _parse_jsonld_menu(self, jsonld_data: Dict) -> Dict:
        """Parse JSON-LD Menu data into structured format."""
        restaurant_info = {}
        sections = []

        graph = jsonld_data.get("@graph", [])
        if not isinstance(graph, list):
            graph = [graph]

        for item in graph:
            if not isinstance(item, dict):
                continue
                
            if item.get("@type") == "Restaurant":
                restaurant_info = {
                    "name": item.get("name", ""),
                    "address": item.get("address", {}),
                    "phone": item.get("telephone", ""),
                    "url": item.get("url", ""),
                }
            elif item.get("@type") == "Menu":
                for section in item.get("hasMenuSection", []):
                    items = []
                    for menu_item in section.get("hasMenuItem", []):
                        offer = menu_item.get("offers", {})
                        image = menu_item.get("image", {})
                        items.append({
                            "name": menu_item.get("name", ""),
                            "price": float(offer.get("price", 0)) if offer.get("price") else None,
                            "currency": offer.get("priceCurrency", "USD"),
                            "description": menu_item.get("description", ""),
                            "image": image.get("url", "") if isinstance(image, dict) else "",
                        })
                    sections.append({
                        "category": section.get("name", ""),
                        "items": items,
                    })

        return {
            "restaurant": restaurant_info,
            "sections": sections,
        }

    def scrape(self, url: str) -> Dict:
        """Main scraping method."""
        result = {"url": url, "locations": []}
        
        # Step 1: Fetch superpollo.nyc to extract ordering URLs
        print(f"[1/3] Fetching {url}...", file=sys.stderr)
        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            print(f"Failed to fetch {url}: {e}", file=sys.stderr)
            # Use fallback URLs
            ordering_urls = [
                "https://www.getsauce.com/order/super-pollo/menu",
                "https://www.getsauce.com/order/super-pollo-brooklyn/menu",
            ]
        else:
            ordering_urls = self._extract_ordering_urls(resp.text)
        
        print(f"[1/3] Found {len(ordering_urls)} ordering URLs", file=sys.stderr)
        
        # Step 2: Fetch each menu page and extract data
        for i, menu_url in enumerate(ordering_urls):
            print(f"[2/3] Fetching menu {i+1}/{len(ordering_urls)}: {menu_url}", file=sys.stderr)
            try:
                resp = self.session.get(menu_url, timeout=30)
                resp.raise_for_status()
            except Exception as e:
                print(f"  ✗ Failed to fetch {menu_url}: {e}", file=sys.stderr)
                continue
            
            soup = BeautifulSoup(resp.text, "html.parser")
            jsonld_data = self._extract_menu_from_jsonld(soup)
            
            if jsonld_data:
                parsed = self._parse_jsonld_menu(jsonld_data)
                result["locations"].append(parsed)
                print(f"  ✓ Extracted {len(parsed.get('sections', []))} categories", file=sys.stderr)
            else:
                print(f"  ✗ No JSON-LD menu data found", file=sys.stderr)
        
        return result


def format_text(data: Dict) -> str:
    lines = [f"URL: {data['url']}", f"Locations: {len(data.get('locations', []))}", ""]
    for loc in data.get("locations", []):
        restaurant = loc.get("restaurant", {})
        lines.append(f"## {restaurant.get('name', 'Unknown')}")
        addr = restaurant.get("address", {})
        if isinstance(addr, dict):
            addr_str = f"{addr.get('streetAddress', '')}, {addr.get('addressLocality', '')}, {addr.get('addressRegion', '')} {addr.get('postalCode', '')}"
        else:
            addr_str = str(addr)
        lines.append(f"Address: {addr_str}")
        lines.append(f"Phone: {restaurant.get('phone', '')}")
        lines.append("")
        
        for section in loc.get("sections", []):
            lines.append(f"### {section.get('category', 'Unknown')}")
            for item in section.get("items", []):
                price = item.get("price")
                price_str = f"${price:.2f}" if price is not None else "N/A"
                desc = item.get("description", "")
                desc_str = f" - {desc}" if desc else ""
                lines.append(f"  - {item.get('name', '?')} ({price_str}){desc_str}")
            lines.append("")
    return "\n".join(lines)


def format_markdown(data: Dict) -> str:
    lines = [f"# {data['url']}\n"]
    for loc in data.get("locations", []):
        restaurant = loc.get("restaurant", {})
        lines.append(f"## {restaurant.get('name', 'Unknown')}\n")
        addr = restaurant.get("address", {})
        if isinstance(addr, dict):
            addr_str = f"{addr.get('streetAddress', '')}, {addr.get('addressLocality', '')}, {addr.get('addressRegion', '')} {addr.get('postalCode', '')}"
        else:
            addr_str = str(addr)
        lines.append(f"**Address:** {addr_str}  ")
        lines.append(f"**Phone:** {restaurant.get('phone', '')}\n")
        
        for section in loc.get("sections", []):
            lines.append(f"### {section.get('category', 'Unknown')}\n")
            lines.append("| Item | Price | Description |")
            lines.append("|------|-------|-------------|")
            for item in section.get("items", []):
                price = item.get("price")
                price_str = f"${price:.2f}" if price is not None else "N/A"
                name = item.get("name", "?")
                desc = item.get("description", "")
                lines.append(f"| {name} | {price_str} | {desc} |")
            lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="Target page URL")
    parser.add_argument("--output", choices=["json", "text", "markdown"], default="json")
    args = parser.parse_args()
    
    scraper = SuperPolloMenuScraper()
    data = scraper.scrape(args.url)
    
    if args.output == "json":
        print(json.dumps(data, indent=2, ensure_ascii=False))
    elif args.output == "text":
        print(format_text(data))
    elif args.output == "markdown":
        print(format_markdown(data))
    
    # CRITICAL: flush stdout to ensure output is not lost
    sys.stdout.flush()


if __name__ == "__main__":
    main()
