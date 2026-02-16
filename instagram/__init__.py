"""
Instagram Scraper Package v1.5
Advanced scraper with Hybrid API, GraphQL, multi-fallback, location clustering,
RL rate limiting, account rotation, predictive crawling, proxy rotation, and story highlights.
"""

from .models import (
    InstagramProfile,
    InstagramPost,
    InstagramStory,
    LocationPoint,
    UserCluster,
)

from .hybrid_client import (
    HybridInstagramClient,
    LayerStatus,
    LayerHealth,
)

from .parsers import (
    InstagramParser,
    parse_profile_data,
)

from .discovery import (
    DocIdDiscovery,
    QUERY_SIGNATURES,
)

from .location_cluster import (
    LocationClusterAnalyzer,
    haversine_distance,
    reverse_geocode_simple,
)

from .browser import (
    InstagramBrowserScraper,
    scrape_profile_browser,
)

from .exporter import InstagramExporter

from .selectors import (
    SelectorHelper,
    get_all_profile_selectors,
    get_post_selectors,
    get_modal_selectors,
    get_login_wall_selectors,
)

from .rate_limiter import AdaptiveRateLimiter

from .account_router import (
    AccountRouter,
    ConsistentHashRing,
    AccountInfo,
)

from .predictive_crawler import (
    PatternAnalyzer,
    CrawlScheduler,
    PostingPattern,
)

from .proxy_rotator import (
    ProxyManager,
    ProxyInfo,
)

from .highlights_crawler import (
    HighlightsCrawler,
    HighlightReel,
    HighlightItem,
)

from .utils import (
    load_cookies,
    generate_web_headers,
    generate_mobile_headers,
    generate_browser_headers,
    smart_delay,
)

__version__ = "1.5.0"
__all__ = [
    # Models
    'InstagramProfile', 'InstagramPost', 'InstagramStory',
    'LocationPoint', 'UserCluster',
    # Client
    'HybridInstagramClient', 'LayerStatus', 'LayerHealth',
    # Parsers
    'InstagramParser', 'parse_profile_data',
    # Discovery
    'DocIdDiscovery', 'QUERY_SIGNATURES',
    # Location
    'LocationClusterAnalyzer', 'haversine_distance', 'reverse_geocode_simple',
    # Browser
    'InstagramBrowserScraper', 'scrape_profile_browser',
    # Export
    'InstagramExporter',
    # Selectors
    'SelectorHelper',
    # Rate Limiter
    'AdaptiveRateLimiter',
    # Account Router
    'AccountRouter', 'ConsistentHashRing', 'AccountInfo',
    # Predictive Crawler
    'PatternAnalyzer', 'CrawlScheduler', 'PostingPattern',
    # Proxy Rotator
    'ProxyManager', 'ProxyInfo',
    # Highlights
    'HighlightsCrawler', 'HighlightReel', 'HighlightItem',
    # Utils
    'load_cookies', 'generate_web_headers', 'smart_delay',
]
