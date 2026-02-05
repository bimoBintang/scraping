"""
Browser Manager
Handle browser lifecycle, anti-detection, rotation, dan proxy support
"""

from typing import Optional, List, Dict

try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from .rotation import UserAgentRotator, ProxyRotator, Proxy
from .sniffer import APISniffer


# Anti-detection browser arguments
STEALTH_ARGS = [
    '--disable-blink-features=AutomationControlled',
    '--no-sandbox',
    '--disable-dev-shm-usage',
    '--disable-accelerated-2d-canvas',
    '--no-first-run',
    '--no-zygote',
    '--disable-gpu',
    '--disable-infobars',
    '--window-position=0,0',
    '--ignore-certificate-errors',
    '--ignore-certificate-errors-skip-list',
]


class BrowserManager:
    """
    Manage Playwright browser dengan anti-detection, rotation, dan sniffing
    
    Features:
    - Anti-detection arguments
    - User-Agent rotation
    - Proxy rotation dengan health checking
    - API sniffing
    """
    
    def __init__(
        self, 
        headless: bool = True, 
        slow_mo: int = 0,
        proxy_file: Optional[str] = None,
        rotate_ua: bool = True
    ):
        self.headless = headless
        self.slow_mo = slow_mo
        self.browser: Optional[Browser] = None
        self.playwright = None
        
        # Rotation
        self.ua_rotator = UserAgentRotator() if rotate_ua else None
        self.proxy_rotator = ProxyRotator()
        if proxy_file:
            self.proxy_rotator.load_from_file(proxy_file)
        
        # Sniffer
        self.sniffer = APISniffer()
        self._current_proxy: Optional[Proxy] = None
    
    async def __aenter__(self):
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def start(self, proxy: Optional[Proxy] = None) -> None:
        """Start browser dengan anti-detection measures"""
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright not installed. Run: pip install playwright && playwright install chromium")
        
        self.playwright = await async_playwright().start()
        
        launch_options = {
            'headless': self.headless,
            'slow_mo': self.slow_mo,
            'args': STEALTH_ARGS
        }
        
        # Proxy support
        if proxy:
            self._current_proxy = proxy
            launch_options['proxy'] = self.proxy_rotator.to_playwright_format(proxy)
            print(f"[+] Using proxy: {proxy.host}:{proxy.port}")
        elif self.proxy_rotator.count > 0:
            self._current_proxy = self.proxy_rotator.get_next()
            if self._current_proxy:
                launch_options['proxy'] = self.proxy_rotator.to_playwright_format(self._current_proxy)
                print(f"[+] Using proxy: {self._current_proxy.host}:{self._current_proxy.port}")
        
        self.browser = await self.playwright.chromium.launch(**launch_options)
        mode = "(headless)" if self.headless else "(visible)"
        print(f"[+] Browser started {mode}")
    
    async def close(self) -> None:
        """Close browser dan cleanup"""
        if self.browser:
            await self.browser.close()
            print("[+] Browser closed")
        if self.playwright:
            await self.playwright.stop()
    
    async def restart_with_new_proxy(self) -> bool:
        """Restart browser dengan proxy baru"""
        if self._current_proxy:
            self._current_proxy.mark_failed()
        
        await self.close()
        
        new_proxy = self.proxy_rotator.get_next()
        if new_proxy:
            await self.start(proxy=new_proxy)
            return True
        
        print("[!] No healthy proxies available")
        return False
    
    def _get_context_options(self, custom_ua: Optional[str] = None) -> Dict:
        """Get context options dengan user-agent rotation"""
        options = {
            'viewport': {'width': 1920, 'height': 1080},
            'locale': 'en-US',
            'timezone_id': 'America/New_York',
        }
        
        # User-Agent rotation
        if custom_ua:
            options['user_agent'] = custom_ua
        elif self.ua_rotator:
            options['user_agent'] = self.ua_rotator.get_random()
        else:
            options['user_agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        
        return options
    
    async def new_context(
        self, 
        cookies: Optional[List[Dict]] = None,
        custom_ua: Optional[str] = None
    ) -> BrowserContext:
        """Create new browser context dengan optional cookies dan UA"""
        if not self.browser:
            raise RuntimeError("Browser not started. Call start() first")
        
        options = self._get_context_options(custom_ua)
        context = await self.browser.new_context(**options)
        
        if cookies:
            await context.add_cookies(cookies)
            print(f"[+] {len(cookies)} cookies injected")
        
        print(f"[+] UA: {options['user_agent'][:50]}...")
        return context
    
    async def new_page(
        self, 
        cookies: Optional[List[Dict]] = None,
        enable_sniffer: bool = False
    ) -> tuple[BrowserContext, Page]:
        """Create new context and page dengan optional sniffer"""
        context = await self.new_context(cookies)
        page = await context.new_page()
        
        if enable_sniffer:
            await self.sniffer.attach(page)
        
        return context, page
    
    def get_captured_apis(self) -> List:
        """Get captured API calls dari sniffer"""
        return self.sniffer.get_api_calls()
    
    def mark_proxy_success(self):
        """Mark current proxy as successful"""
        if self._current_proxy:
            self._current_proxy.mark_success()
    
    def mark_proxy_failed(self):
        """Mark current proxy as failed"""
        if self._current_proxy:
            self._current_proxy.mark_failed()
