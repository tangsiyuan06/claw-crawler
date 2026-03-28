import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class BaseHandler(ABC):
    DOMAINS: List[str] = []

    def __init__(self, proxy: Optional[str] = None):
        self.restaurant_id: str | None = None
        self.location_id: str | None = None
        self._page = None # Store the page object for the handler
        self.api_responses: List[Dict[str, Any]] = [] # To store captured API responses
        self.proxy = proxy # Store proxy for potential direct API calls

    @abstractmethod
    async def setup_network_capture(self, page):
        """Setup CDP network interception for the page."""
        pass

    @classmethod
    @abstractmethod
    def is_target_site(cls, url: str) -> bool:
        """Determines if this handler is suitable for the given URL."""
        pass

    @abstractmethod
    async def wait_for_load(self, page):
        """Wait for the page to fully load and dynamic content to appear."""
        self._page = page # Assign page to handler
        pass

    @abstractmethod
    async def extract_menu_items(self, html: str) -> List[Dict[str, Any]]:
        """Extract menu items from the page."""
        pass

    @abstractmethod
    def extract_restaurant_info(self, html: str) -> Dict[str, Any]:
        """Extract restaurant information from the page."""
        pass

    def normalize_url(self, url: str) -> str:
        """Normalize the URL before navigation (e.g. remove tracking params)."""
        return url

    def get_handler_name(self) -> str:
        """Returns the name of the handler."""
        return self.__class__.__name__.replace("Handler", "")

    def extract_restaurant_id(self, url: str) -> str | None:
        """Extracts the restaurant ID from the URL."""
        return None
    
    # Optional: Direct API fetch
    async def try_direct_fetch(self) -> bool:
        """Attempt to fetch data directly via API without browser.
        Returns True if successful and data is available."""
        return False
    
    # Optional: Network capture
    async def setup_network_capture(self, page):
        """Setup CDP network interception for the page."""
        pass

    # Optional: Get store info (for direct API)
    def get_store_info(self) -> Dict[str, Any]:
        """Returns basic store info, typically for direct API fetches."""
        return {}
    
    # Optional: Get restaurant context from handler
    def get_restaurant_context(self) -> str | None:
        """Returns additional restaurant context."""
        return None
