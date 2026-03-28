import asyncio
import json
import logging
import re
import sys
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

import nodriver.cdp as cdp
from .base_handler import BaseHandler

logger = logging.getLogger(__name__)

# GrubHub API configuration
GRUBHUB_API_BASE = "https://api-gtm.grubhub.com"
GRUBHUB_DOMAINS: Set[str] = {"grubhub.com", "seamless.com"}

# Max size for API response bodies to capture (in bytes)
MAX_RESPONSE_BODY_SIZE = 1 * 1024 * 1024  # 1 MB
# Max number of API responses to store
MAX_CAPTURED_RESPONSES = 500

class GrubhubHandler(BaseHandler):
    """
    Grubhub 专用处理器，用于菜单提取。
    集成了令牌捕获、PerimeterX 处理、分阶段加载以及 V4 API 回退机制。
    """
    DOMAINS = GRUBHUB_DOMAINS

    def __init__(self, proxy: Optional[str] = None):
        super().__init__(proxy)
        self.bearer_token: str | None = None
        self.perimeter_x_token: str | None = None
        # self.api_responses 将在 setup_network_capture 中初始化
        self.all_api_responses: List[Dict[str, Any]] = [] # 用于存储所有捕获到的 API 响应
        self.category_ids: List[str] = []
        self.category_names: Dict[str, str] = {}  # category_id -> name mapping
        self.restaurant_id: str | None = None
        self.restaurant_name: str | None = None
        self._no_menu_categories: bool = False  # Set when enhanced_feed has no real categories
        self._v4_menu_items: Optional[List[Dict[str, Any]]] = None # Store items from v4 API fallback

    @staticmethod
    def extract_restaurant_id(url: str) -> str | None:
        """从 Grubhub URL 中提取餐厅 ID。"""
        match = re.search(r'/(?:restaurant|menu)/[^/]+/(\d+)', url)
        return match.group(1) if match else None

    @staticmethod
    def normalize_url(url: str) -> str:
        """
        清除跟踪/重定向参数，避免中间页面延迟。
        rwg_token (Google Reserve with Google) 是一个一次性重定向令牌，
        通常在我们抓取时已经过期，导致出现闪屏或重定向循环，浪费超时时间。
        """
        parsed = urlparse(url)
        params = parse_qs(parsed.query, keep_blank_values=True)
        for key in list(params.keys()):
            if key == "rwg_token" or key.startswith("utm_"):
                del params[key]
        cleaned = urlencode(params, doseq=True)
        return urlunparse(parsed._replace(query=cleaned))

    async def setup_network_capture(self, page):
        """
        设置 CDP 网络捕获以提取认证令牌和 API 响应。
        """
        self._page = page # Ensure self._page is set for the handler
        self.client = page # Use page itself as the CDP client
        
        self.bearer_token = None
        self.perimeter_x_token = None
        self.all_api_responses = [] # Reset for each new capture
        self.category_ids = []
        self.category_names = {}
        self.restaurant_name = None
        self._no_menu_categories = False
        self._v4_menu_items = None
        pending_requests: Dict[str, Dict] = {} # requestId -> request_info

        async def handle_request(event: cdp.network.RequestWillBeSent):
            """捕获传出请求中的认证令牌。"""
            logger.debug(f"Request Headers type: {type(event.request.headers)}")
            logger.debug(f"Request Headers: {event.request.headers}")
            try:
                headers = event.request.headers
                url = event.request.url

                # Headers might be case-sensitive, check both cases
                headers_lower = {k.lower(): v for k, v in headers.items()} if headers else {}

                # Capture Bearer token
                auth = headers_lower.get("authorization", "")
                if auth and auth.startswith("Bearer ") and self.bearer_token is None:
                    self.bearer_token = auth[7:]
                    logger.info("Captured Bearer token from: %s", url.split("?")[0][-50:])

                # Capture PerimeterX token
                px_token = headers_lower.get("perimeter-x", "")
                if px_token and self.perimeter_x_token is None:
                    self.perimeter_x_token = px_token
                    logger.info("Captured PerimeterX token")

                # Store request info for GrubHub API calls
                if "api-gtm.grubhub.com" in url:
                    pending_requests[str(event.request_id)] = {"url": url}

            except Exception as e:
                logger.debug("Request capture error: %s", e)

        async def handle_response(event: cdp.network.ResponseReceived):
            """跟踪响应元数据。"""
            try:
                mime = event.response.mime_type or ""
                request_id = str(event.request_id)

                # Update pending request with a mime type
                if request_id in pending_requests:
                    pending_requests[request_id]["mime"] = mime

            except Exception as e:
                logger.debug("Response capture error: %s", e)

        async def handle_loading_finished(event: cdp.network.LoadingFinished):
            """加载完成后捕获响应体。"""
            try:
                request_id = str(event.request_id)

                if request_id not in pending_requests:
                    return

                req_info = pending_requests.pop(request_id)
                url = req_info.get("url", "")
                mime = req_info.get("mime", "")

                # Only process JSON responses
                if "json" not in mime:
                    return

                try:
                    body_result = await self.client.send(
                        cdp.network.get_response_body(event.request_id)
                    )
                    if body_result and body_result[0] is not None:
                        body = body_result[0]
                        if len(body) > MAX_RESPONSE_BODY_SIZE:
                            logger.debug("Skipping oversized response: %s (%d bytes)", url[:80], len(body))
                            return
                        if len(self.all_api_responses) >= MAX_CAPTURED_RESPONSES:
                            return # Avoid OOM by limiting stored responses

                        try:
                            data = json.loads(body)
                            self.all_api_responses.append({
                                "url": url,
                                "data": data
                            })

                            # Extract category IDs from nonvolatile response
                            if "/nonvolatile/" in url and isinstance(data, dict):
                                self._extract_category_ids(data)
                                self._extract_restaurant_name(data)
                                if self.category_ids:
                                    logger.info("Extracted %d category IDs from nonvolatile response", len(self.category_ids))

                            logger.debug("Captured API: %s", url.split("?")[0][-60:])
                        except json.JSONDecodeError:
                            logger.debug("Response body is not JSON for %s", url[:80])
                    else:
                        logger.debug("No response body for %s", url[:80])
                except Exception as e:
                    logger.warning("Response body parse error for %s: %s", url.split("?")[0][-40:], e)

            except Exception as e:
                logger.debug("Loading finished error: %s", e)

        async def handle_loading_failed(event: cdp.network.LoadingFailed):
            """清理失败的网络请求中的 pending_requests。"""
            try:
                pending_requests.pop(str(event.request_id), None)
            except Exception:
                pass

        await self.client.send(cdp.network.enable())
        self.client.add_handler(cdp.network.RequestWillBeSent, handle_request)
        self.client.add_handler(cdp.network.ResponseReceived, handle_response)
        self.client.add_handler(cdp.network.LoadingFinished, handle_loading_finished)
        self.client.add_handler(cdp.network.LoadingFailed, handle_loading_failed)


    @classmethod
    def is_target_site(cls, url: str) -> bool:
        """Determines if this handler is suitable for the given URL."""
        hostname = urlparse(url).hostname
        if hostname:
            return any(hostname.endswith(domain) for domain in cls.DOMAINS)
        return False

    async def wait_for_load(self, page, max_wait: int = 25) -> bool:
        """
        等待 Grubhub 页面加载，捕获令牌，并获取所有类别。
        这个方法处理所有 Grubhub 特定的加载逻辑：
        1. 等待页面渲染
        2. 捕获 Bearer token 和 Category IDs
        3. 滚动以触发懒加载
        4. 通过 API 获取所有类别数据
        """
        self.page = page
        self.restaurant_id = self.extract_restaurant_id(page.url)

        # Phase 1: Wait for page to render
        await self._wait_for_page_render(page, max_wait=12)

        # Phase 2: Wait for tokens and category IDs
        await self._wait_for_tokens(page, max_wait=15)

        # Phase 3: Fetch categories or use v4 API fallback
        if self.bearer_token and self.category_ids and self.restaurant_id:
            # Old format: category IDs in enhanced_feed → fetch per-category feeds
            await self._scroll_page(page, max_scrolls=10, scroll_delay=0.8)
            await page.sleep(2.0)
            logger.info("Fetching %d categories via API...", len(self.category_ids))
            await self.fetch_all_categories(page, self.restaurant_id)
        elif self.bearer_token and not self.category_ids and self.restaurant_id:
            # New format: try v4 restaurants API for full menu (single call)
            logger.info("No categories from enhanced_feed — trying v4 API")
            items = await self._fetch_menu_via_v4_api(page, self.restaurant_id)
            if not items:
                # Fallback: scroll to trigger lazy loading
                logger.info("V4 API returned no items, scrolling to trigger loads...")
                await self._scroll_page(page, max_scrolls=5, scroll_delay=0.8)
                await page.sleep(2.0)
        else:
            logger.warning("No bearer token captured, page may be blocked by PerimeterX")
            await page.sleep(3.0)

        # Return True if we captured some API responses or v4 menu items
        return bool(self.all_api_responses) or bool(self._v4_menu_items)

    async def _wait_for_page_render(self, page, max_wait: int = 15) -> bool:
        """等待 Grubhub/Seamless 页面渲染。"""
        page_loaded = False

        for i in range(max_wait):
            await page.sleep(1)
            try:
                title = await page.evaluate("document.title")
                title = self._unwrap_nodriver_value(title)

                if "taste buds" not in title.lower() and "loading" not in title.lower():
                    if not page_loaded:
                        logger.info("Page title changed after %ds: %s", i + 1, title[:50])
                        page_loaded = True

                    has_menu_items = await page.evaluate("""
                        (() => {
                            const items = document.querySelectorAll('[class*="menuItem"], [class*="menu-item"]');
                            return items.length;
                        })()
                    """)
                    has_menu_items = self._unwrap_nodriver_value(has_menu_items)
                    if has_menu_items and has_menu_items > 5:
                        logger.info("Menu items rendered after %ds: %d items", i + 1, has_menu_items)
                        return True

            except Exception as e:
                logger.debug("Load check error: %s", e)

        if page_loaded:
            logger.info("Page loaded but menu items may not be fully rendered")
            return True

        logger.warning("Grubhub page did not fully load within %ds", max_wait)
        return False

    async def _wait_for_tokens(self, page, max_wait: int = 20) -> bool:
        """等待从网络流量中捕获认证令牌。"""
        for i in range(max_wait):
            await page.sleep(1)

            # Log progress every 5 seconds
            if (i + 1) % 5 == 0:
                logger.info(
                    "Waiting for tokens [%ds]: bearer=%s, px=%s, categories=%d, apis=%d",
                    i + 1,
                    "yes" if self.bearer_token else "no",
                    "yes" if self.perimeter_x_token else "no",
                    len(self.category_ids),
                    len(self.all_api_responses)
                )

            # Check if we have tokens and categories
            if self.bearer_token and self.category_ids:
                logger.info(
                    "Tokens captured after %ds: categories=%d",
                    i + 1, len(self.category_ids)
                )
                return True

            if self.bearer_token and not self.category_ids:
                # Wait for PX token, then bail — v4 API fallback will handle it
                if self.perimeter_x_token:
                    # Give one more second for late-arriving categories
                    await page.sleep(1)
                    if self.category_ids:
                        logger.info("Category IDs captured: %d", len(self.category_ids))
                        return True
                    logger.info(
                        "Bearer + PX tokens captured at %ds, "
                        "no categories — will try v4 API", i + 1,
                    )
                    return False
                await page.sleep(2)
                if self.category_ids:
                    logger.info("Category IDs captured: %d", len(self.category_ids))
                    return True

            # Check page state
            try:
                title = await page.evaluate("document.title")
                title = self._unwrap_nodriver_value(title)

                # Grubhub splash screen check
                if "taste buds" in title.lower():
                    logger.debug("[%ds] Still on splash screen...", i + 1)
            except (TypeError, AttributeError):
                pass

        logger.warning(
            "Token capture timeout: bearer=%s, px=%s, categories=%d",
            "yes" if self.bearer_token else "no",
            "yes" if self.perimeter_x_token else "no",
            len(self.category_ids)
        )
        return False

    @staticmethod
    async def _scroll_page(page, max_scrolls: int = 10, scroll_delay: float = 0.5):
        """滚动页面以触发内容懒加载。"""
        scroll_script = """
        () => {
            const scrollHeight = document.documentElement.scrollHeight;
            const viewportHeight = window.innerHeight;
            window.scrollBy(0, viewportHeight);
            return window.scrollY + viewportHeight < scrollHeight;
        }
        """

        for i in range(max_scrolls):
            try:
                can_scroll_more = await page.evaluate(scroll_script)
                await page.sleep(scroll_delay)
                can_scroll_more = GrubhubHandler._unwrap_nodriver_value(can_scroll_more)

                if not can_scroll_more:
                    logger.debug("Reached bottom of page after %d scrolls", i + 1)
                    break
            except Exception as e:
                logger.debug("Scroll error: %s", e)
                break

        try:
            await page.evaluate("window.scrollTo(0, 0)")
        except Exception as e:
            logger.debug("Scroll to top failed: %s", e)

    def _extract_category_ids(self, data: dict):
        """从非易失性 API 响应中提取类别 ID。"""
        try:
            obj = data.get("object")
            menu_data = obj.get("data", {}) if isinstance(obj, dict) else {}
            seen = set(self.category_ids)  # O(1) lookup for deduplication

            def add_category(cat_id, cat_name=None):
                """添加类别 ID，进行去重和验证。"""
                if cat_id is None:
                    return
                cat_id_str = str(cat_id)
                if not cat_id_str.isdigit() or cat_id_str in seen:
                    return
                seen.add(cat_id_str)
                self.category_ids.append(cat_id_str)
                if cat_name:
                    self.category_names[cat_id_str] = cat_name
                logger.debug("Found category: %s (%s)", cat_name or "", cat_id_str)

            # Primary source: enhanced_feed contains category IDs
            enhanced_feed = menu_data.get("enhanced_feed", [])
            logger.debug("Checking enhanced_feed: %d items", len(enhanced_feed))
            for item in enhanced_feed:
                add_category(item.get("id"), item.get("name", ""))

            # Fallback: check feed
            for item in menu_data.get("feed", []):
                add_category(item.get("id") or item.get("category_id"))

            # Also check content for CATEGORY type items
            for item in menu_data.get("content", []):
                if item.get("type") == "CATEGORY":
                    add_category(item.get("entity", {}).get("category_id"))

            # Recursively search for menu_category_list
            self._find_category_ids_recursive(data, seen=seen)

            if self.category_ids:
                logger.info("Found %d category IDs: %s...",
                           len(self.category_ids),
                           self.category_ids[:3])
                logger.info("Category names: %d mapped", len(self.category_names))
            else:
                # Check if enhanced_feed exists but has no real category IDs —
                # this means the restaurant has no menu data available.
                if enhanced_feed:
                    self._no_menu_categories = True
                    logger.warning(
                        "No category IDs in nonvolatile response "
                        "(enhanced_feed has %d non-category entries)",
                        len(enhanced_feed),
                    )
                else:
                    logger.warning("No category IDs found in nonvolatile response")

        except Exception as e:
            logger.warning("Category extraction error: %s", e)

    def _extract_restaurant_name(self, data: dict):
        """从非易失性响应中提取餐厅名称。"""
        try:
            obj = data.get("object")
            menu_data = obj.get("data", {}) if isinstance(obj, dict) else {}
            name = menu_data.get("restaurant_name") or menu_data.get("name")
            # Fallback: extract from content[0].entity.name (restaurant info block)
            if not name:
                content = menu_data.get("content", [])
                for item in content:
                    if isinstance(item, dict):
                        entity = item.get("entity", {})
                        if isinstance(entity, dict) and entity.get("name"):
                            name = entity["name"]
                            break
            if name and self.restaurant_name is None:
                self.restaurant_name = name
                logger.debug("Captured restaurant name: %s", name)
        except Exception as e:
            logger.debug("Restaurant name extraction error: %s", e)

    def _find_category_ids_recursive(self, data, depth=0, seen: Set[str] | None = None):
        """在数据结构中递归查找类别 ID。"""
        if depth > 10:
            return
        if seen is None:
            seen = set(self.category_ids)

        if isinstance(data, dict):
            # Look for category_id fields
            if "category_id" in data:
                cat_id = str(data["category_id"])
                if cat_id not in seen:
                    seen.add(cat_id)
                    self.category_ids.append(cat_id)

            # Look for menu_category_list
            if "menu_category_list" in data:
                for cat in data["menu_category_list"]:
                    if not isinstance(cat, dict):
                        continue
                    cat_id = cat.get("id") or cat.get("category_id")
                    if cat_id:
                        cat_id = str(cat_id)
                        if cat_id not in seen:
                            seen.add(cat_id)
                            self.category_ids.append(cat_id)

            for val in data.values():
                self._find_category_ids_recursive(val, depth + 1, seen=seen)

        elif isinstance(data, list):
            for item in data:
                self._find_category_ids_recursive(item, depth + 1, seen=seen)
    
    # JS types used by nodriver/CDP Runtime.RemoteObject serialization
    _NODRIVER_JS_TYPES = frozenset({
        "object", "function", "undefined", "string", "number",
        "boolean", "symbol", "bigint",
    })

    @staticmethod
    def _unwrap_nodriver_value(data):
        logger.debug(f"Entering _unwrap_nodriver_value with data type: {type(data)}")
        if isinstance(data, dict):
            # Check if this is a nodriver wrapped value (must be a JS type)
            if ("type" in data and "value" in data and len(data) == 2
                    and data["type"] in GrubhubHandler._NODRIVER_JS_TYPES):
                unwrapped_value = GrubhubHandler._unwrap_nodriver_value(data["value"])
                logger.debug(f"Unwrapped nodriver value: {unwrapped_value}, type: {type(unwrapped_value)}")
                return unwrapped_value
            # Regular dict - unwrap values
            unwrapped_dict = {k: GrubhubHandler._unwrap_nodriver_value(v) for k, v in data.items()}
            logger.debug(f"Unwrapped dict: {unwrapped_dict}, type: {type(unwrapped_dict)}")
            return unwrapped_dict
        elif isinstance(data, list):
            logger.debug(f"Processing list data: {data}")
            # Check if this is a list of [key, value] pairs (nodriver object format)
            if data and isinstance(data[0], list) and len(data[0]) == 2:
                try:
                    unwrapped_kv_dict = {k: GrubhubHandler._unwrap_nodriver_value(v) for k, v in data}
                    logger.debug(f"Unwrapped key-value list to dict: {unwrapped_kv_dict}, type: {type(unwrapped_kv_dict)}")
                    return unwrapped_kv_dict
                except (TypeError, ValueError):
                    pass # Not a [key, value] list, treat as regular list
            # Regular list
            unwrapped_list = [GrubhubHandler._unwrap_nodriver_value(item) for item in data]
            logger.debug(f"Unwrapped regular list: {unwrapped_list}, type: {type(unwrapped_list)}")
            return unwrapped_list
        else:
            logger.debug(f"Returning primitive data: {data}, type: {type(data)}")
            return data

    async def fetch_category_data(self, page, restaurant_id: str, category_id: str) -> dict | None:
        """使用 JavaScript fetch 为特定类别获取菜单数据。"""
        if not self.bearer_token:
            logger.warning("No bearer token available for API call")
            return None

        # Build API URL
        api_url = f"{GRUBHUB_API_BASE}/restaurant_gateway/feed/{restaurant_id}/{category_id}"
        params = "task=CATEGORY&platform=WEB&orderType=STANDARD&weightedItemDataIncluded=true"
        full_url = f"{api_url}?{params}"

        # Sanitize tokens before injecting into JavaScript (prevent JS injection)
        safe_bearer = json.dumps(self.bearer_token)[1:-1]  # strip outer quotes
        safe_px = json.dumps(self.perimeter_x_token)[1:-1] if self.perimeter_x_token else ""

        # Use page's JavaScript to make the request (inherits cookies/session)
        fetch_script = f"""
        (async () => {{
            try {{
                const response = await fetch("{full_url}", {{
                    method: "GET",
                    headers: {{
                        "Accept": "application/json",
                        "Authorization": "Bearer {safe_bearer}",
                        {"'perimeter-x': '" + safe_px + "'," if self.perimeter_x_token else ""}
                    }},
                    credentials: "include"
                }});
                if (response.ok) {{
                    const data = await response.json();
                    return {{ success: true, data: data }};
                }}
                const text = await response.text();
                return {{ error: response.status, statusText: response.statusText, body: text.substring(0, 200) }};
            }} catch (e) {{
                return {{ error: 'exception', message: e.message, stack: e.stack }};
            }}
        }})()
        """

        try:
            result = await page.evaluate(fetch_script, await_promise=True)

            # Unwrap nodriver's nested value format
            result = self._unwrap_nodriver_value(result)

            if result is None:
                logger.debug("Category fetch returned None")
                return None
            elif isinstance(result, dict):
                if "error" in result:
                    logger.warning("Category fetch error: %s", result.get("error"))
                    return None
                elif "success" in result and result.get("data"):
                    return result["data"]
                else:
                    return result
            else:
                logger.debug("Category fetch unexpected result type: %s", type(result))
                return None
        except Exception as e:
            logger.warning("Category fetch exception: %s", e)
            return None

    async def fetch_all_categories(self, page, restaurant_id: str) -> List[Dict]:
        """并发获取所有类别的菜单数据。"""
        sem = asyncio.Semaphore(3)
        results: List[tuple[str, Dict | None]] = []

        async def fetch_one(cat_id: str) -> tuple[str, Dict | None]:
            async with sem:
                data = await self.fetch_category_data(page, restaurant_id, cat_id)
                return cat_id, data

        # Fetch all categories concurrently (max 3 in-flight)
        fetched = await asyncio.gather(
            *(fetch_one(cid) for cid in self.category_ids),
            return_exceptions=True,
        )

        all_items = []
        for result in fetched:
            if isinstance(result, Exception):
                logger.warning("Category fetch exception: %s", result)
                continue
            cat_id, data = result
            if not data:
                continue

            cat_name = self.category_names.get(cat_id, "")
            logger.info("Category %s: name=%s", cat_id, cat_name[:30] if cat_name else "(none)")

            # Store in all_api_responses for comprehensive logging
            self.all_api_responses.append({
                "url": f"feed/{restaurant_id}/{cat_id}",
                "data": data,
                "category_name": cat_name,
            })

            items = self._extract_items_from_feed(data, category_name=cat_name)
            all_items.extend(items)
            logger.info("Category %s: %d items extracted", cat_id, len(items))

        return all_items

    async def _fetch_menu_via_v4_api(self, page, restaurant_id: str) -> List[Dict]:
        """通过 v4 餐厅 API 获取完整菜单（新 enhanced_feed 格式的回退方案）。"""
        if not self.bearer_token:
            return []

        safe_bearer = json.dumps(self.bearer_token)[1:-1]
        safe_px = json.dumps(self.perimeter_x_token)[1:-1] if self.perimeter_x_token else ""

        fetch_script = f"""
        (async () => {{
            try {{
                const resp = await fetch(
                    "{GRUBHUB_API_BASE}/restaurants/{restaurant_id}?version=4&variationId=rtpFreeItems&orderType=standard&locationMode=PICKUP",
                    {{
                        headers: {{
                            "Accept": "application/json",
                            "Authorization": "Bearer {safe_bearer}",
                            {"'perimeter-x': '" + safe_px + "'," if self.perimeter_x_token else ""}
                        }},
                        credentials: "include"
                    }}
                );
                if (!resp.ok) return JSON.stringify({{ error: resp.status }});
                const data = await resp.json();
                return JSON.stringify(data);
            }} catch (e) {{
                return JSON.stringify({{ error: e.message }});
            }}
        }})()
        """

        try:
            raw = await page.evaluate(fetch_script, await_promise=True)
            # Unwrap nodriver string wrapper
            raw = self._unwrap_nodriver_value(raw)
            
            if not isinstance(raw, str):
                logger.warning("V4 API: unexpected result type %s", type(raw))
                return []
            
            result = json.loads(raw)

            if not isinstance(result, dict) or "error" in result:
                logger.warning("V4 API error: %s", result.get("error") if isinstance(result, dict) else result)
                return []

            restaurant = result.get("restaurant", {})
            if not isinstance(restaurant, dict):
                return []

            # Extract restaurant name
            name = restaurant.get("name")
            if name and self.restaurant_name is None:
                self.restaurant_name = name

            categories = restaurant.get("menu_category_list", [])
            if not isinstance(categories, list) or not categories:
                logger.info("V4 API: no menu categories")
                return []

            all_items = []
            for cat in categories:
                if not isinstance(cat, dict):
                    continue
                cat_name = cat.get("name", "")
                for item in cat.get("menu_item_list", []):
                    if not isinstance(item, dict):
                        continue
                    price = item.get("price", {})
                    price_amount = price.get("amount") if isinstance(price, dict) else None
                    price_dollars = price_amount / 100 if price_amount is not None else None

                    # Image extraction
                    media = item.get("media_image")
                    image_url = None
                    if isinstance(media, dict):
                        base = media.get("base_url", "")
                        pub_id = media.get("public_id", "")
                        fmt = media.get("format", "jpg")
                        if base and pub_id:
                            image_url = f"{base}{pub_id}.{fmt}"

                    all_items.append({
                        "id": item.get("id"),
                        "name": item.get("name"),
                        "description": item.get("description", ""),
                        "price": price_dollars,
                        "category": cat_name,
                        "image": image_url,
                    })

            logger.info(
                "V4 API: %d items across %d categories for '%s'",
                len(all_items), len(categories), self.restaurant_name or restaurant_id,
            )

            # Store as all_api_responses so extract_menu_items() can find them
            self._v4_menu_items = all_items
            return all_items

        except Exception as e:
            logger.warning("V4 API fetch exception: %s", e)
            return []

    @staticmethod
    def _extract_items_from_feed(data: dict, category_name: str = "") -> List[Dict]:
        """从简化的 feed API 响应中提取菜单项。"""
        items = []
        try:
            obj = data.get("object")
            inner = obj.get("data", {}) if isinstance(obj, dict) else {}
            content = inner.get("content", []) if isinstance(inner, dict) else []

            def extract_price(prices: dict, key: str) -> float | None:
                """从嵌套的价格结构中以美元提取价格。"""
                price_obj = prices.get(key, {})
                if isinstance(price_obj, dict) and "value" in price_obj:
                    return price_obj["value"] / 100  # Convert cents to dollars
                return None

            for item in content:
                try:
                    if not isinstance(item, dict):
                        continue
                    if item.get("type") != "MENU_ITEM":
                        continue
                    entity = item.get("entity", {})
                    if "item_name" not in entity:
                        continue

                    price_data = entity.get("item_price", {})

                    # Defensive image extraction — handle dict, string, or None
                    media_image = entity.get("media_image")
                    image_url = None
                    if isinstance(media_image, dict):
                        image_url = media_image.get("url") or media_image.get("mediaUrl")
                        # Cloudinary-style: base_url + public_id + format
                        if not image_url:
                            base = media_image.get("base_url", "")
                            pub_id = media_image.get("public_id", "")
                            fmt = media_image.get("format", "jpg")
                            if base and pub_id:
                                image_url = f"{base}{pub_id}.{fmt}"
                    elif isinstance(media_image, str) and media_image.startswith("http"):
                        image_url = media_image

                    items.append({
                        "id": entity.get("item_id"),
                        "name": entity.get("item_name"),
                        "description": entity.get("item_description", ""),
                        "price": extract_price(price_data, "pickup") if isinstance(price_data, dict) else None,
                        "price_delivery": extract_price(price_data, "delivery") if isinstance(price_data, dict) else None,
                        "category": category_name,
                        "image": image_url,
                    })
                except Exception as e:
                    logger.debug("Item parse error: %s", e)
        except Exception as e:
            logger.debug("Item extraction error: %s", e)

        return items

    def _category_name_from_url(self, url: str) -> str:
        """通过匹配 URL 中的 category_id 来提取类别名称。"""
        for cat_id, cat_name in self.category_names.items():
            if f"/{cat_id}" in url:
                return cat_name
        return ""

    def extract_menu_items(self) -> List[Dict]:
        """从捕获的 API 响应中提取所有菜单项。"""
        # If v4 API was used (new format), return those items directly
        v4_items = getattr(self, "_v4_menu_items", None)
        if v4_items:
            return v4_items

        # Use dict to allow updating items with better data (e.g., with category)
        items_by_id: Dict[str, Dict] = {}

        for resp in self.all_api_responses:
            url = resp.get("url", "")
            data = resp.get("data", {})
            category_name = resp.get("category_name", "") # From fetch_all_categories

            # For CDP-captured responses (no category_name), look up from URL
            if not category_name and self.category_names:
                category_name = self._category_name_from_url(url)

            # Only process menu-related APIs (feed, category, popular items)
            if not any(pattern in url for pattern in ["feed/", "task=CATEGORY", "task=POPULAR_ITEMS"]):
                continue

            items = self._extract_items_from_feed(data, category_name=category_name)
            for item in items:
                item_id = item.get("id")
                if not item_id:
                    continue

                # If item already exists, prefer the one WITH category
                existing = items_by_id.get(item_id)
                if existing:
                    # Update only if new item has category and existing doesn't
                    if item.get("category") and not existing.get("category"):
                        items_by_id[item_id] = item
                else:
                    items_by_id[item_id] = item

        return list(items_by_id.values())
    
    def extract_restaurant_info(self) -> Dict[str, Any]:
        """提取餐厅信息。"""
        return {
            "name": self.restaurant_name,
            "restaurant_id": self.restaurant_id,
        }
