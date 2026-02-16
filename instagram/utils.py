"""
Instagram Scraper - Utilities
Cookie loading, header generation, helpers
"""

import json
import random
import time
from pathlib import Path
from typing import Dict, List, Optional


# Instagram App IDs (rotated to reduce detection)
IG_APP_IDS = [
    "936619743392459",   # Web
    "1217981644879628",  # Mobile web
]

# Mobile User-Agents for Layer 3
MOBILE_USER_AGENTS = [
    "Instagram 317.0.0.34.109 Android (33/13; 420dpi; 1080x2400; samsung; SM-S908B; b0q; qcom; id_ID; 570430867)",
    "Instagram 317.0.0.34.109 Android (34/14; 480dpi; 1440x3120; Google; Pixel 8 Pro; husky; tensor; en_US; 570430867)",
    "Instagram 317.0.0.34.109 Android (33/13; 420dpi; 1080x2340; Xiaomi; 2201117TG; psyche; qcom; id_ID; 570430867)",
    "Instagram 316.0.0.38.109 (iPhone16,2; iOS 17_4; id_ID; id; scale=3.00; 1290x2796; 567742373)",
    "Instagram 316.0.0.38.109 (iPhone15,3; iOS 17_3_1; id_ID; id; scale=3.00; 1290x2796; 567742373)",
]

# Desktop User-Agents
DESKTOP_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0",
]


def load_cookies(filepath: str) -> List[Dict]:
    """
    Load cookies dari file JSON (EditThisCookie / Netscape format)
    
    Supports:
    - EditThisCookie export format (list of cookie objects)
    - Netscape/curl cookie jar format
    - Simple key-value JSON format
    """
    path = Path(filepath)
    if not path.exists():
        print(f"[!] Cookie file not found: {filepath}")
        return []
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        cookies = []
        
        if isinstance(data, list):
            # EditThisCookie format
            for cookie in data:
                c = {
                    'name': cookie.get('name', ''),
                    'value': cookie.get('value', ''),
                    'domain': cookie.get('domain', '.instagram.com'),
                    'path': cookie.get('path', '/'),
                }
                if c['name'] and c['value']:
                    cookies.append(c)
        elif isinstance(data, dict):
            # Simple key-value format
            for name, value in data.items():
                cookies.append({
                    'name': name,
                    'value': str(value),
                    'domain': '.instagram.com',
                    'path': '/',
                })
        
        print(f"[+] Loaded {len(cookies)} cookies from {filepath}")
        return cookies
    
    except (json.JSONDecodeError, Exception) as e:
        print(f"[!] Error loading cookies: {e}")
        return []


def cookies_to_header(cookies: List[Dict]) -> str:
    """Convert cookie list to Cookie header string"""
    return '; '.join(f"{c['name']}={c['value']}" for c in cookies)


def get_ig_app_id() -> str:
    """Get Instagram App ID (rotated)"""
    return random.choice(IG_APP_IDS)


def generate_web_headers(cookies: Optional[List[Dict]] = None, referer: Optional[str] = None) -> Dict[str, str]:
    """Generate headers for Instagram Web API requests"""
    headers = {
        'User-Agent': random.choice(DESKTOP_USER_AGENTS),
        'Accept': '*/*',
        'Accept-Language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'X-IG-App-ID': get_ig_app_id(),
        'X-Requested-With': 'XMLHttpRequest',
        'X-ASBD-ID': '129477',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Connection': 'keep-alive',
    }
    
    if referer:
        headers['Referer'] = referer
    else:
        headers['Referer'] = 'https://www.instagram.com/'
    
    if cookies:
        headers['Cookie'] = cookies_to_header(cookies)
        # Extract CSRF token if available
        for c in cookies:
            if c['name'] == 'csrftoken':
                headers['X-CSRFToken'] = c['value']
                break
    
    return headers


def generate_mobile_headers(cookies: Optional[List[Dict]] = None) -> Dict[str, str]:
    """Generate headers for Instagram Mobile API requests (Layer 3)"""
    headers = {
        'User-Agent': random.choice(MOBILE_USER_AGENTS),
        'Accept': '*/*',
        'Accept-Language': 'id-ID,id;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
        'X-IG-App-ID': '567067343352427',  # Mobile app ID
        'X-IG-Capabilities': '3brTvw8=',
        'X-IG-Connection-Type': 'WIFI',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Connection': 'keep-alive',
    }
    
    if cookies:
        headers['Cookie'] = cookies_to_header(cookies)
        for c in cookies:
            if c['name'] == 'csrftoken':
                headers['X-CSRFToken'] = c['value']
                break
    
    return headers


def generate_browser_headers() -> Dict[str, str]:
    """Generate headers for regular browser page requests"""
    return {
        'User-Agent': random.choice(DESKTOP_USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7',
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


def extract_user_id(profile_data: Dict) -> Optional[str]:
    """Extract numeric user ID from profile API response"""
    # Try multiple paths
    paths = [
        lambda d: d.get('data', {}).get('user', {}).get('id'),
        lambda d: d.get('user', {}).get('pk'),
        lambda d: d.get('user', {}).get('pk_id'),
        lambda d: str(d.get('user', {}).get('id', '')),
        lambda d: d.get('graphql', {}).get('user', {}).get('id'),
    ]
    
    for path in paths:
        try:
            uid = path(profile_data)
            if uid and str(uid).isdigit():
                return str(uid)
        except (AttributeError, TypeError):
            continue
    
    return None


def smart_delay(min_sec: float = 1.0, max_sec: float = 3.0, jitter: bool = True):
    """Human-like delay with optional jitter"""
    base = random.uniform(min_sec, max_sec)
    if jitter:
        base += random.gauss(0, 0.3)
        base = max(min_sec * 0.5, base)  # Floor at half of min
    time.sleep(base)


def format_timestamp(ts: int) -> str:
    """Format Unix timestamp to readable string"""
    from datetime import datetime
    try:
        return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, OSError):
        return "Unknown"
