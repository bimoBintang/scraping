"""
Shopee Price Tracker
Periodic monitoring with alerts and reporting
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from .models import PriceChange, PriceHistory, PriceSnapshot, ShopeeProduct, WishlistItem
from .api_client import ShopeeAPIClient
from .wishlist import WishlistManager

logger = logging.getLogger(__name__)


class PriceAlert:
    """Price alert notification"""
    
    def __init__(
        self,
        change: PriceChange,
        alert_type: str,  # "price_drop", "price_rise", "target_reached", "significant_change"
        message: str = ""
    ):
        self.change = change
        self.alert_type = alert_type
        self.message = message or self._generate_message()
        self.timestamp = datetime.now().isoformat()
    
    def _generate_message(self) -> str:
        name = self.change.product_name[:50]
        delta = self.change.delta_formatted
        
        if self.alert_type == "target_reached":
            return f"🎯 TARGET HARGA TERCAPAI!\n{name}\nHarga: {self.change.price_after:,.0f}\n{delta}"
        elif self.alert_type == "price_drop":
            return f"📉 HARGA TURUN!\n{name}\n{delta}"
        elif self.alert_type == "price_rise":
            return f"📈 HARGA NAIK!\n{name}\n{delta}"
        else:
            return f"⚠️ PERUBAHAN SIGNIFIKAN!\n{name}\n{delta}"
    
    def to_dict(self) -> Dict:
        return {
            "type": self.alert_type,
            "message": self.message,
            "timestamp": self.timestamp,
            "change": self.change.to_dict(),
        }


class PriceTracker:
    """
    Periodic price monitoring with alerts
    
    Usage:
        tracker = PriceTracker(
            db_path="shopee_data.db",
            check_interval_hours=3,
            alert_callback=my_alert_handler
        )
        
        # Add products
        await tracker.add_url("https://shopee.co.id/product/123/456")
        
        # Run continuous monitoring
        await tracker.start_monitoring()
        
        # Or check once
        alerts = await tracker.check_all_prices()
    """
    
    def __init__(
        self,
        db_path: str = "shopee_wishlist.db",
        check_interval_hours: float = 3.0,
        min_delay: float = 8.0,
        max_delay: float = 15.0,
        alert_threshold: float = 20.0,
        alert_callback: Optional[Callable] = None,
        cookies_file: Optional[str] = None,
    ):
        self.wishlist = WishlistManager(db_path)
        self.check_interval = timedelta(hours=check_interval_hours)
        self.alert_threshold = alert_threshold
        self.alert_callback = alert_callback or self._default_alert
        self.cookies_file = cookies_file
        self.min_delay = min_delay
        self.max_delay = max_delay
        
        self._running = False
        self._alerts: List[PriceAlert] = []
    
    async def add_url(
        self,
        url: str,
        target_price: Optional[float] = None
    ) -> Optional[WishlistItem]:
        """
        Add product by URL and fetch initial price
        """
        async with ShopeeAPIClient(self.min_delay, self.max_delay) as client:
            if self.cookies_file:
                client.load_cookies_from_file(self.cookies_file)
            
            product = await client.get_product_by_url(url)
            
            if not product:
                logger.error(f"[Tracker] Failed to fetch product: {url}")
                # Still add to wishlist with URL only
                return self.wishlist.add_by_url(url, target_price=target_price)
            
            item = self.wishlist.add_from_product(
                product,
                target_price=target_price,
                alert_threshold=self.alert_threshold,
            )
            
            # Record initial price
            self.wishlist.record_price(
                item_id=product.item_id,
                price=product.price,
                price_original=product.price_original,
                discount_percent=product.discount_percent,
                stock=product.stock,
                sold=product.sold,
            )
            
            print(f"✅ Ditambahkan: {product.name}")
            print(f"   Harga: {product.price_formatted}")
            if product.discount_percent > 0:
                print(f"   Diskon: {product.discount_percent:.0f}% (dari {product.price_original_formatted})")
            
            return item
    
    async def add_item_id(
        self,
        item_id: int,
        shop_id: int,
        target_price: Optional[float] = None
    ) -> Optional[WishlistItem]:
        """Add product by item ID and shop ID"""
        async with ShopeeAPIClient(self.min_delay, self.max_delay) as client:
            if self.cookies_file:
                client.load_cookies_from_file(self.cookies_file)
            
            product = await client.get_product_detail(item_id, shop_id)
            
            if not product:
                return self.wishlist.add(
                    item_id=item_id, shop_id=shop_id,
                    product_name="Unknown", target_price=target_price
                )
            
            item = self.wishlist.add_from_product(product, target_price=target_price)
            
            self.wishlist.record_price(
                item_id=product.item_id,
                price=product.price,
                price_original=product.price_original,
                discount_percent=product.discount_percent,
                stock=product.stock,
                sold=product.sold,
            )
            
            return item
    
    async def check_all_prices(self) -> List[PriceAlert]:
        """
        Check prices for all active wishlist items
        
        Returns list of alerts triggered
        """
        items = self.wishlist.list_all(active_only=True)
        
        if not items:
            logger.info("[Tracker] No active items to check")
            return []
        
        alerts = []
        checked = 0
        
        print(f"\n🔍 Mengecek harga {len(items)} produk...")
        print("=" * 60)
        
        async with ShopeeAPIClient(self.min_delay, self.max_delay) as client:
            if self.cookies_file:
                client.load_cookies_from_file(self.cookies_file)
            
            for item in items:
                try:
                    product = await client.get_product_detail(item.item_id, item.shop_id)
                    
                    if not product:
                        logger.warning(f"[Tracker] Could not fetch {item.product_name} (ID: {item.item_id})")
                        continue
                    
                    # Record price
                    price_change = self.wishlist.record_price(
                        item_id=product.item_id,
                        price=product.price,
                        price_original=product.price_original,
                        discount_percent=product.discount_percent,
                        stock=product.stock,
                        sold=product.sold,
                    )
                    
                    checked += 1
                    
                    # Print status
                    status = "➡️"
                    if price_change:
                        if price_change.delta_rupiah < 0:
                            status = "📉"
                        else:
                            status = "📈"
                    
                    price_str = f"Rp {product.price:,.0f}".replace(",", ".")
                    print(f"  {status} {product.name[:45]:45s} | {price_str:>15s}", end="")
                    
                    if price_change:
                        print(f" | {price_change.delta_formatted}")
                    else:
                        print(f" | Tidak berubah")
                    
                    # Check alerts
                    if price_change:
                        alert = self._check_alerts(price_change, item)
                        if alert:
                            alerts.append(alert)
                            self._alerts.append(alert)
                            await self.alert_callback(alert)
                    
                except Exception as e:
                    logger.error(f"[Tracker] Error checking {item.product_name}: {e}")
        
        print("=" * 60)
        print(f"✅ Selesai: {checked}/{len(items)} produk dicek, {len(alerts)} alert")
        
        return alerts
    
    async def start_monitoring(self):
        """
        Start continuous monitoring loop
        
        Checks prices at configured interval
        """
        self._running = True
        interval_hours = self.check_interval.total_seconds() / 3600
        
        print(f"\n🔄 Monitoring dimulai (interval: {interval_hours:.1f} jam)")
        print(f"   Database: {self.wishlist.db_path}")
        print(f"   Rate limit: {self.min_delay}-{self.max_delay}s antar request")
        print(f"   Alert threshold: ±{self.alert_threshold}%")
        print(f"   Tekan Ctrl+C untuk berhenti\n")
        
        while self._running:
            try:
                await self.check_all_prices()
                
                next_check = datetime.now() + self.check_interval
                print(f"\n⏰ Check berikutnya: {next_check.strftime('%H:%M:%S')}")
                
                # Wait for next interval
                await asyncio.sleep(self.check_interval.total_seconds())
                
            except asyncio.CancelledError:
                break
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"[Tracker] Monitor error: {e}")
                await asyncio.sleep(60)  # Wait 1 min on error
        
        self._running = False
        print("\n🛑 Monitoring dihentikan")
    
    def stop_monitoring(self):
        """Stop the monitoring loop"""
        self._running = False
    
    def get_report(self, days: int = 7) -> Dict:
        """
        Generate price report for last N days
        """
        items = self.wishlist.list_all(active_only=False)
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        report = {
            "period": f"Terakhir {days} hari",
            "generated_at": datetime.now().isoformat(),
            "total_items": len(items),
            "items": [],
        }
        
        price_drops = 0
        price_rises = 0
        
        for item in items:
            history = self.wishlist.get_price_history(item.item_id)
            
            # Filter snapshots within period
            recent_snapshots = [
                s for s in history.snapshots 
                if s.timestamp >= cutoff
            ]
            
            if not recent_snapshots:
                continue
            
            first_price = recent_snapshots[0].price
            last_price = recent_snapshots[-1].price
            delta_rp = last_price - first_price
            delta_pct = (delta_rp / first_price * 100) if first_price > 0 else 0
            
            if delta_rp < 0:
                price_drops += 1
            elif delta_rp > 0:
                price_rises += 1
            
            delta_init_rp, delta_init_pct = history.delta_from_initial
            
            item_report = {
                "product_name": item.product_name,
                "item_id": item.item_id,
                "initial_price": f"Rp {item.initial_price:,.0f}".replace(",", "."),
                "current_price": f"Rp {last_price:,.0f}".replace(",", "."),
                "lowest_in_period": f"Rp {min(s.price for s in recent_snapshots):,.0f}".replace(",", "."),
                "highest_in_period": f"Rp {max(s.price for s in recent_snapshots):,.0f}".replace(",", "."),
                "change_period_rp": delta_rp,
                "change_period_pct": round(delta_pct, 2),
                "change_from_initial_rp": delta_init_rp,
                "change_from_initial_pct": round(delta_init_pct, 2),
                "trend": history.price_trend,
                "checks_in_period": len(recent_snapshots),
            }
            
            report["items"].append(item_report)
        
        report["summary"] = {
            "price_drops": price_drops,
            "price_rises": price_rises,
            "stable": len(report["items"]) - price_drops - price_rises,
        }
        
        return report
    
    def print_report(self, days: int = 7):
        """Print formatted price report to console"""
        report = self.get_report(days)
        
        print(f"\n📊 LAPORAN HARGA - {report['period']}")
        print("=" * 80)
        
        for item in report["items"]:
            rp = item["change_period_rp"]
            pct = item["change_period_pct"]
            
            sign = "+" if rp >= 0 else ""
            icon = "📉" if rp < 0 else "📈" if rp > 0 else "➡️"
            
            delta_str = f"{sign}Rp {rp:,.0f} ({sign}{pct:.1f}%)".replace(",", ".")
            
            init_rp = item["change_from_initial_rp"]
            init_pct = item["change_from_initial_pct"]
            init_sign = "+" if init_rp >= 0 else ""
            init_str = f"{init_sign}Rp {init_rp:,.0f} ({init_sign}{init_pct:.1f}%)".replace(",", ".")
            
            print(f"\n  {icon} {item['product_name'][:55]}")
            print(f"     Harga awal:   {item['initial_price']}")
            print(f"     Harga kini:   {item['current_price']}")
            print(f"     Terendah:     {item['lowest_in_period']}")
            print(f"     Tertinggi:    {item['highest_in_period']}")
            print(f"     Perubahan:    {delta_str}")
            print(f"     vs Awal:      {init_str}")
            print(f"     Tren:         {item['trend']}")
        
        print("\n" + "=" * 80)
        s = report["summary"]
        print(f"  📉 Turun: {s['price_drops']}  |  📈 Naik: {s['price_rises']}  |  ➡️ Stabil: {s['stable']}")
        print("=" * 80)
    
    # ============ Private Methods ============
    
    def _check_alerts(self, change: PriceChange, item: WishlistItem) -> Optional[PriceAlert]:
        """Check if price change triggers an alert"""
        
        # Target price reached
        if item.target_price and change.price_after <= item.target_price:
            return PriceAlert(change, "target_reached")
        
        # Significant change (≥ threshold %)
        if abs(change.delta_percent) >= item.alert_threshold:
            if change.delta_rupiah < 0:
                return PriceAlert(change, "price_drop")
            else:
                return PriceAlert(change, "price_rise")
        
        return None
    
    async def _default_alert(self, alert: PriceAlert):
        """Default alert handler - print to console"""
        print(f"\n{'='*50}")
        print(f"  🔔 ALERT: {alert.alert_type.upper()}")
        print(f"  {alert.message}")
        print(f"{'='*50}\n")
