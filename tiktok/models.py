"""
TikTok Profile Model
Data class untuk menyimpan informasi profil TikTok
"""

from dataclasses import dataclass, asdict
from typing import Dict


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
    avatar_url: str = ""
    
    def formatted_stats(self) -> Dict[str, str]:
        """Return stats dengan format K/M/B"""
        return {
            'followers': self._format_number(self.followers),
            'following': self._format_number(self.following),
            'likes': self._format_number(self.likes),
            'videos': self._format_number(self.video_count),
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
        if self.verified:
            status.append("[VERIFIED]")
        if self.private:
            status.append("[PRIVATE]")
        status_str = " ".join(status)
        
        return f"""
+--------------------------------------------------+
| TikTok Profile: @{self.username}
+--------------------------------------------------+
| Nickname  : {self.nickname}
| Followers : {stats['followers']}
| Following : {stats['following']}
| Likes     : {stats['likes']}
| Videos    : {stats['videos']}
| Bio       : {self.bio[:40]}{'...' if len(self.bio) > 40 else ''}
| {status_str}
+--------------------------------------------------+"""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        data = asdict(self)
        data['formatted_stats'] = self.formatted_stats()
        return data
