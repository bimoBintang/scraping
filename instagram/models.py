"""
Instagram Scraper - Data Models
Profile, Post, Story, Location data structures
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple


@dataclass
class InstagramProfile:
    """Data class untuk menyimpan informasi profil Instagram"""
    username: str
    full_name: str = "N/A"
    bio: str = ""
    followers: int = 0
    following: int = 0
    post_count: int = 0
    is_private: bool = False
    is_verified: bool = False
    is_business: bool = False
    profile_pic_url: str = ""
    external_url: str = ""
    category: str = ""
    user_id: str = ""
    
    def formatted_stats(self) -> Dict[str, str]:
        """Return stats dengan format K/M/B"""
        return {
            'followers': self._format_number(self.followers),
            'following': self._format_number(self.following),
            'posts': self._format_number(self.post_count),
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
        status = []
        if self.is_verified:
            status.append("[VERIFIED]")
        if self.is_private:
            status.append("[PRIVATE]")
        if self.is_business:
            status.append("[BUSINESS]")
        status_str = " ".join(status)
        
        return f"""
+--------------------------------------------------+
| Instagram Profile: @{self.username}
+--------------------------------------------------+
| Name      : {self.full_name}
| Followers : {stats['followers']}
| Following : {stats['following']}
| Posts      : {stats['posts']}
| Bio       : {self.bio[:50]}{'...' if len(self.bio) > 50 else ''}
| Category  : {self.category or 'N/A'}
| Link      : {self.external_url or 'N/A'}
| {status_str}
+--------------------------------------------------+"""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        data = asdict(self)
        data['formatted_stats'] = self.formatted_stats()
        return data


@dataclass
class InstagramPost:
    """Data class untuk postingan Instagram"""
    shortcode: str
    post_type: str = "image"       # image, video, carousel
    caption: str = ""
    likes: int = 0
    comments: int = 0
    timestamp: int = 0
    media_url: str = ""
    is_video: bool = False
    video_views: int = 0
    location: Optional[Dict] = None
    hashtags: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        # Auto-extract hashtags from caption
        if self.caption and not self.hashtags:
            import re
            self.hashtags = re.findall(r'#(\w+)', self.caption)
    
    @property
    def url(self) -> str:
        return f"https://www.instagram.com/p/{self.shortcode}/"
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data['url'] = self.url
        return data


@dataclass
class InstagramStory:
    """Data class untuk Instagram Story"""
    story_id: str
    media_type: str = "image"      # image, video
    timestamp: int = 0
    media_url: str = ""
    duration: float = 0.0
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class LocationPoint:
    """Geographic location dari post"""
    location_id: str
    name: str
    latitude: float = 0.0
    longitude: float = 0.0
    post_count: int = 0
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class UserCluster:
    """Cluster geografis dari users"""
    cluster_id: int
    users: List[str] = field(default_factory=list)
    centroid: Tuple[float, float] = (0.0, 0.0)
    city: str = ""
    country: str = ""
    confidence: float = 0.0
    location_count: int = 0
    
    def to_dict(self) -> Dict:
        return asdict(self)
