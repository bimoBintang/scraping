#!/usr/bin/env python
"""
Shopee Price Scraper — CLI subcommand
Moved from shopee_main.py for unified CLI architecture.

When called from the unified CLI (main.py):
    python main.py shopee add "https://shopee.co.id/product/123/456"
    python main.py shopee search "laptop gaming" --limit 10
    python main.py shopee list
    python main.py shopee check
    python main.py shopee login
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime

from .models import WishlistItem
from .wishlist import WishlistManager
from .exporter import ShopeeExporter

logger = logging.getLogger(__name__)

DEFAULT_COOKIES = "shopee/shopeeCookies.json"


def _get_browser():
    """Lazy import ShopeeBrowser to avoid import errors when playwright is not installed."""
    from .browser import ShopeeBrowser
    return ShopeeBrowser


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def get_cookies(args) -> str:
    """Get cookies file path from args or default"""
    cookies = getattr(args, 'cookies', None)
    if cookies:
        return cookies
    if os.path.exists(DEFAULT_COOKIES):
        return DEFAULT_COOKIES
    return None


def check_cookies_status(cookies_path: str):
    """Check and warn about cookie freshness"""
    if not cookies_path or not os.path.exists(cookies_path):
        print("⚠️  Cookies belum tersedia. Jalankan: python main.py shopee login")
        return False

    mtime = os.path.getmtime(cookies_path)
    age_hours = (datetime.now().timestamp() - mtime) / 3600

    if age_hours > 48:
        print(f"⚠️  Cookies sudah {age_hours:.0f} jam. Mungkin expired.")
        print("   Refresh dengan: python main.py shopee login")
        return False
    elif age_hours > 24:
        print(f"ℹ️  Cookies berusia {age_hours:.0f} jam. Pertimbangkan refresh jika error.")

    return True


# ============ Commands ============

async def _cmd_login(args):
    """Interactive login to get fresh cookies"""
    ShopeeBrowser = _get_browser()
    cookies_path = getattr(args, 'cookies', None) or DEFAULT_COOKIES
    await ShopeeBrowser.login(cookies_output=cookies_path)


async def _cmd_add(args):
    """Add product to wishlist (instant, no browser needed)"""
    wishlist = WishlistManager(args.db)
    target = getattr(args, 'target', None)

    print(f"📦 Menambahkan produk...")
    print(f"   URL: {args.url}")

    # Parse URL to get IDs (no browser needed!)
    item_id, shop_id = WishlistItem.parse_shopee_url(args.url)

    if not item_id or not shop_id:
        print("❌ URL tidak valid. Format yang didukung:")
        print("   https://shopee.co.id/product/SHOP_ID/ITEM_ID")
        print("   https://shopee.co.id/nama-produk-i.SHOP_ID.ITEM_ID")
        return

    # Add to wishlist with basic info
    item = wishlist.add(
        item_id=item_id,
        shop_id=shop_id,
        product_name=f"Shopee Product {item_id}",
        product_url=args.url,
        target_price=target,
    )

    print(f"\n✅ Produk ditambahkan ke wishlist!")
    print(f"   Item ID: {item_id}")
    print(f"   Shop ID: {shop_id}")
    if target:
        print(f"   🎯 Target harga: Rp {target:,.0f}".replace(",", "."))
    print(f"\n💡 Jalankan 'python main.py shopee check' untuk cek harga terbaru")

    # Try to get name via browser if cookies available
    cookies = get_cookies(args)
    if cookies and check_cookies_status(cookies):
        try:
            ShopeeBrowser = _get_browser()
            print(f"\n🔍 Mengambil detail produk...")
            async with ShopeeBrowser(cookies_file=cookies, headless=True, min_delay=2, max_delay=4) as sb:
                product = await sb.get_product_detail(item_id, shop_id)

                if product and product.price > 0:
                    # Update wishlist with real data
                    wishlist.update_name(item_id, product.name)
                    wishlist.record_price(
                        item_id=item_id,
                        price=product.price,
                        price_original=product.price_original,
                        discount_percent=product.discount_percent,
                        stock=product.stock,
                        sold=product.sold,
                    )
                    print(f"   📝 Nama: {product.name}")
                    print(f"   💰 Harga: {product.price_formatted}")
                    if product.discount_percent > 0:
                        print(f"   🏷️ Diskon: {product.discount_percent:.0f}%")
                else:
                    print("   ⚠️ Gagal ambil detail. Harga akan dicek saat 'check'.")
        except Exception as e:
            logger.debug(f"Auto-fetch failed: {e}")
            print("   ⚠️ Detail belum tersedia. Akan dicek saat 'check'.")


async def _cmd_list(args):
    """List all wishlist items"""
    wishlist = WishlistManager(args.db)
    show_all = getattr(args, 'all', False)
    items = wishlist.list_all(active_only=not show_all)

    if not items:
        print("📋 Wishlist kosong. Tambahkan produk dengan:")
        print("   python main.py shopee add <URL>")
        return

    print(f"\n📋 WISHLIST ({len(items)} produk)")
    print("=" * 85)
    print(f"  {'ID':>12} | {'Nama':45s} | {'Harga Kini':>15} | {'vs Awal':>12}")
    print("-" * 85)

    for item in items:
        if item.current_price > 0 and item.initial_price > 0:
            delta_rp = item.current_price - item.initial_price
            delta_pct = (delta_rp / item.initial_price * 100)
            sign = "+" if delta_rp >= 0 else ""
            icon = "📉" if delta_rp < 0 else "📈" if delta_rp > 0 else "➡️"
            price_str = f"Rp {item.current_price:,.0f}".replace(",", ".")
            delta_str = f"{sign}{delta_pct:.1f}%"
        else:
            icon = "❓"
            price_str = "Belum dicek"
            delta_str = "-"

        status = "" if item.is_active else " ⏸️"
        name = item.product_name[:43] if item.product_name else "Unknown"

        print(f"  {item.item_id:>12} | {icon} {name:43s} | {price_str:>15} | {delta_str:>12}{status}")

    print("=" * 85)

    summary = wishlist.get_summary()
    print(f"  Total: {summary['total_items']} produk | "
          f"Aktif: {summary['active_items']} | "
          f"Snapshots: {summary['total_snapshots']}")


async def _cmd_check(args):
    """Check prices for all wishlist items using browser"""
    cookies = get_cookies(args)
    if not check_cookies_status(cookies):
        return

    ShopeeBrowser = _get_browser()
    wishlist = WishlistManager(args.db)
    items = wishlist.list_all(active_only=True)

    if not items:
        print("📋 Wishlist kosong")
        return

    print(f"\n🔍 Mengecek harga {len(items)} produk...")
    print("=" * 70)

    checked = 0

    async with ShopeeBrowser(cookies_file=cookies, headless=True) as sb:
        for item in items:
            try:
                product = await sb.get_product_detail(item.item_id, item.shop_id)

                if not product or product.price <= 0:
                    print(f"  ⚠️ {item.product_name[:45]:45s} | Gagal fetch")
                    continue

                # Update name if still placeholder
                if item.product_name.startswith("Shopee Product"):
                    wishlist.update_name(item.item_id, product.name)

                # Record price
                change = wishlist.record_price(
                    item_id=product.item_id,
                    price=product.price,
                    price_original=product.price_original,
                    discount_percent=product.discount_percent,
                    stock=product.stock,
                    sold=product.sold,
                )

                checked += 1
                price_str = f"Rp {product.price:,.0f}".replace(",", ".")

                if change:
                    icon = "📉" if change.delta_rupiah < 0 else "📈"
                    print(f"  {icon} {product.name[:45]:45s} | {price_str:>15} | {change.delta_formatted}")
                else:
                    print(f"  ➡️ {product.name[:45]:45s} | {price_str:>15} | Tidak berubah")

                # Gentle delay between products
                await asyncio.sleep(8)

            except Exception as e:
                print(f"  ❌ {item.product_name[:45]:45s} | Error: {e}")

    print("=" * 70)
    print(f"✅ Selesai: {checked}/{len(items)} produk dicek")


async def _cmd_monitor(args):
    """Start continuous price monitoring"""
    interval = getattr(args, 'interval', 3.0)

    print(f"🔄 Monitoring dimulai (interval: {interval} jam)")
    print(f"   Tekan Ctrl+C untuk berhenti\n")

    while True:
        try:
            await _cmd_check(args)

            next_time = datetime.now().strftime('%H:%M:%S')
            print(f"\n⏰ Selesai pada {next_time}. Menunggu {interval} jam...")
            await asyncio.sleep(interval * 3600)

        except KeyboardInterrupt:
            print("\n🛑 Monitoring dihentikan")
            break
        except Exception as e:
            logger.error(f"Monitor error: {e}")
            print(f"\n⚠️ Error. Coba lagi dalam 5 menit...")
            await asyncio.sleep(300)


async def _cmd_report(args):
    """Show price report"""
    from .price_tracker import PriceTracker

    days = getattr(args, 'days', 7)
    tracker = PriceTracker(db_path=args.db)
    tracker.print_report(days=days)

    output = getattr(args, 'output', None)
    if output:
        report = tracker.get_report(days=days)
        exporter = ShopeeExporter(tracker.wishlist)
        exporter.export_report(report, output)


async def _cmd_search(args):
    """Search Shopee products using browser"""
    cookies = get_cookies(args)
    if not check_cookies_status(cookies):
        return

    ShopeeBrowser = _get_browser()
    limit = getattr(args, 'limit', 20)
    sort = getattr(args, 'sort', 'relevancy')

    print(f"🔍 Mencari: \"{args.keyword}\"...")

    async with ShopeeBrowser(cookies_file=cookies, headless=True) as sb:
        products = await sb.search(args.keyword, max_results=limit, sort_by=sort)

    if not products:
        print("❌ Tidak ada hasil. Coba 'python main.py shopee login' untuk refresh cookies.")
        return

    print(f"\n📦 {len(products)} Produk ditemukan:")
    print("=" * 90)

    for i, p in enumerate(products, 1):
        price_str = f"Rp {p.price:,.0f}".replace(",", ".")
        discount_str = f" (-{p.discount_percent:.0f}%)" if p.discount_percent > 0 else ""
        rating_str = f"⭐{p.rating}" if p.rating > 0 else ""
        sold_str = f"Terjual {p.sold}" if p.sold > 0 else ""

        print(f"\n  {i:2d}. {p.name[:65]}")
        print(f"      💰 {price_str}{discount_str}  |  {rating_str}  |  {sold_str}")
        print(f"      🔗 {p.product_url}")

    output = getattr(args, 'output', None)
    if output:
        fmt = getattr(args, 'format', 'csv')
        exporter = ShopeeExporter(WishlistManager(args.db))
        exporter.export_search_results(products, output, fmt)


async def _cmd_remove(args):
    """Remove item from wishlist"""
    wishlist = WishlistManager(args.db)
    item = wishlist.get_item(args.item_id)

    if not item:
        print(f"❌ Item ID {args.item_id} tidak ditemukan")
        return

    wishlist.remove(args.item_id)
    print(f"✅ Dihapus: {item.product_name} (ID: {args.item_id})")


async def _cmd_export(args):
    """Export data"""
    wishlist = WishlistManager(args.db)
    exporter = ShopeeExporter(wishlist)

    fmt = getattr(args, 'format', 'csv')
    output = getattr(args, 'output', None)

    if args.type == "wishlist":
        output = output or f"shopee_wishlist.{fmt}"
        exporter.export_wishlist(output, fmt)
    elif args.type == "history":
        item_id = getattr(args, 'item_id', None)
        if not item_id:
            output_dir = output or "shopee_history"
            exporter.export_all_history(output_dir, fmt)
        else:
            output = output or f"price_history_{item_id}.{fmt}"
            exporter.export_price_history(item_id, output, fmt)


# ============ Unified CLI Integration ============

def add_arguments(parser):
    """Add Shopee-specific arguments to the subparser."""
    parser.add_argument("--db", default="shopee_wishlist.db", help="Database file path")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")

    subparsers = parser.add_subparsers(dest="shopee_command", help="Shopee commands")

    def add_cookies_arg(p):
        p.add_argument("--cookies", default=None, help="Cookies JSON file")

    # login
    login_parser = subparsers.add_parser("login", help="🔐 Login ke Shopee (refresh cookies)")
    add_cookies_arg(login_parser)

    # add
    add_parser = subparsers.add_parser("add", help="Tambah produk ke wishlist")
    add_parser.add_argument("url", help="URL produk Shopee")
    add_parser.add_argument("--target", type=float, help="Target harga (alert jika <=)")
    add_cookies_arg(add_parser)

    # list
    list_parser = subparsers.add_parser("list", help="Lihat semua wishlist")
    list_parser.add_argument("--all", action="store_true", help="Tampilkan nonaktif juga")

    # check
    check_parser = subparsers.add_parser("check", help="Cek harga semua wishlist sekarang")
    add_cookies_arg(check_parser)

    # monitor
    mon_parser = subparsers.add_parser("monitor", help="Monitoring harga berkala")
    mon_parser.add_argument("--interval", type=float, default=3.0, help="Interval jam (default: 3)")
    add_cookies_arg(mon_parser)

    # report
    rep_parser = subparsers.add_parser("report", help="Laporan perubahan harga")
    rep_parser.add_argument("--days", type=int, default=7, help="Periode hari (default: 7)")
    rep_parser.add_argument("--output", help="Export report ke file")

    # search
    search_parser = subparsers.add_parser("search", help="Cari produk di Shopee")
    search_parser.add_argument("keyword", help="Kata kunci pencarian")
    search_parser.add_argument("--limit", type=int, default=20, help="Jumlah hasil (default: 20)")
    search_parser.add_argument("--sort", default="relevancy",
                                choices=["relevancy", "ctime", "sales", "price"],
                                help="Urutan hasil")
    search_parser.add_argument("--output", help="Export ke file")
    search_parser.add_argument("--format", default="csv", choices=["csv", "json"])
    add_cookies_arg(search_parser)

    # remove
    rem_parser = subparsers.add_parser("remove", help="Hapus dari wishlist")
    rem_parser.add_argument("item_id", type=int, help="Item ID produk")

    # export
    exp_parser = subparsers.add_parser("export", help="Export data")
    exp_parser.add_argument("type", choices=["wishlist", "history"], help="Tipe data")
    exp_parser.add_argument("item_id", type=int, nargs="?", help="Item ID (untuk history)")
    exp_parser.add_argument("--format", default="csv", choices=["csv", "json", "excel"])
    exp_parser.add_argument("--output", help="Output file path")


def main(args):
    """Shopee scraper main entry point."""
    if not hasattr(args, 'shopee_command') or not args.shopee_command:
        print("  [!] Specify a shopee command: login, add, list, check, monitor, report, search, remove, export")
        print("  Use: python main.py shopee --help")
        return

    if hasattr(args, 'verbose') and args.verbose:
        setup_logging(True)

    # Command dispatch
    commands = {
        "login": _cmd_login,
        "add": _cmd_add,
        "list": _cmd_list,
        "check": _cmd_check,
        "monitor": _cmd_monitor,
        "report": _cmd_report,
        "search": _cmd_search,
        "remove": _cmd_remove,
        "export": _cmd_export,
    }

    cmd_func = commands.get(args.shopee_command)
    if cmd_func:
        asyncio.run(cmd_func(args))
    else:
        print(f"  [!] Unknown command: {args.shopee_command}")
