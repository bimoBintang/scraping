#!/usr/bin/env python
"""
Instagram Profile Scraper - Playwright Version
Standalone browser-based scraper with stealth dari tiktok/ package.

Usage:
    python instagram_playwright.py cristiano
    python instagram_playwright.py cristiano --posts --count 24
    python instagram_playwright.py cristiano --followers --cookies cookies.json
    python instagram_playwright.py cristiano --save
    python instagram_playwright.py cristiano --no-headless
"""

import json
import asyncio
import argparse
import sys
from pathlib import Path
from dataclasses import asdict

from instagram.browser import InstagramBrowserScraper
from instagram.exporter import InstagramExporter
from instagram.utils import format_timestamp


async def run_scraper(args):
    """Main async scraper logic"""
    
    print("""
╔══════════════════════════════════════════════════╗
║     📸 Instagram Playwright Scraper             ║
║     Browser-based with stealth                  ║
╚══════════════════════════════════════════════════╝
    """)
    
    headless = not args.no_headless
    
    async with InstagramBrowserScraper(
        cookies_file=args.cookies,
        headless=headless,
        debug_dir=args.output,
    ) as scraper:
        
        profiles = []
        all_posts = []
        
        for username in args.usernames:
            username = username.lstrip('@').strip()
            
            print(f"\n{'='*50}")
            print(f"  Scraping @{username}...")
            print(f"{'='*50}")
            
            # Profile
            profile = await scraper.get_profile(username)
            
            if profile:
                profiles.append(profile)
                print(profile)
                
                # Posts
                if args.posts:
                    print(f"\n[*] Fetching {args.count} posts...")
                    posts = await scraper.get_posts(username, count=args.count)
                    all_posts.extend(posts)
                    
                    if posts:
                        print(f"\n  Posts ({len(posts)}):")
                        for i, post in enumerate(posts[:5], 1):
                            ts = format_timestamp(post.timestamp)
                            cap = post.caption[:50] + '...' if len(post.caption) > 50 else post.caption
                            print(f"  {i}. [{post.post_type}] ❤️{post.likes:,} 💬{post.comments:,} | {ts}")
                            if cap:
                                print(f"     {cap}")
                        if len(posts) > 5:
                            print(f"  ... and {len(posts) - 5} more")
                
                # Followers
                if args.followers:
                    print(f"\n[*] Fetching followers...")
                    followers = await scraper.get_followers(username, count=args.count)
                    if followers:
                        print(f"\n  Followers ({len(followers)}):")
                        for f_user in followers[:10]:
                            print(f"    @{f_user['username']}")
                
                # Following
                if args.following:
                    print(f"\n[*] Fetching following...")
                    following = await scraper.get_following(username, count=args.count)
                    if following:
                        print(f"\n  Following ({len(following)}):")
                        for f_user in following[:10]:
                            print(f"    @{f_user['username']}")
            else:
                print(f"  [!] Failed to scrape @{username}")
        
        # Export
        if args.save and profiles:
            exporter = InstagramExporter(output_dir=args.output)
            exporter.profiles_to_json(profiles)
            if all_posts:
                exporter.posts_to_json(all_posts)
    
    print("\n  Done! 🎉")


def main():
    parser = argparse.ArgumentParser(
        description="Instagram Playwright Scraper — Browser-based with stealth"
    )
    
    parser.add_argument('usernames', nargs='+', help='Instagram usernames')
    parser.add_argument('--posts', action='store_true', help='Fetch posts')
    parser.add_argument('--followers', action='store_true', help='Fetch followers')
    parser.add_argument('--following', action='store_true', help='Fetch following')
    parser.add_argument('--count', type=int, default=12, help='Number of items (default: 12)')
    parser.add_argument('--cookies', type=str, help='Cookies JSON file')
    parser.add_argument('--save', action='store_true', help='Save results')
    parser.add_argument('--output', type=str, default='.', help='Output directory')
    parser.add_argument('--no-headless', action='store_true', help='Show browser window')
    
    args = parser.parse_args()
    asyncio.run(run_scraper(args))


if __name__ == "__main__":
    main()
