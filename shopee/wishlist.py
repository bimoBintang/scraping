"""
Shopee Wishlist Manager
Add/remove products, SQLite-backed persistent storage
"""

import json
import os
import sqlite3
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .models import (
    WishlistItem, PriceHistory, PriceSnapshot, PriceChange, ShopeeProduct
)

logger = logging.getLogger(__name__)


class WishlistManager:
    """
    SQLite-backed wishlist for monitoring Shopee product prices
    
    Usage:
        wishlist = WishlistManager("shopee_data.db")
        
        # Add by URL
        wishlist.add_by_url("https://shopee.co.id/product/123/456")
        
        # Add by ID
        wishlist.add(item_id=456, shop_id=123, name="Laptop")
        
        # List all
        items = wishlist.list_all()
        
        # Remove
        wishlist.remove(item_id=456)
    """
    
    def __init__(self, db_path: str = "shopee_wishlist.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Wishlist table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wishlist (
                item_id INTEGER PRIMARY KEY,
                shop_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                product_url TEXT,
                initial_price REAL DEFAULT 0,
                current_price REAL DEFAULT 0,
                target_price REAL,
                alert_threshold REAL DEFAULT 20.0,
                is_active INTEGER DEFAULT 1,
                added_at TEXT,
                last_checked TEXT
            )
        """)
        
        # Price history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                price REAL NOT NULL,
                price_original REAL DEFAULT 0,
                discount_percent REAL DEFAULT 0,
                stock INTEGER DEFAULT 0,
                sold INTEGER DEFAULT 0,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (item_id) REFERENCES wishlist(item_id)
            )
        """)
        
        # Price changes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                product_name TEXT,
                price_before REAL,
                price_after REAL,
                delta_rupiah REAL,
                delta_percent REAL,
                delta_from_initial_rp REAL,
                delta_from_initial_pct REAL,
                timestamp TEXT,
                FOREIGN KEY (item_id) REFERENCES wishlist(item_id)
            )
        """)
        
        # Index for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_price_history_item 
            ON price_history(item_id, timestamp)
        """)
        
        conn.commit()
        conn.close()
        logger.info(f"[Wishlist] Database initialized: {self.db_path}")
    
    def add(
        self,
        item_id: int,
        shop_id: int,
        product_name: str,
        initial_price: float = 0,
        target_price: Optional[float] = None,
        alert_threshold: float = 20.0,
        product_url: str = ""
    ) -> WishlistItem:
        """
        Add product to wishlist
        
        Args:
            item_id: Shopee item ID
            shop_id: Shopee shop ID
            product_name: Product name
            initial_price: Price when first added
            target_price: Alert when price <= target
            alert_threshold: Alert when change >= threshold %
        """
        if not product_url:
            product_url = f"https://shopee.co.id/product/{shop_id}/{item_id}"
        
        now = datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO wishlist 
            (item_id, shop_id, product_name, product_url, initial_price, 
             current_price, target_price, alert_threshold, is_active, added_at, last_checked)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        """, (item_id, shop_id, product_name, product_url, initial_price,
              initial_price, target_price, alert_threshold, now, now))
        
        conn.commit()
        conn.close()
        
        logger.info(f"[Wishlist] Added: {product_name} (ID: {item_id})")
        
        return WishlistItem(
            item_id=item_id,
            shop_id=shop_id,
            product_name=product_name,
            product_url=product_url,
            initial_price=initial_price,
            current_price=initial_price,
            target_price=target_price,
            alert_threshold=alert_threshold,
            added_at=now,
        )
    
    def add_from_product(
        self,
        product: ShopeeProduct,
        target_price: Optional[float] = None,
        alert_threshold: float = 20.0
    ) -> WishlistItem:
        """Add product from ShopeeProduct object"""
        return self.add(
            item_id=product.item_id,
            shop_id=product.shop_id,
            product_name=product.name,
            initial_price=product.price,
            target_price=target_price,
            alert_threshold=alert_threshold,
            product_url=product.product_url,
        )
    
    def add_by_url(
        self,
        url: str,
        product_name: str = "Unknown",
        target_price: Optional[float] = None
    ) -> Optional[WishlistItem]:
        """
        Add product by Shopee URL
        
        Returns None if URL cannot be parsed
        """
        item_id, shop_id = WishlistItem.parse_shopee_url(url)
        
        if not item_id or not shop_id:
            logger.error(f"[Wishlist] Invalid Shopee URL: {url}")
            return None
        
        return self.add(
            item_id=item_id,
            shop_id=shop_id,
            product_name=product_name,
            product_url=url,
            target_price=target_price,
        )
    
    def remove(self, item_id: int):
        """Remove product from wishlist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM wishlist WHERE item_id = ?", (item_id,))
        cursor.execute("DELETE FROM price_history WHERE item_id = ?", (item_id,))
        cursor.execute("DELETE FROM price_changes WHERE item_id = ?", (item_id,))
        
        conn.commit()
        conn.close()
        logger.info(f"[Wishlist] Removed item {item_id}")
    
    def deactivate(self, item_id: int):
        """Pause monitoring for a product"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE wishlist SET is_active = 0 WHERE item_id = ?", (item_id,))
        conn.commit()
        conn.close()
    
    def activate(self, item_id: int):
        """Resume monitoring for a product"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE wishlist SET is_active = 1 WHERE item_id = ?", (item_id,))
        conn.commit()
        conn.close()
    
    def update_name(self, item_id: int, name: str):
        """Update product name (e.g. replace placeholder with real name)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE wishlist SET product_name = ? WHERE item_id = ?", (name, item_id))
        conn.commit()
        conn.close()
        logger.info(f"[Wishlist] Updated name for {item_id}: {name[:50]}")
    
    def list_all(self, active_only: bool = True) -> List[WishlistItem]:
        """Get all items in wishlist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if active_only:
            cursor.execute("SELECT * FROM wishlist WHERE is_active = 1 ORDER BY added_at DESC")
        else:
            cursor.execute("SELECT * FROM wishlist ORDER BY added_at DESC")
        
        items = []
        for row in cursor.fetchall():
            items.append(WishlistItem(
                item_id=row[0],
                shop_id=row[1],
                product_name=row[2],
                product_url=row[3] or "",
                initial_price=row[4] or 0,
                current_price=row[5] or 0,
                target_price=row[6],
                alert_threshold=row[7] or 20.0,
                is_active=bool(row[8]),
                added_at=row[9] or "",
                last_checked=row[10] or "",
            ))
        
        conn.close()
        return items
    
    def get_item(self, item_id: int) -> Optional[WishlistItem]:
        """Get single item by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM wishlist WHERE item_id = ?", (item_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return WishlistItem(
            item_id=row[0],
            shop_id=row[1],
            product_name=row[2],
            product_url=row[3] or "",
            initial_price=row[4] or 0,
            current_price=row[5] or 0,
            target_price=row[6],
            alert_threshold=row[7] or 20.0,
            is_active=bool(row[8]),
            added_at=row[9] or "",
            last_checked=row[10] or "",
        )
    
    def record_price(
        self,
        item_id: int,
        price: float,
        price_original: float = 0,
        discount_percent: float = 0,
        stock: int = 0,
        sold: int = 0
    ) -> Optional[PriceChange]:
        """
        Record a price observation and return PriceChange if price changed
        """
        now = datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get current state
        cursor.execute(
            "SELECT current_price, initial_price, product_name, alert_threshold FROM wishlist WHERE item_id = ?",
            (item_id,)
        )
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return None
        
        prev_price, initial_price, product_name, threshold = row
        
        # Set initial price if not yet recorded
        if initial_price == 0:
            initial_price = price
            cursor.execute(
                "UPDATE wishlist SET initial_price = ? WHERE item_id = ?",
                (price, item_id)
            )
        
        # Record snapshot
        cursor.execute("""
            INSERT INTO price_history 
            (item_id, price, price_original, discount_percent, stock, sold, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (item_id, price, price_original, discount_percent, stock, sold, now))
        
        # Update current price
        cursor.execute(
            "UPDATE wishlist SET current_price = ?, last_checked = ? WHERE item_id = ?",
            (price, now, item_id)
        )
        
        price_change = None
        
        # Check for price change
        if prev_price > 0 and prev_price != price:
            delta_rp = price - prev_price
            delta_pct = (delta_rp / prev_price * 100) if prev_price > 0 else 0
            delta_init_rp = price - initial_price
            delta_init_pct = (delta_init_rp / initial_price * 100) if initial_price > 0 else 0
            
            price_change = PriceChange(
                item_id=item_id,
                product_name=product_name,
                price_before=prev_price,
                timestamp_before="",
                price_after=price,
                timestamp_after=now,
                delta_rupiah=delta_rp,
                delta_percent=delta_pct,
                delta_from_initial_rp=delta_init_rp,
                delta_from_initial_pct=delta_init_pct,
            )
            
            # Record change
            cursor.execute("""
                INSERT INTO price_changes
                (item_id, product_name, price_before, price_after, delta_rupiah, 
                 delta_percent, delta_from_initial_rp, delta_from_initial_pct, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (item_id, product_name, prev_price, price, delta_rp,
                  delta_pct, delta_init_rp, delta_init_pct, now))
        
        conn.commit()
        conn.close()
        
        return price_change
    
    def get_price_history(self, item_id: int, limit: int = 100) -> PriceHistory:
        """Get complete price history for a product"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get wishlist info
        cursor.execute("SELECT * FROM wishlist WHERE item_id = ?", (item_id,))
        item_row = cursor.fetchone()
        
        if not item_row:
            conn.close()
            return PriceHistory(item_id=item_id, shop_id=0, product_name="Unknown",
                                product_url="", initial_price=0)
        
        # Get snapshots
        cursor.execute(
            "SELECT price, price_original, discount_percent, stock, sold, timestamp "
            "FROM price_history WHERE item_id = ? ORDER BY timestamp DESC LIMIT ?",
            (item_id, limit)
        )
        
        snapshots = []
        for row in cursor.fetchall():
            snapshots.append(PriceSnapshot(
                timestamp=row[5],
                price=row[0],
                price_original=row[1],
                discount_percent=row[2],
                stock=row[3],
                sold=row[4],
            ))
        
        snapshots.reverse()  # Chronological order
        
        conn.close()
        
        return PriceHistory(
            item_id=item_row[0],
            shop_id=item_row[1],
            product_name=item_row[2],
            product_url=item_row[3] or "",
            initial_price=item_row[4] or 0,
            snapshots=snapshots,
        )
    
    def get_price_changes(self, item_id: Optional[int] = None, limit: int = 50) -> List[PriceChange]:
        """Get recorded price changes"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if item_id:
            cursor.execute(
                "SELECT * FROM price_changes WHERE item_id = ? ORDER BY timestamp DESC LIMIT ?",
                (item_id, limit)
            )
        else:
            cursor.execute(
                "SELECT * FROM price_changes ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )
        
        changes = []
        for row in cursor.fetchall():
            changes.append(PriceChange(
                item_id=row[1],
                product_name=row[2] or "",
                price_before=row[3] or 0,
                timestamp_before="",
                price_after=row[4] or 0,
                timestamp_after=row[8] or "",
                delta_rupiah=row[5] or 0,
                delta_percent=row[6] or 0,
                delta_from_initial_rp=row[7] or 0,
                delta_from_initial_pct=0,
            ))
        
        conn.close()
        return changes
    
    def get_summary(self) -> Dict:
        """Get wishlist summary"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM wishlist WHERE is_active = 1")
        active = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM wishlist")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM price_history")
        snapshots = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM price_changes")
        changes = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "active_items": active,
            "total_items": total,
            "total_snapshots": snapshots,
            "total_price_changes": changes,
            "database": self.db_path,
        }
