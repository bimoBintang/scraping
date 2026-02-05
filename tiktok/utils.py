"""
Cookie Utilities
Load dan convert cookies dari berbagai format
"""

import json
from typing import List, Dict, Optional


def load_cookies(cookies_file: str) -> List[Dict]:
    """
    Load cookies dari file JSON (Cookie-Editor/EditThisCookie format)
    dan convert ke Playwright format
    
    Args:
        cookies_file: Path ke file cookies JSON
        
    Returns:
        List of cookies dalam format Playwright
    """
    try:
        with open(cookies_file, 'r', encoding='utf-8') as f:
            raw_cookies = json.load(f)
        
        cookies = []
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
                sameSite = cookie['sameSite']
                if sameSite in ['Strict', 'Lax', 'None']:
                    pw_cookie['sameSite'] = sameSite
                elif sameSite == 'no_restriction':
                    pw_cookie['sameSite'] = 'None'
                else:
                    pw_cookie['sameSite'] = 'Lax'
            
            cookies.append(pw_cookie)
        
        print(f"[+] Loaded {len(cookies)} cookies from {cookies_file}")
        return cookies
        
    except FileNotFoundError:
        print(f"[!] Cookie file not found: {cookies_file}")
        return []
    except json.JSONDecodeError as e:
        print(f"[!] Error parsing cookie file: {e}")
        return []
    except Exception as e:
        print(f"[!] Error loading cookies: {e}")
        return []
