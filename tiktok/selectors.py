"""
Centralized CSS/DOM Selectors for TikTok
Avoid hardcoding selectors throughout the codebase
"""

from typing import List, Dict

# ==================== FOLLOW-RELATED SELECTORS ====================

FOLLOWING_CONTAINER_SELECTORS: List[str] = [
    '[data-e2e="following-list"]',
    '[class*="FollowingList"]',
    '[class*="follow-list"]',
    'section[aria-label*="Following"]',
]

FOLLOWER_CONTAINER_SELECTORS: List[str] = [
    '[data-e2e="follower-list"]',
    '[class*="FollowerList"]',
    'section[aria-label*="Follower"]',
]

FOLLOW_ITEM_SELECTORS: List[str] = [
    '[class*="follow-item"]',
    '[class*="FollowerItem"]',
    '[class*="FollowingItem"]',
    '[data-e2e*="user-"]',
    'a[href*="/@"]:not([href*="/video/"])',
]

FOLLOW_TAB_SELECTORS: List[str] = [
    '[data-e2e="following-count"]',
    '[data-e2e="followers-count"]',
    'a[href*="/following"]',
    'a[href*="/followers"]',
]

# ==================== PRIVACY SELECTORS ====================

PRIVACY_GATE_SELECTORS: List[str] = [
    '[class*="PrivateAccount"]',
    '[class*="private-account"]',
    '[data-e2e*="private"]',
    'div[class*="DivPrivateAccount"]',
    '[aria-label*="private"]',
]

PRIVACY_OVERLAY_SELECTORS: List[str] = [
    '.blur-overlay',
    '.private-overlay',
    '[class*="overlay"]',
    '[style*="blur"]',
]

PRIVACY_ICON_SELECTORS: List[str] = [
    'svg[class*="lock"]',
    'i[class*="icon-lock"]',
    '[class*="icon-private"]',
    '[class*="PrivateIcon"]',
]

# ==================== PROFILE SELECTORS ====================

PROFILE_SELECTORS: List[str] = [
    '[data-e2e="user-page"]',
    '[class*="UserProfile"]',
    'main',
]

AVATAR_SELECTORS: List[str] = [
    'img[class*="Avatar"]',
    'img[class*="avatar"]',
]

# ==================== MODAL SELECTORS ====================

MODAL_SELECTORS: List[str] = [
    '[data-e2e="user-list-modal"]',
    '[class*="DivUserListContainer"]',
    'div[role="dialog"]',
    '[class*="Modal"]',
]

# ==================== BUTTON SELECTORS ====================

FOLLOW_BUTTON_SELECTORS: List[str] = [
    '[class*="follow-button"]',
    'button:has-text("Follow")',
    'button:has-text("Following")',
    '[data-e2e="follow-button"]',
]

# ==================== COMBINED SELECTORS ====================

def get_all_follow_selectors() -> str:
    """Get all follow-related selectors as comma-separated string"""
    all_selectors = (
        FOLLOWING_CONTAINER_SELECTORS + 
        FOLLOWER_CONTAINER_SELECTORS + 
        FOLLOW_ITEM_SELECTORS
    )
    return ', '.join(all_selectors)


def get_privacy_selectors() -> str:
    """Get all privacy-related selectors as comma-separated string"""
    return ', '.join(PRIVACY_GATE_SELECTORS + PRIVACY_OVERLAY_SELECTORS)


def get_modal_selectors() -> str:
    """Get all modal selectors as comma-separated string"""
    return ', '.join(MODAL_SELECTORS)


# ==================== STATE TARGETS ====================

STATE_TARGETS: List[str] = [
    '__REDUX_STORE__',
    '__VUE__',
    '__NEXT_DATA__',
    '__META_DATA__',
    '_tiktok',
    'TT_CONFIG',
    'ssrData',
    'webpackJsonp',
    '__INITIAL_STATE__',
]

PRIVACY_FLAGS: List[str] = [
    'privateAccount',
    'isPrivate',
    'followingVisibility',
    'followerVisibility',
    'followerStatus',
    'hideFollowing',
    'hideFollowers',
]

# ==================== API PATTERNS ====================

API_PATTERNS: List[str] = [
    '/follow',
    '/user/',
    '/relation',
    '/profile',
]

# ==================== SELECTOR HELPER ====================

class SelectorHelper:
    """Helper class for working with selectors"""
    
    @staticmethod
    def find_first_match(selectors: List[str]) -> str:
        """Return first selector from list for use in queries"""
        return selectors[0] if selectors else ''
    
    @staticmethod
    def to_css_string(selectors: List[str]) -> str:
        """Convert list of selectors to CSS selector string"""
        return ', '.join(selectors)
    
    @staticmethod
    def to_js_array(selectors: List[str]) -> str:
        """Convert list to JavaScript array string"""
        escaped = [s.replace("'", "\\'") for s in selectors]
        return "['" + "', '".join(escaped) + "']"
