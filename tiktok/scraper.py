"""
TikTok Scraper
Core scraping functionality untuk profile, following, dan followers
"""

import json
import asyncio
from pathlib import Path
from typing import Optional, List, Dict

from .models import TikTokProfile
from .browser import BrowserManager
from .parsers import parse_profile_data
from .utils import load_cookies


# CAPTCHA detection selectors
CAPTCHA_SELECTORS = [
    'div[class*="captcha"]',
    'div[id*="captcha"]',
    '#captcha-verify-container',
    '#captcha_container',
    'div[class*="Verify"]',
    'div[data-e2e*="verify"]',
    'iframe[src*="captcha"]',
    'div[class*="secsdk"]',
]


class TikTokScraper:
    """
    TikTok Profile & Social Scraper
    
    Usage:
        async with TikTokScraper() as scraper:
            profile = await scraper.get_profile("username")
            followers = await scraper.get_followers("username", max_count=50)
    """
    
    def __init__(
        self, 
        headless: bool = True, 
        cookies_file: Optional[str] = None,
        proxy_file: Optional[str] = None
    ):
        self.browser_manager = BrowserManager(
            headless=headless,
            proxy_file=proxy_file
        )
        self.cookies: List[Dict] = []
        
        if cookies_file:
            self.cookies = load_cookies(cookies_file)
    
    async def __aenter__(self):
        await self.browser_manager.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.browser_manager.close()
    
    # ==================== CAPTCHA HANDLING ====================
    
    async def _detect_captcha(self, page) -> bool:
        """Check if CAPTCHA is present on page"""
        # Check DOM selectors
        for selector in CAPTCHA_SELECTORS:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    return True
            except:
                continue
        
        # Check page content
        try:
            html = await page.content()
            html_lower = html.lower()
            if any(keyword in html_lower for keyword in [
                'captcha', 'verify your identity', 'security check',
                'verifikasi', 'secsdk-captcha'
            ]):
                return True
        except:
            pass
        
        return False
    
    async def _wait_for_captcha_solved(self, page, timeout: float = 300.0) -> bool:
        """
        Wait for user to manually solve CAPTCHA.
        
        Args:
            page: Playwright page
            timeout: Max wait time in seconds (default: 5 minutes)
        
        Returns:
            True if CAPTCHA solved, False if timeout
        """
        if not await self._detect_captcha(page):
            return True  # No CAPTCHA, continue
        
        print("\n" + "=" * 50)
        print("[!] CAPTCHA DETECTED!")
        print("[!] Silakan solve CAPTCHA secara manual di browser...")
        print("[!] Scraper akan otomatis lanjut setelah CAPTCHA selesai.")
        print(f"[!] Timeout: {int(timeout)} detik")
        print("=" * 50)
        
        elapsed = 0.0
        check_interval = 2.0
        
        while elapsed < timeout:
            await asyncio.sleep(check_interval)
            elapsed += check_interval
            
            # Check if CAPTCHA is gone
            if not await self._detect_captcha(page):
                print(f"\n[+] CAPTCHA solved! Melanjutkan scraping...")
                await asyncio.sleep(2)  # Small delay after solve
                return True
            
            remaining = int(timeout - elapsed)
            print(f"[~] Menunggu CAPTCHA diselesaikan... ({remaining}s remaining)", end='\r')
        
        print(f"\n[X] Timeout! CAPTCHA tidak diselesaikan dalam {int(timeout)} detik")
        return False
    
    # ==================== PROFILE SCRAPING ====================
    
    async def get_profile(self, username: str, save_debug: bool = False) -> Optional[TikTokProfile]:
        """
        Dapatkan profil TikTok user
        
        Args:
            username: Username TikTok (tanpa @)
            save_debug: Simpan HTML untuk debugging
            
        Returns:
            TikTokProfile atau None jika gagal
        """
        url = f"https://www.tiktok.com/@{username}"
        print(f"[~] Mengakses: {url}")
        
        context, page = await self.browser_manager.new_page()
        
        try:
            response = await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            print(f"[~] HTTP Status: {response.status if response else 'N/A'}")
            
            await page.wait_for_load_state('networkidle', timeout=15000)
            await page.wait_for_timeout(3000)
            
            # Cek apakah avatar muncul (indikator halaman ready)
            try:
                await page.wait_for_selector('img[class*="Avatar"], img[class*="avatar"]', timeout=5000)
                print("[+] Profile avatar found")
            except:
                pass
            
            html = await page.content()
            
            # Debug
            if save_debug:
                debug_path = f"debug_{username}_playwright.html"
                Path(debug_path).write_text(html, encoding='utf-8')
                print(f"[+] Debug HTML saved: {debug_path}")
            
            # Parse profile
            profile = parse_profile_data(html, username)
            
            if profile:
                print("[+] Data JSON ditemukan!")
                return profile
            
            # Check for CAPTCHA
            html_lower = html.lower()
            if "captcha" in html_lower or "verify" in html_lower:
                solved = await self._wait_for_captcha_solved(page)
                if solved:
                    # Re-fetch page content after CAPTCHA solved
                    html = await page.content()
                    profile = parse_profile_data(html, username)
                    if profile:
                        print("[+] Data JSON ditemukan setelah CAPTCHA!")
                        return profile
                    print("[!] CAPTCHA solved tapi data profil tidak ditemukan")
                return None
            elif "couldn't find this account" in html_lower:
                print(f"[!] Akun @{username} tidak ditemukan")
            else:
                print("[!] Tidak dapat parse data profil")
            
            return None
            
        except Exception as e:
            print(f"[X] Error: {e}")
            return None
        finally:
            await context.close()
    
    # ==================== FOLLOWING SCRAPING ====================
    
    async def get_following(self, username: str, max_count: int = 100) -> List[Dict]:
        """
        Dapatkan daftar following dari user TikTok
        
        Args:
            username: Username TikTok (tanpa @)
            max_count: Maksimal jumlah following
            
        Returns:
            List of dict dengan info user yang di-follow
        """
        return await self._scrape_user_list(
            username=username,
            max_count=max_count,
            tab_type="following",
            tab_selectors=[
                '[data-e2e="following-count"]',
                'a[href*="/following"]',
            ]
        )
    
    # ==================== FOLLOWERS SCRAPING ====================
    
    async def get_followers(self, username: str, max_count: int = 100) -> List[Dict]:
        """
        Dapatkan daftar followers dari user TikTok
        
        Args:
            username: Username TikTok (tanpa @)
            max_count: Maksimal jumlah followers
            
        Returns:
            List of dict dengan info user followers
        """
        return await self._scrape_user_list(
            username=username,
            max_count=max_count,
            tab_type="followers",
            tab_selectors=[
                '[data-e2e="followers-count"]',
                'a[href*="/followers"]',
            ]
        )
    
    # ==================== INTERNAL HELPERS ====================
    
    async def _scrape_user_list(
        self,
        username: str,
        max_count: int,
        tab_type: str,
        tab_selectors: List[str]
    ) -> List[Dict]:
        """Internal: Scrape following/followers list"""
        
        url = f"https://www.tiktok.com/@{username}"
        print(f"[~] Mengakses profil: @{username}")
        
        context, page = await self.browser_manager.new_page(cookies=self.cookies)
        user_list = []
        
        try:
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_load_state('networkidle', timeout=15000)
            await page.wait_for_timeout(2000)
            
            # Check for CAPTCHA and wait if detected
            await self._wait_for_captcha_solved(page)
            
            # Klik tab
            print(f"[~] Mencari tab {tab_type.capitalize()}...")
            clicked = False
            
            for selector in tab_selectors:
                try:
                    element = await page.wait_for_selector(selector, timeout=3000)
                    if element:
                        await element.click()
                        clicked = True
                        print(f"[+] Tab {tab_type.capitalize()} diklik")
                        break
                except:
                    continue
            
            if not clicked:
                print(f"[X] Tidak dapat menemukan tab {tab_type.capitalize()}")
                return []
            
            await page.wait_for_timeout(3000)
            
            # Cari modal
            modal = await self._find_modal(page)
            
            # Screenshot debug
            await page.screenshot(path=f'debug_{username}_{tab_type}.png')
            print(f"[+] Screenshot: debug_{username}_{tab_type}.png")
            
            # Cek private
            if modal:
                try:
                    modal_html = await modal.inner_html()
                    if "list is private" in modal_html.lower() or "currently hidden" in modal_html.lower():
                        print(f"[!] {tab_type.capitalize()} list is private")
                        return []
                except:
                    pass
            
            # Scroll dan kumpulkan data
            print(f"[~] Mengumpulkan {tab_type} (max: {max_count})...")
            user_list = await self._collect_users(page, modal, username, max_count)
            
            print(f"\n[+] Total {tab_type} ditemukan: {len(user_list)}")
            return user_list
            
        except Exception as e:
            print(f"[X] Error: {e}")
            return user_list
        finally:
            await context.close()
    
    async def _find_modal(self, page):
        """Find modal dialog on page"""
        modal_selectors = [
            '[data-e2e="user-list-modal"]',
            '[class*="DivUserListContainer"]',
            'div[role="dialog"]',
            '[class*="Modal"]',
        ]
        
        for selector in modal_selectors:
            try:
                modal = await page.wait_for_selector(selector, timeout=5000)
                if modal:
                    print("[+] Modal ditemukan")
                    return modal
            except:
                continue
        return None
    
    async def _collect_users(self, page, modal, skip_username: str, max_count: int) -> List[Dict]:
        """Collect users from modal with scrolling"""
        collected = set()
        users = []
        scroll_attempts = 0
        max_attempts = 50
        no_new_count = 0
        
        while len(users) < max_count and scroll_attempts < max_attempts:
            # Find user links
            items = []
            if modal:
                try:
                    items = await modal.query_selector_all('a[href*="/@"]')
                except:
                    pass
            
            if not items:
                for sel in ['div[role="dialog"] a[href*="/@"]', '[class*="Modal"] a[href*="/@"]']:
                    try:
                        items = await page.query_selector_all(sel)
                        if items:
                            break
                    except:
                        continue
            
            # Extract data
            last_count = len(users)
            for item in items:
                if len(users) >= max_count:
                    break
                
                try:
                    href = await item.get_attribute('href')
                    if href and '/@' in href:
                        item_username = href.split('/@')[-1].split('?')[0].split('/')[0]
                        
                        if item_username.lower() == skip_username.lower():
                            continue
                        
                        if item_username and item_username not in collected:
                            collected.add(item_username)
                            users.append({
                                'username': item_username,
                                'profile_url': f"https://www.tiktok.com/@{item_username}"
                            })
                except:
                    continue
            
            # Check progress
            if len(users) == last_count:
                no_new_count += 1
                if no_new_count >= 5:
                    break
            else:
                no_new_count = 0
            
            # Scroll
            if modal:
                try:
                    await modal.evaluate('el => el.scrollTop += 400')
                except:
                    await page.evaluate('window.scrollBy(0, 400)')
            else:
                await page.evaluate('window.scrollBy(0, 400)')
            
            await page.wait_for_timeout(800)
            scroll_attempts += 1
            print(f"[~] Terkumpul: {len(users)} users (scroll: {scroll_attempts})", end='\r')
        
        return users
    
    # ==================== UTILITY METHODS ====================
    
    def save_profile(self, profile: TikTokProfile, output_dir: str = ".") -> str:
        """Simpan profil ke file JSON"""
        output_path = Path(output_dir) / f"tiktok_{profile.username}.json"
        output_path.write_text(
            json.dumps(profile.to_dict(), indent=2, ensure_ascii=False),
            encoding='utf-8'
        )
        return str(output_path)
    
    def save_user_list(self, users: List[Dict], username: str, list_type: str, output_dir: str = ".") -> str:
        """Simpan following/followers list ke file JSON"""
        output_path = Path(output_dir) / f"tiktok_{username}_{list_type}.json"
        output_path.write_text(
            json.dumps(users, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )
        return str(output_path)
