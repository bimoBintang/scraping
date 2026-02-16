"""
Instagram GraphQL doc_id Discovery — Algorithm 2

Auto-discover Instagram GraphQL doc_ids by:
1. Visit instagram.com, capture all <script> tags with src attributes
2. Fetch and parse JavaScript bundles
3. Regex match for doc_id patterns in query definitions
4. Map doc_ids to query types (posts, followers, following, comments)
5. Cache results with TTL (default: 7 days)

Eliminates the need for manual doc_id maintenance when Instagram
updates their GraphQL schema (every 2-4 weeks).
"""

import re
import json
import time
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

from .utils import generate_browser_headers, smart_delay


# Query type signatures — used to match doc_ids to their purpose
QUERY_SIGNATURES: Dict[str, List[str]] = {
    "user_posts": [
        "edge_owner_to_timeline_media",
        "PolarisProfilePostsQuery",
        "xdt_api__v1__feed__user_timeline_graphql_connection",
    ],
    "user_followers": [
        "edge_followed_by",
        "PolarisProfileFollowersQuery",
        "xdt_api__v1__friendships__followers",
    ],
    "user_following": [
        "edge_follow",
        "PolarisProfileFollowingQuery", 
        "xdt_api__v1__friendships__following",
    ],
    "post_comments": [
        "edge_media_to_comment",
        "CommentsQuery",
        "xdt_api__v1__media__comments",
    ],
    "post_likes": [
        "edge_liked_by",
        "LikesQuery",
        "xdt_api__v1__media__likers",
    ],
    "user_info": [
        "PolarisProfilePageQuery",
        "user_detail",
        "xdt_api__v1__users__web_profile_info",
    ],
}

# Cache file location
DEFAULT_CACHE_FILE = "instagram_doc_ids.json"
CACHE_TTL_DAYS = 7


class DocIdDiscovery:
    """
    Automatically discover Instagram GraphQL doc_ids.
    
    Usage:
        discovery = DocIdDiscovery()
        doc_ids = await discovery.discover_all()
        
        # Get specific doc_id
        posts_doc_id = discovery.get_doc_id("user_posts")
    """
    
    def __init__(self, cache_file: Optional[str] = None, cache_ttl_days: int = CACHE_TTL_DAYS):
        self.cache_file = Path(cache_file or DEFAULT_CACHE_FILE)
        self.cache_ttl = timedelta(days=cache_ttl_days)
        self._cache: Dict[str, Dict] = {}
        self._load_cache()
    
    def get_doc_id(self, query_type: str) -> Optional[str]:
        """
        Get cached doc_id for a query type.
        Returns None if not cached or expired.
        
        Args:
            query_type: One of QUERY_SIGNATURES keys
        """
        if query_type in self._cache:
            entry = self._cache[query_type]
            cached_time = datetime.fromisoformat(entry.get('discovered_at', '2000-01-01'))
            if datetime.now() - cached_time < self.cache_ttl:
                return entry.get('doc_id')
            else:
                print(f"  [!] doc_id for {query_type} expired (cached {cached_time})")
        return None
    
    def get_all_doc_ids(self) -> Dict[str, str]:
        """Get all valid (non-expired) doc_ids"""
        result = {}
        for query_type in QUERY_SIGNATURES:
            doc_id = self.get_doc_id(query_type)
            if doc_id:
                result[query_type] = doc_id
        return result
    
    def discover_all(self) -> Dict[str, str]:
        """
        Discover all doc_ids by fetching and parsing Instagram's JS bundles.
        
        Returns:
            Dict mapping query_type to doc_id
        """
        print("\n[*] Starting doc_id discovery...")
        
        # Check cache first
        cached = self.get_all_doc_ids()
        if len(cached) >= len(QUERY_SIGNATURES) * 0.5:
            print(f"  [+] Using cached doc_ids ({len(cached)}/{len(QUERY_SIGNATURES)} types)")
            return cached
        
        try:
            # Step 1: Fetch Instagram homepage to get script URLs
            script_urls = self._get_script_urls()
            if not script_urls:
                print("  [!] No script URLs found")
                return cached
            
            print(f"  [+] Found {len(script_urls)} JavaScript bundles")
            
            # Step 2: Fetch and parse each bundle
            discovered = {}
            for i, url in enumerate(script_urls):
                if len(discovered) >= len(QUERY_SIGNATURES):
                    break  # Found all
                
                new_ids = self._parse_bundle(url)
                discovered.update(new_ids)
                
                if new_ids:
                    print(f"  [+] Bundle {i+1}: found {len(new_ids)} doc_ids")
                
                smart_delay(0.5, 1.5)
            
            # Step 3: Cache results
            if discovered:
                self._update_cache(discovered)
                print(f"\n  [✓] Discovered {len(discovered)} doc_ids total")
            else:
                print("\n  [!] No doc_ids discovered from bundles")
            
            # Merge with any remaining cached
            result = {**cached, **discovered}
            return result
            
        except Exception as e:
            print(f"  [!] Discovery error: {e}")
            return cached
    
    def _get_script_urls(self) -> List[str]:
        """Fetch Instagram homepage and extract JS bundle URLs"""
        try:
            headers = generate_browser_headers()
            response = requests.get(
                "https://www.instagram.com/",
                headers=headers,
                timeout=15,
                allow_redirects=True
            )
            
            if response.status_code != 200:
                print(f"  [!] Homepage returned HTTP {response.status_code}")
                return []
            
            html = response.text
            
            # Find all script tags with src
            script_pattern = r'<script[^>]+src=["\']([^"\']*(?:Consumer|ProfilePage|Bundle|Polaris|polaris)[^"\']*\.js)["\']'
            urls = re.findall(script_pattern, html, re.IGNORECASE)
            
            # Also find generic bundled scripts
            generic_pattern = r'<script[^>]+src=["\']([^"\']+/static/bundles/[^"\']+\.js)["\']'
            urls.extend(re.findall(generic_pattern, html))
            
            # Also check for chunked scripts
            chunk_pattern = r'<script[^>]+src=["\']([^"\']+\.js\?[^"\']*)["\']'
            chunk_urls = re.findall(chunk_pattern, html)
            # Filter to likely relevant bundles
            for url in chunk_urls:
                if any(kw in url.lower() for kw in ['consumer', 'profile', 'polaris', 'main', 'vendor']):
                    urls.append(url)
            
            # Deduplicate and make absolute
            seen = set()
            absolute_urls = []
            for url in urls:
                if url in seen:
                    continue
                seen.add(url)
                if url.startswith('//'):
                    url = 'https:' + url
                elif url.startswith('/'):
                    url = 'https://www.instagram.com' + url
                absolute_urls.append(url)
            
            return absolute_urls[:15]  # Limit to 15 bundles
            
        except Exception as e:
            print(f"  [!] Error fetching homepage: {e}")
            return []
    
    def _parse_bundle(self, url: str) -> Dict[str, str]:
        """Fetch a JS bundle and extract doc_ids"""
        discovered = {}
        
        try:
            headers = generate_browser_headers()
            headers['Accept'] = '*/*'
            headers['Referer'] = 'https://www.instagram.com/'
            
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                return {}
            
            js_content = response.text
            
            # Pattern 1: e.params.doc_id="12345"
            doc_id_patterns = [
                r'doc_id\s*[=:]\s*["\'](\d{10,20})["\']',
                r'"doc_id"\s*:\s*"(\d{10,20})"',
                r'queryId\s*[=:]\s*["\'](\d{10,20})["\']',
                r'query_id\s*[=:]\s*["\'](\d{10,20})["\']',
            ]
            
            # Find all doc_ids in the bundle
            all_doc_ids: List[Tuple[int, str]] = []
            for pattern in doc_id_patterns:
                for match in re.finditer(pattern, js_content):
                    pos = match.start()
                    doc_id = match.group(1)
                    all_doc_ids.append((pos, doc_id))
            
            if not all_doc_ids:
                return {}
            
            # For each doc_id, look at surrounding context to determine query type
            for pos, doc_id in all_doc_ids:
                # Get context: 2000 chars before and after
                ctx_start = max(0, pos - 2000)
                ctx_end = min(len(js_content), pos + 2000)
                context = js_content[ctx_start:ctx_end]
                
                # Match against signatures
                for query_type, signatures in QUERY_SIGNATURES.items():
                    if query_type in discovered:
                        continue
                    
                    for sig in signatures:
                        if sig.lower() in context.lower():
                            discovered[query_type] = doc_id
                            break
            
            return discovered
            
        except Exception as e:
            return {}
    
    # ==================== CACHE MANAGEMENT ====================
    
    def _load_cache(self):
        """Load cached doc_ids from file"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    self._cache = json.load(f)
                print(f"  [+] Loaded doc_id cache: {len(self._cache)} entries")
            except (json.JSONDecodeError, Exception):
                self._cache = {}
    
    def _save_cache(self):
        """Save doc_id cache to file"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self._cache, f, indent=2)
        except Exception as e:
            print(f"  [!] Error saving cache: {e}")
    
    def _update_cache(self, discovered: Dict[str, str]):
        """Update cache with newly discovered doc_ids"""
        now = datetime.now().isoformat()
        for query_type, doc_id in discovered.items():
            self._cache[query_type] = {
                'doc_id': doc_id,
                'discovered_at': now,
            }
        self._save_cache()
    
    def clear_cache(self):
        """Clear all cached doc_ids"""
        self._cache = {}
        if self.cache_file.exists():
            self.cache_file.unlink()
        print("  [+] Cache cleared")
    
    def cache_status(self) -> Dict:
        """Get cache status summary"""
        status = {}
        now = datetime.now()
        for query_type in QUERY_SIGNATURES:
            entry = self._cache.get(query_type)
            if entry:
                cached_time = datetime.fromisoformat(entry['discovered_at'])
                age = now - cached_time
                status[query_type] = {
                    'doc_id': entry['doc_id'],
                    'age_days': age.days,
                    'expired': age > self.cache_ttl,
                }
            else:
                status[query_type] = {'doc_id': None, 'age_days': None, 'expired': True}
        return status
