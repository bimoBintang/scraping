#!/usr/bin/env python
"""
Instagram Scraper - CLI Entry Point
Advanced scraper dengan Hybrid API, GraphQL auto-discovery, multi-fallback parsing,
location-based user clustering, dan adaptive RL rate limiting.

Usage:
    python instagram_main.py cristiano                      # Profile
    python instagram_main.py cristiano --save               # Save to JSON
    python instagram_main.py user1 user2 user3              # Multiple profiles
    python instagram_main.py cristiano --posts --count 50   # Posts
    python instagram_main.py cristiano --followers --cookies cookies.json  # Followers
    python instagram_main.py --search "photography"         # Search
    python instagram_main.py user1 user2 --cluster-location # Location clustering
    python instagram_main.py cristiano --export csv         # Export format
    python instagram_main.py cristiano --layer browser      # Force layer
    python instagram_main.py --discover-doc-ids             # Discover GraphQL doc_ids
"""

import json
import argparse
import sys
from pathlib import Path

from instagram import (
    HybridInstagramClient,
    InstagramExporter,
    DocIdDiscovery,
    LocationClusterAnalyzer,
    InstagramProfile,
    AdaptiveRateLimiter,
    AccountRouter,
)


def main():
    parser = argparse.ArgumentParser(
        description="Instagram Scraper v1.2 — Hybrid API + Browser + Mobile API + RL + Account Rotation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s cristiano                        Profile info
  %(prog)s cristiano --posts --count 50     Fetch 50 posts
  %(prog)s cristiano --followers --cookies cookies.json
  %(prog)s user1 user2 user3 --compare      Compare profiles
  %(prog)s user1 user2 --cluster-location   Location clustering
  %(prog)s --search "photography"           Search users
  %(prog)s --discover-doc-ids               Refresh GraphQL doc_ids
        """
    )
    
    # Positional
    parser.add_argument('usernames', nargs='*', help='Instagram usernames to scrape')
    
    # Actions
    parser.add_argument('--posts', action='store_true', help='Fetch posts')
    parser.add_argument('--followers', action='store_true', help='Fetch followers (requires cookies)')
    parser.add_argument('--following', action='store_true', help='Fetch following (requires cookies)')
    parser.add_argument('--search', type=str, help='Search for users')
    parser.add_argument('--compare', action='store_true', help='Compare multiple profiles')
    parser.add_argument('--cluster-location', action='store_true', help='Location-based clustering')
    parser.add_argument('--discover-doc-ids', action='store_true', help='Discover GraphQL doc_ids')
    
    # Options
    parser.add_argument('--count', type=int, default=12, help='Number of items to fetch (default: 12)')
    parser.add_argument('--cookies', type=str, help='Path to cookies JSON file')
    parser.add_argument('--save', action='store_true', help='Save results to JSON')
    parser.add_argument('--export', choices=['json', 'csv', 'excel'], help='Export format')
    parser.add_argument('--output', type=str, default='.', help='Output directory')
    parser.add_argument('--layer', choices=['web_api', 'browser', 'mobile_api'], help='Force specific layer')
    parser.add_argument('--no-rl', action='store_true', help='Disable RL rate limiter')
    parser.add_argument('--rl-stats', action='store_true', help='Show RL rate limiter training stats')
    parser.add_argument('--rl-debug', action='store_true', help='Enable RL debug output')
    parser.add_argument('--accounts-dir', type=str, help='Directory with cookie files for multi-account rotation')
    parser.add_argument('--ring-status', action='store_true', help='Show account rotation ring status')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    # Validate
    if not args.usernames and not args.search and not args.discover_doc_ids:
        parser.print_help()
        sys.exit(1)
    
    # Initialize components
    client = HybridInstagramClient(
        cookies_file=args.cookies,
        accounts_dir=args.accounts_dir,
        debug_dir=args.output,
        enable_rl=not args.no_rl,
        rl_debug=args.rl_debug,
    )
    exporter = InstagramExporter(output_dir=args.output)
    
    # Force specific layer if requested
    if args.layer:
        for name in client.layers:
            if name != args.layer:
                client.layers[name].status = __import__('instagram.hybrid_client', fromlist=['LayerStatus']).LayerStatus.DISABLED
    
    rl_label = "🧠 RL Rate Limiter" if not args.no_rl else "Static Delay"
    acct_label = f"🔄 {len(client.router.accounts) if client.router else 0} Accounts" if args.accounts_dir else "Single Account"
    print(f"""
╔══════════════════════════════════════════════════╗
║     📸 Instagram Scraper v1.2                   ║
║     Hybrid API + Browser + Mobile API           ║
║     {rl_label:<42} ║
║     {acct_label:<42} ║
╚══════════════════════════════════════════════════╝
    """)
    
    # ==================== DOC_ID DISCOVERY ====================
    
    if args.discover_doc_ids:
        print("[*] Discovering GraphQL doc_ids...")
        discovery = DocIdDiscovery()
        doc_ids = discovery.discover_all()
        
        print("\n  Results:")
        for query_type, doc_id in doc_ids.items():
            print(f"    {query_type}: {doc_id}")
        
        status = discovery.cache_status()
        print("\n  Cache Status:")
        for qt, info in status.items():
            age = f"{info['age_days']}d" if info['age_days'] is not None else "N/A"
            expired = "⚠ EXPIRED" if info['expired'] else "✓"
            print(f"    {qt}: {info['doc_id'] or 'not found'} ({age}) {expired}")
        
        return
    
    # ==================== SEARCH ====================
    
    if args.search:
        results = client.search_users(args.search)
        
        if not results:
            print("[!] No results found")
            return
        
        print(f"\n  Search Results for '{args.search}':")
        print(f"  {'Username':<25} {'Full Name':<30} {'Followers':>12} {'V':>3}")
        print(f"  {'-'*75}")
        
        for user in results:
            v = "✓" if user.get('is_verified') else " "
            fc = user.get('follower_count', 0)
            fc_str = f"{fc:,}" if fc else "N/A"
            print(f"  @{user['username']:<24} {user['full_name']:<30} {fc_str:>12} {v:>3}")
        
        if args.export == 'json' or args.save:
            with open(Path(args.output) / "instagram_search.json", 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"\n  [+] Results saved to instagram_search.json")
        
        return
    
    # ==================== PROFILE SCRAPING ====================
    
    profiles = []
    all_posts = []
    
    for username in args.usernames:
        # Clean username
        username = username.lstrip('@').strip()
        
        # Get profile
        profile = client.get_profile(username)
        
        if profile:
            profiles.append(profile)
            print(profile)
            
            # ==================== POSTS ====================
            
            if args.posts:
                posts = client.get_posts(username, count=args.count)
                all_posts.extend(posts)
                
                if posts:
                    print(f"\n  Recent Posts for @{username}:")
                    for i, post in enumerate(posts[:5], 1):
                        from instagram.utils import format_timestamp
                        ts = format_timestamp(post.timestamp)
                        cap = post.caption[:60] + '...' if len(post.caption) > 60 else post.caption
                        print(f"  {i}. [{post.post_type}] ❤️{post.likes:,} 💬{post.comments:,} | {ts}")
                        if cap:
                            print(f"     {cap}")
                    
                    if len(posts) > 5:
                        print(f"  ... and {len(posts) - 5} more posts")
            
            # ==================== FOLLOWERS ====================
            
            if args.followers:
                followers = client.get_followers(username, count=args.count)
                if followers:
                    print(f"\n  Followers ({len(followers)}):")
                    for f_user in followers[:10]:
                        print(f"    @{f_user['username']} — {f_user.get('full_name', '')}")
                    if len(followers) > 10:
                        print(f"    ... and {len(followers) - 10} more")
            
            # ==================== FOLLOWING ====================
            
            if args.following:
                following = client.get_following(username, count=args.count)
                if following:
                    print(f"\n  Following ({len(following)}):")
                    for f_user in following[:10]:
                        print(f"    @{f_user['username']} — {f_user.get('full_name', '')}")
                    if len(following) > 10:
                        print(f"    ... and {len(following) - 10} more")
        else:
            print(f"\n  [!] Failed to scrape @{username}")
    
    # ==================== LOCATION CLUSTERING ====================
    
    if args.cluster_location and len(args.usernames) > 1:
        print("\n[*] Running location clustering...")
        analyzer = LocationClusterAnalyzer()
        
        user_locations = {}
        for profile in profiles:
            posts = client.get_posts(profile.username, count=50)
            loc = analyzer.analyze_user(posts)
            user_locations[profile.username] = loc
            
            # Predict location
            prediction = analyzer.predict_location(profile.username, posts)
            if prediction['predicted_city']:
                print(f"  @{profile.username}: {prediction['predicted_city']}, {prediction['predicted_country']} "
                      f"(confidence: {prediction['confidence']:.0%})")
        
        clusters = analyzer.cluster_users(user_locations)
        report = analyzer.generate_report(clusters, user_locations)
        print(report)
        
        if args.save or args.export:
            exporter.clusters_to_json(clusters)
    
    # ==================== COMPARE ====================
    
    if args.compare and len(profiles) > 1:
        exporter.comparison_report(profiles)
    
    # ==================== EXPORT ====================
    
    if args.save or args.export:
        fmt = args.export or 'json'
        
        if profiles:
            if fmt == 'json':
                exporter.profiles_to_json(profiles)
            elif fmt == 'csv':
                exporter.profiles_to_csv(profiles)
            elif fmt == 'excel':
                exporter.to_excel(profiles, all_posts if all_posts else None)
        
        if all_posts:
            if fmt == 'json':
                exporter.posts_to_json(all_posts, args.usernames[0] if len(args.usernames) == 1 else '')
            elif fmt == 'csv':
                exporter.posts_to_csv(all_posts, args.usernames[0] if len(args.usernames) == 1 else '')
    
    # ==================== STATS ====================
    
    stats = client.get_stats()
    print(f"\n  Client Stats:")
    print(f"    Total requests: {stats['total_requests']}")
    for layer, count in stats['layer_usage'].items():
        if count > 0:
            print(f"    {layer}: {count} requests")
    
    # RL Rate Limiter stats
    if args.rl_stats and client.rate_limiter:
        client.rate_limiter.print_stats()
        client.rate_limiter.print_learned_strategy()
    elif client.rate_limiter and stats.get('rl_rate_limiter'):
        rl = stats['rl_rate_limiter']
        print(f"    RL steps: {rl['total_steps']}, ε={rl['epsilon']:.4f}, "
              f"dominant: {rl['dominant_action']}")
    
    # Account Router stats
    if client.router:
        if args.ring_status:
            client.router.print_ring_status()
        else:
            rs = stats.get('account_router', {})
            print(f"    Accounts: {rs.get('active_accounts', 0)}/{rs.get('total_accounts', 0)} active, "
                  f"rerouted: {rs.get('total_rerouted', 0)}")
    
    # Save RL policy
    if client.rate_limiter:
        client.rate_limiter.save_policy()
    
    print("\n  Done! 🎉")


if __name__ == "__main__":
    main()
