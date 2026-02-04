"""
TikTok Profile Scraper - Optimized Version
Menggabungkan dan mengoptimalkan semua fungsi scraping TikTok
"""

import requests
import json
import re
import time
import argparse
from dataclasses import dataclass
from typing import Optional, Dict, Any
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed


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
    raw_data: Optional[Dict] = None

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
| Bio       : {self.bio[:60]}{'...' if len(self.bio) > 60 else ''}
| {status}
+--------------------------------------------------+"""


class TikTokScraper:
    """Scraper TikTok yang dioptimalkan"""
    
    # JSON patterns untuk ekstraksi data
    JSON_PATTERNS = [
        (r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">(.*?)</script>', 'universal'),
        (r'<script id="SIGI_STATE" type="application/json">(.*?)</script>', 'sigi'),
        (r"window\['SIGI_STATE'\]\s*=\s*({.*?});", 'sigi_window'),
    ]
    
    # Default headers
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,id;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }
    
    def __init__(self, timeout: int = 15, max_retries: int = 3, save_debug: bool = False):
        self.timeout = timeout
        self.max_retries = max_retries
        self.save_debug = save_debug
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
    
    def _make_request(self, url: str, retry_count: int = 0) -> Optional[requests.Response]:
        """Buat request dengan retry logic"""
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            if retry_count < self.max_retries:
                time.sleep(2 ** retry_count)  # Exponential backoff
                return self._make_request(url, retry_count + 1)
            print(f"[X] Request gagal setelah {self.max_retries} percobaan: {e}")
            return None
    
    def _extract_json_data(self, html: str) -> tuple[Optional[Dict], str]:
        """Ekstrak data JSON dari HTML menggunakan berbagai pattern"""
        for pattern, pattern_type in self.JSON_PATTERNS:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    return data, pattern_type
                except json.JSONDecodeError:
                    continue
        return None, ""
    
    def _parse_universal_data(self, data: Dict, username: str) -> Optional[TikTokProfile]:
        """Parse data dari format __UNIVERSAL_DATA_FOR_REHYDRATION__"""
        try:
            # Cari dalam berbagai struktur
            user_info = None
            
            # Path 1: __DEFAULT_SCOPE__
            if '__DEFAULT_SCOPE__' in data:
                scope = data['__DEFAULT_SCOPE__']
                if 'webapp.user-detail' in scope:
                    user_info = scope['webapp.user-detail'].get('userInfo', {}).get('user', {})
                    stats = scope['webapp.user-detail'].get('userInfo', {}).get('stats', {})
            
            if not user_info:
                return None
            
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
                raw_data=data
            )
        except Exception as e:
            print(f"[!] Error parsing universal data: {e}")
            return None
    
    def _parse_sigi_data(self, data: Dict, username: str) -> Optional[TikTokProfile]:
        """Parse data dari format SIGI_STATE"""
        try:
            if 'UserModule' not in data or 'users' not in data['UserModule']:
                return None
            
            users = data['UserModule']['users']
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
                video_count=user_stats.get('videoCount', user_info.get('videoCount', 0)),
                bio=user_info.get('signature', ''),
                verified=user_info.get('verified', False),
                private=user_info.get('privateAccount', False),
                raw_data=data
            )
        except Exception as e:
            print(f"[!] Error parsing SIGI data: {e}")
            return None
    
    def _check_page_status(self, html: str) -> Optional[str]:
        """Cek status halaman (banned, private, tidak tersedia, dll)"""
        html_lower = html.lower()
        checks = [
            ("account banned", "[X] Akun dibanned"),
            ("not available", "[X] Halaman tidak tersedia"),
            ("private account", "[!] Akun private"),
            ("suspended", "[!] Akun suspended"),
        ]
        for keyword, message in checks:
            if keyword in html_lower:
                return message
        if len(html) < 1000:
            return "[!] Response terlalu pendek (mungkin diblokir)"
        return None
    
    def get_profile(self, username: str) -> Optional[TikTokProfile]:
        """Dapatkan profil TikTok untuk username tertentu"""
        url = f"https://www.tiktok.com/@{username}"
        print(f"[~] Mengakses profil: @{username}")
        
        response = self._make_request(url)
        if not response:
            return None
        
        html = response.text
        
        # Debug save
        if self.save_debug:
            Path(f'debug_{username}.html').write_text(html, encoding='utf-8')
            print(f"[+] HTML disimpan: debug_{username}.html")
        
        # Cek status halaman
        status = self._check_page_status(html)
        if status:
            print(status)
            return None
        
        # Ekstrak JSON
        data, data_type = self._extract_json_data(html)
        if not data:
            print("[X] Tidak menemukan data JSON dalam halaman")
            return None
        
        print(f"[+] Data ditemukan (format: {data_type})")
        
        # Parse berdasarkan tipe data
        if data_type == 'universal':
            profile = self._parse_universal_data(data, username)
        else:
            profile = self._parse_sigi_data(data, username)
        
        return profile
    
    def get_multiple_profiles(self, usernames: list[str]) -> Dict[str, Optional[TikTokProfile]]:
        """Dapatkan profil untuk multiple usernames secara concurrent"""
        results = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_username = {
                executor.submit(self.get_profile, username): username 
                for username in usernames
            }
            for future in as_completed(future_to_username):
                username = future_to_username[future]
                try:
                    results[username] = future.result()
                except Exception as e:
                    print(f"[X] Error untuk @{username}: {e}")
                    results[username] = None
        return results
    
    def save_profile(self, profile: TikTokProfile, output_dir: str = ".") -> str:
        """Simpan profil ke file JSON"""
        output_path = Path(output_dir) / f"tiktok_{profile.username}.json"
        
        data = {
            "username": profile.username,
            "nickname": profile.nickname,
            "followers": profile.followers,
            "following": profile.following,
            "likes": profile.likes,
            "video_count": profile.video_count,
            "bio": profile.bio,
            "verified": profile.verified,
            "private": profile.private,
            "formatted_stats": profile.formatted_stats(),
        }
        
        output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
        return str(output_path)


def main():
    parser = argparse.ArgumentParser(
        description="TikTok Profile Scraper - Optimized",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh penggunaan:
  python tiktok_scraper.py username1
  python tiktok_scraper.py user1 user2 user3 --save
  python tiktok_scraper.py username --debug
        """
    )
    parser.add_argument("usernames", nargs="+", help="Username TikTok (tanpa @)")
    parser.add_argument("--save", "-s", action="store_true", help="Simpan hasil ke file JSON")
    parser.add_argument("--debug", "-d", action="store_true", help="Simpan HTML untuk debugging")
    parser.add_argument("--timeout", "-t", type=int, default=15, help="Timeout request (default: 15)")
    parser.add_argument("--output", "-o", default=".", help="Direktori output (default: .)")
    
    args = parser.parse_args()
    
    scraper = TikTokScraper(
        timeout=args.timeout,
        save_debug=args.debug
    )
    
    print("=" * 55)
    print("  TikTok Profile Scraper - Optimized Version")
    print("=" * 55)
    
    if len(args.usernames) == 1:
        profile = scraper.get_profile(args.usernames[0])
        if profile:
            print(profile)
            if args.save:
                path = scraper.save_profile(profile, args.output)
                print(f"[+] Disimpan ke: {path}")
    else:
        profiles = scraper.get_multiple_profiles(args.usernames)
        for username, profile in profiles.items():
            if profile:
                print(profile)
                if args.save:
                    path = scraper.save_profile(profile, args.output)
                    print(f"[+] Disimpan ke: {path}")
            else:
                print(f"\n[X] Gagal mendapatkan profil @{username}")
    
    print("\n[OK] Selesai!")


if __name__ == "__main__":
    main()
