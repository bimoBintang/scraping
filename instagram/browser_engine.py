"""
Selenium Playwright Hybrid Engine — Algorithm 10

Dual-engine browser automation yang memilih antara Playwright (cepat)
dan Selenium (stealth) berdasarkan difficulty scoring per-target.

Engine Selection:
- Playwright: default, faster, good for bulk scraping
- Selenium: high-risk targets (verified, >1M followers), login wall recovery

Usage:
    engine = HybridBrowserEngine(engine_preference="auto")
    await engine.start()
    
    html = await engine.get_page_html("https://instagram.com/cristiano",
                                       difficulty="high")
    await engine.close()
"""

import asyncio
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Any
from pathlib import Path

from .utils import load_cookies, smart_delay


# ==================== CONSTANTS ====================

# Difficulty thresholds
HIGH_FOLLOWER_THRESHOLD = 1_000_000   # >1M = high-risk
MEDIUM_FOLLOWER_THRESHOLD = 100_000   # >100K = medium-risk

# Consecutive failures before switching engine
ENGINE_SWITCH_THRESHOLD = 2

# Anti-detection: Playwright args
PLAYWRIGHT_STEALTH_ARGS = [
    '--disable-blink-features=AutomationControlled',
    '--disable-features=IsolateOrigins,site-per-process',
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-dev-shm-usage',
    '--disable-accelerated-2d-canvas',
    '--disable-gpu',
    '--window-size=1920,1080',
]

# Anti-detection: Playwright init script
PLAYWRIGHT_STEALTH_SCRIPT = """
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'languages', { get: () => ['id-ID', 'id', 'en-US', 'en'] });
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
    
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) :
            originalQuery(parameters)
    );
    
    window.chrome = { runtime: {} };
"""

# Standard user agents
UA_PLAYWRIGHT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
)
UA_SELENIUM = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
)


# ==================== ENUMS ====================

class EngineType(str, Enum):
    PLAYWRIGHT = "playwright"
    SELENIUM = "selenium"


class Difficulty(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ==================== ENGINE HEALTH ====================

@dataclass
class EngineHealth:
    """Track per-engine performance stats"""
    engine_type: EngineType
    success_count: int = 0
    fail_count: int = 0
    consecutive_failures: int = 0
    total_latency_ms: float = 0.0
    request_count: int = 0
    login_walls: int = 0
    
    @property
    def success_rate(self) -> float:
        total = self.success_count + self.fail_count
        return self.success_count / total if total > 0 else 1.0
    
    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / self.request_count if self.request_count > 0 else 0.0
    
    def record_success(self, latency_ms: float = 0.0):
        self.success_count += 1
        self.consecutive_failures = 0
        self.request_count += 1
        self.total_latency_ms += latency_ms
    
    def record_failure(self, is_login_wall: bool = False):
        self.fail_count += 1
        self.consecutive_failures += 1
        if is_login_wall:
            self.login_walls += 1
    
    def to_dict(self) -> Dict:
        return {
            'engine': self.engine_type.value,
            'success_rate': round(self.success_rate, 3),
            'avg_latency_ms': round(self.avg_latency_ms, 1),
            'successes': self.success_count,
            'failures': self.fail_count,
            'consecutive_failures': self.consecutive_failures,
            'login_walls': self.login_walls,
        }


# ==================== ABSTRACT ENGINE ====================

class BrowserEngine(ABC):
    """Abstract base class for browser automation engines"""
    
    engine_type: EngineType
    
    @abstractmethod
    async def start(self, headless: bool = True, cookies: list = None):
        """Initialize the browser engine"""
        pass
    
    @abstractmethod
    async def close(self):
        """Close the browser"""
        pass
    
    @abstractmethod
    async def get_page_html(self, url: str, wait_ms: int = 2000) -> str:
        """Navigate to URL and return page HTML"""
        pass
    
    @abstractmethod
    async def execute_js(self, script: str) -> Any:
        """Execute JavaScript and return result"""
        pass
    
    @abstractmethod
    async def scroll_page(self, pixels: int = 0):
        """Scroll the page (0 = full page)"""
        pass
    
    @abstractmethod
    async def click_element(self, selector: str) -> bool:
        """Click an element by CSS selector"""
        pass
    
    @abstractmethod
    async def wait(self, ms: int):
        """Wait for specified milliseconds"""
        pass
    
    @abstractmethod
    async def get_current_url(self) -> str:
        """Get current page URL"""
        pass
    
    @abstractmethod
    async def is_element_visible(self, selector: str, timeout_ms: int = 2000) -> bool:
        """Check if an element is visible"""
        pass


# ==================== PLAYWRIGHT ENGINE ====================

class PlaywrightEngine(BrowserEngine):
    """
    Playwright-based browser engine.
    Fast, async-native, good for bulk scraping.
    """
    
    engine_type = EngineType.PLAYWRIGHT
    
    def __init__(self):
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
    
    async def start(self, headless: bool = True, cookies: list = None):
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError(
                "Playwright required: pip install playwright && playwright install chromium"
            )
        
        self._playwright = await async_playwright().start()
        
        self._browser = await self._playwright.chromium.launch(
            headless=headless,
            args=PLAYWRIGHT_STEALTH_ARGS,
        )
        
        self._context = await self._browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=UA_PLAYWRIGHT,
            locale='id-ID',
            timezone_id='Asia/Jakarta',
        )
        
        # Add cookies
        if cookies:
            ig_cookies = []
            for c in cookies:
                ig_cookies.append({
                    'name': c['name'],
                    'value': c['value'],
                    'domain': c.get('domain', '.instagram.com'),
                    'path': c.get('path', '/'),
                })
            await self._context.add_cookies(ig_cookies)
        
        # Anti-detection
        await self._context.add_init_script(PLAYWRIGHT_STEALTH_SCRIPT)
        
        self._page = await self._context.new_page()
        print("    [PW] Playwright engine started")
    
    async def close(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._page = None
    
    async def get_page_html(self, url: str, wait_ms: int = 2000) -> str:
        await self._page.goto(url, wait_until='networkidle', timeout=30000)
        if wait_ms > 0:
            await self._page.wait_for_timeout(wait_ms)
        return await self._page.content()
    
    async def execute_js(self, script: str) -> Any:
        return await self._page.evaluate(script)
    
    async def scroll_page(self, pixels: int = 0):
        if pixels > 0:
            await self._page.evaluate(f'window.scrollBy(0, {pixels})')
        else:
            await self._page.evaluate('window.scrollBy(0, window.innerHeight)')
        await self._page.wait_for_timeout(500)
    
    async def click_element(self, selector: str) -> bool:
        try:
            locator = self._page.locator(selector).first
            if await locator.is_visible(timeout=3000):
                await locator.click()
                return True
        except Exception:
            pass
        return False
    
    async def wait(self, ms: int):
        await self._page.wait_for_timeout(ms)
    
    async def get_current_url(self) -> str:
        return self._page.url if self._page else ""
    
    async def is_element_visible(self, selector: str, timeout_ms: int = 2000) -> bool:
        try:
            locator = self._page.locator(selector).first
            return await locator.is_visible(timeout=timeout_ms)
        except Exception:
            return False


# ==================== SELENIUM ENGINE ====================

class SeleniumEngine(BrowserEngine):
    """
    Selenium-based browser engine.
    Uses undetected-chromedriver for stealth. Harder to detect as bot.
    Sync-based, wrapped in async executor for compatibility.
    """
    
    engine_type = EngineType.SELENIUM
    
    def __init__(self):
        self._driver = None
        self._loop = None
    
    async def start(self, headless: bool = True, cookies: list = None):
        try:
            import undetected_chromedriver as uc
        except ImportError:
            try:
                from selenium import webdriver
                from selenium.webdriver.chrome.options import Options
                from selenium.webdriver.chrome.service import Service
                
                options = Options()
                if headless:
                    options.add_argument('--headless=new')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--disable-blink-features=AutomationControlled')
                options.add_argument(f'--user-agent={UA_SELENIUM}')
                options.add_argument('--window-size=1920,1080')
                options.add_experimental_option("excludeSwitches", ["enable-automation"])
                options.add_experimental_option('useAutomationExtension', False)
                
                self._driver = webdriver.Chrome(options=options)
                
                # Anti-detection via CDP
                self._driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                    'source': '''
                        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                        window.chrome = { runtime: {} };
                    '''
                })
                
                # Add cookies
                if cookies:
                    self._driver.get("https://www.instagram.com/")
                    await asyncio.sleep(2)
                    for c in cookies:
                        cookie = {
                            'name': c['name'],
                            'value': c['value'],
                            'domain': c.get('domain', '.instagram.com'),
                            'path': c.get('path', '/'),
                        }
                        try:
                            self._driver.add_cookie(cookie)
                        except Exception:
                            pass
                
                print("    [SE] Selenium engine started (standard)")
                return
            except ImportError:
                raise ImportError(
                    "Selenium required: pip install selenium "
                    "(or pip install undetected-chromedriver for stealth)"
                )
        
        # undetected-chromedriver path (preferred)
        options = uc.ChromeOptions()
        if headless:
            options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument(f'--user-agent={UA_SELENIUM}')
        options.add_argument('--window-size=1920,1080')
        
        self._loop = asyncio.get_event_loop()
        self._driver = await self._loop.run_in_executor(
            None, lambda: uc.Chrome(options=options)
        )
        
        # Add cookies
        if cookies:
            await self._loop.run_in_executor(
                None, lambda: self._driver.get("https://www.instagram.com/")
            )
            await asyncio.sleep(2)
            for c in cookies:
                cookie = {
                    'name': c['name'],
                    'value': c['value'],
                    'domain': c.get('domain', '.instagram.com'),
                    'path': c.get('path', '/'),
                }
                try:
                    await self._loop.run_in_executor(
                        None, lambda co=cookie: self._driver.add_cookie(co)
                    )
                except Exception:
                    pass
        
        print("    [SE] Selenium engine started (undetected)")
    
    async def close(self):
        if self._driver:
            loop = self._loop or asyncio.get_event_loop()
            try:
                await loop.run_in_executor(None, self._driver.quit)
            except Exception:
                pass
        self._driver = None
    
    async def get_page_html(self, url: str, wait_ms: int = 2000) -> str:
        loop = self._loop or asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self._driver.get(url))
        if wait_ms > 0:
            await asyncio.sleep(wait_ms / 1000)
        return await loop.run_in_executor(None, lambda: self._driver.page_source)
    
    async def execute_js(self, script: str) -> Any:
        loop = self._loop or asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self._driver.execute_script(f"return {script}")
        )
    
    async def scroll_page(self, pixels: int = 0):
        loop = self._loop or asyncio.get_event_loop()
        if pixels > 0:
            await loop.run_in_executor(
                None, lambda: self._driver.execute_script(f"window.scrollBy(0, {pixels})")
            )
        else:
            await loop.run_in_executor(
                None, lambda: self._driver.execute_script("window.scrollBy(0, window.innerHeight)")
            )
        await asyncio.sleep(0.5)
    
    async def click_element(self, selector: str) -> bool:
        loop = self._loop or asyncio.get_event_loop()
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            def _click():
                element = WebDriverWait(self._driver, 3).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                element.click()
                return True
            
            return await loop.run_in_executor(None, _click)
        except Exception:
            return False
    
    async def wait(self, ms: int):
        await asyncio.sleep(ms / 1000)
    
    async def get_current_url(self) -> str:
        if not self._driver:
            return ""
        loop = self._loop or asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self._driver.current_url)
    
    async def is_element_visible(self, selector: str, timeout_ms: int = 2000) -> bool:
        loop = self._loop or asyncio.get_event_loop()
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            def _check():
                wait = WebDriverWait(self._driver, timeout_ms / 1000)
                element = wait.until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
                )
                return element.is_displayed()
            
            return await loop.run_in_executor(None, _check)
        except Exception:
            return False


# ==================== HYBRID ENGINE ====================

class HybridBrowserEngine:
    """
    Intelligent browser engine router.
    
    Selects between Playwright (fast) and Selenium (stealth) based on:
    - Target difficulty (followers, verified status)
    - Previous engine failures (auto-switch on consecutive fails)
    - User preference (auto/playwright/selenium)
    
    Implements automatic fallback: if primary engine fails, retries with
    the alternative engine.
    """
    
    def __init__(
        self,
        engine_preference: str = "auto",
        headless: bool = True,
        cookies: list = None,
    ):
        """
        Args:
            engine_preference: "auto", "playwright", or "selenium"
            headless: Run browsers in headless mode
            cookies: Cookie list for authentication
        """
        self.preference = engine_preference.lower()
        self.headless = headless
        self.cookies = cookies or []
        
        # Engine instances (lazy-initialized)
        self._engines: Dict[EngineType, Optional[BrowserEngine]] = {
            EngineType.PLAYWRIGHT: None,
            EngineType.SELENIUM: None,
        }
        
        # Per-engine health tracking
        self.health: Dict[EngineType, EngineHealth] = {
            EngineType.PLAYWRIGHT: EngineHealth(EngineType.PLAYWRIGHT),
            EngineType.SELENIUM: EngineHealth(EngineType.SELENIUM),
        }
        
        # Check availability
        self._playwright_available = self._check_playwright()
        self._selenium_available = self._check_selenium()
        
        avail = []
        if self._playwright_available:
            avail.append("Playwright")
        if self._selenium_available:
            avail.append("Selenium")
        
        print(f"  [🔀] Hybrid Engine: {', '.join(avail) or 'None'} available "
              f"(preference: {self.preference})")
    
    @staticmethod
    def _check_playwright() -> bool:
        try:
            import playwright.async_api
            return True
        except ImportError:
            return False
    
    @staticmethod
    def _check_selenium() -> bool:
        try:
            import selenium
            return True
        except ImportError:
            try:
                import undetected_chromedriver
                return True
            except ImportError:
                return False
    
    async def _get_engine(self, engine_type: EngineType) -> BrowserEngine:
        """Get or create an engine instance (lazy init)"""
        if self._engines[engine_type] is None:
            if engine_type == EngineType.PLAYWRIGHT:
                engine = PlaywrightEngine()
            else:
                engine = SeleniumEngine()
            
            await engine.start(headless=self.headless, cookies=self.cookies)
            self._engines[engine_type] = engine
        
        return self._engines[engine_type]
    
    async def close(self):
        """Close all running engines"""
        for engine_type, engine in self._engines.items():
            if engine is not None:
                try:
                    await engine.close()
                    print(f"    [{engine_type.value}] Engine closed")
                except Exception:
                    pass
                self._engines[engine_type] = None
    
    # ==================== DIFFICULTY SCORING ====================
    
    @staticmethod
    def difficulty_score(
        followers: int = 0,
        is_verified: bool = False,
        is_private: bool = False,
    ) -> Difficulty:
        """
        Calculate target difficulty for engine selection.
        
        High difficulty targets are more likely to have bot-detection,
        so Selenium (harder to detect) is preferred.
        """
        score = 0
        
        # Follower-based scoring
        if followers >= HIGH_FOLLOWER_THRESHOLD:
            score += 3
        elif followers >= MEDIUM_FOLLOWER_THRESHOLD:
            score += 2
        elif followers >= 10_000:
            score += 1
        
        # Verified accounts have more protection
        if is_verified:
            score += 2
        
        # Private accounts need auth
        if is_private:
            score += 1
        
        if score >= 4:
            return Difficulty.HIGH
        elif score >= 2:
            return Difficulty.MEDIUM
        return Difficulty.LOW
    
    def select_engine(
        self,
        difficulty: Difficulty = Difficulty.LOW,
    ) -> EngineType:
        """
        Select the optimal engine based on difficulty and preference.
        
        Logic:
        - preference="playwright" → always Playwright (if available)
        - preference="selenium"  → always Selenium (if available)
        - preference="auto":
          - LOW difficulty  → Playwright (faster)
          - MEDIUM          → Playwright (with fallback ready)
          - HIGH            → Selenium (stealthier)
          - If engine has consecutive failures > threshold → switch
        """
        # Explicit preference
        if self.preference == "playwright" and self._playwright_available:
            return EngineType.PLAYWRIGHT
        if self.preference == "selenium" and self._selenium_available:
            return EngineType.SELENIUM
        
        # Auto mode
        pw_health = self.health[EngineType.PLAYWRIGHT]
        se_health = self.health[EngineType.SELENIUM]
        
        # Check if primary engine is failing too much
        if (pw_health.consecutive_failures >= ENGINE_SWITCH_THRESHOLD
                and self._selenium_available):
            return EngineType.SELENIUM
        
        if (se_health.consecutive_failures >= ENGINE_SWITCH_THRESHOLD
                and self._playwright_available):
            return EngineType.PLAYWRIGHT
        
        # Difficulty-based selection
        if difficulty == Difficulty.HIGH and self._selenium_available:
            return EngineType.SELENIUM
        
        # Default to Playwright (faster)
        if self._playwright_available:
            return EngineType.PLAYWRIGHT
        if self._selenium_available:
            return EngineType.SELENIUM
        
        raise RuntimeError("No browser engine available. Install playwright or selenium.")
    
    def _get_fallback_engine(self, primary: EngineType) -> Optional[EngineType]:
        """Get the alternative engine for fallback"""
        if primary == EngineType.PLAYWRIGHT and self._selenium_available:
            return EngineType.SELENIUM
        if primary == EngineType.SELENIUM and self._playwright_available:
            return EngineType.PLAYWRIGHT
        return None
    
    # ==================== EXECUTION ====================
    
    async def get_page_html(
        self,
        url: str,
        difficulty: Difficulty = Difficulty.LOW,
        wait_ms: int = 2000,
    ) -> Optional[str]:
        """
        Fetch page HTML with automatic engine selection and fallback.
        
        Returns:
            Page HTML string, or None if both engines fail
        """
        primary_type = self.select_engine(difficulty)
        
        # Try primary engine
        html = await self._try_engine(primary_type, url, wait_ms)
        if html is not None:
            return html
        
        # Try fallback engine
        fallback_type = self._get_fallback_engine(primary_type)
        if fallback_type:
            print(f"    [🔀] Falling back to {fallback_type.value}...")
            html = await self._try_engine(fallback_type, url, wait_ms)
            if html is not None:
                return html
        
        return None
    
    async def _try_engine(
        self,
        engine_type: EngineType,
        url: str,
        wait_ms: int = 2000,
    ) -> Optional[str]:
        """Try to fetch page with specific engine"""
        try:
            engine = await self._get_engine(engine_type)
            
            start_time = time.time()
            html = await engine.get_page_html(url, wait_ms=wait_ms)
            latency_ms = (time.time() - start_time) * 1000
            
            if html and len(html) > 500:
                self.health[engine_type].record_success(latency_ms)
                print(f"    [{engine_type.value}] ✓ {len(html)} bytes ({latency_ms:.0f}ms)")
                return html
            else:
                self.health[engine_type].record_failure()
                return None
                
        except Exception as e:
            self.health[engine_type].record_failure()
            print(f"    [{engine_type.value}] ✗ Error: {e}")
            return None
    
    async def get_engine_for_task(
        self,
        difficulty: Difficulty = Difficulty.LOW,
    ) -> BrowserEngine:
        """
        Get the raw engine instance for custom browser operations.
        Useful when caller needs direct access (e.g., scrolling, clicking).
        """
        engine_type = self.select_engine(difficulty)
        return await self._get_engine(engine_type)
    
    # ==================== STATS ====================
    
    def get_stats(self) -> Dict:
        """Get combined engine statistics"""
        return {
            'preference': self.preference,
            'playwright_available': self._playwright_available,
            'selenium_available': self._selenium_available,
            'engines': {
                et.value: self.health[et].to_dict()
                for et in EngineType
            },
        }
    
    def print_engine_status(self):
        """Print formatted engine status table"""
        print(f"""
╔═══════════════════════════════════════════════════╗
║   🔀 Hybrid Browser Engine Status                 ║
╠═══════════════════════════════════════════════════╣
║  Preference: {self.preference:<37} ║
╠═══════════════════════════════════════════════════╣
║  Engine       Avail  Rate    Latency  Fails  LW  ║
║  ─────────    ─────  ─────   ───────  ─────  ──  ║""")
        
        engines = [
            (EngineType.PLAYWRIGHT, self._playwright_available),
            (EngineType.SELENIUM, self._selenium_available),
        ]
        
        for et, avail in engines:
            h = self.health[et]
            avail_str = "✓" if avail else "✗"
            rate_str = f"{h.success_rate:.0%}"
            lat_str = f"{h.avg_latency_ms:.0f}ms" if h.request_count > 0 else "N/A"
            
            print(f"║  {et.value:<11}  {avail_str:<5}  {rate_str:<6}  {lat_str:<7}  "
                  f"{h.consecutive_failures:<5}  {h.login_walls:<2}  ║")
        
        print("╚═══════════════════════════════════════════════════╝")
