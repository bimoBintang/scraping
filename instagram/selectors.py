"""
Instagram CSS/DOM Selectors
Centralized selectors for browser-based scraping — avoid hardcoding.
"""

from typing import List

# ==================== PROFILE SELECTORS ====================

PROFILE_CONTAINER_SELECTORS: List[str] = [
    'header section',
    'main[role="main"] header',
    '[class*="ProfileHeader"]',
    '[data-testid="user-profile"]',
]

AVATAR_SELECTORS: List[str] = [
    'header img[alt]',
    'img[data-testid="user-avatar"]',
    '[class*="ProfileAvatar"] img',
    'header canvas + span img',
]

BIO_SELECTORS: List[str] = [
    'header section > div:nth-child(3)',
    '[class*="Biography"]',
    'header span[class*=""]',
    'div[class*="-about"]',
]

STATS_SELECTORS: List[str] = [
    'header section ul li',
    '[class*="ProfileStats"]',
    'a[href*="/followers/"] span',
    'a[href*="/following/"] span',
]

# ==================== POST GRID SELECTORS ====================

POST_GRID_SELECTORS: List[str] = [
    'article > div > div > div',
    'main[role="main"] article',
    '[class*="ProfileGrid"]',
    '[data-testid="post-grid"]',
]

POST_ITEM_SELECTORS: List[str] = [
    'article a[href*="/p/"]',
    'article a[href*="/reel/"]',
    'div[class*="PostItem"]',
    'a[href^="/p/"]',
]

POST_IMAGE_SELECTORS: List[str] = [
    'article img[src]',
    'img[class*="Post"]',
    'img[decoding="auto"]',
]

# ==================== MODAL SELECTORS ====================

MODAL_SELECTORS: List[str] = [
    'div[role="dialog"]',
    '[class*="Modal"]',
    '[class*="RnEpo"]',
    'div[class*="DialogContent"]',
]

FOLLOWERS_MODAL_SELECTORS: List[str] = [
    'div[role="dialog"] a[href*="/"]',
    '[class*="FollowList"] a',
    'div[role="dialog"] ul li',
    'div[role="dialog"] [class*="UserList"]',
]

MODAL_SCROLL_CONTAINER: List[str] = [
    'div[role="dialog"] ul',
    'div[role="dialog"] [style*="overflow"]',
    'div[role="dialog"] div[class*="List"]',
]

MODAL_CLOSE_SELECTORS: List[str] = [
    'div[role="dialog"] button[class*="Close"]',
    'div[role="dialog"] svg[aria-label="Close"]',
    'button[aria-label="Close"]',
]

# ==================== LOGIN WALL SELECTORS ====================

LOGIN_WALL_SELECTORS: List[str] = [
    'form[id="loginForm"]',
    'input[name="username"]',
    '[class*="LoginForm"]',
    'a[href="/accounts/login/"]',
    'button:has-text("Log in")',
]

COOKIE_BANNER_SELECTORS: List[str] = [
    'button:has-text("Allow")',
    'button:has-text("Accept")',
    '[class*="CookieBanner"] button',
    'button:has-text("Allow essential and optional cookies")',
]

# ==================== STORY SELECTORS ====================

STORY_RING_SELECTORS: List[str] = [
    'header canvas',
    '[class*="StoryRing"]',
    'button[aria-label*="story"]',
    'header span[role="link"]',
]

# ==================== NAVIGATION SELECTORS ====================

TAB_SELECTORS: List[str] = [
    'a[href*="/followers"]',
    'a[href*="/following"]',
    '[class*="Tabs"] a',
]

# ==================== HELPER FUNCTIONS ====================

def get_all_profile_selectors() -> str:
    """Get comma-separated profile selectors"""
    return ', '.join(PROFILE_CONTAINER_SELECTORS)

def get_post_selectors() -> str:
    """Get comma-separated post selectors"""
    return ', '.join(POST_ITEM_SELECTORS)

def get_modal_selectors() -> str:
    """Get comma-separated modal selectors"""
    return ', '.join(MODAL_SELECTORS)

def get_login_wall_selectors() -> str:
    """Get comma-separated login wall selectors"""
    return ', '.join(LOGIN_WALL_SELECTORS)


class SelectorHelper:
    """Helper class for working with selectors"""
    
    @staticmethod
    def first(selectors: List[str]) -> str:
        return selectors[0] if selectors else ''
    
    @staticmethod
    def to_css(selectors: List[str]) -> str:
        return ', '.join(selectors)
    
    @staticmethod
    def to_js_array(selectors: List[str]) -> str:
        escaped = [s.replace("'", "\\'") for s in selectors]
        return "['" + "', '".join(escaped) + "']"
