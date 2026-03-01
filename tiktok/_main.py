#!/usr/bin/env python
"""
TikTok Scraper — CLI subcommand
Moved from root main.py for unified CLI architecture.
"""

import json
import asyncio
import argparse
from pathlib import Path

from tiktok import (
    TikTokScraper,
    GraphCrawler,
    get_delay_manager,
    AStarCrawler,
    BidirectionalSearch,
    RandomWalkSampler,
    InfluenceScorer,
    CommunityDetector
)
from tiktok.export import DataExporter
from tiktok.reconnaissance import TikTokReconnaissance
from tiktok.injection import TikTokInjector
from tiktok.maintenance import TikTokMaintenance
from tiktok.dom_algorithms import DOMAlgorithmOrchestrator
from tiktok.ai_analyzer import AIContextAnalyzer, AdaptiveStrategySelector


def add_arguments(parser: argparse.ArgumentParser):
    """Add TikTok-specific arguments to the subparser."""
    # Basic args
    parser.add_argument("usernames", nargs="+", help="Username TikTok (tanpa @)")
    parser.add_argument("--save", "-s", action="store_true", help="Simpan hasil ke JSON")
    parser.add_argument("--cookies", "-c", help="Path ke file cookies JSON")
    parser.add_argument("--max", "-m", type=int, default=100, help="Max results (default: 100)")
    parser.add_argument("--output", "-o", default=".", help="Direktori output")

    # Social scraping
    parser.add_argument("--following", "-f", action="store_true", help="Ambil daftar following")
    parser.add_argument("--followers", "-F", action="store_true", help="Ambil daftar followers")

    # Basic Graph algorithms
    parser.add_argument("--bfs", action="store_true", help="BFS crawling (level by level)")
    parser.add_argument("--dfs", action="store_true", help="DFS crawling (deep first)")
    parser.add_argument("--depth", type=int, default=2, help="Crawl depth (default: 2)")

    # Advanced algorithms
    parser.add_argument("--astar", action="store_true", help="A* search (find influencers)")
    parser.add_argument("--bidirectional", metavar="USER", help="Find path to USER")
    parser.add_argument("--random-walk", action="store_true", help="Random walk sampling")
    parser.add_argument("--walks", type=int, default=10, help="Number of random walks (default: 10)")
    parser.add_argument("--steps", type=int, default=20, help="Steps per walk (default: 20)")
    parser.add_argument("--influence", action="store_true", help="Calculate influence scores")
    parser.add_argument("--community", action="store_true", help="Detect communities")

    # DOM Manipulation phases
    parser.add_argument("--recon", action="store_true", help="Run DOM reconnaissance phase")
    parser.add_argument("--inject", action="store_true", help="Run DOM injection phase")
    parser.add_argument("--maintain", action="store_true", help="Run maintenance monitoring")
    parser.add_argument("--full-bypass", action="store_true", help="Run full bypass (recon+inject+maintain)")
    parser.add_argument("--dom-deep", action="store_true", help="Run advanced DOM algorithms (D1-D15)")
    parser.add_argument("--ai-analyze", action="store_true", help="AI context analysis via Ollama (MCP-D1)")
    parser.add_argument("--ai-strategy", action="store_true", help="AI adaptive strategy (MCP-D2, includes MCP-D1)")

    # Export options
    parser.add_argument("--export", choices=['csv', 'excel', 'jsonl', 'graphml', 'gexf'],
                        help="Export format")
    parser.add_argument("--stats", action="store_true", help="Generate statistics")

    # Anti-detection
    parser.add_argument("--proxy-file", help="File dengan daftar proxy")
    parser.add_argument("--delay", choices=['aggressive', 'normal', 'cautious', 'stealth'],
                        default='normal', help="Delay profile")
    parser.add_argument("--sniff", action="store_true", help="Enable API sniffing")

    # Browser
    parser.add_argument("--headless", "-H", action="store_true", help="Headless mode")
    parser.add_argument("--debug", "-d", action="store_true", help="Debug mode")


async def _run_dom_bypass(scraper, username: str, args) -> dict:
    """
    Run full DOM bypass: Reconnaissance -> Injection -> Maintenance
    For bypassing private following/followers lists
    """
    results = {
        'username': username,
        'recon': None,
        'injection': None,
        'maintenance': None,
        'data_extracted': []
    }

    print(f"\n[===] Starting DOM Bypass for @{username} [===]")

    # Get browser page
    context, page = await scraper.browser_manager.new_page(cookies=scraper.cookies)

    try:
        # Navigate to profile
        url = f"https://www.tiktok.com/@{username}"
        print(f"[~] Navigating to {url}")
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_load_state('networkidle', timeout=15000)
        
        # Check for CAPTCHA and wait if detected
        await scraper._wait_for_captcha_solved(page)

        # ===== PHASE 1: RECONNAISSANCE =====
        if args.recon or args.full_bypass:
            print("\n[PHASE 1] Reconnaissance...")
            recon = TikTokReconnaissance(page)
            await recon.start_reconnaissance(username)
            results['recon'] = recon.generate_recon_report()

            if args.save:
                path = Path(args.output) / f"recon_{username}.json"
                path.write_text(json.dumps(results['recon'], indent=2, default=str), encoding='utf-8')
                print(f"[+] Recon saved: {path}")

        # ===== PHASE 2: INJECTION =====
        if args.inject or args.full_bypass:
            print("\n[PHASE 2] Injection...")

            # Need recon data for injection
            if not results['recon']:
                print("[~] Running quick recon first...")
                recon = TikTokReconnaissance(page)
                await recon.start_reconnaissance(username)
                results['recon'] = recon.generate_recon_report()

            injector = TikTokInjector(page, results['recon'])
            await injector.execute_injection_phase()
            results['injection'] = injector.get_injection_report()

            # Extract data after injection
            if results['injection'].get('data_extracted'):
                results['data_extracted'] = results['injection']['data_extracted']

            if args.save:
                path = Path(args.output) / f"injection_{username}.json"
                path.write_text(json.dumps(results['injection'], indent=2, default=str), encoding='utf-8')
                print(f"[+] Injection saved: {path}")

        # ===== PHASE 3: MAINTENANCE =====
        if args.maintain or args.full_bypass:
            print("\n[PHASE 3] Maintenance monitoring...")

            injection_results = results['injection'].get('results', []) if results['injection'] else []
            maint = TikTokMaintenance(page, injection_results)
            await maint.start_maintenance()

            # Monitor for 30 seconds
            print("[~] Monitoring for 30 seconds...")
            await asyncio.sleep(30)

            await maint.stop_maintenance()
            results['maintenance'] = maint.get_maintenance_report()

            if args.save:
                path = Path(args.output) / f"maintenance_{username}.json"
                path.write_text(json.dumps(results['maintenance'], indent=2, default=str), encoding='utf-8')
                print(f"[+] Maintenance saved: {path}")

        # ===== PHASE 4: ADVANCED DOM ALGORITHMS =====
        if args.dom_deep or args.full_bypass:
            print("\n[PHASE 4] Advanced DOM Algorithms (D1-D15)...")
            orchestrator = DOMAlgorithmOrchestrator(page)
            dom_results = await orchestrator.run_all()
            results['dom_algorithms'] = dom_results

            # Merge extracted users
            if dom_results.get('users_extracted'):
                for user in dom_results['users_extracted']:
                    if user.get('username'):
                        results['data_extracted'].append({
                            'username': user['username'],
                            'profile_url': f"https://www.tiktok.com/@{user['username']}",
                            'source': user.get('source', 'dom_algorithm')
                        })

            if args.save:
                path = Path(args.output) / f"dom_deep_{username}.json"
                path.write_text(json.dumps(dom_results, indent=2, default=str), encoding='utf-8')
                print(f"[+] DOM results saved: {path}")

        # ===== PHASE 5: AI CONTEXT ANALYSIS =====
        if args.ai_analyze or args.full_bypass:
            print("\n[PHASE 5] AI Context Analysis (MCP-D1)...")
            analyzer = AIContextAnalyzer(page)
            ai_results = await analyzer.execute()
            results['ai_analysis'] = ai_results

            if ai_results.get('analysis'):
                analysis = ai_results['analysis']
                print(f"\n  🤖 AI Analysis Report:")
                print(f"     Framework : {analysis.get('framework_detected', 'unknown')}")
                print(f"     Anti-bot  : {', '.join(analysis.get('anti_bot_mechanisms', [])) or 'none'}")
                for rec in analysis.get('bypass_recommendations', [])[:5]:
                    print(f"     → {rec}")

            if args.save:
                path = Path(args.output) / f"ai_analysis_{username}.json"
                path.write_text(json.dumps(ai_results, indent=2, default=str), encoding='utf-8')
                print(f"[+] AI analysis saved: {path}")

        # ===== PHASE 6: AI ADAPTIVE STRATEGY =====
        if args.ai_strategy:
            print("\n[PHASE 6] AI Adaptive Strategy (MCP-D2)...")
            selector = AdaptiveStrategySelector(page)
            # Pass MCP-D1 result if available
            strategy_results = await selector.execute(results.get('ai_analysis'))
            results['ai_strategy'] = strategy_results

            # Merge extracted users
            if strategy_results.get('users_extracted'):
                for user in strategy_results['users_extracted']:
                    if user.get('username'):
                        results['data_extracted'].append({
                            'username': user['username'],
                            'profile_url': f"https://www.tiktok.com/@{user['username']}",
                            'source': user.get('source', 'ai_strategy')
                        })

            if args.save:
                path = Path(args.output) / f"ai_strategy_{username}.json"
                path.write_text(json.dumps(strategy_results, indent=2, default=str), encoding='utf-8')
                print(f"[+] AI strategy saved: {path}")

        # Print summary
        print(f"\n[===] DOM Bypass Complete [===]")
        if results['recon']:
            print(f"  Recon: {len(results['recon'].get('components', []))} components found")
        if results['injection']:
            print(f"  Injection: {results['injection'].get('success_count', 0)} successful")
        if results.get('dom_algorithms'):
            print(f"  DOM Deep: {results['dom_algorithms'].get('total_unique_users', 0)} users extracted")
        if results.get('ai_analysis'):
            print(f"  AI Analysis: {'✅' if results['ai_analysis'].get('success') else '❌'}")
        if results.get('ai_strategy'):
            s = results['ai_strategy']
            print(f"  AI Strategy: {s.get('steps_succeeded',0)}/{s.get('steps_total',0)} steps, {s.get('total_unique_users',0)} users")
        if results['data_extracted']:
            print(f"  Data: {len(results['data_extracted'])} users extracted")

        return results

    except Exception as e:
        print(f"[X] DOM Bypass error: {e}")
        return results
    finally:
        await context.close()


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


async def main(args):
    """TikTok scraper main entry point."""
    # Validate
    needs_cookies = (args.following or args.followers or args.bfs or args.dfs or
                     args.astar or args.bidirectional or args.random_walk or
                     args.influence or args.community or args.recon or args.inject or
                     args.maintain or args.full_bypass or args.dom_deep or
                     args.ai_analyze or args.ai_strategy)
    if needs_cookies and not args.cookies:
        print("\n[!] Fitur social memerlukan cookies!")
        print("    Gunakan: --cookies tiktok_cookies.json")
        return

    # Header
    print(f"  Mode     : {'Headless' if args.headless else 'Visible'}")
    print(f"  Delay    : {args.delay}")
    if args.cookies:
        print(f"  Cookies  : {args.cookies}")
    if args.proxy_file:
        print(f"  Proxies  : {args.proxy_file}")

    # Show algorithm/mode
    if args.full_bypass:
        print(f"  Mode     : Full DOM Bypass + Deep Algorithms + AI")
    elif args.ai_strategy:
        print(f"  Mode     : AI Adaptive Strategy (Ollama MCP-D2)")
    elif args.ai_analyze:
        print(f"  Mode     : AI Context Analysis (Ollama MCP-D1)")
    elif args.dom_deep:
        print(f"  Mode     : DOM Deep Algorithms (D1-D15)")
    elif args.recon:
        print(f"  Mode     : Reconnaissance Only")
    elif args.inject:
        print(f"  Mode     : Injection Only")
    elif args.maintain:
        print(f"  Mode     : Maintenance Only")
    elif args.bfs:
        print(f"  Algorithm: BFS (depth={args.depth})")
    elif args.dfs:
        print(f"  Algorithm: DFS (depth={args.depth})")
    elif args.astar:
        print(f"  Algorithm: A* Search (depth={args.depth})")
    elif args.bidirectional:
        print(f"  Algorithm: Bidirectional (target={args.bidirectional})")
    elif args.random_walk:
        print(f"  Algorithm: Random Walk ({args.walks} walks, {args.steps} steps)")
    elif args.influence:
        print(f"  Algorithm: Influence Scoring")
    elif args.community:
        print(f"  Algorithm: Community Detection")

    if args.export:
        print(f"  Export   : {args.export}")
    print("=" * 60)

    # Get delay manager
    delay = get_delay_manager(args.delay)
    exporter = DataExporter(args.output)

    async with TikTokScraper(
        headless=args.headless,
        cookies_file=args.cookies,
        proxy_file=args.proxy_file
    ) as scraper:

        for username in args.usernames:
            print(f"\n{'='*50}")

            # ===== DOM BYPASS MODES =====
            if args.recon or args.inject or args.maintain or args.full_bypass or args.dom_deep or args.ai_analyze or args.ai_strategy:
                bypass_results = await _run_dom_bypass(scraper, username, args)

                # Use extracted data for export
                if bypass_results['data_extracted']:
                    results = bypass_results['data_extracted']
                    result_type = "bypass"

                    if args.export:
                        base_name = f"tiktok_{username}_{result_type}"
                        if args.export == "csv":
                            exporter.to_csv(results, f"{base_name}.csv")
                        elif args.export == "excel":
                            exporter.to_excel(results, f"{base_name}.xlsx")
                        elif args.export == "jsonl":
                            exporter.to_jsonl(results, f"{base_name}.jsonl")
                continue

            # Get profile first
            profile = await scraper.get_profile(username, save_debug=args.debug)

            if profile:
                print(profile)
                if args.save:
                    path = scraper.save_profile(profile, args.output)
                    print(f"[+] Saved: {path}")
            else:
                print(f"[X] Failed: @{username}")
                continue

            results = []
            result_type = "users"

            # ===== A* SEARCH =====
            if args.astar:
                print(f"\n[~] A* search from @{username}...")
                crawler = AStarCrawler(
                    max_depth=args.depth,
                    max_users=args.max,
                    delay_between=delay.base_delay
                )
                results = await crawler.search(
                    username,
                    scraper.get_followers,
                    scraper.get_profile
                )
                result_type = "astar"

            # ===== BIDIRECTIONAL SEARCH =====
            elif args.bidirectional:
                print(f"\n[~] Finding path: @{username} <-> @{args.bidirectional}...")
                searcher = BidirectionalSearch(
                    max_depth=args.depth,
                    delay_between=delay.base_delay
                )
                path = await searcher.find_path(
                    username,
                    args.bidirectional,
                    scraper.get_followers
                )
                if path:
                    results = [{'username': u, 'position': i} for i, u in enumerate(path)]
                    print(f"\n[+] Path found: {' -> '.join(path)}")
                result_type = "path"

            # ===== RANDOM WALK =====
            elif args.random_walk:
                print(f"\n[~] Random walk from @{username}...")
                sampler = RandomWalkSampler(
                    num_walks=args.walks,
                    walk_length=args.steps,
                    delay_between=delay.base_delay
                )
                results = await sampler.sample(username, scraper.get_followers)
                result_type = "randomwalk"

            # ===== INFLUENCE SCORING =====
            elif args.influence:
                print(f"\n[~] Calculating influence scores from @{username}...")
                scorer = InfluenceScorer(delay_between=delay.base_delay)
                results = await scorer.calculate(
                    [username],
                    scraper.get_followers,
                    max_users=args.max
                )
                result_type = "influence"

                if results:
                    print("\n+-- Top Influencers --+")
                    for i, user in enumerate(results[:10], 1):
                        print(f"| {i:2}. @{user['username'][:20]:<20} score={user['influence_score']:.4f}")
                    print("+---------------------+")

            # ===== COMMUNITY DETECTION =====
            elif args.community:
                print(f"\n[~] Detecting communities from @{username}...")
                detector = CommunityDetector(delay_between=delay.base_delay)
                communities = await detector.detect(
                    [username],
                    scraper.get_followers,
                    max_users=args.max
                )

                results = []
                for comm_id, members in communities.items():
                    results.extend(members)
                result_type = "community"

                print(f"\n+-- Communities ({len(communities)}) --+")
                for comm_id, members in list(communities.items())[:5]:
                    print(f"| {comm_id}: {len(members)} members")
                print("+------------------------+")

            # ===== BFS/DFS CRAWLING =====
            elif args.bfs or args.dfs:
                algorithm = "bfs" if args.bfs else "dfs"
                print(f"\n[~] {algorithm.upper()} crawling @{username}...")

                crawler = GraphCrawler(
                    max_depth=args.depth,
                    max_users=args.max,
                    delay_between=delay.base_delay
                )

                if args.bfs:
                    results = await crawler.bfs(username, scraper.get_followers)
                else:
                    results = await crawler.dfs(username, scraper.get_followers)
                result_type = algorithm

                if results:
                    _print_crawl_results(results, algorithm, username)

            # ===== SIMPLE FOLLOWING/FOLLOWERS =====
            elif args.following:
                await delay.wait_short()
                results = await scraper.get_following(username, max_count=args.max)
                result_type = "following"
                if results:
                    _print_user_list(results, "Following", username)

            elif args.followers:
                await delay.wait_short()
                results = await scraper.get_followers(username, max_count=args.max)
                result_type = "followers"
                if results:
                    _print_user_list(results, "Followers", username)

            # ===== EXPORT =====
            if results:
                base_name = f"tiktok_{username}_{result_type}"

                if args.save:
                    path = Path(args.output) / f"{base_name}.json"
                    path.write_text(json.dumps(results, indent=2), encoding='utf-8')
                    print(f"[+] Saved: {path}")

                if args.export:
                    if args.export == "csv":
                        exporter.to_csv(results, f"{base_name}.csv")
                    elif args.export == "excel":
                        exporter.to_excel(results, f"{base_name}.xlsx")
                    elif args.export == "jsonl":
                        exporter.to_jsonl(results, f"{base_name}.jsonl")
                    elif args.export == "graphml":
                        exporter.to_graphml(results, f"{base_name}.graphml")
                    elif args.export == "gexf":
                        exporter.to_gexf(results, f"{base_name}.gexf")

                if args.stats:
                    exporter.save_stats(results, f"{base_name}_stats.json")

        # Show sniffed APIs
        if args.sniff:
            apis = scraper.browser_manager.get_captured_apis()
            if apis:
                print(f"\n[Sniffer] Captured {len(apis)} API calls:")
                for api in apis[:10]:
                    print(f"  - {api.url[:80]}")

    print("\n[OK] Complete!")
