"""
Instagram Hybrid Client — Algorithm 1: Tri-Layer Fallback

Layer 1: Web API (i.instagram.com/api/v1/) — fast & lightweight
Layer 2: Browser automation (Playwright) — bypass anti-bot detection
Layer 3: Mobile API (different endpoints, mobile UA) — last resort

Each layer tracks health state with exponential backoff cooldowns.
Automatically switches layers based on response status.
"""

import json
import time
import requests
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from .models import InstagramProfile, InstagramPost
from .parsers import InstagramParser
from .discovery import DocIdDiscovery
from .rate_limiter import AdaptiveRateLimiter
from .utils import (
    generate_web_headers,
    generate_mobile_headers,
    generate_browser_headers,
    load_cookies,
    cookies_to_header,
    extract_user_id,
    smart_delay,
)


class LayerStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    COOLDOWN = "cooldown"
    DISABLED = "disabled"


@dataclass
class LayerHealth:
    """Track health state for each layer"""
    status: LayerStatus = LayerStatus.HEALTHY
    consecutive_failures: int = 0
    last_failure_time: float = 0
    cooldown_seconds: float = 60
    total_requests: int = 0
    total_failures: int = 0
    
    def mark_success(self):
        self.consecutive_failures = 0
        self.status = LayerStatus.HEALTHY
        self.cooldown_seconds = 60  # Reset cooldown
        self.total_requests += 1
    
    def mark_failure(self):
        self.consecutive_failures += 1
        self.total_failures += 1
        self.total_requests += 1
        self.last_failure_time = time.time()
        
        # Exponential backoff
        if self.consecutive_failures >= 5:
            self.status = LayerStatus.COOLDOWN
            self.cooldown_seconds = min(self.cooldown_seconds * 2, 3600)  # Max 1 hour
        elif self.consecutive_failures >= 3:
            self.status = LayerStatus.DEGRADED
    
    def is_available(self) -> bool:
        if self.status == LayerStatus.DISABLED:
            return False
        if self.status == LayerStatus.COOLDOWN:
            elapsed = time.time() - self.last_failure_time
            if elapsed >= self.cooldown_seconds:
                self.status = LayerStatus.DEGRADED
                return True
            return False
        return True


class HybridInstagramClient:
    """
    Tri-layer Instagram client with automatic fallback.
    
    Usage:
        client = HybridInstagramClient()
        
        # Auto-selects best available layer
        profile = client.get_profile("cristiano")
        posts = client.get_posts("cristiano", count=12)
        
        # With cookies for authenticated features
        client = HybridInstagramClient(cookies_file="cookies.json")
        followers = client.get_followers("cristiano", count=100)
    """
    
    # Instagram API endpoints
    WEB_API_BASE = "https://i.instagram.com/api/v1"
    GRAPHQL_URL = "https://www.instagram.com/graphql/query/"
    MOBILE_API_BASE = "https://i.instagram.com/api/v1"
    
    def __init__(
        self,
        cookies_file: Optional[str] = None,
        debug_dir: str = ".",
        enable_discovery: bool = True,
        enable_rl: bool = True,
        rl_debug: bool = False,
    ):
        self.cookies = load_cookies(cookies_file) if cookies_file else []
        self.parser = InstagramParser(debug_dir=debug_dir)
        self.discovery = DocIdDiscovery() if enable_discovery else None
        self.debug_dir = Path(debug_dir)
        
        # Session for connection reuse
        self.session = requests.Session()
        
        # Algorithm 5: Adaptive Rate Limiter (Q-Learning)
        self.enable_rl = enable_rl
        if enable_rl:
            self.rate_limiter = AdaptiveRateLimiter(
                policy_file=str(Path(debug_dir) / "instagram_rl_policy.json"),
                debug=rl_debug,
            )
            print("  [🧠] Adaptive Rate Limiter (Q-Learning) aktif")
        else:
            self.rate_limiter = None
        
        # Layer health tracking
        self.layers: Dict[str, LayerHealth] = {
            "web_api": LayerHealth(),
            "browser": LayerHealth(),
            "mobile_api": LayerHealth(),
        }
        
        # Statistics
        self._stats = {
            'total_requests': 0,
            'layer_usage': {'web_api': 0, 'browser': 0, 'mobile_api': 0},
        }
    
    # ==================== PUBLIC API ====================
    
    def get_profile(self, username: str) -> Optional[InstagramProfile]:
        """
        Get Instagram profile using the best available layer.
        
        Args:
            username: Instagram username (without @)
            
        Returns:
            InstagramProfile or None
        """
        print(f"\n{'='*50}")
        print(f"  Scraping profile: @{username}")
        print(f"{'='*50}")
        
        # Layer priority order
        layer_methods = [
            ("web_api", self._get_profile_web_api),
            ("browser", self._get_profile_browser),
            ("mobile_api", self._get_profile_mobile_api),
        ]
        
        for layer_name, method in layer_methods:
            health = self.layers[layer_name]
            
            if not health.is_available():
                print(f"  [→] Layer {layer_name}: {health.status.value} (skipping)")
                continue
            
            print(f"  [→] Trying Layer: {layer_name}")
            
            try:
                profile = method(username)
                if profile:
                    health.mark_success()
                    self._stats['layer_usage'][layer_name] += 1
                    self._stats['total_requests'] += 1
                    if self.rate_limiter:
                        self.rate_limiter.record_result(success=True)
                    print(f"  [✓] Success via {layer_name}")
                    return profile
                else:
                    health.mark_failure()
                    if self.rate_limiter:
                        self.rate_limiter.record_result(success=False)
                    print(f"  [✗] Layer {layer_name}: no data returned")
            except Exception as e:
                health.mark_failure()
                is_429 = "429" in str(e) or "rate limit" in str(e).lower()
                if self.rate_limiter:
                    self.rate_limiter.record_result(success=False, rate_limited=is_429)
                print(f"  [✗] Layer {layer_name} error: {e}")
            
            self._adaptive_delay(1, 2)
        
        print(f"  [!] All layers failed for @{username}")
        return None
    
    def get_posts(self, username: str, count: int = 12) -> List[InstagramPost]:
        """
        Get user posts with automatic layer switching.
        
        Args:
            username: Instagram username
            count: Number of posts to fetch
        """
        print(f"\n[*] Fetching {count} posts for @{username}...")
        
        # First get profile to obtain user_id
        profile = self.get_profile(username)
        if not profile or not profile.user_id:
            print("  [!] Could not get user_id for post fetching")
            return []
        
        posts = []
        cursor = ""
        
        while len(posts) < count:
            batch = self._fetch_posts_batch(profile.user_id, cursor=cursor, count=min(50, count - len(posts)))
            if not batch:
                break
            
            new_posts, pagination = batch
            posts.extend(new_posts)
            
            if not pagination.get('has_next_page'):
                break
            cursor = pagination.get('end_cursor', '')
            
            self._adaptive_delay(1.5, 3)
        
        print(f"  [✓] Fetched {len(posts)} posts")
        return posts[:count]
    
    def get_followers(self, username: str, count: int = 100) -> List[Dict]:
        """Get followers list (requires cookies)"""
        return self._get_social_list(username, "followers", count)
    
    def get_following(self, username: str, count: int = 100) -> List[Dict]:
        """Get following list (requires cookies)"""
        return self._get_social_list(username, "following", count)
    
    def search_users(self, query: str) -> List[Dict]:
        """Search for Instagram users"""
        print(f"\n[*] Searching: '{query}'")
        
        try:
            headers = generate_web_headers(self.cookies)
            response = self.session.get(
                "https://www.instagram.com/web/search/topsearch/",
                params={'query': query, 'context': 'blended'},
                headers=headers,
                timeout=15,
            )
            
            if response.status_code == 200:
                data = response.json()
                users = []
                for item in data.get('users', []):
                    u = item.get('user', {})
                    users.append({
                        'username': u.get('username', ''),
                        'full_name': u.get('full_name', ''),
                        'is_private': u.get('is_private', False),
                        'is_verified': u.get('is_verified', False),
                        'profile_pic_url': u.get('profile_pic_url', ''),
                        'follower_count': u.get('follower_count', 0),
                    })
                print(f"  [✓] Found {len(users)} users")
                return users
        except Exception as e:
            print(f"  [!] Search error: {e}")
        
        return []
    
    def get_stats(self) -> Dict:
        """Get client usage statistics"""
        stats = {
            **self._stats,
            'layer_health': {
                name: {
                    'status': h.status.value,
                    'failures': h.consecutive_failures,
                    'total_requests': h.total_requests,
                    'total_failures': h.total_failures,
                }
                for name, h in self.layers.items()
            }
        }
        if self.rate_limiter:
            stats['rl_rate_limiter'] = self.rate_limiter.get_stats()
        return stats
    
    # ==================== LAYER 1: WEB API ====================
    
    def _get_profile_web_api(self, username: str) -> Optional[InstagramProfile]:
        """Layer 1: Fetch profile via Instagram Web API"""
        url = f"{self.WEB_API_BASE}/users/web_profile_info/"
        headers = generate_web_headers(self.cookies, referer=f"https://www.instagram.com/{username}/")
        
        response = self.session.get(
            url,
            params={'username': username},
            headers=headers,
            timeout=15,
        )
        
        if response.status_code == 404:
            print(f"  [!] User @{username} not found")
            return None
        
        if response.status_code == 429:
            print("  [!] Rate limited on Web API")
            raise Exception("Rate limited (429)")
        
        if response.status_code == 401 or response.status_code == 302:
            print("  [!] Login required / redirected")
            raise Exception("Login required")
        
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}")
        
        # Check content type
        content_type = response.headers.get('Content-Type', '')
        if 'application/json' not in content_type and 'text/javascript' not in content_type:
            # Got HTML instead of JSON — likely login wall
            if 'login' in response.text.lower()[:1000]:
                raise Exception("Login wall detected")
            # Try parsing HTML
            return self.parser.parse_profile_page(response.text, username)
        
        data = response.json()
        
        # Save raw data for debugging
        self._save_debug_data(data, f"instagram_{username}_web_api.json")
        
        return self.parser.parse_web_profile_info(data, username)
    
    # ==================== LAYER 2: BROWSER ====================
    
    def _get_profile_browser(self, username: str) -> Optional[InstagramProfile]:
        """Layer 2: Fetch profile via direct HTTP request + HTML parsing"""
        url = f"https://www.instagram.com/{username}/"
        headers = generate_browser_headers()
        
        if self.cookies:
            from .utils import cookies_to_header
            headers['Cookie'] = cookies_to_header(self.cookies)
        
        response = self.session.get(
            url,
            headers=headers,
            timeout=15,
            allow_redirects=True,
        )
        
        if response.status_code == 404:
            return None
        
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}")
        
        html = response.text
        
        # Check for login wall
        if self._is_login_wall(html):
            raise Exception("Login wall — bot detected")
        
        # Save HTML for debugging
        self._save_debug_html(html, f"instagram_{username}_browser.html")
        
        # Use multi-strategy parser
        return self.parser.parse_profile_page(html, username)
    
    # ==================== LAYER 3: MOBILE API ====================
    
    def _get_profile_mobile_api(self, username: str) -> Optional[InstagramProfile]:
        """Layer 3: Fetch profile via Mobile API endpoint"""
        # First get user_id via search
        user_id = self._resolve_user_id(username)
        
        if user_id:
            # Direct user info endpoint
            url = f"{self.MOBILE_API_BASE}/users/{user_id}/info/"
        else:
            # Fallback to username-based endpoint
            url = f"{self.MOBILE_API_BASE}/users/web_profile_info/"
        
        headers = generate_mobile_headers(self.cookies)
        
        params = {'username': username} if not user_id else {}
        
        response = self.session.get(
            url,
            params=params,
            headers=headers,
            timeout=15,
        )
        
        if response.status_code != 200:
            raise Exception(f"Mobile API: HTTP {response.status_code}")
        
        data = response.json()
        self._save_debug_data(data, f"instagram_{username}_mobile_api.json")
        
        # Parse mobile API format
        user = data.get('user', {})
        if not user:
            return None
        
        return InstagramProfile(
            username=user.get('username', username),
            full_name=user.get('full_name', 'N/A'),
            bio=user.get('biography', '') or user.get('bio', ''),
            followers=user.get('follower_count', 0),
            following=user.get('following_count', 0),
            post_count=user.get('media_count', 0),
            is_private=user.get('is_private', False),
            is_verified=user.get('is_verified', False),
            is_business=user.get('is_business', False),
            profile_pic_url=user.get('hd_profile_pic_url_info', {}).get('url', '') or user.get('profile_pic_url', ''),
            external_url=user.get('external_url', '') or '',
            category=user.get('category', ''),
            user_id=str(user.get('pk', '') or user.get('pk_id', '')),
        )
    
    # ==================== POSTS FETCHING ====================
    
    def _fetch_posts_batch(self, user_id: str, cursor: str = "", count: int = 12):
        """Fetch a batch of posts via GraphQL"""
        doc_id = None
        if self.discovery:
            doc_id = self.discovery.get_doc_id("user_posts")
        
        if doc_id:
            return self._fetch_posts_graphql(user_id, doc_id, cursor, count)
        else:
            return self._fetch_posts_api(user_id, cursor, count)
    
    def _fetch_posts_graphql(self, user_id: str, doc_id: str, cursor: str, count: int):
        """Fetch posts via GraphQL with discovered doc_id"""
        variables = {
            "id": user_id,
            "first": count,
        }
        if cursor:
            variables["after"] = cursor
        
        headers = generate_web_headers(self.cookies)
        
        try:
            response = self.session.get(
                self.GRAPHQL_URL,
                params={
                    'doc_id': doc_id,
                    'variables': json.dumps(variables),
                },
                headers=headers,
                timeout=15,
            )
            
            if response.status_code == 200:
                data = response.json()
                posts = self.parser.parse_graphql_posts(data)
                pagination = self.parser.get_pagination_info(data)
                return posts, pagination
        except Exception as e:
            print(f"  [!] GraphQL posts error: {e}")
        
        return None
    
    def _fetch_posts_api(self, user_id: str, cursor: str, count: int):
        """Fetch posts via REST API fallback"""
        url = f"{self.WEB_API_BASE}/feed/user/{user_id}/"
        headers = generate_web_headers(self.cookies)
        
        params = {'count': count}
        if cursor:
            params['max_id'] = cursor
        
        try:
            response = self.session.get(url, params=params, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                items = data.get('items', [])
                posts = []
                for item in items:
                    post = InstagramPost(
                        shortcode=item.get('code', ''),
                        post_type='video' if item.get('media_type') == 2 else 'image',
                        caption=item.get('caption', {}).get('text', '') if item.get('caption') else '',
                        likes=item.get('like_count', 0),
                        comments=item.get('comment_count', 0),
                        timestamp=item.get('taken_at', 0),
                        media_url=item.get('image_versions2', {}).get('candidates', [{}])[0].get('url', '') if item.get('image_versions2') else '',
                        is_video=item.get('media_type') == 2,
                        video_views=item.get('view_count', 0) or item.get('play_count', 0),
                    )
                    posts.append(post)
                
                pagination = {
                    'has_next_page': data.get('more_available', False),
                    'end_cursor': data.get('next_max_id', ''),
                }
                return posts, pagination
        except Exception as e:
            print(f"  [!] REST API posts error: {e}")
        
        return None
    
    # ==================== SOCIAL LIST ====================
    
    def _get_social_list(self, username: str, list_type: str, count: int) -> List[Dict]:
        """Get followers or following list"""
        if not self.cookies:
            print(f"  [!] Cookies required for {list_type} list")
            return []
        
        print(f"\n[*] Fetching {list_type} for @{username} (max {count})...")
        
        profile = self.get_profile(username)
        if not profile or not profile.user_id:
            print("  [!] Could not get user_id")
            return []
        
        doc_id_key = f"user_{list_type}"
        doc_id = self.discovery.get_doc_id(doc_id_key) if self.discovery else None
        
        users = []
        cursor = ""
        
        while len(users) < count:
            batch_size = min(50, count - len(users))
            
            if doc_id:
                batch = self._fetch_social_graphql(profile.user_id, doc_id, cursor, batch_size)
            else:
                batch = self._fetch_social_api(profile.user_id, list_type, cursor, batch_size)
            
            if not batch:
                break
            
            new_users, pagination = batch
            users.extend(new_users)
            
            if not pagination.get('has_next_page'):
                break
            cursor = pagination.get('end_cursor', '')
            
            self._adaptive_delay(2, 4)
        
        print(f"  [✓] Fetched {len(users)} {list_type}")
        return users[:count]
    
    def _fetch_social_graphql(self, user_id, doc_id, cursor, count):
        """Fetch social list via GraphQL"""
        variables = {"id": user_id, "first": count}
        if cursor:
            variables["after"] = cursor
        
        headers = generate_web_headers(self.cookies)
        
        try:
            response = self.session.get(
                self.GRAPHQL_URL,
                params={'doc_id': doc_id, 'variables': json.dumps(variables)},
                headers=headers,
                timeout=15,
            )
            if response.status_code == 200:
                data = response.json()
                users = self.parser.parse_graphql_users(data)
                pagination = self.parser.get_pagination_info(data)
                return users, pagination
        except Exception as e:
            print(f"  [!] GraphQL social error: {e}")
        return None
    
    def _fetch_social_api(self, user_id, list_type, cursor, count):
        """Fetch social list via REST API"""
        endpoint = "followers" if list_type == "followers" else "following"
        url = f"{self.WEB_API_BASE}/friendships/{user_id}/{endpoint}/"
        headers = generate_web_headers(self.cookies)
        
        params = {'count': count}
        if cursor:
            params['max_id'] = cursor
        
        try:
            response = self.session.get(url, params=params, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                users = []
                for u in data.get('users', []):
                    users.append({
                        'username': u.get('username', ''),
                        'full_name': u.get('full_name', ''),
                        'user_id': str(u.get('pk', '')),
                        'is_private': u.get('is_private', False),
                        'is_verified': u.get('is_verified', False),
                        'profile_pic_url': u.get('profile_pic_url', ''),
                    })
                pagination = {
                    'has_next_page': bool(data.get('next_max_id')),
                    'end_cursor': data.get('next_max_id', ''),
                }
                return users, pagination
        except Exception as e:
            print(f"  [!] REST API social error: {e}")
        return None
    
    # ==================== DELAY & HELPERS ====================
    
    def _adaptive_delay(self, min_sec: float, max_sec: float):
        """Use RL rate limiter if enabled, otherwise static delay"""
        if self.rate_limiter:
            self.rate_limiter.smart_delay()
        else:
            smart_delay(min_sec, max_sec)
    
    # ==================== HELPERS ====================
    
    def _resolve_user_id(self, username: str) -> Optional[str]:
        """Try to resolve username to user_id via search"""
        try:
            headers = generate_web_headers(self.cookies)
            response = self.session.get(
                "https://www.instagram.com/web/search/topsearch/",
                params={'query': username, 'context': 'user'},
                headers=headers,
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                for item in data.get('users', []):
                    u = item.get('user', {})
                    if u.get('username', '').lower() == username.lower():
                        return str(u.get('pk', ''))
        except Exception:
            pass
        return None
    
    def _is_login_wall(self, html: str) -> bool:
        """Detect if Instagram is showing login wall"""
        indicators = [
            'loginForm',
            '"viewerId":null',
            'not-logged-in',
            '/accounts/login/',
        ]
        html_lower = html[:5000].lower()
        matches = sum(1 for ind in indicators if ind.lower() in html_lower)
        return matches >= 2
    
    def _save_debug_data(self, data: Dict, filename: str):
        """Save JSON data for debugging"""
        try:
            filepath = self.debug_dir / filename
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
    
    def _save_debug_html(self, html: str, filename: str):
        """Save HTML for debugging"""
        try:
            filepath = self.debug_dir / filename
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html[:100000])  # Limit size
        except Exception:
            pass
