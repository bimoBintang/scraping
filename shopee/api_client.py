"""
Shopee Internal API Client
Gentle scraping with proper rate limiting for long-term monitoring
"""

import asyncio
import json
import random
import time
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    import aiohttp
except ImportError:
    aiohttp = None

from .models import ShopeeProduct, ProductVariant

logger = logging.getLogger(__name__)


class RateLimiter:
    """Gentle rate limiter: 8-15 seconds between requests"""
    
    def __init__(self, min_delay: float = 8.0, max_delay: float = 15.0):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._last_request = 0.0
        self._request_count = 0
        self._hour_start = time.time()
    
    async def wait(self):
        """Wait appropriate time before next request"""
        now = time.time()
        
        # Reset hourly counter
        if now - self._hour_start >= 3600:
            self._request_count = 0
            self._hour_start = now
        
        # Cap at 50 requests per hour
        if self._request_count >= 50:
            wait_time = 3600 - (now - self._hour_start)
            if wait_time > 0:
                logger.info(f"[RateLimit] Hourly limit reached, waiting {wait_time:.0f}s")
                await asyncio.sleep(wait_time)
                self._request_count = 0
                self._hour_start = time.time()
        
        # Min delay between requests
        elapsed = now - self._last_request
        delay = random.uniform(self.min_delay, self.max_delay)
        
        if elapsed < delay:
            wait = delay - elapsed
            logger.debug(f"[RateLimit] Waiting {wait:.1f}s before next request")
            await asyncio.sleep(wait)
        
        self._last_request = time.time()
        self._request_count += 1
    
    @property
    def requests_this_hour(self) -> int:
        return self._request_count


class ShopeeAPIClient:
    """
    Shopee internal API client with gentle rate limiting
    
    Usage:
        async with ShopeeAPIClient() as client:
            products = await client.search_products("laptop gaming")
            detail = await client.get_product_detail(item_id, shop_id)
    """
    
    BASE_URL = "https://shopee.co.id"
    
    # API endpoints
    ENDPOINTS = {
        "search": "/api/v4/search/search_items",
        "item_detail": "/api/v4/item/get",
        "shop_info": "/api/v4/shop/get",
        "categories": "/api/v4/pages/get_category_tree",
    }
    
    # User-Agent pool
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    ]
    
    def __init__(
        self,
        min_delay: float = 8.0,
        max_delay: float = 15.0,
        max_retries: int = 3,
        timeout: int = 30,
        proxy: Optional[str] = None
    ):
        if aiohttp is None:
            raise ImportError("aiohttp is required. Install with: pip install aiohttp")
        
        self.rate_limiter = RateLimiter(min_delay, max_delay)
        self.max_retries = max_retries
        self.timeout = timeout
        self.proxy = proxy
        self._session: Optional[aiohttp.ClientSession] = None
        self._cookies: Dict[str, str] = {}
    
    async def __aenter__(self):
        await self._create_session()
        return self
    
    async def __aexit__(self, *args):
        await self.close()
    
    async def _create_session(self):
        """Create aiohttp session with default headers"""
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        self._session = aiohttp.ClientSession(
            timeout=timeout,
            headers=self._get_headers()
        )
    
    async def close(self):
        """Close the session"""
        if self._session:
            await self._session.close()
            self._session = None
    
    def _get_headers(self) -> Dict[str, str]:
        """Generate realistic headers"""
        return {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "application/json",
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://shopee.co.id/",
            "X-Requested-With": "XMLHttpRequest",
            "X-API-SOURCE": "pc",
            "X-Shopee-Language": "id",
            "Connection": "keep-alive",
            "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        }
    
    def set_cookies(self, cookies: Dict[str, str]):
        """Set session cookies (SPC_EC, SPC_F, etc.)"""
        self._cookies = cookies
    
    def load_cookies_from_file(self, filepath: str):
        """Load cookies from JSON file"""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        if isinstance(data, list):
            # Cookie-Editor format
            self._cookies = {c['name']: c['value'] for c in data}
        elif isinstance(data, dict):
            self._cookies = data
        
        logger.info(f"[Shopee] Loaded {len(self._cookies)} cookies")
    
    async def _request(
        self,
        endpoint: str,
        params: Dict[str, Any] = None,
        method: str = "GET"
    ) -> Optional[Dict]:
        """
        Make rate-limited request to Shopee API
        """
        if not self._session:
            await self._create_session()
        
        url = f"{self.BASE_URL}{endpoint}"
        
        for attempt in range(self.max_retries):
            await self.rate_limiter.wait()
            
            try:
                # Rotate headers
                headers = self._get_headers()
                
                # Build cookie string
                cookie_str = "; ".join(f"{k}={v}" for k, v in self._cookies.items())
                if cookie_str:
                    headers["Cookie"] = cookie_str
                
                async with self._session.request(
                    method, url, params=params, headers=headers, proxy=self.proxy
                ) as resp:
                    
                    if resp.status == 200:
                        data = await resp.json()
                        logger.debug(f"[Shopee] {endpoint} -> 200 OK")
                        return data
                    
                    elif resp.status == 429:
                        # Rate limited - wait longer
                        wait = 60 * (attempt + 1)
                        logger.warning(f"[Shopee] Rate limited (429), waiting {wait}s...")
                        await asyncio.sleep(wait)
                        continue
                    
                    elif resp.status == 403:
                        logger.warning(f"[Shopee] Forbidden (403) - may need cookies")
                        return None
                    
                    else:
                        logger.warning(f"[Shopee] HTTP {resp.status} for {endpoint}")
                        await asyncio.sleep(10 * (attempt + 1))
                        
            except asyncio.TimeoutError:
                logger.warning(f"[Shopee] Timeout for {endpoint} (attempt {attempt + 1})")
                await asyncio.sleep(15)
            except Exception as e:
                logger.error(f"[Shopee] Error: {e}")
                await asyncio.sleep(10)
        
        return None
    
    # ============ Public API Methods ============
    
    async def search_products(
        self,
        keyword: str,
        limit: int = 30,
        page: int = 0,
        sort_by: str = "relevancy",
        price_min: Optional[int] = None,
        price_max: Optional[int] = None
    ) -> List[ShopeeProduct]:
        """
        Search products by keyword
        
        Args:
            keyword: Search query
            limit: Results per page (max 60)
            page: Page number (0-indexed)
            sort_by: relevancy, ctime (newest), sales, price
            price_min: Minimum price filter
            price_max: Maximum price filter
        """
        params = {
            "by": sort_by,
            "keyword": keyword,
            "limit": min(limit, 60),
            "newest": page * limit,
            "order": "desc" if sort_by != "price" else "asc",
            "page_type": "search",
            "scenario": "PAGE_GLOBAL_SEARCH",
            "version": 2,
        }
        
        if price_min is not None:
            params["price_min"] = price_min * 100000  # Shopee uses cents * 1000
        if price_max is not None:
            params["price_max"] = price_max * 100000
        
        data = await self._request(self.ENDPOINTS["search"], params)
        
        if not data:
            return []
        
        items = data.get("items", [])
        return [self._parse_search_item(item) for item in items if item.get("item_basic")]
    
    async def get_product_detail(
        self,
        item_id: int,
        shop_id: int
    ) -> Optional[ShopeeProduct]:
        """
        Get detailed product information
        
        Args:
            item_id: Product item ID
            shop_id: Shop ID
        """
        params = {
            "itemid": item_id,
            "shopid": shop_id,
        }
        
        data = await self._request(self.ENDPOINTS["item_detail"], params)
        
        if not data or not data.get("data"):
            return None
        
        return self._parse_item_detail(data["data"])
    
    async def get_product_by_url(self, url: str) -> Optional[ShopeeProduct]:
        """
        Get product by Shopee URL
        
        Args:
            url: Shopee product URL
        """
        from .models import WishlistItem
        
        item_id, shop_id = WishlistItem.parse_shopee_url(url)
        
        if not item_id or not shop_id:
            logger.error(f"[Shopee] Could not parse URL: {url}")
            return None
        
        return await self.get_product_detail(item_id, shop_id)
    
    async def get_shop_info(self, shop_id: int) -> Optional[Dict]:
        """Get shop information"""
        params = {"shopid": shop_id}
        data = await self._request(self.ENDPOINTS["shop_info"], params)
        
        if not data or not data.get("data"):
            return None
        
        return data["data"]
    
    # ============ Parsing Methods ============
    
    def _parse_search_item(self, item: Dict) -> ShopeeProduct:
        """Parse search result item to ShopeeProduct"""
        basic = item.get("item_basic", {})
        
        # Shopee prices are in cents * 1000 (100000 = Rp 1)
        price = basic.get("price", 0) / 100000
        price_original = basic.get("price_before_discount", basic.get("price", 0)) / 100000
        
        # Calculate discount
        discount = 0.0
        if price_original > 0 and price < price_original:
            discount = ((price_original - price) / price_original) * 100
        
        # Explicit discount from Shopee
        raw_discount = basic.get("raw_discount", 0)
        if raw_discount > 0:
            discount = raw_discount
        
        item_id = basic.get("itemid", 0)
        shop_id = basic.get("shopid", 0)
        
        return ShopeeProduct(
            item_id=item_id,
            shop_id=shop_id,
            name=basic.get("name", ""),
            price=price,
            price_original=price_original,
            discount_percent=round(discount, 1),
            stock=basic.get("stock", 0),
            sold=basic.get("sold", basic.get("historical_sold", 0)),
            rating=round(basic.get("item_rating", {}).get("rating_star", 0), 1),
            rating_count=basic.get("item_rating", {}).get("rating_count", [0, 0, 0, 0, 0, 0])[0],
            shop_location=basic.get("shop_location", ""),
            image_url=f"https://cf.shopee.co.id/file/{basic.get('image', '')}",
            product_url=f"https://shopee.co.id/product/{shop_id}/{item_id}",
            raw_data=basic,
        )
    
    def _parse_item_detail(self, data: Dict) -> ShopeeProduct:
        """Parse item detail response"""
        price = data.get("price", 0) / 100000
        price_original = data.get("price_before_discount", data.get("price", 0)) / 100000
        
        # Handle price ranges (min/max)
        price_min = data.get("price_min", 0) / 100000
        price_max = data.get("price_max", 0) / 100000
        
        if price_min > 0:
            price = price_min  # Use lowest price
        
        discount = 0.0
        if price_original > 0 and price < price_original:
            discount = ((price_original - price) / price_original) * 100
        
        raw_discount = data.get("raw_discount", 0)
        if raw_discount > 0:
            discount = raw_discount
        
        # Parse variants/models
        variants = []
        for model in data.get("models", []):
            variants.append(ProductVariant(
                name=model.get("name", ""),
                price=model.get("price", 0) / 100000,
                price_original=model.get("price_before_discount", model.get("price", 0)) / 100000,
                stock=model.get("stock", 0),
                sku=model.get("sku", ""),
                model_id=model.get("modelid", 0),
            ))
        
        item_id = data.get("itemid", 0)
        shop_id = data.get("shopid", 0)
        
        # Category path
        categories = data.get("categories", [])
        category = " > ".join(c.get("display_name", "") for c in categories) if categories else ""
        
        return ShopeeProduct(
            item_id=item_id,
            shop_id=shop_id,
            name=data.get("name", ""),
            price=price,
            price_original=price_original,
            discount_percent=round(discount, 1),
            stock=data.get("stock", 0),
            sold=data.get("sold", data.get("historical_sold", 0)),
            rating=round(data.get("item_rating", {}).get("rating_star", 0), 1),
            rating_count=data.get("item_rating", {}).get("rating_count", [0]*6)[0],
            category=category,
            shop_name=data.get("shop_name", ""),
            shop_location=data.get("shop_location", ""),
            image_url=f"https://cf.shopee.co.id/file/{data.get('image', '')}",
            product_url=f"https://shopee.co.id/product/{shop_id}/{item_id}",
            variants=variants,
            raw_data=data,
        )
