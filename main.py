#!/usr/bin/env python
"""
TikTok Scraper - CLI Entry Point
Advanced scraper dengan BFS/DFS, rotation, delays, dan API sniffing
"""

import json
import asyncio
import argparse
from pathlib import Path

from tiktok import TikTokScraper, GraphCrawler, get_delay_manager


def create_parser() -> argparse.ArgumentParser:
    """Create CLI argument parser"""
    parser = argparse.ArgumentParser(
        description="TikTok Advanced Scraper v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh penggunaan:
  python main.py username                                    # Profil saja
  python main.py username --followers --cookies cookies.json # Followers
  
  # BFS crawling (level by level)
  python main.py username --bfs --depth 2 --cookies cookies.json
  
  # DFS crawling (deep first)  
  python main.py username --dfs --depth 2 --cookies cookies.json
  
  # Dengan proxy
  python main.py username --proxy-file proxies.txt
  
  # Delay mode
  python main.py username --delay cautious

Delay Modes:
  aggressive : 0.5s delay (faster, risky)
  normal     : 2.0s delay (default)
  cautious   : 4.0s delay (safer)
  stealth    : 8.0s delay (safest)
        """
    )
    
    # Basic args
    parser.add_argument("usernames", nargs="+", help="Username TikTok (tanpa @)")
    parser.add_argument("--save", "-s", action="store_true", help="Simpan hasil ke JSON")
    parser.add_argument("--cookies", "-c", help="Path ke file cookies JSON")
    parser.add_argument("--max", "-m", type=int, default=100, help="Max results (default: 100)")
    parser.add_argument("--output", "-o", default=".", help="Direktori output")
    
    # Social scraping
    parser.add_argument("--following", "-f", action="store_true", help="Ambil daftar following")
    parser.add_argument("--followers", "-F", action="store_true", help="Ambil daftar followers")
    
    # Graph algorithms
    parser.add_argument("--bfs", action="store_true", help="BFS crawling (level by level)")
    parser.add_argument("--dfs", action="store_true", help="DFS crawling (deep first)")
    parser.add_argument("--depth", type=int, default=2, help="Crawl depth (default: 2)")
    
    # Anti-detection
    parser.add_argument("--proxy-file", help="File dengan daftar proxy")
    parser.add_argument("--delay", choices=['aggressive', 'normal', 'cautious', 'stealth'], 
                        default='normal', help="Delay profile")
    parser.add_argument("--sniff", action="store_true", help="Enable API sniffing")
    
    # Browser
    parser.add_argument("--headless", "-H", action="store_true", help="Headless mode")
    parser.add_argument("--debug", "-d", action="store_true", help="Debug mode")
    
    return parser


async def main():
    parser = create_parser()
    args = parser.parse_args()
    
    # Validate
    needs_cookies = args.following or args.followers or args.bfs or args.dfs
    if needs_cookies and not args.cookies:
        print("\n[!] Fitur social memerlukan cookies!")
        print("    Gunakan: --cookies tiktok_cookies.json")
        return
    
    # Header
    print("=" * 60)
    print("  TikTok Advanced Scraper v2.0")
    print("=" * 60)
    print(f"  Mode     : {'Headless' if args.headless else 'Visible'}")
    print(f"  Delay    : {args.delay}")
    if args.cookies:
        print(f"  Cookies  : {args.cookies}")
    if args.proxy_file:
        print(f"  Proxies  : {args.proxy_file}")
    if args.bfs:
        print(f"  Algorithm: BFS (depth={args.depth})")
    elif args.dfs:
        print(f"  Algorithm: DFS (depth={args.depth})")
    print("=" * 60)
    
    # Get delay manager
    delay = get_delay_manager(args.delay)
    
    async with TikTokScraper(
        headless=args.headless, 
        cookies_file=args.cookies,
        proxy_file=args.proxy_file
    ) as scraper:
        
        for username in args.usernames:
            print(f"\n{'='*50}")
            
            # Get profile
            profile = await scraper.get_profile(username, save_debug=args.debug)
            
            if profile:
                print(profile)
                if args.save:
                    path = scraper.save_profile(profile, args.output)
                    print(f"[+] Saved: {path}")
            else:
                print(f"[X] Failed: @{username}")
                continue
            
            # BFS/DFS Crawling
            if args.bfs or args.dfs:
                algorithm = "bfs" if args.bfs else "dfs"
                print(f"\n[~] {algorithm.upper()} crawling @{username}...")
                
                crawler = GraphCrawler(
                    max_depth=args.depth,
                    max_users=args.max,
                    delay_between=delay.base_delay
                )
                
                get_conn = scraper.get_followers
                if args.bfs:
                    users = await crawler.bfs(username, get_conn)
                else:
                    users = await crawler.dfs(username, get_conn)
                
                if users:
                    _print_crawl_results(users, algorithm, username)
                    if args.save:
                        path = Path(args.output) / f"tiktok_{username}_{algorithm}.json"
                        path.write_text(json.dumps(users, indent=2), encoding='utf-8')
                        print(f"[+] Saved: {path}")
            
            # Simple following/followers
            elif args.following:
                await delay.wait_short()
                following = await scraper.get_following(username, max_count=args.max)
                if following:
                    _print_user_list(following, "Following", username)
                    if args.save:
                        path = scraper.save_user_list(following, username, "following", args.output)
                        print(f"[+] Saved: {path}")
            
            elif args.followers:
                await delay.wait_short()
                followers = await scraper.get_followers(username, max_count=args.max)
                if followers:
                    _print_user_list(followers, "Followers", username)
                    if args.save:
                        path = scraper.save_user_list(followers, username, "followers", args.output)
                        print(f"[+] Saved: {path}")
        
        # Show sniffed APIs
        if args.sniff:
            apis = scraper.browser_manager.get_captured_apis()
            if apis:
                print(f"\n[Sniffer] Captured {len(apis)} API calls:")
                for api in apis[:10]:
                    print(f"  - {api.url[:80]}")
    
    print("\n[OK] Complete!")


def _print_user_list(users: list, list_type: str, username: str, limit: int = 20):
    """Print user list"""
    print(f"\n+-- {list_type} (@{username}) --+")
    for i, user in enumerate(users[:limit], 1):
        print(f"| {i:3}. @{user['username'][:25]:<25}")
    if len(users) > limit:
        print(f"| ... +{len(users) - limit} more")
    print("+--------------------------------+")


def _print_crawl_results(users: list, algorithm: str, username: str, limit: int = 25):
    """Print crawl results with depth info"""
    print(f"\n+-- {algorithm.upper()} Results (@{username}) --+")
    for i, user in enumerate(users[:limit], 1):
        depth = user.get('depth', '?')
        print(f"| {i:3}. [D{depth}] @{user['username'][:22]:<22}")
    if len(users) > limit:
        print(f"| ... +{len(users) - limit} more")
    print("+------------------------------------+")


if __name__ == "__main__":
    asyncio.run(main())
