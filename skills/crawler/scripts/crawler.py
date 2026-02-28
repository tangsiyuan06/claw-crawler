#!/usr/bin/env python3
"""
Advanced Web Crawler for OpenClaw
Handles JavaScript-heavy sites, anti-bot measures, and complex web structures.
"""

import argparse
import json
import time
import sys
from urllib.parse import urljoin, urlparse
from typing import Dict, List, Optional

# Try to import required libraries
try:
    from playwright.sync_api import sync_playwright, Browser, Page
    from bs4 import BeautifulSoup
    import requests
except ImportError as e:
    print(f"Error: Missing required dependencies: {e}", file=sys.stderr)
    print("Install with: pip install playwright beautifulsoup4 requests", file=sys.stderr)
    sys.exit(1)

class WebCrawler:
    def __init__(self, headless: bool = True, timeout: int = 30000):
        self.headless = headless
        self.timeout = timeout
        self.browser: Optional[Browser] = None
        
    def __enter__(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu'
            ]
        )
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            self.browser.close()
        if hasattr(self, 'playwright'):
            self.playwright.stop()
    
    def create_context(self, user_agent: str = None):
        """Create browser context with custom settings"""
        context_options = {
            'viewport': {'width': 1920, 'height': 1080},
            'bypass_csp': True,
        }
        if user_agent:
            context_options['user_agent'] = user_agent
        else:
            context_options['user_agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        
        return self.browser.new_context(**context_options)
    
    def crawl_page(self, url: str, selector: str = None, wait_for: str = None, 
                   js_enabled: bool = True, auth: tuple = None) -> Dict:
        """Crawl a single page and extract content"""
        with self.create_context() as context:
            page = context.new_page()
            
            # Set extra HTTP headers if needed
            if auth:
                page.set_extra_http_headers({
                    'Authorization': f'Basic {auth[0]}:{auth[1]}'
                })
            
            # Navigate to page
            response = page.goto(url, wait_until='networkidle' if js_enabled else 'load')
            
            # Wait for specific element if requested
            if wait_for:
                page.wait_for_selector(wait_for, timeout=self.timeout)
            elif js_enabled:
                # Wait a bit for JS to execute
                page.wait_for_timeout(2000)
            
            # Get page content
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract title
            title = page.title()
            
            # Extract main content based on selector or auto-detect
            if selector:
                elements = soup.select(selector)
                content = '\n'.join([elem.get_text(strip=True) for elem in elements])
            else:
                # Auto-detect main content
                main_content_selectors = [
                    'main', 'article', '.article', '.post', '.content',
                    '#content', '.main-content', '.entry-content'
                ]
                content = ""
                for sel in main_content_selectors:
                    elements = soup.select(sel)
                    if elements:
                        content = '\n'.join([elem.get_text(strip=True) for elem in elements])
                        break
                
                if not content:
                    # Fallback to body text
                    content = soup.get_text(strip=True)
            
            # Extract metadata
            meta_data = {
                'url': url,
                'title': title,
                'status_code': response.status if response else 200,
                'content_length': len(html),
                'timestamp': time.time(),
                'links': [urljoin(url, link.get('href')) for link in soup.find_all('a', href=True)],
                'images': [urljoin(url, img.get('src')) for img in soup.find_all('img', src=True)]
            }
            
            return {
                'metadata': meta_data,
                'content': content,
                'html': html if js_enabled else None
            }

def main():
    parser = argparse.ArgumentParser(description='Advanced Web Crawler')
    parser.add_argument('--url', required=True, help='URL to crawl')
    parser.add_argument('--selector', help='CSS selector for content extraction')
    parser.add_argument('--wait-for', help='CSS selector to wait for before extracting')
    parser.add_argument('--js', action='store_true', help='Enable JavaScript rendering')
    parser.add_argument('--auth', help='Basic auth credentials (username:password)')
    parser.add_argument('--user-agent', help='Custom User-Agent string')
    parser.add_argument('--output', choices=['json', 'text', 'markdown'], default='json', 
                       help='Output format')
    parser.add_argument('--delay', type=int, default=0, help='Delay between requests (seconds)')
    
    args = parser.parse_args()
    
    # Parse auth if provided
    auth = None
    if args.auth:
        if ':' in args.auth:
            username, password = args.auth.split(':', 1)
            auth = (username, password)
        else:
            print("Error: Auth must be in format 'username:password'", file=sys.stderr)
            sys.exit(1)
    
    # Add delay if specified
    if args.delay > 0:
        time.sleep(args.delay)
    
    # Perform crawling
    try:
        with WebCrawler(headless=True) as crawler:
            result = crawler.crawl_page(
                url=args.url,
                selector=args.selector,
                wait_for=args.wait_for,
                js_enabled=args.js,
                auth=auth
            )
        
        # Output based on format
        if args.output == 'json':
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif args.output == 'text':
            print(result['content'])
        elif args.output == 'markdown':
            print(f"# {result['metadata']['title']}\n\n{result['content']}")
            
    except Exception as e:
        print(f"Error crawling {args.url}: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()