"""
Shopee Browser Scraper
Playwright-based scraping with network interception
Falls back to DOM scraping when API interception fails
"""

import asyncio
import json
import logging
import random
import re
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from playwright.async_api import async_playwright, Page, BrowserContext
except ImportError:
    async_playwright = None

from .models import ShopeeProduct, ProductVariant

logger = logging.getLogger(__name__)


class ShopeeBrowser:
    """
    Playwright-based Shopee scraper with network interception
    
    Strategy:
    1. Open real browser with cookies
    2. Intercept internal API responses (JSON)
    3. Fallback to DOM scraping if interception fails
    
    Usage:
        async with ShopeeBrowser(cookies_file="shopeeCookies.json") as sb:
            products = await sb.search("laptop gaming", max_results=10)
            detail = await sb.get_product_detail(item_id, shop_id)
    """
    
    def __init__(
        self,
        cookies_file: Optional[str] = None,
        headless: bool = True,
        min_delay: float = 8.0,
        max_delay: float = 15.0,
        proxy: Optional[str] = None,
    ):
        if async_playwright is None:
            raise ImportError("playwright required. Install: pip install playwright && playwright install chromium")
        
        self.cookies_file = cookies_file
        self.headless = headless
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.proxy = proxy
        
        self._playwright = None
        self._browser = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._intercepted: Dict[str, Any] = {}
    
    async def __aenter__(self):
        await self.init()
        return self
    
    async def __aexit__(self, *args):
        await self.close()
    
    async def init(self):
        """Initialize browser"""
        self._playwright = await async_playwright().start()
        
        launch_opts = {
            "headless": self.headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ]
        }
        
        if self.proxy:
            launch_opts["proxy"] = {"server": self.proxy}
        
        self._browser = await self._playwright.chromium.launch(**launch_opts)
        
        self._context = await self._browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="id-ID",
            timezone_id="Asia/Jakarta",
        )
        
        # Load cookies
        if self.cookies_file:
            await self._load_cookies()
        
        # Hide automation signals
        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {} };
        """)
        
        self._page = await self._context.new_page()
        
        # Setup API interception
        self._page.on("response", self._handle_response)
        
        logger.info("[ShopeeBrowser] Browser initialized")
    
    async def close(self):
        """Cleanup"""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
    
    async def _load_cookies(self):
        """Load cookies from JSON file"""
        with open(self.cookies_file, 'r') as f:
            raw = json.load(f)
        
        cookies = []
        for c in raw:
            cookie = {
                "name": c["name"],
                "value": c["value"],
                "domain": c["domain"],
                "path": c.get("path", "/"),
                "secure": c.get("secure", True),
                "httpOnly": c.get("httpOnly", False),
            }
            
            if c.get("expirationDate"):
                cookie["expires"] = c["expirationDate"]
            
            sm = c.get("sameSite")
            if sm and sm in ("Strict", "Lax", "None"):
                cookie["sameSite"] = sm
            
            cookies.append(cookie)
        
        await self._context.add_cookies(cookies)
        logger.info(f"[ShopeeBrowser] Loaded {len(cookies)} cookies")
    
    async def _handle_response(self, response):
        """Intercept Shopee API responses"""
        url = response.url
        
        try:
            if "api/v4/search/search_items" in url:
                data = await response.json()
                self._intercepted["search"] = data
                logger.debug(f"[Intercept] Search API captured")
            
            elif "api/v4/item/get" in url:
                data = await response.json()
                self._intercepted["item_detail"] = data
                logger.debug(f"[Intercept] Item detail captured")
            
            elif "api/v4/shop/get" in url:
                data = await response.json()
                self._intercepted["shop"] = data
        except Exception:
            pass
    
    async def _gentle_wait(self):
        """Wait humanly between actions"""
        delay = random.uniform(self.min_delay, self.max_delay)
        await asyncio.sleep(delay)
    
    async def _human_scroll(self, page: Page, scrolls: int = 3):
        """Simulate human scrolling"""
        for _ in range(scrolls):
            scroll_amount = random.randint(300, 700)
            await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
            await asyncio.sleep(random.uniform(0.5, 1.5))
    
    # ============ Public Methods ============
    
    async def search(
        self,
        keyword: str,
        max_results: int = 30,
        sort_by: str = "relevancy",
    ) -> List[ShopeeProduct]:
        """
        Search products on Shopee
        
        Args:
            keyword: Search query
            max_results: Max products to return
            sort_by: relevancy, ctime, sales, price
        """
        self._intercepted.pop("search", None)
        
        # Map sort
        sort_map = {
            "relevancy": "relevancy",
            "newest": "ctime", 
            "ctime": "ctime",
            "sales": "sales",
            "price": "price",
        }
        sort_param = sort_map.get(sort_by, "relevancy")
        
        url = f"https://shopee.co.id/search?keyword={keyword}&sortBy={sort_param}"
        
        logger.info(f"[ShopeeBrowser] Searching: {keyword}")
        
        await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
        
        # Wait for products to load
        await asyncio.sleep(3)
        await self._human_scroll(self._page, scrolls=2)
        await asyncio.sleep(2)
        
        # Try intercepted API data first
        if "search" in self._intercepted:
            items = self._intercepted["search"].get("items", [])
            products = []
            
            for item in items[:max_results]:
                basic = item.get("item_basic", {})
                if not basic:
                    continue
                products.append(self._parse_api_item(basic))
            
            logger.info(f"[ShopeeBrowser] Got {len(products)} from API interception")
            return products
        
        # Fallback: DOM scraping
        logger.info("[ShopeeBrowser] API interception failed, trying DOM scraping")
        return await self._scrape_search_dom(max_results)
    
    async def get_product_detail(
        self,
        item_id: int,
        shop_id: int
    ) -> Optional[ShopeeProduct]:
        """Get product detail by visiting product page"""
        self._intercepted.pop("item_detail", None)
        
        url = f"https://shopee.co.id/product/{shop_id}/{item_id}"
        
        logger.info(f"[ShopeeBrowser] Loading product: {item_id}")
        
        await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)
        await self._human_scroll(self._page, scrolls=1)
        await asyncio.sleep(2)
        
        # Try intercepted data
        if "item_detail" in self._intercepted:
            data = self._intercepted["item_detail"].get("data", {})
            if data:
                return self._parse_api_detail(data)
        
        # Fallback: DOM scraping for product page
        return await self._scrape_product_dom(item_id, shop_id, url)
    
    async def get_product_by_url(self, url: str) -> Optional[ShopeeProduct]:
        """Get product by Shopee URL"""
        from .models import WishlistItem
        item_id, shop_id = WishlistItem.parse_shopee_url(url)
        
        if not item_id or not shop_id:
            # Try visiting URL directly
            self._intercepted.pop("item_detail", None)
            
            await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(4)
            
            if "item_detail" in self._intercepted:
                data = self._intercepted["item_detail"].get("data", {})
                if data:
                    return self._parse_api_detail(data)
            
            return None
        
        return await self.get_product_detail(item_id, shop_id)
    
    # ============ DOM Scraping Fallbacks ============
    
    async def _scrape_search_dom(self, max_results: int) -> List[ShopeeProduct]:
        """Scrape search results from DOM"""
        products = []
        
        # Try various selectors
        selectors = [
            "li.shopee-search-item-result__item",
            "[data-sqe='item']",
            ".col-xs-2-4",  # Shopee grid items
        ]
        
        elements = []
        for selector in selectors:
            elements = await self._page.query_selector_all(selector)
            if elements:
                break
        
        if not elements:
            logger.warning("[ShopeeBrowser] No product elements found in DOM")
            return []
        
        for el in elements[:max_results]:
            try:
                product = await self._parse_dom_item(el)
                if product:
                    products.append(product)
            except Exception as e:
                logger.debug(f"[ShopeeBrowser] DOM parse error: {e}")
        
        logger.info(f"[ShopeeBrowser] Scraped {len(products)} from DOM")
        return products
    
    async def _parse_dom_item(self, element) -> Optional[ShopeeProduct]:
        """Parse a single product from DOM element"""
        try:
            # Get link (contains item & shop IDs)
            link = await element.query_selector("a")
            href = await link.get_attribute("href") if link else ""
            
            # Parse IDs from URL
            from .models import WishlistItem
            item_id, shop_id = WishlistItem.parse_shopee_url(href) if href else (None, None)
            
            # Name
            name_el = await element.query_selector("[data-sqe='name']")
            if not name_el:
                name_el = await element.query_selector(".ie3A\\+n, .yQmmFK")
            name = await name_el.inner_text() if name_el else "Unknown"
            
            # Price
            price_el = await element.query_selector("[data-sqe='adPrice']")
            if not price_el:
                price_el = await element.query_selector(".ZEgDH9, .vioxXd")
            price_text = await price_el.inner_text() if price_el else "0"
            price = self._parse_price_text(price_text)
            
            # Sold
            sold_el = await element.query_selector(".OwmBnn, .r6HknA")
            sold_text = await sold_el.inner_text() if sold_el else "0"
            sold = self._parse_sold_text(sold_text)
            
            # Rating
            rating = 0.0
            rating_el = await element.query_selector(".shopee-rating-stars__lit")
            if rating_el:
                style = await rating_el.get_attribute("style") or ""
                width_match = re.search(r'width:\s*([\d.]+)%', style)
                if width_match:
                    rating = float(width_match.group(1)) / 20  # Convert to 0-5
            
            # Location
            loc_el = await element.query_selector(".zGGwiV, .nj1bUF")
            location = await loc_el.inner_text() if loc_el else ""
            
            product_url = f"https://shopee.co.id{href}" if href and not href.startswith("http") else (href or "")
            
            return ShopeeProduct(
                item_id=item_id or 0,
                shop_id=shop_id or 0,
                name=name.strip(),
                price=price,
                price_original=price,
                discount_percent=0,
                sold=sold,
                rating=round(rating, 1),
                shop_location=location.strip(),
                product_url=product_url,
            )
        except Exception as e:
            logger.debug(f"[DOM] Parse error: {e}")
            return None
    
    async def _scrape_product_dom(self, item_id: int, shop_id: int, url: str) -> Optional[ShopeeProduct]:
        """Scrape product detail from DOM"""
        try:
            # Product name
            name_el = await self._page.query_selector("h1, [class*='ProductName'], .WBVL_7")
            name = await name_el.inner_text() if name_el else "Unknown"
            
            # Price
            price_el = await self._page.query_selector("[class*='Price'], .pqTWkA")
            price_text = await price_el.inner_text() if price_el else "0"
            price = self._parse_price_text(price_text)
            
            # Rating
            rating_el = await self._page.query_selector("[class*='rating']")
            rating_text = await rating_el.inner_text() if rating_el else "0"
            try:
                rating = float(re.search(r'[\d.]+', rating_text).group())
            except:
                rating = 0
            
            # Sold
            sold = 0
            sold_el = await self._page.query_selector("[class*='sold']")
            if sold_el:
                sold_text = await sold_el.inner_text()
                sold = self._parse_sold_text(sold_text)
            
            return ShopeeProduct(
                item_id=item_id,
                shop_id=shop_id,
                name=name.strip(),
                price=price,
                price_original=price,
                discount_percent=0,
                sold=sold,
                rating=round(rating, 1),
                product_url=url,
            )
        except Exception as e:
            logger.error(f"[DOM] Product detail error: {e}")
            return None
    
    # ============ Parsing Helpers ============
    
    def _parse_api_item(self, basic: Dict) -> ShopeeProduct:
        """Parse item from intercepted API data"""
        price = basic.get("price", 0) / 100000
        price_original = basic.get("price_before_discount", basic.get("price", 0)) / 100000
        
        discount = 0.0
        raw_discount = basic.get("raw_discount", 0)
        if raw_discount > 0:
            discount = raw_discount
        elif price_original > 0 and price < price_original:
            discount = ((price_original - price) / price_original) * 100
        
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
            rating_count=basic.get("item_rating", {}).get("rating_count", [0]*6)[0],
            shop_location=basic.get("shop_location", ""),
            image_url=f"https://cf.shopee.co.id/file/{basic.get('image', '')}",
            product_url=f"https://shopee.co.id/product/{shop_id}/{item_id}",
            raw_data=basic,
        )
    
    def _parse_api_detail(self, data: Dict) -> ShopeeProduct:
        """Parse from intercepted item detail API"""
        price = data.get("price", 0) / 100000
        price_original = data.get("price_before_discount", data.get("price", 0)) / 100000
        
        price_min = data.get("price_min", 0) / 100000
        if price_min > 0:
            price = price_min
        
        discount = data.get("raw_discount", 0)
        if discount == 0 and price_original > 0 and price < price_original:
            discount = ((price_original - price) / price_original) * 100
        
        # Variants
        variants = []
        for m in data.get("models", []):
            variants.append(ProductVariant(
                name=m.get("name", ""),
                price=m.get("price", 0) / 100000,
                price_original=m.get("price_before_discount", m.get("price", 0)) / 100000,
                stock=m.get("stock", 0),
                sku=m.get("sku", ""),
                model_id=m.get("modelid", 0),
            ))
        
        item_id = data.get("itemid", 0)
        shop_id = data.get("shopid", 0)
        
        categories = data.get("categories", [])
        category = " > ".join(c.get("display_name", "") for c in categories)
        
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
    
    @staticmethod
    def _parse_price_text(text: str) -> float:
        """Parse price from display text: 'Rp1.500.000' -> 1500000"""
        text = text.strip()
        # Remove prefix
        text = re.sub(r'[Rr]p\.?\s*', '', text)
        # Handle range: take first price
        if '-' in text:
            text = text.split('-')[0].strip()
        # Remove dots (thousands separator) and convert comma to dot
        text = text.replace('.', '').replace(',', '.')
        # Extract number
        match = re.search(r'[\d.]+', text)
        return float(match.group()) if match else 0
    
    @staticmethod
    def _parse_sold_text(text: str) -> int:
        """Parse sold count from text: 'Terjual 1,2rb' -> 1200"""
        text = text.lower().strip()
        match = re.search(r'([\d.,]+)\s*(rb|ribu|k|jt|juta|m)?', text)
        if not match:
            return 0
        
        num_str = match.group(1).replace(',', '.')
        num = float(num_str)
        
        suffix = match.group(2) or ""
        if suffix in ('rb', 'ribu', 'k'):
            num *= 1000
        elif suffix in ('jt', 'juta', 'm'):
            num *= 1000000
        
        return int(num)
