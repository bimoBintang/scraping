"""
Instagram Browser Scraper — Layer 2 Implementation
Uses Playwright for browser automation with stealth from tiktok/ package.
"""

import json
import asyncio
from typing import Dict, List, Optional
from pathlib import Path

from .models import InstagramProfile, InstagramPost
from .parsers import InstagramParser
from .selectors import (
    LOGIN_WALL_SELECTORS,
    COOKIE_BANNER_SELECTORS,
    POST_ITEM_SELECTORS,
    MODAL_SELECTORS,
    FOLLOWERS_MODAL_SELECTORS,
    MODAL_SCROLL_CONTAINER,
    MODAL_CLOSE_SELECTORS,
)
from .utils import load_cookies, smart_delay

try:
    from playwright.async_api import async_playwright, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class InstagramBrowserScraper:
    """
    Browser-based Instagram scraper using Playwright.
    Acts as Layer 2 fallback when API is blocked.
    
    Usage:
        async with InstagramBrowserScraper() as scraper:
            profile = await scraper.get_profile("cristiano")
            posts = await scraper.get_posts("cristiano", count=12)
    """
    
    INSTAGRAM_URL = "https://www.instagram.com"
    
    def __init__(
        self,
        cookies_file: Optional[str] = None,
        headless: bool = True,
        debug_dir: str = ".",
    ):
        self.cookies = load_cookies(cookies_file) if cookies_file else []
        self.headless = headless
        self.debug_dir = Path(debug_dir)
        self.parser = InstagramParser(debug_dir=debug_dir)
        
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
    
    async def __aenter__(self):
        await self.start()
        return self
    
    async def __aexit__(self, *args):
        await self.close()
    
    async def start(self):
        """Initialize browser"""
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright required: pip install playwright && playwright install chromium")
        
        self._playwright = await async_playwright().start()
        
        # Anti-detection args
        args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-features=IsolateOrigins,site-per-process',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--disable-gpu',
            '--window-size=1920,1080',
        ]
        
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=args,
        )
        
        self._context = await self._browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            locale='id-ID',
            timezone_id='Asia/Jakarta',
        )
        
        # Add cookies if available
        if self.cookies:
            ig_cookies = []
            for c in self.cookies:
                ig_cookies.append({
                    'name': c['name'],
                    'value': c['value'],
                    'domain': c.get('domain', '.instagram.com'),
                    'path': c.get('path', '/'),
                })
            await self._context.add_cookies(ig_cookies)
        
        # Anti-detection scripts
        await self._context.add_init_script("""
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
        """)
        
        self._page = await self._context.new_page()
        print("  [+] Browser started")
    
    async def close(self):
        """Close browser"""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        print("  [+] Browser closed")
    
    async def get_profile(self, username: str) -> Optional[InstagramProfile]:
        """Scrape profile via browser"""
        url = f"{self.INSTAGRAM_URL}/{username}/"
        print(f"  [→] Browser navigating to @{username}...")
        
        try:
            response = await self._page.goto(url, wait_until='networkidle', timeout=30000)
            
            if not response or response.status == 404:
                print(f"  [!] User @{username} not found")
                return None
            
            # Dismiss cookie banner if present
            await self._dismiss_cookie_banner()
            
            # Check for login wall
            if await self._is_login_wall():
                print("  [!] Login wall detected")
                return None
            
            # Wait for profile to load
            await self._page.wait_for_timeout(2000)
            
            # Try to extract data from page
            html = await self._page.content()
            
            # Save debug HTML
            debug_path = self.debug_dir / f"ig_browser_{username}.html"
            with open(debug_path, 'w', encoding='utf-8') as f:
                f.write(html[:100000])
            
            # Parse using multi-strategy parser
            profile = self.parser.parse_profile_page(html, username)
            
            if not profile:
                # Fallback: try extracting from JavaScript context
                profile = await self._extract_from_js(username)
            
            return profile
            
        except Exception as e:
            print(f"  [!] Browser error: {e}")
            return None
    
    async def get_posts(self, username: str, count: int = 12) -> List[InstagramPost]:
        """Scrape posts by scrolling the post grid"""
        if not await self._ensure_on_profile(username):
            return []
        
        posts = []
        last_count = 0
        scroll_attempts = 0
        max_scrolls = (count // 3) + 5  # 3 posts per row
        
        while len(posts) < count and scroll_attempts < max_scrolls:
            # Get current HTML and parse posts
            html = await self._page.content()
            posts = self.parser.parse_posts_from_html(html)
            
            if len(posts) >= count or len(posts) == last_count:
                break
            
            last_count = len(posts)
            
            # Scroll down
            await self._page.evaluate('window.scrollBy(0, window.innerHeight)')
            await self._page.wait_for_timeout(1500)
            scroll_attempts += 1
        
        return posts[:count]
    
    async def get_followers(self, username: str, count: int = 100) -> List[Dict]:
        """Get followers by opening modal and scrolling"""
        return await self._get_social_list(username, "followers", count)
    
    async def get_following(self, username: str, count: int = 100) -> List[Dict]:
        """Get following by opening modal and scrolling"""
        return await self._get_social_list(username, "following", count)
    
    # ==================== HELPERS ====================
    
    async def _ensure_on_profile(self, username: str) -> bool:
        """Make sure we're on the user's profile page"""
        current_url = self._page.url
        target = f"/{username}/"
        
        if target not in current_url:
            url = f"{self.INSTAGRAM_URL}/{username}/"
            await self._page.goto(url, wait_until='networkidle', timeout=30000)
            await self._dismiss_cookie_banner()
            
            if await self._is_login_wall():
                return False
        
        return True
    
    async def _get_social_list(self, username: str, list_type: str, count: int) -> List[Dict]:
        """Open followers/following modal and scroll to collect users"""
        if not self.cookies:
            print(f"  [!] Cookies required for {list_type}")
            return []
        
        if not await self._ensure_on_profile(username):
            return []
        
        # Click on followers/following link
        try:
            selector = f'a[href*="/{list_type}"]'
            link = self._page.locator(selector).first
            await link.click()
            await self._page.wait_for_timeout(2000)
        except Exception as e:
            print(f"  [!] Could not open {list_type} modal: {e}")
            return []
        
        # Scroll modal to collect users
        users = []
        scroll_attempts = 0
        max_scrolls = (count // 10) + 5
        
        while len(users) < count and scroll_attempts < max_scrolls:
            # Get users from modal
            items = await self._page.query_selector_all('div[role="dialog"] a[href*="/"]')
            
            for item in items:
                href = await item.get_attribute('href')
                if href and href.startswith('/') and '/p/' not in href:
                    uname = href.strip('/')
                    if uname and uname not in [u['username'] for u in users]:
                        text_content = await item.inner_text()
                        users.append({
                            'username': uname,
                            'full_name': text_content,
                        })
            
            # Scroll modal
            modal_scroll = self._page.locator(', '.join(MODAL_SCROLL_CONTAINER)).first
            try:
                await modal_scroll.evaluate('el => el.scrollTop = el.scrollHeight')
            except Exception:
                # Fallback scroll
                await self._page.keyboard.press('End')
            
            await self._page.wait_for_timeout(1500)
            scroll_attempts += 1
        
        # Close modal
        try:
            close_btn = self._page.locator(', '.join(MODAL_CLOSE_SELECTORS)).first
            await close_btn.click()
        except Exception:
            await self._page.keyboard.press('Escape')
        
        return users[:count]
    
    async def _extract_from_js(self, username: str) -> Optional[InstagramProfile]:
        """Extract profile data from page's JavaScript context"""
        try:
            # Try to get data from window.__additionalData or _sharedData
            data = await self._page.evaluate("""() => {
                // Try SharedData
                if (window._sharedData) {
                    const pages = window._sharedData.entry_data?.ProfilePage;
                    if (pages && pages[0]) {
                        return pages[0].graphql?.user || pages[0].user || null;
                    }
                }
                
                // Try to find user data in any global
                for (const key of Object.keys(window)) {
                    try {
                        const val = window[key];
                        if (val && typeof val === 'object' && val.username) {
                            return val;
                        }
                    } catch(e) {}
                }
                
                return null;
            }""")
            
            if data and isinstance(data, dict):
                return self.parser._user_dict_to_profile(data, username)
        except Exception:
            pass
        
        return None
    
    async def _dismiss_cookie_banner(self):
        """Try to dismiss cookie consent banner"""
        for selector in COOKIE_BANNER_SELECTORS:
            try:
                btn = self._page.locator(selector).first
                if await btn.is_visible(timeout=2000):
                    await btn.click()
                    await self._page.wait_for_timeout(500)
                    return
            except Exception:
                continue
    
    async def _is_login_wall(self) -> bool:
        """Check if login wall is shown"""
        for selector in LOGIN_WALL_SELECTORS[:3]:
            try:
                el = self._page.locator(selector).first
                if await el.is_visible(timeout=2000):
                    return True
            except Exception:
                continue
        return False


# ==================== SYNC WRAPPER ====================

def scrape_profile_browser(username: str, cookies_file: Optional[str] = None) -> Optional[InstagramProfile]:
    """Synchronous wrapper for browser scraping"""
    async def _run():
        async with InstagramBrowserScraper(cookies_file=cookies_file) as scraper:
            return await scraper.get_profile(username)
    
    return asyncio.run(_run())
