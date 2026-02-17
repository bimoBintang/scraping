"""
Shopee Browser Scraper
Playwright-based scraping with stealth + network interception

Key insights from testing:
- Search pages work well with API interception (fresh cookies required)
- Direct product page navigation often gets blocked ("Terjadi Kesalahan")
- Cookies expire after ~1-3 days; use `ShopeeBrowser.login()` to refresh
- Solution: stealth + warm-up + gentle pacing + fresh cookies
"""

import asyncio
import json
import logging
import os
import random
import re
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from playwright.async_api import async_playwright, Page, BrowserContext
except ImportError:
    async_playwright = None
    Page = None
    BrowserContext = None

try:
    from playwright_stealth import stealth_async
except ImportError:
    stealth_async = None

from .models import ShopeeProduct, ProductVariant

logger = logging.getLogger(__name__)


class ShopeeBrowser:
    """
    Playwright-based Shopee scraper with stealth and network interception
    
    Usage:
        # First time: login to get cookies
        await ShopeeBrowser.login("shopee/shopeeCookies.json")
        
        # Then scrape:
        async with ShopeeBrowser(cookies_file="shopee/shopeeCookies.json") as sb:
            products = await sb.search("laptop gaming", max_results=10)
    """
    
    @staticmethod
    async def login(cookies_output: str = "shopee/shopeeCookies.json"):
        """
        Open a REAL Chrome browser (no Playwright/automation) for login.
        After user logs in and presses Enter, cookies are extracted from
        Chrome's internal SQLite database.
        
        This bypasses ALL anti-bot detection because Chrome runs completely
        normally with zero automation framework.
        """
        import subprocess
        import shutil
        import sqlite3
        import tempfile
        
        # Find Chrome executable
        chrome_paths = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ]
        
        chrome_exe = None
        for p in chrome_paths:
            if os.path.exists(p):
                chrome_exe = p
                break
        
        if not chrome_exe:
            print("❌ Chrome tidak ditemukan! Install Google Chrome terlebih dahulu.")
            print("   Download: https://www.google.com/chrome/")
            return None
        
        # Create a temporary profile directory for this login session
        profile_dir = os.path.join(os.path.dirname(cookies_output) or ".", ".chrome_login_profile")
        os.makedirs(profile_dir, exist_ok=True)
        
        print("\n🔐 Shopee Login")
        print("=" * 55)
        print("Chrome akan terbuka (bukan automation, Chrome biasa!).")
        print("1. Login ke Shopee seperti biasa")
        print("2. Selesaikan CAPTCHA jika ada")  
        print("3. Pastikan sudah masuk ke halaman utama Shopee")
        print("4. Kembali ke terminal ini dan tekan ENTER")
        print("=" * 55)
        
        # Launch Chrome as a completely normal browser
        chrome_args = [
            chrome_exe,
            f"--user-data-dir={profile_dir}",
            "--new-window",
            "--no-first-run",
            "--no-default-browser-check",
            "https://shopee.co.id/buyer/login",
        ]
        
        proc = subprocess.Popen(chrome_args)
        print(f"\n⏳ Chrome terbuka (PID: {proc.pid})")
        print("   Login ke Shopee, lalu kembali ke sini...")
        
        # Wait for user to press Enter
        input("\n👉 Tekan ENTER setelah berhasil login ke Shopee... ")
        
        print("\n📥 Mengambil cookies dari Chrome...")
        
        # Read cookies from Chrome's SQLite database
        cookies_db = os.path.join(profile_dir, "Default", "Cookies")
        network_cookies_db = os.path.join(profile_dir, "Default", "Network", "Cookies")
        
        # Chrome might store cookies in either location
        db_path = None
        for candidate in [network_cookies_db, cookies_db]:
            if os.path.exists(candidate):
                db_path = candidate
                break
        
        if not db_path:
            print("⚠️ Cookie database tidak ditemukan. Pastikan sudah login.")
            print(f"   Mencari di: {profile_dir}")
            # Try to terminate Chrome
            try:
                proc.terminate()
            except:
                pass
            return None
        
        # Copy the db (Chrome locks it while running)
        tmp_db = db_path + ".tmp"
        shutil.copy2(db_path, tmp_db)
        
        try:
            conn = sqlite3.connect(tmp_db)
            cursor = conn.cursor()
            
            # Get Shopee cookies
            cursor.execute("""
                SELECT name, value, host_key, path, is_secure, is_httponly, 
                       expires_utc, samesite
                FROM cookies 
                WHERE host_key LIKE '%shopee%'
            """)
            
            cookie_list = []
            for row in cursor.fetchall():
                name, value, domain, path, secure, httponly, expires, samesite = row
                
                # Chrome stores encrypted cookies on Windows
                # But the 'value' column has the decrypted value if available
                if not value:
                    # Try encrypted_value column
                    try:
                        cursor2 = conn.cursor()
                        cursor2.execute(
                            "SELECT encrypted_value FROM cookies WHERE name=? AND host_key=?",
                            (name, domain)
                        )
                        enc_row = cursor2.fetchone()
                        if enc_row and enc_row[0]:
                            # On Windows, Chrome uses DPAPI to encrypt cookies
                            try:
                                import win32crypt
                                value = win32crypt.CryptUnprotectData(enc_row[0], None, None, None, 0)[1].decode('utf-8')
                            except ImportError:
                                # If win32crypt not available, skip encrypted cookies
                                continue
                            except Exception:
                                continue
                    except Exception:
                        continue
                
                if not value:
                    continue
                
                cookie_data = {
                    "name": name,
                    "value": value,
                    "domain": domain,
                    "path": path or "/",
                    "secure": bool(secure),
                    "httpOnly": bool(httponly),
                }
                
                if expires > 0:
                    # Chrome stores timestamps as microseconds since 1601-01-01
                    # Convert to Unix timestamp
                    cookie_data["expirationDate"] = (expires / 1000000) - 11644473600
                
                samesite_map = {0: "None", 1: "Lax", 2: "Strict"}
                if samesite in samesite_map:
                    cookie_data["sameSite"] = samesite_map[samesite]
                
                cookie_list.append(cookie_data)
            
            conn.close()
        finally:
            # Clean up temp db
            try:
                os.remove(tmp_db)
            except:
                pass
        
        if not cookie_list:
            print("⚠️ Tidak ada Shopee cookies ditemukan.")
            print("   Pastikan kamu sudah login di browser yang terbuka tadi.")
            try:
                proc.terminate()
            except:
                pass
            return None
        
        # Save cookies
        os.makedirs(os.path.dirname(cookies_output) or ".", exist_ok=True)
        with open(cookies_output, 'w') as f:
            json.dump(cookie_list, f, indent=2)
        
        print(f"💾 {len(cookie_list)} Shopee cookies disimpan ke: {cookies_output}")
        
        # Try to close Chrome
        try:
            proc.terminate()
            print("🔒 Chrome ditutup.")
        except:
            print("ℹ️ Tutup Chrome secara manual jika masih terbuka.")
        
        print("✅ Selesai! Jalankan: python shopee_main.py check")
        return cookies_output
    
    @staticmethod
    async def check_cookies(cookies_file: str) -> bool:
        """Check if cookies file exists and is recent enough"""
        if not os.path.exists(cookies_file):
            return False
        
        # Check file age (cookies usually expire within 1-3 days)
        mtime = os.path.getmtime(cookies_file)
        age_hours = (datetime.now().timestamp() - mtime) / 3600
        
        if age_hours > 48:
            logger.warning(f"[ShopeeBrowser] Cookies are {age_hours:.0f}h old. Consider refreshing with 'login' command.")
            return False
        
        return True
    
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
        self._warmed_up = False
    
    async def __aenter__(self):
        await self.init()
        return self
    
    async def __aexit__(self, *args):
        await self.close()
    
    async def init(self):
        """Initialize browser with stealth and warm up session"""
        self._playwright = await async_playwright().start()
        
        launch_opts = {
            "headless": self.headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-web-security",
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
        
        # Load cookies before page creation
        if self.cookies_file:
            await self._load_cookies()
        
        self._page = await self._context.new_page()
        
        # Apply stealth
        if stealth_async:
            await stealth_async(self._page)
            logger.debug("[ShopeeBrowser] Stealth applied")
        else:
            # Manual stealth fallback
            await self._context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['id-ID', 'id', 'en-US', 'en']});
            """)
        
        # Setup API interception
        self._page.on("response", self._handle_response)
        
        # Warm up: visit homepage to establish session
        await self._warm_up()
        
        logger.info("[ShopeeBrowser] Browser initialized")
    
    async def _warm_up(self):
        """Visit homepage to establish cookies and session"""
        if self._warmed_up:
            return
        
        logger.info("[ShopeeBrowser] Warming up session...")
        await self._page.goto("https://shopee.co.id", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(random.uniform(3, 5))
        
        # Simulate natural browsing - scroll a bit on homepage
        await self._human_scroll(self._page, scrolls=1)
        await asyncio.sleep(random.uniform(1, 2))
        
        self._warmed_up = True
    
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
                logger.debug("[Intercept] Search API captured")
            
            elif "api/v4/item/get" in url:
                data = await response.json()
                self._intercepted["item_detail"] = data
                logger.debug("[Intercept] Item detail captured")
            
            elif "api/v4/shop/get" in url:
                data = await response.json()
                self._intercepted["shop"] = data
        except Exception:
            pass
    
    async def _gentle_wait(self):
        """Wait humanly between actions"""
        delay = random.uniform(self.min_delay, self.max_delay)
        logger.debug(f"[ShopeeBrowser] Waiting {delay:.1f}s...")
        await asyncio.sleep(delay)
    
    async def _human_scroll(self, page: Page, scrolls: int = 3):
        """Simulate human scrolling"""
        for _ in range(scrolls):
            scroll_amount = random.randint(300, 700)
            await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
            await asyncio.sleep(random.uniform(0.5, 1.5))
    
    async def _is_error_page(self) -> bool:
        """Check if current page shows Shopee error"""
        try:
            content = await self._page.content()
            return "Terjadi Kesalahan" in content
        except:
            return True
    
    async def _try_retry_button(self) -> bool:
        """Click 'Coba Lagi' retry button if present"""
        try:
            btn = await self._page.query_selector("button:has-text('Coba Lagi')")
            if btn:
                await btn.click()
                await asyncio.sleep(random.uniform(4, 6))
                return not await self._is_error_page()
        except Exception:
            pass
        return False
    
    async def _navigate_with_retry(self, url: str, max_retries: int = 2) -> bool:
        """Navigate to URL with retry on error pages"""
        for attempt in range(max_retries + 1):
            await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(random.uniform(3, 5))
            
            if not await self._is_error_page():
                return True
            
            logger.warning(f"[ShopeeBrowser] Error page (attempt {attempt + 1}/{max_retries + 1})")
            
            if await self._try_retry_button():
                return True
            
            if attempt < max_retries:
                await asyncio.sleep(random.uniform(5, 10))
        
        return False
    
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
        
        success = await self._navigate_with_retry(url)
        if not success:
            logger.error("[ShopeeBrowser] Search page failed to load")
            return []
        
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
        """
        Get product detail with multi-strategy approach:
        1. Navigate to product page (may work with stealth)
        2. Try in-page API call from Shopee page
        3. Search for product by item_id on Shopee search
        """
        logger.info(f"[ShopeeBrowser] Getting product: {item_id}")
        
        # Strategy 1: Direct page navigation
        self._intercepted.pop("item_detail", None)
        url = f"https://shopee.co.id/product/{shop_id}/{item_id}"
        
        success = await self._navigate_with_retry(url, max_retries=1)
        
        if success:
            await self._human_scroll(self._page, scrolls=1)
            await asyncio.sleep(2)
            
            if "item_detail" in self._intercepted:
                data = self._intercepted["item_detail"].get("data", {})
                if data and data.get("name"):
                    return self._parse_api_detail(data)
            
            product = await self._scrape_product_dom(item_id, shop_id, url)
            if product and product.price > 0:
                return product
        
        # Strategy 2: In-page API call (from current page w/ session cookies)
        logger.info("[ShopeeBrowser] Trying in-page API call...")
        
        # Go back to homepage first if we're on error page
        if await self._is_error_page():
            await self._page.goto("https://shopee.co.id", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
        
        product = await self._fetch_via_page_api(item_id, shop_id)
        if product:
            return product
        
        # Strategy 3: Search for product to get basic data
        logger.info("[ShopeeBrowser] Trying search-based lookup...")
        product = await self._search_for_product(item_id, shop_id)
        if product:
            return product
        
        logger.warning(f"[ShopeeBrowser] All strategies failed for product {item_id}")
        return None
    
    async def _fetch_via_page_api(self, item_id: int, shop_id: int) -> Optional[ShopeeProduct]:
        """Fetch product via JS fetch from within the browser page"""
        try:
            result = await self._page.evaluate("""
                async ([itemId, shopId]) => {
                    try {
                        const resp = await fetch(
                            `https://shopee.co.id/api/v4/item/get?itemid=${itemId}&shopid=${shopId}`,
                            {
                                credentials: 'include',
                                headers: {
                                    'X-Shopee-Language': 'id',
                                    'X-Requested-With': 'XMLHttpRequest',
                                    'X-API-SOURCE': 'pc',
                                }
                            }
                        );
                        if (!resp.ok) return {error: resp.status};
                        const data = await resp.json();
                        return data;
                    } catch(e) {
                        return {error: e.message};
                    }
                }
            """, [item_id, shop_id])
            
            if result and not result.get("error"):
                data = result.get("data", {})
                if data and data.get("name"):
                    return self._parse_api_detail(data)
            
            err = result.get("error", "unknown") if result else "no result"
            logger.debug(f"[ShopeeBrowser] In-page API: {err}")
        except Exception as e:
            logger.debug(f"[ShopeeBrowser] In-page API error: {e}")
        
        return None
    
    async def _search_for_product(self, item_id: int, shop_id: int) -> Optional[ShopeeProduct]:
        """Try to find product via search by item_id (last resort)"""
        self._intercepted.pop("search", None)
        
        url = f"https://shopee.co.id/search?keyword={item_id}"
        
        success = await self._navigate_with_retry(url, max_retries=1)
        if not success:
            return None
        
        await self._human_scroll(self._page, scrolls=1)
        await asyncio.sleep(2)
        
        if "search" in self._intercepted:
            items = self._intercepted["search"].get("items", [])
            for item in items:
                basic = item.get("item_basic", {})
                if basic.get("itemid") == item_id:
                    return self._parse_api_item(basic)
            
            # If exact match not found but we have results, return first one
            if items:
                basic = items[0].get("item_basic", {})
                if basic:
                    logger.info("[ShopeeBrowser] Using best search match (not exact)")
                    return self._parse_api_item(basic)
        
        return None
    
    async def get_product_by_url(self, url: str) -> Optional[ShopeeProduct]:
        """Get product by Shopee URL"""
        from .models import WishlistItem
        item_id, shop_id = WishlistItem.parse_shopee_url(url)
        
        if not item_id or not shop_id:
            # Try visiting URL directly (e.g. short links)
            self._intercepted.pop("item_detail", None)
            
            success = await self._navigate_with_retry(url)
            if success and "item_detail" in self._intercepted:
                data = self._intercepted["item_detail"].get("data", {})
                if data:
                    return self._parse_api_detail(data)
            
            return None
        
        return await self.get_product_detail(item_id, shop_id)
    
    # ============ DOM Scraping Fallbacks ============
    
    async def _scrape_search_dom(self, max_results: int) -> List[ShopeeProduct]:
        """Scrape search results from DOM"""
        products = []
        
        selectors = [
            "li.shopee-search-item-result__item",
            "[data-sqe='item']",
            ".col-xs-2-4",
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
            link = await element.query_selector("a")
            href = await link.get_attribute("href") if link else ""
            
            from .models import WishlistItem
            item_id, shop_id = WishlistItem.parse_shopee_url(href) if href else (None, None)
            
            name_el = await element.query_selector("[data-sqe='name']")
            if not name_el:
                name_el = await element.query_selector(".ie3A\\+n, .yQmmFK")
            name = await name_el.inner_text() if name_el else "Unknown"
            
            price_el = await element.query_selector("[data-sqe='adPrice']")
            if not price_el:
                price_el = await element.query_selector(".ZEgDH9, .vioxXd")
            price_text = await price_el.inner_text() if price_el else "0"
            price = self._parse_price_text(price_text)
            
            sold_el = await element.query_selector(".OwmBnn, .r6HknA")
            sold_text = await sold_el.inner_text() if sold_el else "0"
            sold = self._parse_sold_text(sold_text)
            
            rating = 0.0
            rating_el = await element.query_selector(".shopee-rating-stars__lit")
            if rating_el:
                style = await rating_el.get_attribute("style") or ""
                width_match = re.search(r'width:\s*([\d.]+)%', style)
                if width_match:
                    rating = float(width_match.group(1)) / 20
            
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
            name_el = await self._page.query_selector("h1, [class*='ProductName'], .WBVL_7")
            name = await name_el.inner_text() if name_el else "Unknown"
            
            price_el = await self._page.query_selector("[class*='Price'], .pqTWkA")
            price_text = await price_el.inner_text() if price_el else "0"
            price = self._parse_price_text(price_text)
            
            rating_el = await self._page.query_selector("[class*='rating']")
            rating_text = await rating_el.inner_text() if rating_el else "0"
            try:
                rating = float(re.search(r'[\d.]+', rating_text).group())
            except:
                rating = 0
            
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
        text = re.sub(r'[Rr]p\.?\s*', '', text)
        if '-' in text:
            text = text.split('-')[0].strip()
        text = text.replace('.', '').replace(',', '.')
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
