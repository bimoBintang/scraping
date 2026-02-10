"""
Shopee Price Scraper - Data Models
Product, variant, price history, and wishlist data structures
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ProductVariant:
    """Variant of a product (size, color, etc.)"""
    name: str
    price: float           # Harga dalam Rupiah
    price_original: float  # Harga sebelum diskon
    stock: int
    sku: str = ""
    model_id: int = 0
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ShopeeProduct:
    """Complete product data from Shopee"""
    item_id: int
    shop_id: int
    name: str
    
    # Pricing
    price: float               # Harga aktual (sudah diskon), dalam Rupiah
    price_original: float      # Harga sebelum diskon
    discount_percent: float    # Persentase diskon (0-100)
    currency: str = "IDR"
    
    # Stats
    stock: int = 0
    sold: int = 0              # Total terjual
    rating: float = 0.0        # 0-5.0
    rating_count: int = 0
    
    # Category & shop
    category: str = ""
    shop_name: str = ""
    shop_location: str = ""
    
    # Media & URL
    image_url: str = ""
    product_url: str = ""
    
    # Variants
    variants: List[ProductVariant] = field(default_factory=list)
    
    # Metadata
    scraped_at: str = ""  # ISO format datetime
    raw_data: Dict = field(default_factory=dict, repr=False)
    
    def __post_init__(self):
        if not self.scraped_at:
            self.scraped_at = datetime.now().isoformat()
        if not self.product_url and self.item_id and self.shop_id:
            self.product_url = f"https://shopee.co.id/product/{self.shop_id}/{self.item_id}"
    
    @property
    def discount_amount(self) -> float:
        """Selisih harga diskon dalam Rupiah"""
        return self.price_original - self.price
    
    @property
    def price_formatted(self) -> str:
        """Format harga: Rp 1.500.000"""
        return f"Rp {self.price:,.0f}".replace(",", ".")
    
    @property
    def price_original_formatted(self) -> str:
        return f"Rp {self.price_original:,.0f}".replace(",", ".")
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d.pop('raw_data', None)
        return d
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


@dataclass
class PriceSnapshot:
    """Single price observation at a point in time"""
    timestamp: str      # ISO format
    price: float
    price_original: float
    discount_percent: float
    stock: int
    sold: int
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class PriceChange:
    """Price change between two observations"""
    item_id: int
    product_name: str
    
    # Previous
    price_before: float
    timestamp_before: str
    
    # Current
    price_after: float
    timestamp_after: str
    
    # Delta
    delta_rupiah: float        # Selisih nominal (negatif = turun)
    delta_percent: float       # Selisih persentase
    
    # vs initial price
    delta_from_initial_rp: float
    delta_from_initial_pct: float
    
    @property
    def direction(self) -> str:
        if self.delta_rupiah < 0:
            return "📉 TURUN"
        elif self.delta_rupiah > 0:
            return "📈 NAIK"
        return "➡️ STABIL"
    
    @property
    def is_significant(self) -> bool:
        """Change >= 20%"""
        return abs(self.delta_percent) >= 20
    
    @property
    def delta_formatted(self) -> str:
        """Format: -Rp 150.000 (-12.5%)"""
        sign = "+" if self.delta_rupiah >= 0 else ""
        rp = f"{sign}Rp {self.delta_rupiah:,.0f}".replace(",", ".")
        pct = f"{sign}{self.delta_percent:.1f}%"
        return f"{rp} ({pct})"
    
    def to_dict(self) -> Dict:
        return {
            "item_id": self.item_id,
            "product_name": self.product_name,
            "price_before": self.price_before,
            "price_after": self.price_after,
            "delta_rupiah": self.delta_rupiah,
            "delta_percent": round(self.delta_percent, 2),
            "delta_from_initial_rp": self.delta_from_initial_rp,
            "delta_from_initial_pct": round(self.delta_from_initial_pct, 2),
            "direction": self.direction,
            "is_significant": self.is_significant,
            "timestamp": self.timestamp_after,
        }


@dataclass
class PriceHistory:
    """Complete price history for a product"""
    item_id: int
    shop_id: int
    product_name: str
    product_url: str
    
    initial_price: float       # Harga saat pertama kali ditambahkan
    snapshots: List[PriceSnapshot] = field(default_factory=list)
    
    @property
    def current_price(self) -> float:
        return self.snapshots[-1].price if self.snapshots else self.initial_price
    
    @property
    def lowest_price(self) -> float:
        if not self.snapshots:
            return self.initial_price
        return min(s.price for s in self.snapshots)
    
    @property
    def highest_price(self) -> float:
        if not self.snapshots:
            return self.initial_price
        return max(s.price for s in self.snapshots)
    
    @property
    def price_trend(self) -> str:
        """Trend berdasarkan 3 snapshot terakhir"""
        if len(self.snapshots) < 2:
            return "insufficient_data"
        
        recent = self.snapshots[-3:] if len(self.snapshots) >= 3 else self.snapshots
        prices = [s.price for s in recent]
        
        if all(prices[i] <= prices[i+1] for i in range(len(prices)-1)):
            return "rising"
        elif all(prices[i] >= prices[i+1] for i in range(len(prices)-1)):
            return "falling"
        return "fluctuating"
    
    @property
    def delta_from_initial(self) -> Tuple[float, float]:
        """(delta_rp, delta_pct) from initial price"""
        if not self.snapshots:
            return (0.0, 0.0)
        
        current = self.current_price
        delta_rp = current - self.initial_price
        delta_pct = (delta_rp / self.initial_price * 100) if self.initial_price > 0 else 0
        return (delta_rp, delta_pct)
    
    def add_snapshot(self, snapshot: PriceSnapshot) -> Optional[PriceChange]:
        """Add snapshot and return PriceChange if price changed"""
        prev_price = self.current_price
        self.snapshots.append(snapshot)
        
        if prev_price != snapshot.price:
            delta_rp = snapshot.price - prev_price
            delta_pct = (delta_rp / prev_price * 100) if prev_price > 0 else 0
            
            delta_init_rp = snapshot.price - self.initial_price
            delta_init_pct = (delta_init_rp / self.initial_price * 100) if self.initial_price > 0 else 0
            
            return PriceChange(
                item_id=self.item_id,
                product_name=self.product_name,
                price_before=prev_price,
                timestamp_before=self.snapshots[-2].timestamp if len(self.snapshots) >= 2 else "",
                price_after=snapshot.price,
                timestamp_after=snapshot.timestamp,
                delta_rupiah=delta_rp,
                delta_percent=delta_pct,
                delta_from_initial_rp=delta_init_rp,
                delta_from_initial_pct=delta_init_pct,
            )
        return None
    
    def to_dict(self) -> Dict:
        delta_rp, delta_pct = self.delta_from_initial
        return {
            "item_id": self.item_id,
            "shop_id": self.shop_id,
            "product_name": self.product_name,
            "product_url": self.product_url,
            "initial_price": self.initial_price,
            "current_price": self.current_price,
            "lowest_price": self.lowest_price,
            "highest_price": self.highest_price,
            "price_trend": self.price_trend,
            "delta_from_initial_rp": delta_rp,
            "delta_from_initial_pct": round(delta_pct, 2),
            "total_snapshots": len(self.snapshots),
        }


@dataclass
class WishlistItem:
    """Item in the price monitoring wishlist"""
    item_id: int
    shop_id: int
    product_name: str
    product_url: str
    
    # Monitoring config
    added_at: str = ""          # ISO format
    target_price: Optional[float] = None  # Alert jika harga <= target
    alert_threshold: float = 20.0          # Alert jika perubahan >= threshold %
    is_active: bool = True
    
    # Current state
    initial_price: float = 0.0
    current_price: float = 0.0
    last_checked: str = ""
    
    def __post_init__(self):
        if not self.added_at:
            self.added_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @staticmethod
    def parse_shopee_url(url: str) -> Tuple[Optional[int], Optional[int]]:
        """
        Parse Shopee URL to extract item_id and shop_id
        
        Supports:
        - https://shopee.co.id/product/123456/789012
        - https://shopee.co.id/Nama-Produk-i.123456.789012
        - https://shopee.co.id/product-name-i.123456.789012?...
        """
        import re
        
        # Pattern 1: /product/shop_id/item_id
        match = re.search(r'/product/(\d+)/(\d+)', url)
        if match:
            return int(match.group(2)), int(match.group(1))
        
        # Pattern 2: -i.shop_id.item_id
        match = re.search(r'-i\.(\d+)\.(\d+)', url)
        if match:
            return int(match.group(2)), int(match.group(1))
        
        # Pattern 3: i.shop_id.item_id
        match = re.search(r'i\.(\d+)\.(\d+)', url)
        if match:
            return int(match.group(2)), int(match.group(1))
        
        return None, None
