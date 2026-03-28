#!/usr/bin/env python3
"""
Grubhub 菜单爬虫 - 通用分类点击版 v10 (使用 Handler 模式)
实现：自动查找并点击所有分类标签，获取完整菜单
"""

import asyncio
import json
import argparse
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

import nodriver as nd

# Import handlers
from scripts.base_handler import BaseHandler
from scripts.grubhub_handler import GrubhubHandler

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class GrubhubCrawler:
    def __init__(self, proxy: str = "127.0.0.1:7890"):
        self.proxy = proxy
        self.browser = None
        self.page = None
        self.html = ""
        # Register handlers
        # self.handlers = {
        #     "grubhub.com": GrubhubHandler(),
        #     "seamless.com": GrubhubHandler(),
        # }

    async def run(self, url: str, output_file: str, headless: bool = True):
        logger.info(f"Starting Grubhub crawler for URL: {url}")
        logger.info(f"Output will be saved to: {output_file}")
        logger.info(f"Proxy server: {self.proxy}")
        
        # Determine handler based on URL
        handler = GrubhubHandler(proxy=self.proxy) # Always use GrubhubHandler for now
        self.browser = None
        self.page = None

        try:
            # Initialize nodriver with proxy settings
            logger.info("Launching browser...")
            self.browser = await nd.start(
                headless=headless,
                browser_args=[
                    '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
                    '--proxy-server={}'.format(self.proxy),
                    '--no-sandbox',
                    '--disable-setuid-sandbox'
                ]
            )
            self.page = await self.browser.get(url)
            logger.info("Browser launched and navigated to URL.")
            


            await handler.setup_network_capture(self.page)
            logger.info("Network capture setup complete. Waiting for page load and tokens...")

            success = await handler.wait_for_load(self.page)
            
            self.restaurant_id = handler.extract_restaurant_id(self.page.url)
            if not self.restaurant_id:
                logger.error("Could not extract restaurant ID from URL: %s", self.page.url)
                return
            
            if success:
                logger.info("Page loaded and tokens captured. Extracting menu items...")
                menu_items = handler.extract_menu_items()
                restaurant_info = handler.extract_restaurant_info()

                output_data = {
                    "restaurant_info": restaurant_info,
                    "menu_items": menu_items,
                    "timestamp": datetime.now().isoformat()
                }

                Path(output_file).parent.mkdir(parents=True, exist_ok=True)
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(output_data, f, ensure_ascii=False, indent=4)
                logger.info(f"Successfully saved {len(menu_items)} menu items to {output_file}")
            else:
                logger.warning("Failed to load page or capture tokens. No menu data extracted.")

        except Exception as e:
            logger.error("An error occurred during crawling: %s", e, exc_info=True)
        finally:
            if self.browser:
                browser_pid = getattr(self.browser, '_process_pid', 'N/A')
                logger.debug(f"Attempting to stop browser (pid: {browser_pid})")
                try:
                    await self.browser.stop()
                    logger.info(f"Browser (pid: {browser_pid}) stopped successfully.")
                except Exception as e:
                    logger.error(f"Error stopping browser (pid: {browser_pid}): {e}", exc_info=True)
                self.browser = None # Explicitly clear after attempt
            else:
                logger.info("Browser was not initialized or already stopped.")


async def main():
    parser = argparse.ArgumentParser(description="Grubhub Menu Crawler")
    parser.add_argument("--url", required=True, help="URL of the Grubhub restaurant page")
    parser.add_argument("--output", default="output/menu.json", help="Output JSON file path")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--proxy", default="127.0.0.1:7890", help="Proxy server address (e.g., 127.0.0.1:7890)")
    args = parser.parse_args()

    crawler = GrubhubCrawler(proxy=args.proxy)
    await crawler.run(args.url, args.output, headless=args.headless)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error("An unhandled exception occurred: %s", e, exc_info=True)
        sys.exit(1)
