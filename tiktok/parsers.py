"""
TikTok Data Parsers
Ekstrak dan parse data JSON dari HTML TikTok
"""

import re
import json
from typing import Optional, Dict

from .models import TikTokProfile


# Patterns untuk ekstrak JSON dari HTML
JSON_PATTERNS = [
    r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">(.*?)</script>',
    r'<script id="SIGI_STATE" type="application/json">(.*?)</script>',
]


def extract_json_data(html: str) -> Optional[Dict]:
    """Ekstrak data JSON dari HTML TikTok"""
    for pattern in JSON_PATTERNS:
        match = re.search(pattern, html, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
    return None


def parse_universal_data(data: Dict, username: str) -> Optional[TikTokProfile]:
    """Parse data dari format __UNIVERSAL_DATA_FOR_REHYDRATION__"""
    try:
        # Navigate ke user data
        default_scope = data.get('__DEFAULT_SCOPE__', {})
        webapp_user = default_scope.get('webapp.user-detail', {})
        user_info = webapp_user.get('userInfo', {})
        user = user_info.get('user', {})
        stats = user_info.get('stats', {})
        
        if not user:
            return None
        
        return TikTokProfile(
            username=user.get('uniqueId', username),
            nickname=user.get('nickname', 'N/A'),
            followers=stats.get('followerCount', 0),
            following=stats.get('followingCount', 0),
            likes=stats.get('heartCount', 0) or stats.get('heart', 0),
            video_count=stats.get('videoCount', 0),
            bio=user.get('signature', ''),
            verified=user.get('verified', False),
            private=user.get('privateAccount', False),
            avatar_url=user.get('avatarLarger', '') or user.get('avatarMedium', '')
        )
    except Exception as e:
        print(f"[!] Error parsing universal data: {e}")
        return None


def parse_sigi_data(data: Dict, username: str) -> Optional[TikTokProfile]:
    """Parse data dari format SIGI_STATE"""
    try:
        user_module = data.get('UserModule', {})
        users = user_module.get('users', {})
        stats = user_module.get('stats', {})
        
        # Cari user data
        user_data = users.get(username, {})
        user_stats = stats.get(username, {})
        
        if not user_data:
            # Coba cari dengan key lain
            for key in users:
                if key.lower() == username.lower():
                    user_data = users[key]
                    user_stats = stats.get(key, {})
                    break
        
        if not user_data:
            return None
        
        return TikTokProfile(
            username=user_data.get('uniqueId', username),
            nickname=user_data.get('nickname', 'N/A'),
            followers=user_stats.get('followerCount', 0),
            following=user_stats.get('followingCount', 0),
            likes=user_stats.get('heartCount', 0) or user_stats.get('heart', 0),
            video_count=user_stats.get('videoCount', 0),
            bio=user_data.get('signature', ''),
            verified=user_data.get('verified', False),
            private=user_data.get('privateAccount', False),
            avatar_url=user_data.get('avatarLarger', '') or user_data.get('avatarMedium', '')
        )
    except Exception as e:
        print(f"[!] Error parsing SIGI data: {e}")
        return None


def parse_profile_data(html: str, username: str) -> Optional[TikTokProfile]:
    """Parse profile data dari HTML - coba semua format"""
    json_data = extract_json_data(html)
    
    if not json_data:
        return None
    
    # Coba parse sebagai Universal Data
    profile = parse_universal_data(json_data, username)
    if profile:
        return profile
    
    # Coba parse sebagai SIGI State
    profile = parse_sigi_data(json_data, username)
    if profile:
        return profile
    
    return None
