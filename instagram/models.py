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


# ==================== Algorithm 11: Private Account Anomaly Detection ====================

@dataclass
class CommentData:
    """A single comment from a public post"""
    comment_id: str
    text: str = ""
    author: str = ""
    author_id: str = ""
    timestamp: int = 0
    likes: int = 0
    post_shortcode: str = ""
    mentions: List[str] = field(default_factory=list)
    is_reply: bool = False
    parent_id: str = ""
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class MentionEdge:
    """A directional mention relationship: source → mentioned user"""
    source_user: str
    mentioned_user: str
    frequency: int = 1
    contexts: List[str] = field(default_factory=list)  # snippet around each mention
    post_shortcodes: List[str] = field(default_factory=list)
    first_seen: int = 0
    last_seen: int = 0
    source_followers: int = 0
    source_is_verified: bool = False
    
    @property
    def weight(self) -> float:
        """Connection strength: frequency * log(source_followers)"""
        import math
        follower_factor = math.log10(max(self.source_followers, 10))
        verified_bonus = 1.5 if self.source_is_verified else 1.0
        return self.frequency * follower_factor * verified_bonus
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d['weight'] = self.weight
        return d


@dataclass
class PrivateAccountReport:
    """Inferred report for a private Instagram account"""
    username: str
    is_private: bool = True
    
    # Inferred stats
    estimated_followers: int = 0
    estimated_following: int = 0
    confidence: float = 0.0           # 0.0 to 1.0
    
    # Network data
    mentioning_users: List[str] = field(default_factory=list)
    mention_edges: List[MentionEdge] = field(default_factory=list)
    total_mentions: int = 0
    unique_mentioners: int = 0
    
    # Anomaly signals
    activity_score: float = 0.0       # how active despite being private
    network_density: float = 0.0      # how interconnected the mentioners are
    ghost_score: float = 0.0          # 0=very active, 1=zero indirect presence
    
    # Context
    connected_public_accounts: List[str] = field(default_factory=list)
    common_hashtags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        d = {
            'username': self.username,
            'is_private': self.is_private,
            'estimated_followers': self.estimated_followers,
            'estimated_following': self.estimated_following,
            'confidence': round(self.confidence, 3),
            'mentioning_users': self.mentioning_users,
            'total_mentions': self.total_mentions,
            'unique_mentioners': self.unique_mentioners,
            'activity_score': round(self.activity_score, 3),
            'network_density': round(self.network_density, 3),
            'ghost_score': round(self.ghost_score, 3),
            'connected_public_accounts': self.connected_public_accounts,
            'common_hashtags': self.common_hashtags,
            'mention_edges': [e.to_dict() for e in self.mention_edges],
        }
        return d
