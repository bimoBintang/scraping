#!/usr/bin/env python
"""
Instagram Scraper — CLI subcommand
Moved from instagram_main.py for unified CLI architecture.
"""

import json
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


def add_arguments(parser):
    """Add Instagram-specific arguments to the subparser."""
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
    parser.add_argument('--analyze-pattern', action='store_true', help='Analyze posting pattern for usernames')
    parser.add_argument('--schedule', action='store_true', help='Show predicted crawl schedule')
    parser.add_argument('--highlights', action='store_true', help='Fetch story highlights')
    parser.add_argument('--analyze-private', action='store_true',
                        help='Analyze private account via indirect interactions (Algorithm 11)')
    parser.add_argument('--depth', type=int, default=2,
                        help='Network search depth for --analyze-private (default: 2)')
    parser.add_argument('--seed-users', nargs='*',
                        help='Known public accounts connected to target (for --analyze-private)')
    parser.add_argument('--stream', action='store_true',
                        help='Enable streaming mode — chunk-by-chunk to file/DB (Algorithm 12)')
    parser.add_argument('--stream-format', choices=['jsonl', 'csv', 'sqlite', 'mongodb'],
                        default='jsonl', help='Streaming output format (default: jsonl)')
    parser.add_argument('--stream-output', type=str, default='.',
                        help='Output path for streaming mode')
    parser.add_argument('--mongo-uri', type=str, default='mongodb://localhost:27017',
                        help='MongoDB connection URI (for --stream-format mongodb)')
    parser.add_argument('--mongo-db', type=str, default='instascope',
                        help='MongoDB database name (for --stream-format mongodb)')
    parser.add_argument('--chunk-size', type=int, default=50,
                        help='Batch size per chunk for streaming (default: 50)')
    parser.add_argument('--filter-min-likes', type=int, help='Filter: minimum likes')
    parser.add_argument('--filter-has-location', action='store_true',
                        help='Filter: only posts with location data')
    parser.add_argument('--resume', action='store_true',
                        help='Resume streaming from last checkpoint (Algorithm 13)')
    parser.add_argument('--checkpoint-dir', type=str, default='.checkpoint',
                        help='Checkpoint directory (default: .checkpoint)')
    parser.add_argument('--checkpoint-status', action='store_true',
                        help='Show all active checkpoints')
    parser.add_argument('--checkpoint-clear', action='store_true',
                        help='Clear checkpoint for target username(s)')

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
    parser.add_argument('--proxy-file', type=str, help='Path to proxy pool JSON file')
    parser.add_argument('--proxy-status', action='store_true', help='Show proxy pool status table')
    parser.add_argument('--test-proxies', action='store_true', help='Test all proxies latency')
    parser.add_argument('--engine', choices=['auto', 'playwright', 'selenium'], default='auto',
                        help='Browser engine preference (default: auto)')
    parser.add_argument('--engine-status', action='store_true', help='Show browser engine status')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')


def main(args):
    """Instagram scraper main entry point."""
    # Validate
    if not args.usernames and not args.search and not args.discover_doc_ids:
        print("  [!] Specify usernames, --search, --discover-doc-ids, or --analyze-private")
        sys.exit(1)

    # Initialize components
    client = HybridInstagramClient(
        cookies_file=args.cookies,
        accounts_dir=args.accounts_dir,
        proxy_file=args.proxy_file,
        engine=args.engine,
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
    proxy_label = f"🌐 {len(client.proxy_manager.proxies)} Proxies" if client.proxy_manager else "Direct Connection"
    engine_label = f"🔀 Engine: {args.engine}"
    print(f"  {rl_label}")
    print(f"  {acct_label}")
    print(f"  {proxy_label}")
    print(f"  {engine_label}")
    print()

    # ==================== TEST PROXIES ====================

    if args.test_proxies and client.proxy_manager:
        client.proxy_manager.test_all_proxies()
        client.proxy_manager.print_pool_status()
        return

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

    # ==================== PATTERN ANALYSIS ====================

    if args.analyze_pattern and args.usernames:
        for username in args.usernames:
            username = username.lstrip('@').strip()
            print(f"\n[*] Analyzing posting pattern for @{username}...")
            pattern = client.analyze_pattern(username, post_count=args.count or 50)

            if pattern:
                pattern.print_pattern()

                if args.schedule:
                    client.crawler_scheduler.print_schedule(pattern, hours_ahead=24)

                if args.save or args.export:
                    with open(Path(args.output) / f"instagram_{username}_pattern.json", 'w', encoding='utf-8') as f:
                        json.dump(pattern.to_dict(), f, indent=2, ensure_ascii=False)
                    print(f"  [+] Pattern saved to instagram_{username}_pattern.json")
            else:
                print(f"  [!] Not enough posts to analyze pattern for @{username}")
        return

    # ==================== ANOMALY DETECTION (Algorithm 11) ====================

    if args.analyze_private and args.usernames:
        for username in args.usernames:
            username = username.lstrip('@').strip()
            report = client.analyze_private_account(
                username,
                seed_users=args.seed_users,
                depth=args.depth,
            )

            if report and (args.save or args.export):
                with open(Path(args.output) / f"instagram_{username}_anomaly_report.json", 'w', encoding='utf-8') as f:
                    json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
                print(f"  [+] Report saved to instagram_{username}_anomaly_report.json")
        return

    # ==================== CHECKPOINT STATUS (Algorithm 13) ====================

    if args.checkpoint_status:
        from .checkpoint import CheckpointManager
        cp = CheckpointManager(args.checkpoint_dir)
        cp.print_status()
        return

    if args.checkpoint_clear and args.usernames:
        from .checkpoint import CheckpointManager
        cp = CheckpointManager(args.checkpoint_dir)
        for u in args.usernames:
            u = u.lstrip('@').strip()
            if cp.delete(u):
                print(f"  [✓] Cleared checkpoint for @{u}")
            else:
                print(f"  [i] No checkpoint found for @{u}")
        return

    # ==================== STREAMING MODE (Algorithm 12 + 13) ====================

    if args.stream and args.usernames:
        filters = {}
        if args.filter_min_likes:
            filters['min_likes'] = args.filter_min_likes
        if args.filter_has_location:
            filters['has_location'] = True

        stats = client.stream_posts(
            usernames=[u.lstrip('@').strip() for u in args.usernames],
            count=args.count,
            fmt=args.stream_format,
            output=args.stream_output,
            chunk_size=args.chunk_size,
            filters=filters if filters else None,
            mongo_uri=args.mongo_uri,
            mongo_db=args.mongo_db,
            resume=args.resume,
            checkpoint_dir=args.checkpoint_dir,
        )
        return

    # ==================== HIGHLIGHTS ====================

    if args.highlights and args.usernames:
        for username in args.usernames:
            username = username.lstrip('@').strip()
            reels = client.get_highlights(username, fetch_items=True)

            if reels and (args.save or args.export):
                highlights_data = [r.to_dict() for r in reels]
                with open(Path(args.output) / f"instagram_{username}_highlights.json", 'w', encoding='utf-8') as f:
                    json.dump(highlights_data, f, indent=2, ensure_ascii=False)
                total_items = sum(len(r.items) for r in reels)
                print(f"  [+] Saved {len(reels)} reels ({total_items} items) to instagram_{username}_highlights.json")
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

    # Proxy pool stats
    if client.proxy_manager:
        if args.proxy_status:
            client.proxy_manager.print_pool_status()
        else:
            ps = stats.get('proxy_pool', {})
            print(f"    Proxies: {ps.get('active_proxies', 0)}/{ps.get('total_proxies', 0)} active, "
                  f"avg latency: {ps.get('avg_latency_ms', 0):.0f}ms")

    # Browser Engine stats
    if args.engine_status:
        client.hybrid_engine.print_engine_status()
    else:
        be = stats.get('browser_engine', {})
        print(f"    Engine: {be.get('preference', 'auto')}, "
              f"PW={'✓' if be.get('playwright_available') else '✗'}, "
              f"SE={'✓' if be.get('selenium_available') else '✗'}")
    # Save RL policy
    if client.rate_limiter:
        client.rate_limiter.save_policy()

    print("\n  Done! 🎉")
