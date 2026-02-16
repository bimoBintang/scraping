"""
Story Highlights Detection dan Crawling — Algorithm 9

Mengambil Story Highlights permanen dari profil Instagram.
Highlight reels berisi story yang disimpan user secara permanen.

API Flow (2-Step):
1. Tray  → GET /api/v1/highlights/{user_id}/highlights_tray/
2. Items → GET /api/v1/feed/reels_media/?reel_ids=highlight:{id}

Usage:
    from instagram.highlights_crawler import HighlightsCrawler
    
    crawler = HighlightsCrawler(session, make_request_fn, cookies)
    reels = crawler.get_all_highlights(user_id="12345")
    
    for reel in reels:
        print(f"{reel.title}: {len(reel.items)} items")
        for item in reel.items:
            print(f"  {item.media_type}: {item.media_url}")
"""

import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Callable, Dict, List, Optional

import requests

from .utils import generate_mobile_headers, generate_web_headers


# ==================== CONSTANTS ====================

HIGHLIGHTS_TRAY_URL = "https://i.instagram.com/api/v1/highlights/{user_id}/highlights_tray/"
REELS_MEDIA_URL = "https://i.instagram.com/api/v1/feed/reels_media/"
GRAPHQL_HIGHLIGHTS_URL = "https://www.instagram.com/graphql/query/"

# Known doc_ids for highlights (may need discovery refresh)
HIGHLIGHTS_DOC_ID = "7668003626611903"  # PolarisProfileHighlightsTrayContentQuery

# Delay between reel fetches
REEL_FETCH_DELAY = 1.5  # seconds


# ==================== DATA MODELS ====================

@dataclass
class HighlightItem:
    """Single media item within a highlight reel"""
    item_id: str
    media_type: str = "image"       # image, video
    media_url: str = ""
    thumbnail_url: str = ""
    timestamp: int = 0
    expiring_at: int = 0
    duration: float = 0.0           # Video duration in seconds
    width: int = 0
    height: int = 0
    has_audio: bool = False
    
    @property
    def date_str(self) -> str:
        if self.timestamp > 0:
            return datetime.fromtimestamp(self.timestamp).strftime('%Y-%m-%d %H:%M')
        return "N/A"
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d['date_str'] = self.date_str
        return d


@dataclass
class HighlightReel:
    """A single highlight reel (collection of saved stories)"""
    reel_id: str
    title: str = ""
    cover_url: str = ""
    item_count: int = 0
    created_at: int = 0
    
    # Items fetched in second pass
    items: List[HighlightItem] = field(default_factory=list)
    
    @property
    def created_date(self) -> str:
        if self.created_at > 0:
            return datetime.fromtimestamp(self.created_at).strftime('%Y-%m-%d')
        return "N/A"
    
    @property
    def highlight_id(self) -> str:
        """Extract numeric ID from reel_id (e.g., 'highlight:12345' -> '12345')"""
        if ':' in self.reel_id:
            return self.reel_id.split(':')[1]
        return self.reel_id
    
    def to_dict(self) -> Dict:
        d = {
            'reel_id': self.reel_id,
            'highlight_id': self.highlight_id,
            'title': self.title,
            'cover_url': self.cover_url,
            'item_count': self.item_count,
            'created_at': self.created_at,
            'created_date': self.created_date,
            'items': [item.to_dict() for item in self.items],
        }
        return d
    
    def print_reel(self):
        """Print details of this reel"""
        print(f"\n  📂 {self.title} ({self.item_count} items, created {self.created_date})")
        
        media_types = {'image': 0, 'video': 0}
        for item in self.items:
            media_types[item.media_type] = media_types.get(item.media_type, 0) + 1
        
        type_str = ", ".join(f"{k}: {v}" for k, v in media_types.items() if v > 0)
        print(f"    Types: {type_str}")
        
        if self.items:
            oldest = min(self.items, key=lambda i: i.timestamp if i.timestamp > 0 else float('inf'))
            newest = max(self.items, key=lambda i: i.timestamp)
            print(f"    Range: {oldest.date_str} → {newest.date_str}")


# ==================== HIGHLIGHTS CRAWLER ====================

class HighlightsCrawler:
    """
    Fetches Story Highlights from Instagram profiles.
    
    Uses 2-step approach:
    1. Fetch highlights tray (list of reels with metadata)
    2. Fetch individual reel items (media URLs)
    
    Supports both Mobile API and GraphQL endpoints.
    """
    
    def __init__(
        self,
        session: requests.Session,
        make_request: Callable,
        cookies: list,
    ):
        """
        Args:
            session: requests.Session from HybridInstagramClient
            make_request: _make_request function for proxy support
            cookies: Cookie list for authentication
        """
        self.session = session
        self.make_request = make_request
        self.cookies = cookies
    
    def get_highlights_tray(self, user_id: str) -> List[HighlightReel]:
        """
        Step 1: Fetch the highlights tray (list of all highlight reels).
        
        Args:
            user_id: Instagram user ID (numeric)
            
        Returns:
            List of HighlightReel (without items filled)
        """
        reels = []
        
        # Try Mobile API first
        tray = self._fetch_tray_mobile(user_id)
        if tray is not None:
            reels = tray
        else:
            # Fallback to GraphQL
            tray = self._fetch_tray_graphql(user_id)
            if tray is not None:
                reels = tray
        
        return reels
    
    def get_reel_items(self, reel_id: str) -> List[HighlightItem]:
        """
        Step 2: Fetch media items for a specific highlight reel.
        
        Args:
            reel_id: Highlight reel ID (e.g., "highlight:12345")
            
        Returns:
            List of HighlightItem with media URLs
        """
        items = []
        
        # Try Mobile API
        result = self._fetch_reel_items_mobile(reel_id)
        if result is not None:
            items = result
        else:
            # Fallback to GraphQL
            result = self._fetch_reel_items_graphql(reel_id)
            if result is not None:
                items = result
        
        return items
    
    def get_all_highlights(
        self,
        user_id: str,
        fetch_items: bool = True,
    ) -> List[HighlightReel]:
        """
        Fetch all highlights with their items.
        
        Args:
            user_id: Instagram user ID
            fetch_items: If True, fetch items for each reel (slower but complete)
            
        Returns:
            List of HighlightReel with items populated
        """
        print(f"\n  [📂] Fetching highlights tray...")
        reels = self.get_highlights_tray(user_id)
        
        if not reels:
            print("  [!] No highlights found")
            return []
        
        print(f"  [✓] Found {len(reels)} highlight reels")
        
        if fetch_items:
            print(f"  [📥] Fetching items for {len(reels)} reels...")
            for i, reel in enumerate(reels):
                print(f"    [{i+1}/{len(reels)}] {reel.title}...", end=" ")
                
                items = self.get_reel_items(reel.reel_id)
                reel.items = items
                reel.item_count = max(reel.item_count, len(items))
                
                print(f"{len(items)} items")
                
                if i < len(reels) - 1:
                    time.sleep(REEL_FETCH_DELAY)
        
        total_items = sum(len(r.items) for r in reels)
        print(f"  [✓] Total: {len(reels)} reels, {total_items} items")
        
        return reels
    
    # ==================== MOBILE API ====================
    
    def _fetch_tray_mobile(self, user_id: str) -> Optional[List[HighlightReel]]:
        """Fetch highlights tray via Mobile API"""
        url = HIGHLIGHTS_TRAY_URL.format(user_id=user_id)
        headers = generate_mobile_headers(self.cookies)
        
        try:
            response = self.make_request(
                url,
                headers=headers,
                timeout=15,
            )
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            return self._parse_tray_response(data)
            
        except Exception as e:
            print(f"  [!] Mobile tray error: {e}")
            return None
    
    def _fetch_reel_items_mobile(self, reel_id: str) -> Optional[List[HighlightItem]]:
        """Fetch reel items via Mobile API"""
        headers = generate_mobile_headers(self.cookies)
        
        # Ensure format is "highlight:ID"
        if not reel_id.startswith("highlight:"):
            reel_id = f"highlight:{reel_id}"
        
        try:
            response = self.make_request(
                REELS_MEDIA_URL,
                params={'reel_ids': reel_id},
                headers=headers,
                timeout=15,
            )
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            return self._parse_reel_items_response(data, reel_id)
            
        except Exception as e:
            print(f"  [!] Mobile reel error: {e}")
            return None
    
    # ==================== GRAPHQL FALLBACK ====================
    
    def _fetch_tray_graphql(self, user_id: str) -> Optional[List[HighlightReel]]:
        """Fetch highlights tray via GraphQL"""
        headers = generate_web_headers(self.cookies)
        
        variables = {
            "user_id": user_id,
            "include_chaining": False,
            "include_reel": False,
            "include_suggested_users": False,
            "include_logged_out_extras": False,
            "include_highlight_reels": True,
            "include_live_status": False,
        }
        
        try:
            response = self.make_request(
                GRAPHQL_HIGHLIGHTS_URL,
                params={
                    'doc_id': HIGHLIGHTS_DOC_ID,
                    'variables': json.dumps(variables),
                },
                headers=headers,
                timeout=15,
            )
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            return self._parse_graphql_tray(data)
            
        except Exception as e:
            print(f"  [!] GraphQL tray error: {e}")
            return None
    
    def _fetch_reel_items_graphql(self, reel_id: str) -> Optional[List[HighlightItem]]:
        """Fetch reel items via GraphQL"""
        headers = generate_web_headers(self.cookies)
        
        highlight_id = reel_id.split(':')[1] if ':' in reel_id else reel_id
        
        variables = {
            "highlight_reel_ids": [highlight_id],
            "reel_ids": [],
            "location_ids": [],
            "precomposed_overlay": False,
        }
        
        try:
            response = self.make_request(
                GRAPHQL_HIGHLIGHTS_URL,
                params={
                    'doc_id': HIGHLIGHTS_DOC_ID,
                    'variables': json.dumps(variables),
                },
                headers=headers,
                timeout=15,
            )
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            return self._parse_graphql_reel_items(data, reel_id)
            
        except Exception as e:
            print(f"  [!] GraphQL reel error: {e}")
            return None
    
    # ==================== PARSERS ====================
    
    def _parse_tray_response(self, data: Dict) -> List[HighlightReel]:
        """Parse Mobile API highlights tray response"""
        reels = []
        
        tray = data.get('tray', [])
        for item in tray:
            reel_id = item.get('id', '')
            title = item.get('title', 'Untitled')
            
            # Cover image
            cover_media = item.get('cover_media', {})
            cropped_cover = cover_media.get('cropped_image_version', {})
            cover_url = cropped_cover.get('url', '')
            if not cover_url:
                # Fallback to standard cover
                image_versions = cover_media.get('image_versions2', {})
                candidates = image_versions.get('candidates', [])
                if candidates:
                    cover_url = candidates[0].get('url', '')
            
            item_count = item.get('media_count', 0)
            created_at = item.get('created_at', 0)
            
            reels.append(HighlightReel(
                reel_id=str(reel_id),
                title=title,
                cover_url=cover_url,
                item_count=item_count,
                created_at=created_at,
            ))
        
        return reels
    
    def _parse_reel_items_response(
        self,
        data: Dict,
        reel_id: str,
    ) -> List[HighlightItem]:
        """Parse Mobile API reel media response"""
        items = []
        
        reels_media = data.get('reels_media', [])
        if not reels_media:
            # Alternative structure
            reels = data.get('reels', {})
            reel_data = reels.get(reel_id, {})
            media_items = reel_data.get('items', [])
        else:
            media_items = reels_media[0].get('items', [])
        
        for media in media_items:
            item = self._parse_media_item(media)
            if item:
                items.append(item)
        
        return items
    
    def _parse_graphql_tray(self, data: Dict) -> List[HighlightReel]:
        """Parse GraphQL highlights tray response"""
        reels = []
        
        # Navigate nested structure
        user = (
            data.get('data', {})
            .get('user', {})
        )
        
        edges = (
            user.get('edge_highlight_reels', {})
            .get('edges', [])
        )
        
        if not edges:
            # Alternative path
            edges = (
                user.get('highlight_reels', {})
                .get('edges', [])
            )
        
        for edge in edges:
            node = edge.get('node', {})
            reel_id = node.get('id', '')
            title = node.get('title', 'Untitled')
            
            # Cover
            cover = node.get('cover_media_cropped_thumbnail', {})
            cover_url = cover.get('url', '')
            if not cover_url:
                cover = node.get('cover_media', {})
                cover_url = cover.get('thumbnail_src', '')
            
            reels.append(HighlightReel(
                reel_id=f"highlight:{reel_id}" if not str(reel_id).startswith("highlight:") else str(reel_id),
                title=title,
                cover_url=cover_url,
                item_count=node.get('media_count', 0),
            ))
        
        return reels
    
    def _parse_graphql_reel_items(
        self,
        data: Dict,
        reel_id: str,
    ) -> List[HighlightItem]:
        """Parse GraphQL reel items response"""
        items = []
        
        reels_media = (
            data.get('data', {})
            .get('reels_media', [])
        )
        
        for reel in reels_media:
            for edge in reel.get('items', []):
                node = edge if isinstance(edge, dict) else edge.get('node', {})
                item = self._parse_graphql_media_item(node)
                if item:
                    items.append(item)
        
        return items
    
    def _parse_media_item(self, media: Dict) -> Optional[HighlightItem]:
        """Parse a single media item from Mobile API"""
        item_id = str(media.get('pk', '') or media.get('id', ''))
        if not item_id:
            return None
        
        media_type_code = media.get('media_type', 1)
        media_type = 'video' if media_type_code == 2 else 'image'
        
        # Get best quality media URL
        media_url = ''
        thumbnail_url = ''
        width = 0
        height = 0
        
        if media_type == 'video':
            video_versions = media.get('video_versions', [])
            if video_versions:
                # Sort by width (highest first)
                video_versions.sort(key=lambda v: v.get('width', 0), reverse=True)
                media_url = video_versions[0].get('url', '')
                width = video_versions[0].get('width', 0)
                height = video_versions[0].get('height', 0)
            
            # Thumbnail for video
            image_versions = media.get('image_versions2', {})
            candidates = image_versions.get('candidates', [])
            if candidates:
                thumbnail_url = candidates[0].get('url', '')
        else:
            image_versions = media.get('image_versions2', {})
            candidates = image_versions.get('candidates', [])
            if candidates:
                # Sort by width (highest first)
                candidates.sort(key=lambda c: c.get('width', 0), reverse=True)
                media_url = candidates[0].get('url', '')
                width = candidates[0].get('width', 0)
                height = candidates[0].get('height', 0)
                thumbnail_url = media_url
        
        return HighlightItem(
            item_id=item_id,
            media_type=media_type,
            media_url=media_url,
            thumbnail_url=thumbnail_url,
            timestamp=media.get('taken_at', 0),
            expiring_at=media.get('expiring_at', 0),
            duration=media.get('video_duration', 0.0),
            width=width,
            height=height,
            has_audio=media.get('has_audio', False),
        )
    
    def _parse_graphql_media_item(self, node: Dict) -> Optional[HighlightItem]:
        """Parse a single media item from GraphQL response"""
        item_id = str(node.get('id', '') or node.get('pk', ''))
        if not item_id:
            return None
        
        is_video = node.get('is_video', False)
        media_type = 'video' if is_video else 'image'
        
        # Media URL
        if is_video:
            media_url = node.get('video_url', '')
            thumbnail_url = node.get('display_url', '') or node.get('thumbnail_src', '')
        else:
            media_url = node.get('display_url', '') or node.get('thumbnail_src', '')
            thumbnail_url = media_url
        
        # Dimensions
        dimensions = node.get('dimensions', {})
        width = dimensions.get('width', 0)
        height = dimensions.get('height', 0)
        
        return HighlightItem(
            item_id=item_id,
            media_type=media_type,
            media_url=media_url,
            thumbnail_url=thumbnail_url,
            timestamp=node.get('taken_at_timestamp', 0),
            duration=node.get('video_duration', 0.0),
            width=width,
            height=height,
            has_audio=node.get('has_audio', False),
        )
    
    # ==================== DISPLAY ====================
    
    def print_highlights_summary(self, reels: List[HighlightReel]):
        """Print formatted highlights summary"""
        if not reels:
            print("  [!] No highlights to display")
            return
        
        total_items = sum(len(r.items) for r in reels)
        total_images = sum(1 for r in reels for i in r.items if i.media_type == 'image')
        total_videos = sum(1 for r in reels for i in r.items if i.media_type == 'video')
        
        print(f"""
╔══════════════════════════════════════════════════════════════╗
║   📂 Story Highlights Summary                                ║
╠══════════════════════════════════════════════════════════════╣
║  Reels: {len(reels):<10} Items: {total_items:<10} 📸 {total_images}  🎬 {total_videos:<14}║
╠══════════════════════════════════════════════════════════════╣""")
        
        print(f"║  {'#':<4} {'Title':<24} {'Items':>6} {'📸':>4} {'🎬':>4} {'Created':<12}   ║")
        print(f"║  {'─'*4} {'─'*24} {'─'*6} {'─'*4} {'─'*4} {'─'*12}   ║")
        
        for idx, reel in enumerate(reels, 1):
            images = sum(1 for i in reel.items if i.media_type == 'image')
            videos = sum(1 for i in reel.items if i.media_type == 'video')
            title_display = reel.title[:22] + '..' if len(reel.title) > 24 else reel.title
            
            print(f"║  {idx:<4} {title_display:<24} {reel.item_count:>6} {images:>4} {videos:>4} {reel.created_date:<12}   ║")
        
        print("╚══════════════════════════════════════════════════════════════╝")
        
        # Print each reel detail if items were fetched
        if any(r.items for r in reels):
            for reel in reels:
                reel.print_reel()
