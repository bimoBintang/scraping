#!/usr/bin/env python
"""
INSTASCOPE — Unified Social Media Scraping Platform v5.4
Supports TikTok, Instagram, Shopee, and Journal with one CLI entry point.

Usage:
    python main.py tiktok <username> --bfs --depth 2 --cookies cookies.json
    python main.py instagram cristiano --posts --count 50
    python main.py shopee search "laptop gaming"
"""

import sys
import asyncio
import argparse

try:
    import pyfiglet
except ImportError:
    pyfiglet = None


# ─── ANSI color codes ───────────────────────────────────────────────────
CYAN    = "\033[96m"
MAGENTA = "\033[95m"
YELLOW  = "\033[93m"
GREEN   = "\033[92m"
DIM     = "\033[2m"
BOLD    = "\033[1m"
RESET   = "\033[0m"


def print_banner(platform: str = None):
    """Print the INSTASCOPE ASCII art banner."""
    if pyfiglet:
        ascii_art = pyfiglet.figlet_format("INSTASCOPE", font="slant")
        # Colorize the ASCII art
        lines = ascii_art.rstrip('\n').split('\n')
        for line in lines:
            print(f"  {CYAN}{line}{RESET}")
    else:
        print(f"  {CYAN}{BOLD}INSTASCOPE{RESET}")

    print(f"  {CYAN}{BOLD}{22 * ' '} by WireRoot{RESET}")
    print(f"  {DIM}{'─' * 55}{RESET}")
    print(f"  {MAGENTA}Multi-Platform Scraping{RESET} {DIM}v5.3{RESET}")

    platforms = {
        'tiktok':    f" TikTok    {DIM}— Graph algorithms, AI/ML, stealth{RESET}",
        'instagram': f" Instagram {DIM}— 10 algorithms, hybrid engine{RESET}",
        'shopee':    f" Shopee    {DIM}— Price tracker, wishlist, search{RESET}",
    }

    print()
    for key, desc in platforms.items():
        marker = f"{GREEN}▶{RESET} " if key == platform else "  "
        print(f"  {marker}{desc}")

    print(f"  {DIM}{'─' * 55}{RESET}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="INSTASCOPE — Unified Social Media Scraping Platform v5.3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
{BOLD}Usage:{RESET}
  python main.py tiktok <username>                     Profile scraping
  python main.py tiktok <username> --bfs --depth 2     BFS crawling
  python main.py instagram <username> --posts           Fetch posts
  python main.py instagram <username> --highlights      Story highlights
  python main.py shopee search "laptop gaming"         Search products
  python main.py shopee add <url> --target 5000000     Wishlist tracking

{BOLD}Platforms:{RESET}
  tiktok      TikTok scraper (graph algorithms, DOM bypass, AI/ML)
  instagram   Instagram scraper (10 algorithms, hybrid engine)
  shopee      Shopee price tracker (wishlist, monitoring, search)
        """
    )

    parser.add_argument("--version", "-v", action="version", version="INSTASCOPE v5.4")
    parser.add_argument("--no-banner", action="store_true", help="Sembunyikan banner ASCII")
    parser.add_argument("--list-platforms", action="store_true", help="Tampilkan daftar platform")

    subparsers = parser.add_subparsers(dest="platform", help="Target platform")

    # ─── TikTok ──────────────────────────────────────────────────────
    tiktok_parser = subparsers.add_parser(
        "tiktok",
        help="TikTok scraper — graph algorithms, DOM bypass, stealth",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py tiktok username                                    Profile
  python main.py tiktok username --followers --cookies cookies.json Followers
  python main.py tiktok username --bfs --depth 2 --cookies c.json  BFS crawl
  python main.py tiktok username --astar --depth 3 --cookies c.json A* search
  python main.py tiktok user1 --bidirectional user2 --cookies c.json Path find
  python main.py tiktok username --full-bypass --cookies c.json     DOM bypass
        """
    )
    try:
        from tiktok._main import add_arguments as tiktok_add_args
        tiktok_add_args(tiktok_parser)
    except ImportError as e:
        tiktok_parser.description = f"⚠️ TikTok module unavailable: {e}"

    # ─── Instagram ───────────────────────────────────────────────────
    instagram_parser = subparsers.add_parser(
        "instagram",
        help="Instagram scraper — 10 algorithms, hybrid browser engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py instagram <username>                        Profile info
  python main.py instagram <username> --posts --count 50     Fetch 50 posts
  python main.py instagram <username> --highlights           Story highlights
  python main.py instagram <username> --engine selenium      Force Selenium
  python main.py instagram user1 user2 --compare            Compare profiles
  python main.py instagram --search "photography"           Search users
  python main.py instagram --discover-doc-ids               Refresh doc_ids
        """
    )
    try:
        from instagram._main import add_arguments as instagram_add_args
        instagram_add_args(instagram_parser)
    except ImportError as e:
        instagram_parser.description = f"⚠️ Instagram module unavailable: {e}"

    # ─── Shopee ──────────────────────────────────────────────────────
    shopee_parser = subparsers.add_parser(
        "shopee",
        help="Shopee price tracker — wishlist, monitoring, search",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py shopee add "https://shopee.co.id/product/123/456"
  python main.py shopee list
  python main.py shopee check
  python main.py shopee monitor --interval 3
  python main.py shopee search "laptop gaming" --limit 20
  python main.py shopee report --days 7
  python main.py shopee export wishlist --format csv
        """
    )
    try:
        from shopee._main import add_arguments as shopee_add_args
        shopee_add_args(shopee_parser)
    except ImportError as e:
        shopee_parser.description = f"⚠️ Shopee module unavailable: {e}"

    # ─── Journal ──────────────────────────────────────────────────────
    try:
        from journal._main import setup_parser as journal_setup
        journal_parser = journal_setup(subparsers)
    except ImportError as e:
        journal_parser = subparsers.add_parser(
            'journal',
            help=f'⚠️ Journal module unavailable: {e}',
        )

    # Keep references to platform parsers for interactive help
    platform_parsers = {
        'tiktok': tiktok_parser,
        'instagram': instagram_parser,
        'shopee': shopee_parser,
        'journal': journal_parser,
    }

    # ─── Parse and dispatch ──────────────────────────────────────────
    args = parser.parse_args()
    interactive = False  # Track if platform was selected interactively

    if args.list_platforms:
        print_banner()
        sys.exit(0)

    if not args.platform:
        if not args.no_banner:
            print_banner()
        
        print(f"  {YELLOW}No platform specified.{RESET} Pilih platform untuk dijalankan:")
        print(f"  1. {BOLD}tiktok{RESET}")
        print(f"  2. {BOLD}instagram{RESET}")
        print(f"  3. {BOLD}shopee{RESET}")
        print(f"  4. {BOLD}journal{RESET}")
        print(f"  h. {DIM}help{RESET}")
        print(f"  q. {DIM}exit{RESET}")
        
        try:
            choice = input(f"\n  {GREEN}Pilihan (1-4/h/q): {RESET}").lower().strip()
        except KeyboardInterrupt:
            print(f"\n\n  {YELLOW}Exiting...{RESET}")
            sys.exit(0)
        
        if choice in ('1', '2', '3', '4'):
            args.platform = {'1': 'tiktok', '2': 'instagram', '3': 'shopee', '4': 'journal'}[choice]
            interactive = True
        elif choice == 'h':
            parser.print_help()
            sys.exit(0)
        elif choice == 'q':
            sys.exit(0)
        else:
            print(f"\n  {YELLOW}Invalid choice.{RESET} Gunakan --help untuk melihat bantuan lengkap.")
            sys.exit(0)

    # Show banner with active platform highlighted
    if not args.no_banner:
        print_banner(args.platform)

    # If selected interactively (no CLI args), show that platform's help
    if interactive:
        print(f"  {GREEN}▶ Menampilkan opsi untuk {args.platform}:{RESET}\n")
        platform_parsers[args.platform].print_help()
        sys.exit(0)

    # Dispatch to platform handler
    if args.platform == "tiktok":
        from tiktok._main import main as tiktok_main
        asyncio.run(tiktok_main(args))

    elif args.platform == "instagram":
        from instagram._main import main as instagram_main
        instagram_main(args)

    elif args.platform == "shopee":
        from shopee._main import main as shopee_main
        shopee_main(args)

    elif args.platform == "journal":
        from journal._main import run as journal_run
        journal_run(args)


if __name__ == "__main__":
    main()
