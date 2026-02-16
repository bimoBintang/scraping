"""
Instagram Data Parsers — Algorithm 3: Multi-Fallback HTML Parsing

4-strategy parsing pipeline:
  Strategy 1: window._sharedData (script tag JSON)
  Strategy 2: __additionalDataLoaded (XHR-injected data)  
  Strategy 3: __require / ScheduledServerJS definitions
  Strategy 4: Regex pattern matching (JSON-like structures)

On complete failure: saves HTML snapshot for future analysis.
"""

import re
import json
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime

from .models import InstagramProfile, InstagramPost, InstagramStory


class InstagramParser:
    """
    Multi-fallback HTML parsing for Instagram pages.
    
    Tries 4 strategies in order of reliability, falling back
    to the next when one fails. Saves HTML snapshots on
    complete failure for debugging.
    """
    
    def __init__(self, debug_dir: str = "."):
        self.debug_dir = Path(debug_dir)
        self._last_strategy: Optional[str] = None
    
    @property
    def last_strategy(self) -> Optional[str]:
        """Name of the last successful parsing strategy"""
        return self._last_strategy
    
    # ==================== MAIN ENTRY POINT ====================
    
    def parse_profile_page(self, html: str, username: str) -> Optional[InstagramProfile]:
        """
        Try all parsing strategies in order until one succeeds.
        
        Args:
            html: Raw HTML content of Instagram profile page
            username: Target username
            
        Returns:
            InstagramProfile or None if all strategies fail
        """
        strategies = [
            ("shared_data", self._parse_shared_data),
            ("additional_data", self._parse_additional_data),
            ("require_defs", self._parse_require_defs),
            ("regex_fallback", self._parse_regex_fallback),
        ]
        
        for name, strategy in strategies:
            try:
                result = strategy(html, username)
                if result:
                    self._last_strategy = name
                    print(f"  [+] Parsed via strategy: {name}")
                    return result
            except Exception as e:
                print(f"  [!] Strategy {name} failed: {e}")
                continue
        
        # All strategies failed — save snapshot
        self._save_failure_snapshot(html, username)
        return None
    
    def parse_posts_from_html(self, html: str) -> List[InstagramPost]:
        """Extract posts from profile page HTML"""
        data = self._extract_any_json(html)
        if not data:
            return []
        
        # Try to find posts in the data
        posts = []
        edges = self._find_nested_key(data, 'edge_owner_to_timeline_media')
        if edges and 'edges' in edges:
            for edge in edges['edges']:
                node = edge.get('node', {})
                post = self._node_to_post(node)
                if post:
                    posts.append(post)
        
        return posts
    
    # ==================== STRATEGY 1: SharedData ====================
    
    def _parse_shared_data(self, html: str, username: str) -> Optional[InstagramProfile]:
        """
        Parse window._sharedData = {...};
        Classic Instagram data embedding method.
        """
        pattern = r'window\._sharedData\s*=\s*({.*?});\s*</script>'
        match = re.search(pattern, html, re.DOTALL)
        
        if not match:
            return None
        
        data = json.loads(match.group(1))
        
        # Navigate: entry_data -> ProfilePage[0] -> graphql -> user
        entry_data = data.get('entry_data', {})
        profile_pages = entry_data.get('ProfilePage', [])
        
        if not profile_pages:
            return None
        
        user = profile_pages[0].get('graphql', {}).get('user', {})
        if not user:
            user = profile_pages[0].get('user', {})
        
        if not user:
            return None
        
        return self._user_dict_to_profile(user, username)
    
    # ==================== STRATEGY 2: AdditionalDataLoaded ====================
    
    def _parse_additional_data(self, html: str, username: str) -> Optional[InstagramProfile]:
        """
        Parse __additionalDataLoaded('/<username>/', {...});
        Used when SharedData doesn't contain full profile data.
        """
        # Pattern for additionalDataLoaded
        patterns = [
            rf"__additionalDataLoaded\s*\(\s*['\"]/{re.escape(username)}/['\"]\s*,\s*(\{{.*?\}})\s*\)\s*;",
            r"__additionalDataLoaded\s*\(\s*['\"][^'\"]*['\"]\s*,\s*(\{.*?\})\s*\)\s*;",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    user = data.get('graphql', {}).get('user', {})
                    if not user:
                        user = data.get('user', {})
                    if user:
                        return self._user_dict_to_profile(user, username)
                except json.JSONDecodeError:
                    continue
        
        return None
    
    # ==================== STRATEGY 3: Require Definitions ====================
    
    def _parse_require_defs(self, html: str, username: str) -> Optional[InstagramProfile]:
        """
        Parse require("ScheduledServerJS").handle({...}) or
        requireLazy([...], function(module) {...}) patterns.
        
        Modern Instagram embeds data via module system.
        """
        # Pattern for ScheduledServerJS
        patterns = [
            r'requireLazy\(\[.*?\],\s*function\s*\([^)]*\)\s*\{.*?\"user\"\s*:\s*(\{.*?\})\s*[,}]',
            r'"ScheduledServerJS".*?"user"\s*:\s*(\{[^}]+(?:\{[^}]*\}[^}]*)*\})',
            r'handle\(\s*\{.*?"user"\s*:\s*(\{.*?\})\s*[,}]',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, html, re.DOTALL)
            for match in matches:
                try:
                    user_str = match.group(1)
                    # Attempt JSON parse — may need to fix truncation
                    user = json.loads(user_str)
                    profile = self._user_dict_to_profile(user, username)
                    if profile and profile.user_id:
                        return profile
                except json.JSONDecodeError:
                    continue
        
        # Alternative: find any JSON blob containing the username
        user_pattern = rf'"username"\s*:\s*"{re.escape(username)}"'
        if re.search(user_pattern, html):
            # Try to extract the containing object
            return self._extract_user_object_around(html, username)
        
        return None
    
    def _extract_user_object_around(self, html: str, username: str) -> Optional[InstagramProfile]:
        """Find and extract user JSON object around a username match"""
        pattern = rf'"username"\s*:\s*"{re.escape(username)}"'
        match = re.search(pattern, html)
        if not match:
            return None
        
        # Look backwards and forwards for object boundaries
        pos = match.start()
        start = html.rfind('{', max(0, pos - 5000), pos)
        if start == -1:
            return None
        
        # Try incrementally larger chunks
        for end_offset in [1000, 3000, 5000, 10000]:
            end = min(pos + end_offset, len(html))
            chunk = html[start:end]
            
            # Balance braces
            depth = 0
            for i, ch in enumerate(chunk):
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        try:
                            obj = json.loads(chunk[:i+1])
                            if isinstance(obj, dict) and obj.get('username') == username:
                                return self._user_dict_to_profile(obj, username)
                        except json.JSONDecodeError:
                            break
        
        return None
    
    # ==================== STRATEGY 4: Regex Fallback ====================
    
    def _parse_regex_fallback(self, html: str, username: str) -> Optional[InstagramProfile]:
        """
        Last resort: regex extraction of individual fields.
        Less reliable but works when JSON structure is broken.
        """
        profile = InstagramProfile(username=username)
        found_any = False
        
        # Full name
        name_match = re.search(r'"full_name"\s*:\s*"([^"]*)"', html)
        if name_match:
            profile.full_name = name_match.group(1).encode().decode('unicode_escape')
            found_any = True
        
        # Bio
        bio_match = re.search(r'"biography"\s*:\s*"([^"]*)"', html)
        if bio_match:
            profile.bio = bio_match.group(1).encode().decode('unicode_escape')
            found_any = True
        
        # Followers
        follower_match = re.search(r'"edge_followed_by"\s*:\s*\{\s*"count"\s*:\s*(\d+)', html)
        if follower_match:
            profile.followers = int(follower_match.group(1))
            found_any = True
        
        # Following
        following_match = re.search(r'"edge_follow"\s*:\s*\{\s*"count"\s*:\s*(\d+)', html)
        if following_match:
            profile.following = int(following_match.group(1))
            found_any = True
        
        # Post count
        posts_match = re.search(r'"edge_owner_to_timeline_media"\s*:\s*\{\s*"count"\s*:\s*(\d+)', html)
        if posts_match:
            profile.post_count = int(posts_match.group(1))
            found_any = True
        
        # Verified
        if re.search(r'"is_verified"\s*:\s*true', html):
            profile.is_verified = True
            found_any = True
        
        # Private
        if re.search(r'"is_private"\s*:\s*true', html):
            profile.is_private = True
            found_any = True
        
        # Business
        if re.search(r'"is_business_account"\s*:\s*true', html):
            profile.is_business = True
            found_any = True
        
        # User ID
        id_match = re.search(r'"id"\s*:\s*"(\d+)"', html)
        if id_match:
            profile.user_id = id_match.group(1)
            found_any = True
        
        # Profile pic
        pic_match = re.search(r'"profile_pic_url_hd"\s*:\s*"([^"]*)"', html)
        if not pic_match:
            pic_match = re.search(r'"profile_pic_url"\s*:\s*"([^"]*)"', html)
        if pic_match:
            profile.profile_pic_url = pic_match.group(1).replace('\\u0026', '&')
            found_any = True
        
        # External URL
        url_match = re.search(r'"external_url"\s*:\s*"([^"]*)"', html)
        if url_match and url_match.group(1) != 'null':
            profile.external_url = url_match.group(1)
        
        # Category
        cat_match = re.search(r'"category_name"\s*:\s*"([^"]*)"', html)
        if cat_match:
            profile.category = cat_match.group(1)
        
        return profile if found_any else None
    
    # ==================== API RESPONSE PARSERS ====================
    
    def parse_web_profile_info(self, data: Dict, username: str) -> Optional[InstagramProfile]:
        """
        Parse response from i.instagram.com/api/v1/users/web_profile_info/
        
        Args:
            data: JSON response dict
            username: Target username
            
        Returns:
            InstagramProfile or None
        """
        user = data.get('data', {}).get('user', {})
        if not user:
            user = data.get('user', {})
        if not user:
            return None
        
        return self._user_dict_to_profile(user, username)
    
    def parse_graphql_posts(self, data: Dict) -> List[InstagramPost]:
        """Parse posts from GraphQL API response"""
        posts = []
        
        # Navigate through possible paths
        edges_data = None
        
        # Path 1: data -> user -> edge_owner_to_timeline_media
        user = data.get('data', {}).get('user', {})
        if user:
            edges_data = user.get('edge_owner_to_timeline_media', {})
        
        # Path 2: graphql -> user -> edge_owner_to_timeline_media
        if not edges_data:
            user = data.get('graphql', {}).get('user', {})
            if user:
                edges_data = user.get('edge_owner_to_timeline_media', {})
        
        if not edges_data:
            return posts
        
        for edge in edges_data.get('edges', []):
            node = edge.get('node', {})
            post = self._node_to_post(node)
            if post:
                posts.append(post)
        
        return posts
    
    def parse_graphql_users(self, data: Dict) -> List[Dict]:
        """Parse followers/following from GraphQL response"""
        users = []
        
        # Find edges in various paths
        for key in ['edge_followed_by', 'edge_follow', 'edge_mutual_followed_by']:
            edges_data = self._find_nested_key(data, key)
            if edges_data and 'edges' in edges_data:
                for edge in edges_data['edges']:
                    node = edge.get('node', {})
                    if node:
                        users.append({
                            'username': node.get('username', ''),
                            'full_name': node.get('full_name', ''),
                            'user_id': node.get('id', ''),
                            'is_private': node.get('is_private', False),
                            'is_verified': node.get('is_verified', False),
                            'profile_pic_url': node.get('profile_pic_url', ''),
                        })
                break
        
        return users
    
    def get_pagination_info(self, data: Dict) -> Dict:
        """Extract pagination cursor from GraphQL response"""
        for key in ['edge_owner_to_timeline_media', 'edge_followed_by', 'edge_follow']:
            edges_data = self._find_nested_key(data, key)
            if edges_data:
                page_info = edges_data.get('page_info', {})
                return {
                    'has_next_page': page_info.get('has_next_page', False),
                    'end_cursor': page_info.get('end_cursor', ''),
                }
        return {'has_next_page': False, 'end_cursor': ''}
    
    # ==================== HELPERS ====================
    
    def _user_dict_to_profile(self, user: Dict, username: str) -> InstagramProfile:
        """Convert a user dict (from any source) to InstagramProfile"""
        # Handle both graphql and API formats
        followers = (
            user.get('edge_followed_by', {}).get('count', 0)
            or user.get('follower_count', 0)
        )
        following = (
            user.get('edge_follow', {}).get('count', 0)
            or user.get('following_count', 0)
        )
        post_count = (
            user.get('edge_owner_to_timeline_media', {}).get('count', 0)
            or user.get('media_count', 0)
        )
        
        return InstagramProfile(
            username=user.get('username', username),
            full_name=user.get('full_name', 'N/A'),
            bio=user.get('biography', '') or user.get('bio', ''),
            followers=followers,
            following=following,
            post_count=post_count,
            is_private=user.get('is_private', False),
            is_verified=user.get('is_verified', False),
            is_business=user.get('is_business_account', False) or user.get('is_business', False),
            profile_pic_url=user.get('profile_pic_url_hd', '') or user.get('profile_pic_url', '') or user.get('hd_profile_pic_url_info', {}).get('url', ''),
            external_url=user.get('external_url', '') or '',
            category=user.get('category_name', '') or user.get('category', '') or '',
            user_id=str(user.get('id', '') or user.get('pk', '') or user.get('pk_id', '')),
        )
    
    def _node_to_post(self, node: Dict) -> Optional[InstagramPost]:
        """Convert a GraphQL edge node to InstagramPost"""
        if not node:
            return None
        
        shortcode = node.get('shortcode', '')
        if not shortcode:
            return None
        
        # Determine post type
        typename = node.get('__typename', '')
        if typename == 'GraphVideo' or node.get('is_video', False):
            post_type = 'video'
        elif typename == 'GraphSidecar':
            post_type = 'carousel'
        else:
            post_type = 'image'
        
        # Extract caption
        caption = ''
        caption_edges = node.get('edge_media_to_caption', {}).get('edges', [])
        if caption_edges:
            caption = caption_edges[0].get('node', {}).get('text', '')
        
        # Extract location
        location = None
        loc_data = node.get('location')
        if loc_data and isinstance(loc_data, dict):
            location = {
                'id': loc_data.get('id', ''),
                'name': loc_data.get('name', ''),
                'slug': loc_data.get('slug', ''),
                'lat': loc_data.get('lat', 0),
                'lng': loc_data.get('lng', 0),
            }
        
        return InstagramPost(
            shortcode=shortcode,
            post_type=post_type,
            caption=caption,
            likes=node.get('edge_liked_by', {}).get('count', 0) or node.get('edge_media_preview_like', {}).get('count', 0),
            comments=node.get('edge_media_to_comment', {}).get('count', 0) or node.get('edge_media_preview_comment', {}).get('count', 0),
            timestamp=node.get('taken_at_timestamp', 0),
            media_url=node.get('display_url', '') or node.get('thumbnail_src', ''),
            is_video=node.get('is_video', False),
            video_views=node.get('video_view_count', 0),
            location=location,
        )
    
    def _extract_any_json(self, html: str) -> Optional[Dict]:
        """Try to extract any embedded JSON data from HTML"""
        patterns = [
            r'window\._sharedData\s*=\s*({.*?});\s*</script>',
            r'__additionalDataLoaded\s*\([^,]*,\s*({.*?})\s*\)\s*;',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue
        return None
    
    def _find_nested_key(self, data, target_key, max_depth=10):
        """Recursively find a key in nested dict"""
        if max_depth <= 0:
            return None
        
        if isinstance(data, dict):
            if target_key in data:
                return data[target_key]
            for value in data.values():
                result = self._find_nested_key(value, target_key, max_depth - 1)
                if result is not None:
                    return result
        elif isinstance(data, list):
            for item in data[:10]:  # Limit list traversal
                result = self._find_nested_key(item, target_key, max_depth - 1)
                if result is not None:
                    return result
        
        return None
    
    def _save_failure_snapshot(self, html: str, username: str):
        """Save HTML snapshot when all parsing strategies fail"""
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filepath = self.debug_dir / f"instagram_parse_fail_{username}_{timestamp}.html"
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"  [!] All strategies failed. HTML snapshot saved: {filepath}")
        except Exception as e:
            print(f"  [!] Failed to save snapshot: {e}")


# ==================== CONVENIENCE FUNCTIONS ====================

def parse_profile_data(html: str, username: str) -> Optional[InstagramProfile]:
    """Parse profile data from HTML - convenience function"""
    parser = InstagramParser()
    return parser.parse_profile_page(html, username)
