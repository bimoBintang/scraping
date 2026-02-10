"""
Shopee Price Scraper Package
Personal wishlist price monitoring for Shopee Indonesia
"""

from .models import (
    ShopeeProduct,
    ProductVariant,
    PriceSnapshot,
    PriceChange,
    PriceHistory,
    WishlistItem,
)

from .api_client import ShopeeAPIClient, RateLimiter
from .wishlist import WishlistManager
from .price_tracker import PriceTracker, PriceAlert
from .exporter import ShopeeExporter


__all__ = [
    # Models
    'ShopeeProduct',
    'ProductVariant',
    'PriceSnapshot',
    'PriceChange',
    'PriceHistory',
    'WishlistItem',
    
    # Client & Wishlist
    'ShopeeAPIClient',
    'RateLimiter',
    'WishlistManager',
    
    # Tracker & Export
    'PriceTracker',
    'PriceAlert',
    'ShopeeExporter',
]

__version__ = '1.0.0'
