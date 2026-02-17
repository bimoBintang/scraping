#!/usr/bin/env python
"""
Shopee Price Scraper — CLI subcommand
Moved from shopee_main.py for unified CLI architecture.
"""

import asyncio
import json
import logging
import sys
from datetime import datetime

from shopee import (
    ShopeeAPIClient, WishlistManager, PriceTracker,
    ShopeeExporter, WishlistItem
)


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


async def _cmd_add(args):
    """Add product to wishlist"""
    tracker = PriceTracker(
        db_path=args.db,
        cookies_file=args.cookies if hasattr(args, 'cookies') and args.cookies else None,
    )

    target = args.target if hasattr(args, 'target') and args.target else None

    print(f"📦 Menambahkan produk...")
    item = await tracker.add_url(args.url, target_price=target)

    if item:
        print(f"\n✅ Berhasil ditambahkan ke wishlist!")
        print(f"   ID: {item.item_id}")
        print(f"   Nama: {item.product_name}")
        if target:
            print(f"   🎯 Target harga: Rp {target:,.0f}".replace(",", "."))
    else:
        print("❌ Gagal menambahkan produk. Periksa URL.")


async def _cmd_list(args):
    """List all wishlist items"""
    wishlist = WishlistManager(args.db)
    items = wishlist.list_all(active_only=not args.all if hasattr(args, 'all') else True)

    if not items:
        print("📋 Wishlist kosong. Tambahkan produk dengan: python main.py shopee add <URL>")
        return

    print(f"\n📋 WISHLIST ({len(items)} produk)")
    print("=" * 85)
    print(f"  {'ID':>12} | {'Nama':45s} | {'Harga Kini':>15} | {'vs Awal':>12}")
    print("-" * 85)

    for item in items:
        delta_rp = item.current_price - item.initial_price
        delta_pct = (delta_rp / item.initial_price * 100) if item.initial_price > 0 else 0

        sign = "+" if delta_rp >= 0 else ""
        icon = "📉" if delta_rp < 0 else "📈" if delta_rp > 0 else "➡️"

        price_str = f"Rp {item.current_price:,.0f}".replace(",", ".")
        delta_str = f"{sign}{delta_pct:.1f}%"

        status = "" if item.is_active else " ⏸️"

        print(f"  {item.item_id:>12} | {icon} {item.product_name[:43]:43s} | {price_str:>15} | {delta_str:>12}{status}")

    print("=" * 85)

    summary = wishlist.get_summary()
    print(f"  Total: {summary['total_items']} produk | "
          f"Aktif: {summary['active_items']} | "
          f"Snapshots: {summary['total_snapshots']} | "
          f"Perubahan: {summary['total_price_changes']}")


async def _cmd_check(args):
    """Check prices for all wishlist items"""
    tracker = PriceTracker(
        db_path=args.db,
        cookies_file=args.cookies if hasattr(args, 'cookies') and args.cookies else None,
    )

    await tracker.check_all_prices()


async def _cmd_monitor(args):
    """Start continuous price monitoring"""
    interval = args.interval if hasattr(args, 'interval') and args.interval else 3.0

    tracker = PriceTracker(
        db_path=args.db,
        check_interval_hours=interval,
        cookies_file=args.cookies if hasattr(args, 'cookies') and args.cookies else None,
    )

    await tracker.start_monitoring()


async def _cmd_report(args):
    """Show price report"""
    days = args.days if hasattr(args, 'days') and args.days else 7

    tracker = PriceTracker(db_path=args.db)
    tracker.print_report(days=days)

    # Export if requested
    if hasattr(args, 'output') and args.output:
        report = tracker.get_report(days=days)
        exporter = ShopeeExporter(tracker.wishlist)
        exporter.export_report(report, args.output)


async def _cmd_search(args):
    """Search Shopee products"""
    async with ShopeeAPIClient() as client:
        if hasattr(args, 'cookies') and args.cookies:
            client.load_cookies_from_file(args.cookies)

        limit = args.limit if hasattr(args, 'limit') and args.limit else 20
        sort = args.sort if hasattr(args, 'sort') and args.sort else "relevancy"

        print(f'🔍 Mencari: "{args.keyword}"...')
        products = await client.search_products(args.keyword, limit=limit, sort_by=sort)

        if not products:
            print("❌ Tidak ada hasil")
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

        # Export if requested
        if hasattr(args, 'output') and args.output:
            fmt = args.format if hasattr(args, 'format') and args.format else "csv"
            exporter = ShopeeExporter(WishlistManager(args.db))
            exporter.export_search_results(products, args.output, fmt)


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

    fmt = args.format if hasattr(args, 'format') and args.format else "csv"

    if args.type == "wishlist":
        output = args.output or f"shopee_wishlist.{fmt}"
        exporter.export_wishlist(output, fmt)
    elif args.type == "history":
        if not hasattr(args, 'item_id') or not args.item_id:
            output_dir = args.output or "shopee_history"
            exporter.export_all_history(output_dir, fmt)
        else:
            output = args.output or f"price_history_{args.item_id}.{fmt}"
            exporter.export_price_history(args.item_id, output, fmt)


def add_arguments(parser):
    """Add Shopee-specific arguments to the subparser."""
    parser.add_argument("--db", default="shopee_wishlist.db", help="Database file path")
    parser.add_argument("--cookies", default=None, help="Cookies JSON file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")

    subparsers = parser.add_subparsers(dest="shopee_command", help="Shopee commands")

    # add
    add_parser = subparsers.add_parser("add", help="Tambah produk ke wishlist")
    add_parser.add_argument("url", help="URL produk Shopee")
    add_parser.add_argument("--target", type=float, help="Target harga (alert jika <=)")

    # list
    list_parser = subparsers.add_parser("list", help="Lihat semua wishlist")
    list_parser.add_argument("--all", action="store_true", help="Tampilkan nonaktif juga")

    # check
    subparsers.add_parser("check", help="Cek harga semua wishlist sekarang")

    # monitor
    mon_parser = subparsers.add_parser("monitor", help="Monitoring harga berkala")
    mon_parser.add_argument("--interval", type=float, default=3.0, help="Interval jam (default: 3)")

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
        print("  [!] Specify a shopee command: add, list, check, monitor, report, search, remove, export")
        print("  Use: python main.py shopee --help")
        return

    if hasattr(args, 'verbose'):
        setup_logging(args.verbose)

    # Command dispatch
    commands = {
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
