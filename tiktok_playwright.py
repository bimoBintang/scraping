"""
TikTok Profile Scraper - Playwright Version
Menggunakan browser automation untuk bypass proteksi anti-bot TikTok
"""

import json
import re
import argparse
import asyncio
from dataclasses import dataclass, asdict
from typing import Optional, Dict, List
from pathlib import Path

try:
    from playwright.async_api import async_playwright, Page, Browser
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("[!] Playwright tidak terinstall. Jalankan: pip install playwright")
    print("    Lalu: playwright install chromium")


@dataclass
class TikTokProfile:
    """Data class untuk menyimpan informasi profil TikTok"""
    username: str
    nickname: str = "N/A"
    followers: int = 0
    following: int = 0
    likes: int = 0
    video_count: int = 0
    bio: str = ""
    verified: bool = False
    private: bool = False
    avatar_url: str = ""

    def formatted_stats(self) -> Dict[str, str]:
        """Return stats dengan format K/M/B"""
        return {
            "followers": self._format_number(self.followers),
            "following": self._format_number(self.following),
            "likes": self._format_number(self.likes),
            "videos": self._format_number(self.video_count),
        }

    @staticmethod
    def _format_number(num: int) -> str:
        """Format angka dengan K, M, B"""
        if num >= 1_000_000_000:
            return f"{num/1_000_000_000:.1f}B"
        elif num >= 1_000_000:
            return f"{num/1_000_000:.1f}M"
        elif num >= 1_000:
            return f"{num/1_000:.1f}K"
        return str(num)

    def __str__(self) -> str:
        stats = self.formatted_stats()
        status = "[PRIVATE]" if self.private else ("[VERIFIED]" if self.verified else "")
        return f"""
+--------------------------------------------------+
| TikTok Profile: @{self.username}
+--------------------------------------------------+
| Nickname  : {self.nickname}
| Followers : {stats['followers']}
| Following : {stats['following']}
| Likes     : {stats['likes']}
| Videos    : {stats['videos']}
| Bio       : {self.bio[:50]}{'...' if len(self.bio) > 50 else ''}
| {status}
+--------------------------------------------------+"""

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        data = asdict(self)
        data['formatted_stats'] = self.formatted_stats()
        return data


class TikTokPlaywrightScraper:
    """Scraper TikTok menggunakan browser automation"""
    
    JSON_PATTERNS = [
        r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">(.*?)</script>',
        r'<script id="SIGI_STATE" type="application/json">(.*?)</script>',
    ]
    
    def __init__(self, headless: bool = True, slow_mo: int = 0, cookies_file: Optional[str] = None):
        self.headless = headless
        self.slow_mo = slow_mo
        self.cookies_file = cookies_file
        self.cookies: List[Dict] = []
        self.browser: Optional[Browser] = None
        self.playwright = None
        
        # Load cookies jika ada
        if cookies_file:
            self._load_cookies(cookies_file)
    
    def _load_cookies(self, cookies_file: str) -> None:
        """Load cookies dari file JSON (EditThisCookie format)"""
        try:
            with open(cookies_file, 'r', encoding='utf-8') as f:
                raw_cookies = json.load(f)
            
            # Convert dari EditThisCookie format ke Playwright format
            self.cookies = []
            for cookie in raw_cookies:
                pw_cookie = {
                    'name': cookie.get('name', ''),
                    'value': cookie.get('value', ''),
                    'domain': cookie.get('domain', '.tiktok.com'),
                    'path': cookie.get('path', '/'),
                }
                
                # Optional fields
                if 'expirationDate' in cookie:
                    pw_cookie['expires'] = cookie['expirationDate']
                if 'secure' in cookie:
                    pw_cookie['secure'] = cookie['secure']
                if 'httpOnly' in cookie:
                    pw_cookie['httpOnly'] = cookie['httpOnly']
                if 'sameSite' in cookie:
                    # Playwright expects: 'Strict', 'Lax', 'None'
                    sameSite = cookie['sameSite']
                    if sameSite in ['Strict', 'Lax', 'None']:
                        pw_cookie['sameSite'] = sameSite
                    elif sameSite == 'no_restriction':
                        pw_cookie['sameSite'] = 'None'
                    else:
                        pw_cookie['sameSite'] = 'Lax'
                
                self.cookies.append(pw_cookie)
            
            print(f"[+] Loaded {len(self.cookies)} cookies from {cookies_file}")
        except FileNotFoundError:
            print(f"[!] Cookie file not found: {cookies_file}")
        except json.JSONDecodeError as e:
            print(f"[!] Error parsing cookie file: {e}")
        except Exception as e:
            print(f"[!] Error loading cookies: {e}")
    
    async def __aenter__(self):
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def start(self):
        """Start browser with anti-detection measures"""
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright tidak tersedia. Install dengan: pip install playwright")
        
        self.playwright = await async_playwright().start()
        
        # Anti-detection arguments
        args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-dev-shm-usage',
            '--disable-infobars',
            '--disable-background-networking',
            '--disable-default-apps',
            '--disable-extensions',
            '--disable-gpu',
            '--disable-sync',
            '--no-first-run',
            '--no-sandbox',
            '--disable-setuid-sandbox',
        ]
        
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            slow_mo=self.slow_mo,
            args=args
        )
        print("[+] Browser started" + (" (headless)" if self.headless else " (visible)"))
    
    async def close(self):
        """Close browser"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        print("[+] Browser closed")
    
    def _extract_json_data(self, html: str) -> Optional[Dict]:
        """Ekstrak data JSON dari HTML"""
        for pattern in self.JSON_PATTERNS:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue
        return None
    
    def _parse_universal_data(self, data: Dict, username: str) -> Optional[TikTokProfile]:
        """Parse data dari format __UNIVERSAL_DATA_FOR_REHYDRATION__"""
        try:
            if '__DEFAULT_SCOPE__' not in data:
                return None
            
            scope = data['__DEFAULT_SCOPE__']
            if 'webapp.user-detail' not in scope:
                return None
            
            user_detail = scope['webapp.user-detail']
            if 'userInfo' not in user_detail:
                return None
            
            user_info = user_detail['userInfo'].get('user', {})
            stats = user_detail['userInfo'].get('stats', {})
            
            return TikTokProfile(
                username=user_info.get('uniqueId', username),
                nickname=user_info.get('nickname', 'N/A'),
                followers=stats.get('followerCount', 0),
                following=stats.get('followingCount', 0),
                likes=stats.get('heartCount', 0),
                video_count=stats.get('videoCount', 0),
                bio=user_info.get('signature', ''),
                verified=user_info.get('verified', False),
                private=user_info.get('privateAccount', False),
                avatar_url=user_info.get('avatarLarger', '')
            )
        except Exception as e:
            print(f"[!] Error parsing data: {e}")
            return None
    
    def _parse_sigi_data(self, data: Dict, username: str) -> Optional[TikTokProfile]:
        """Parse data dari format SIGI_STATE"""
        try:
            if 'UserModule' not in data:
                return None
            
            users = data['UserModule'].get('users', {})
            stats_module = data['UserModule'].get('stats', {})
            
            # Cari user yang cocok
            user_key = None
            for key in users.keys():
                if username.lower() in key.lower():
                    user_key = key
                    break
            
            if not user_key:
                return None
            
            user_info = users[user_key]
            user_stats = stats_module.get(user_key, {})
            
            return TikTokProfile(
                username=user_info.get('uniqueId', username),
                nickname=user_info.get('nickname', 'N/A'),
                followers=user_stats.get('followerCount', user_info.get('follower', 0)),
                following=user_stats.get('followingCount', user_info.get('following', 0)),
                likes=user_stats.get('heartCount', user_info.get('heart', 0)),
                video_count=user_stats.get('videoCount', 0),
                bio=user_info.get('signature', ''),
                verified=user_info.get('verified', False),
                private=user_info.get('privateAccount', False),
                avatar_url=user_info.get('avatarLarger', '')
            )
        except Exception as e:
            print(f"[!] Error parsing SIGI data: {e}")
            return None
    
    async def get_profile(self, username: str, save_debug: bool = False) -> Optional[TikTokProfile]:
        """Dapatkan profil TikTok menggunakan browser"""
        if not self.browser:
            raise RuntimeError("Browser not started. Call start() first")
        
        url = f"https://www.tiktok.com/@{username}"
        print(f"[~] Mengakses: {url}")
        
        context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/New_York'
        )
        
        page = await context.new_page()
        
        try:
            # Navigate ke halaman profil
            response = await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            
            if not response:
                print("[X] No response from server")
                return None
            
            print(f"[~] HTTP Status: {response.status}")
            
            # Tunggu halaman sepenuhnya dimuat
            await page.wait_for_load_state('networkidle', timeout=15000)
            
            # Tunggu konten tambahan
            await page.wait_for_timeout(3000)
            
            # Coba tunggu elemen profile muncul (optional, tidak error jika tidak ada)
            try:
                await page.wait_for_selector('[data-e2e="user-avatar"]', timeout=5000)
                print("[+] Profile avatar found")
            except:
                print("[~] Avatar not found, checking for data...")
            
            # Ambil HTML
            html = await page.content()
            
            # Debug save
            if save_debug:
                Path(f'debug_{username}_playwright.html').write_text(html, encoding='utf-8')
                print(f"[+] HTML disimpan: debug_{username}_playwright.html")
            
            # Ekstrak JSON - coba langsung tanpa pengecekan dulu
            data = self._extract_json_data(html)
            
            if data:
                print("[+] Data JSON ditemukan!")
                
                # Cek apakah ada error dalam data
                if '__DEFAULT_SCOPE__' in data:
                    scope = data['__DEFAULT_SCOPE__']
                    if 'webapp.user-detail' in scope:
                        user_detail = scope['webapp.user-detail']
                        # Cek status code dari API
                        if user_detail.get('statusCode') == 10202:
                            print("[X] User not found (status 10202)")
                            return None
                
                # Parse data
                profile = self._parse_universal_data(data, username)
                if not profile:
                    profile = self._parse_sigi_data(data, username)
                
                if profile:
                    return profile
                else:
                    print("[!] Data found but parse failed - saving debug")
                    if not save_debug:
                        Path(f'debug_{username}_fail.html').write_text(html, encoding='utf-8')
            else:
                # Tidak ada JSON, cek error di halaman
                html_lower = html.lower()
                if "captcha" in html_lower or "verify" in html_lower:
                    print("[!] CAPTCHA detected - try running with --visible flag")
                else:
                    print("[X] Could not find JSON data in page")
            
            return None
            
        except Exception as e:
            print(f"[X] Error: {e}")
            return None
        finally:
            await context.close()
    
    async def get_following(self, username: str, max_count: int = 100) -> List[Dict]:
        """
        Dapatkan daftar following dari user TikTok
        
        Args:
            username: Username TikTok tanpa @
            max_count: Maksimal jumlah following yang diambil (default 100)
        
        Returns:
            List of dict dengan info user yang di-follow
        """
        if not self.browser:
            raise RuntimeError("Browser not started. Call start() first")
        
        url = f"https://www.tiktok.com/@{username}"
        print(f"[~] Mengakses profil: @{username}")
        
        context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/New_York'
        )
        
        # Inject cookies jika ada
        if self.cookies:
            await context.add_cookies(self.cookies)
            print(f"[+] {len(self.cookies)} cookies injected")
        
        page = await context.new_page()
        following_list = []
        
        try:
            # Navigate ke halaman profil
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_load_state('networkidle', timeout=15000)
            await page.wait_for_timeout(2000)
            
            # Klik tab Following
            print("[~] Mencari tab Following...")
            
            # Cari link following dengan berbagai selector
            following_selectors = [
                '[data-e2e="following-count"]',
                'a[href*="/following"]',
                'strong:has-text("Following")',
                'span:has-text("Following")',
            ]
            
            clicked = False
            for selector in following_selectors:
                try:
                    element = await page.wait_for_selector(selector, timeout=3000)
                    if element:
                        await element.click()
                        clicked = True
                        print("[+] Tab Following diklik")
                        break
                except:
                    continue
            
            if not clicked:
                print("[X] Tidak dapat menemukan tab Following")
                return []
            
            # Tunggu modal muncul dengan selector yang lebih spesifik
            await page.wait_for_timeout(2000)
            
            # TikTok following modal biasanya muncul dalam overlay/dialog
            modal_selectors = [
                '[data-e2e="user-list-modal"]',
                '[class*="DivUserListContainer"]',
                '[class*="UserListModal"]',
                'div[role="dialog"]',
                '[class*="Modal"]',
            ]
            
            modal = None
            for selector in modal_selectors:
                try:
                    modal = await page.wait_for_selector(selector, timeout=5000)
                    if modal:
                        print(f"[+] Modal following ditemukan")
                        break
                except:
                    continue
            
            if not modal:
                print("[!] Modal tidak ditemukan, mencoba cara alternatif...")
            
            # Tunggu list user dimuat
            await page.wait_for_timeout(3000)
            
            # Debug: simpan screenshot dan HTML modal
            await page.screenshot(path=f'debug_{username}_modal.png')
            print(f"[+] Screenshot disimpan: debug_{username}_modal.png")
            
            # Dump modal HTML untuk debug
            if modal:
                try:
                    modal_html = await modal.inner_html()
                    Path(f'debug_{username}_modal.html').write_text(modal_html[:10000], encoding='utf-8')
                    print(f"[+] Modal HTML disimpan: debug_{username}_modal.html")
                except:
                    pass
            
            # Scroll dan kumpulkan data dari dalam modal
            print(f"[~] Mengumpulkan following (max: {max_count})...")
            
            collected_usernames = set()
            scroll_attempts = 0
            max_scroll_attempts = 30
            last_count = 0
            no_new_data_count = 0
            
            while len(following_list) < max_count and scroll_attempts < max_scroll_attempts:
                # Cari SEMUA link dalam modal dengan berbagai cara
                user_items = []
                
                # Method 1: Dari modal langsung
                if modal:
                    try:
                        user_items = await modal.query_selector_all('a[href*="/@"]')
                        if user_items:
                            print(f"[+] Found {len(user_items)} links in modal") if scroll_attempts == 0 else None
                    except:
                        pass
                
                # Method 2: Selector spesifik
                if not user_items:
                    selectors_to_try = [
                        'div[role="dialog"] a[href*="/@"]',
                        '[class*="Modal"] a[href*="/@"]',
                        '[class*="UserList"] a[href*="/@"]',
                        '[class*="follow"] a[href*="/@"]',
                    ]
                    for sel in selectors_to_try:
                        try:
                            user_items = await page.query_selector_all(sel)
                            if user_items and len(user_items) > 0:
                                print(f"[+] Found {len(user_items)} with: {sel}") if scroll_attempts == 0 else None
                                break
                        except:
                            continue
                
                # Method 3: Cari semua link di halaman yang ada dalam area modal
                if not user_items:
                    scroll_attempts += 1
                    await page.wait_for_timeout(1000)
                    continue
                
                for item in user_items:
                    if len(following_list) >= max_count:
                        break
                    
                    try:
                        href = await item.get_attribute('href')
                        if href and href.startswith('/@'):
                            item_username = href.replace('/@', '').split('?')[0].split('/')[0]
                            
                            # Skip jika username adalah target user sendiri
                            if item_username.lower() == username.lower():
                                continue
                            
                            if item_username and item_username not in collected_usernames:
                                collected_usernames.add(item_username)
                                
                                user_data = {
                                    'username': item_username,
                                    'profile_url': f"https://www.tiktok.com/@{item_username}"
                                }
                                
                                # Coba ambil info tambahan dari parent element
                                try:
                                    parent = await item.evaluate_handle('el => el.closest("[class*=UserItem], [class*=user-card], [class*=Container]")')
                                    if parent:
                                        # Coba ambil avatar
                                        avatar_el = await parent.query_selector('img')
                                        if avatar_el:
                                            user_data['avatar'] = await avatar_el.get_attribute('src')
                                        
                                        # Coba ambil nickname - biasanya di element terpisah
                                        text_content = await parent.inner_text()
                                        lines = [l.strip() for l in text_content.split('\n') if l.strip() and l.strip() != item_username]
                                        if lines:
                                            user_data['nickname'] = lines[0][:50]
                                except:
                                    pass
                                
                                following_list.append(user_data)
                    except:
                        continue
                
                # Cek apakah ada data baru
                if len(following_list) == last_count:
                    no_new_data_count += 1
                    if no_new_data_count >= 5:
                        print(f"\n[~] Tidak ada data baru setelah {no_new_data_count} scroll")
                        break
                else:
                    no_new_data_count = 0
                    last_count = len(following_list)
                
                # Scroll dalam modal (bukan halaman utama)
                if modal:
                    try:
                        await modal.evaluate('el => el.scrollTop += 300')
                    except:
                        await page.evaluate('window.scrollBy(0, 300)')
                else:
                    await page.evaluate('window.scrollBy(0, 300)')
                
                await page.wait_for_timeout(800)
                scroll_attempts += 1
                
                print(f"[~] Terkumpul: {len(following_list)} users (scroll: {scroll_attempts})", end='\r')
            
            print(f"\n[+] Total following ditemukan: {len(following_list)}")
            return following_list
            
        except Exception as e:
            print(f"[X] Error: {e}")
            return following_list
        finally:
            await context.close()
    
    async def get_followers(self, username: str, max_count: int = 100) -> List[Dict]:
        """
        Dapatkan daftar followers dari user TikTok
        
        Args:
            username: Username TikTok tanpa @
            max_count: Maksimal jumlah followers yang diambil (default 100)
        
        Returns:
            List of dict dengan info user yang follow akun tersebut
        """
        if not self.browser:
            raise RuntimeError("Browser not started. Call start() first")
        
        url = f"https://www.tiktok.com/@{username}"
        print(f"[~] Mengakses profil: @{username}")
        
        context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/New_York'
        )
        
        # Inject cookies jika ada
        if self.cookies:
            await context.add_cookies(self.cookies)
            print(f"[+] {len(self.cookies)} cookies injected")
        
        page = await context.new_page()
        followers_list = []
        
        try:
            # Navigate ke halaman profil
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_load_state('networkidle', timeout=15000)
            await page.wait_for_timeout(2000)
            
            # Klik tab Followers
            print("[~] Mencari tab Followers...")
            
            followers_selectors = [
                '[data-e2e="followers-count"]',
                'a[href*="/followers"]',
                'strong:has-text("Followers")',
                'span:has-text("Followers")',
            ]
            
            clicked = False
            for selector in followers_selectors:
                try:
                    element = await page.wait_for_selector(selector, timeout=3000)
                    if element:
                        await element.click()
                        clicked = True
                        print("[+] Tab Followers diklik")
                        break
                except:
                    continue
            
            if not clicked:
                print("[X] Tidak dapat menemukan tab Followers")
                return []
            
            # Tunggu modal muncul
            await page.wait_for_timeout(3000)
            
            # Cari modal
            modal_selectors = [
                '[data-e2e="user-list-modal"]',
                '[class*="DivUserListContainer"]',
                '[class*="UserListModal"]',
                'div[role="dialog"]',
                '[class*="Modal"]',
            ]
            
            modal = None
            for selector in modal_selectors:
                try:
                    modal = await page.wait_for_selector(selector, timeout=5000)
                    if modal:
                        print("[+] Modal followers ditemukan")
                        break
                except:
                    continue
            
            # Screenshot untuk debug
            await page.screenshot(path=f'debug_{username}_followers.png')
            print(f"[+] Screenshot: debug_{username}_followers.png")
            
            # Cek apakah private - hanya cek dalam modal, bukan seluruh halaman
            if modal:
                try:
                    modal_html = await modal.inner_html()
                    if "list is private" in modal_html.lower() or "currently hidden" in modal_html.lower():
                        print("[!] Followers list is private")
                        return []
                except:
                    pass
            
            # Scroll dan kumpulkan data
            print(f"[~] Mengumpulkan followers (max: {max_count})...")
            
            collected_usernames = set()
            scroll_attempts = 0
            max_scroll_attempts = 50
            last_count = 0
            no_new_data_count = 0
            
            while len(followers_list) < max_count and scroll_attempts < max_scroll_attempts:
                user_items = []
                
                # Cari user items dalam modal
                if modal:
                    try:
                        user_items = await modal.query_selector_all('a[href*="/@"]')
                    except:
                        pass
                
                if not user_items:
                    selectors_to_try = [
                        'div[role="dialog"] a[href*="/@"]',
                        '[class*="Modal"] a[href*="/@"]',
                        '[class*="UserList"] a[href*="/@"]',
                    ]
                    for sel in selectors_to_try:
                        try:
                            user_items = await page.query_selector_all(sel)
                            if user_items and len(user_items) > 0:
                                break
                        except:
                            continue
                
                for item in user_items:
                    if len(followers_list) >= max_count:
                        break
                    
                    try:
                        href = await item.get_attribute('href')
                        if href and '/@' in href:
                            item_username = href.split('/@')[-1].split('?')[0].split('/')[0]
                            
                            if item_username.lower() == username.lower():
                                continue
                            
                            if item_username and item_username not in collected_usernames:
                                collected_usernames.add(item_username)
                                
                                user_data = {
                                    'username': item_username,
                                    'profile_url': f"https://www.tiktok.com/@{item_username}"
                                }
                                
                                try:
                                    parent = await item.evaluate_handle('el => el.closest("[class*=UserItem], [class*=user-card], [class*=Container]")')
                                    if parent:
                                        avatar_el = await parent.query_selector('img')
                                        if avatar_el:
                                            user_data['avatar'] = await avatar_el.get_attribute('src')
                                except:
                                    pass
                                
                                followers_list.append(user_data)
                    except:
                        continue
                
                # Cek progress
                if len(followers_list) == last_count:
                    no_new_data_count += 1
                    if no_new_data_count >= 5:
                        print(f"\n[~] Tidak ada data baru setelah {no_new_data_count} scroll")
                        break
                else:
                    no_new_data_count = 0
                    last_count = len(followers_list)
                
                # Scroll dalam modal
                if modal:
                    try:
                        await modal.evaluate('el => el.scrollTop += 400')
                    except:
                        await page.evaluate('window.scrollBy(0, 400)')
                else:
                    await page.evaluate('window.scrollBy(0, 400)')
                
                await page.wait_for_timeout(800)
                scroll_attempts += 1
                
                print(f"[~] Terkumpul: {len(followers_list)} followers (scroll: {scroll_attempts})", end='\r')
            
            print(f"\n[+] Total followers ditemukan: {len(followers_list)}")
            return followers_list
            
        except Exception as e:
            print(f"[X] Error: {e}")
            return followers_list
        finally:
            await context.close()
    
    async def get_multiple_profiles(self, usernames: List[str]) -> Dict[str, Optional[TikTokProfile]]:
        """Dapatkan profil untuk multiple users"""
        results = {}
        for username in usernames:
            print(f"\n{'='*50}")
            results[username] = await self.get_profile(username)
        return results
    
    def save_profile(self, profile: TikTokProfile, output_dir: str = ".") -> str:
        """Simpan profil ke file JSON"""
        output_path = Path(output_dir) / f"tiktok_{profile.username}.json"
        output_path.write_text(
            json.dumps(profile.to_dict(), indent=2, ensure_ascii=False),
            encoding='utf-8'
        )
        return str(output_path)


async def main():
    parser = argparse.ArgumentParser(
        description="TikTok Profile Scraper - Playwright Version",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh penggunaan:
  python tiktok_playwright.py username
  python tiktok_playwright.py username --save
  python tiktok_playwright.py username --following --cookies tiktok_cookies.json
  python tiktok_playwright.py username --following --max 50 --cookies tiktok_cookies.json
  
Untuk fitur following, diperlukan cookies:
  1. Login ke TikTok di browser
  2. Export cookies dengan extension EditThisCookie
  3. Simpan sebagai file JSON (misal: tiktok_cookies.json)
  4. Gunakan: --cookies tiktok_cookies.json
        """
    )
    parser.add_argument("usernames", nargs="+", help="Username TikTok (tanpa @)")
    parser.add_argument("--save", "-s", action="store_true", help="Simpan hasil ke file JSON")
    parser.add_argument("--following", "-f", action="store_true", help="Ambil daftar following (perlu cookies)")
    parser.add_argument("--followers", "-F", action="store_true", help="Ambil daftar followers (perlu cookies)")
    parser.add_argument("--cookies", "-c", help="Path ke file cookies JSON (dari Cookie-Editor)")
    parser.add_argument("--max", "-m", type=int, default=100, help="Maksimal following/followers yang diambil (default: 100)")
    parser.add_argument("--headless", "-H", action="store_true", help="Jalankan browser tanpa tampilan (bisa kena CAPTCHA)")
    parser.add_argument("--debug", "-d", action="store_true", help="Simpan HTML untuk debugging")
    parser.add_argument("--output", "-o", default=".", help="Direktori output")
    
    args = parser.parse_args()
    
    if not PLAYWRIGHT_AVAILABLE:
        print("\n[!] Playwright tidak tersedia!")
        print("    Install dengan perintah berikut:")
        print("    pip install playwright")
        print("    playwright install chromium")
        return
    
    # Cek cookies untuk fitur following/followers
    if (args.following or args.followers) and not args.cookies:
        print("\n[!] Fitur following/followers memerlukan cookies!")
        print("    Gunakan: --cookies tiktok_cookies.json")
        print("    Lihat README.md untuk cara export cookies")
        return
    
    print("=" * 55)
    print("  TikTok Scraper - Playwright Version")
    print("  Mode: " + ("Headless" if args.headless else "Visible (recommended)"))
    if args.cookies:
        print("  Cookies: " + args.cookies)
    print("=" * 55)
    
    async with TikTokPlaywrightScraper(headless=args.headless, cookies_file=args.cookies) as scraper:
        for username in args.usernames:
            print(f"\n{'='*50}")
            
            # Ambil profil dulu
            profile = await scraper.get_profile(username, save_debug=args.debug)
            if profile:
                print(profile)
                if args.save:
                    path = scraper.save_profile(profile, args.output)
                    print(f"[+] Profil disimpan ke: {path}")
            else:
                print(f"[X] Gagal mendapatkan profil @{username}")
                continue
            
            # Jika flag --following aktif
            if args.following:
                print(f"\n[~] Mengambil daftar following @{username}...")
                following = await scraper.get_following(username, max_count=args.max)
                
                if following:
                    print(f"\n+-- Following List (@{username}) --+")
                    for i, user in enumerate(following[:20], 1):  # Tampilkan 20 pertama
                        nickname = user.get('nickname', '')
                        print(f"| {i:3}. @{user['username'][:20]:<20} {nickname[:15]}")
                    
                    if len(following) > 20:
                        print(f"| ... dan {len(following) - 20} lainnya")
                    print("+----------------------------------+")
                    
                    # Simpan ke file
                    if args.save:
                        following_path = Path(args.output) / f"tiktok_{username}_following.json"
                        following_path.write_text(
                            json.dumps(following, indent=2, ensure_ascii=False),
                            encoding='utf-8'
                        )
                        print(f"[+] Following list disimpan ke: {following_path}")
                else:
                    print(f"[X] Tidak dapat mengambil following @{username}")
            
            # Jika flag --followers aktif
            if args.followers:
                print(f"\n[~] Mengambil daftar followers @{username}...")
                followers = await scraper.get_followers(username, max_count=args.max)
                
                if followers:
                    print(f"\n+-- Followers List (@{username}) --+")
                    for i, user in enumerate(followers[:20], 1):  # Tampilkan 20 pertama
                        nickname = user.get('nickname', '')
                        print(f"| {i:3}. @{user['username'][:20]:<20} {nickname[:15]}")
                    
                    if len(followers) > 20:
                        print(f"| ... dan {len(followers) - 20} lainnya")
                    print("+----------------------------------+")
                    
                    # Simpan ke file
                    if args.save:
                        followers_path = Path(args.output) / f"tiktok_{username}_followers.json"
                        followers_path.write_text(
                            json.dumps(followers, indent=2, ensure_ascii=False),
                            encoding='utf-8'
                        )
                        print(f"[+] Followers list disimpan ke: {followers_path}")
                else:
                    print(f"[X] Tidak dapat mengambil followers @{username}")
    
    print("\n[OK] Selesai!")


if __name__ == "__main__":
    asyncio.run(main())
