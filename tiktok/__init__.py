"""
TikTok Scraper Package v4.2.0
Advanced scraper with stealth, BFS/DFS, DOM manipulation, rotation, delays, export
"""

from .models import TikTokProfile
from .scraper import TikTokScraper
from .browser import BrowserManager
from .algorithms import (
    GraphCrawler, 
    crawl_network,
    AStarCrawler,
    BidirectionalSearch,
    RandomWalkSampler,
    InfluenceScorer,
    CommunityDetector
)
from .rotation import (
    UserAgentRotator, ProxyRotator, Proxy,
    ProxyChain, ProxyChainConfig, ResidentialProxyManager, AutoRotatingProxy
)
from .delays import DelayManager, get_delay_manager
from .sniffer import APISniffer
from .export import DataExporter
from .reconnaissance import TikTokReconnaissance
from .injection import TikTokInjector
from .maintenance import TikTokMaintenance

# Stealth modules
from .fingerprint import (
    FingerprintProfile, FingerprintGenerator, 
    FingerprintSpoofing, IdentityManager
)
from .human_behavior import HumanBehavior, HumanMouse, HumanScroll, HumanTyping
from .isolation import SessionIsolator, EmergencyWipe, IdentityRotationPolicy
from .async_utils import with_timeout, safe_evaluate, async_retry

__all__ = [
    # Core
    'TikTokProfile',
    'TikTokScraper',
    'BrowserManager',
    
    # Algorithms
    'GraphCrawler',
    'crawl_network',
    'AStarCrawler',
    'BidirectionalSearch',
    'RandomWalkSampler',
    'InfluenceScorer',
    'CommunityDetector',
    
    # DOM Manipulation
    'TikTokReconnaissance',
    'TikTokInjector',
    'TikTokMaintenance',
    
    # Export
    'DataExporter',
    
    # Rotation & Proxy
    'UserAgentRotator',
    'ProxyRotator', 
    'Proxy',
    'ProxyChain',
    'ProxyChainConfig',
    'ResidentialProxyManager',
    'AutoRotatingProxy',
    
    # Delays
    'DelayManager',
    'get_delay_manager',
    
    # Sniffer
    'APISniffer',
    
    # Stealth - Fingerprint
    'FingerprintProfile',
    'FingerprintGenerator',
    'FingerprintSpoofing',
    'IdentityManager',
    
    # Stealth - Human Behavior
    'HumanBehavior',
    'HumanMouse',
    'HumanScroll',
    'HumanTyping',
    
    # Stealth - Isolation
    'SessionIsolator',
    'EmergencyWipe',
    'IdentityRotationPolicy',
    
    # Async Utilities
    'with_timeout',
    'safe_evaluate',
    'async_retry',
]

__version__ = '4.2.0'
