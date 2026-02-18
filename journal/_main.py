"""
Journal Article Scraper — CLI Handler

Handles all 'python main.py journal ...' commands.
"""

import argparse
import json
import sys
from pathlib import Path


def setup_parser(subparsers):
    """Register journal subcommands to the main parser"""
    parser = subparsers.add_parser(
        'journal',
        help='Journal article research scraper — search, cite, trend, recommend, author',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py journal search "machine learning" --count 20
  python main.py journal search "NLP transformers" --year 2024-2026 --source openalex
  python main.py journal cite 10.1038/s41586-021-03819-2 --depth 2
  python main.py journal trend "deep learning" --years 2015-2026
  python main.py journal recommend 10.1038/s41586-021-03819-2 --count 15
  python main.py journal harvest --topic "computer vision" --year 2025 --count 500
  python main.py journal author "Geoffrey Hinton" --network --count 50
  python main.py journal intent 10.1038/s41586-021-03819-2 --count 100
  python main.py journal frontier "machine learning" --topics 10 --years 2020-2026
  python main.py journal rank "Nature" --years 2020-2025
  python main.py journal rank --compare "Nature,Science,IEEE" --year 2025
        """,
    )

    # Subcommands
    sub = parser.add_subparsers(dest='command', help='Journal commands')

    # ── SEARCH ──
    search_p = sub.add_parser('search', help='Search for papers (Algorithm J1)')
    search_p.add_argument('query', type=str, help='Search query')
    search_p.add_argument('--count', type=int, default=25, help='Number of results (default: 25)')
    search_p.add_argument('--year', type=str, help='Year range, e.g. 2020-2026 or 2025')
    search_p.add_argument('--source', type=str, default='all',
                          choices=['all', 'openalex', 'semantic_scholar', 'crossref'],
                          help='API source (default: all)')
    search_p.add_argument('--sort', type=str, default='relevance',
                          choices=['relevance', 'citations', 'year'],
                          help='Sort order (default: relevance)')
    search_p.add_argument('--export', type=str,
                          choices=['json', 'csv', 'bibtex', 'ris', 'markdown'],
                          help='Export format')
    search_p.add_argument('--output', type=str, default='.', help='Output directory')

    # ── CITE ──
    cite_p = sub.add_parser('cite', help='Citation graph crawl (Algorithm J2)')
    cite_p.add_argument('doi', type=str, help='Paper DOI or ID')
    cite_p.add_argument('--depth', type=int, default=1, help='Crawl depth (default: 1)')
    cite_p.add_argument('--direction', type=str, default='both',
                        choices=['forward', 'backward', 'both'],
                        help='Crawl direction (default: both)')
    cite_p.add_argument('--max-per-level', type=int, default=20,
                        help='Max papers per level (default: 20)')
    cite_p.add_argument('--export', type=str, choices=['json', 'csv', 'bibtex'],
                        help='Export format')
    cite_p.add_argument('--output', type=str, default='.', help='Output directory')

    # ── TREND ──
    trend_p = sub.add_parser('trend', help='Research trend analysis (Algorithm J3)')
    trend_p.add_argument('query', type=str, help='Topic or search term')
    trend_p.add_argument('--years', type=str, default='2015-2026',
                         help='Year range (default: 2015-2026)')
    trend_p.add_argument('--export', type=str, choices=['json', 'csv'], help='Export')
    trend_p.add_argument('--output', type=str, default='.', help='Output directory')

    # ── RECOMMEND ──
    rec_p = sub.add_parser('recommend', help='Paper recommendations (Algorithm J4)')
    rec_p.add_argument('doi', type=str, help='Paper DOI or S2 ID')
    rec_p.add_argument('--count', type=int, default=20, help='Number of recommendations')
    rec_p.add_argument('--min-year', type=int, help='Minimum publication year')
    rec_p.add_argument('--export', type=str,
                       choices=['json', 'csv', 'bibtex', 'ris', 'markdown'],
                       help='Export format')
    rec_p.add_argument('--output', type=str, default='.', help='Output directory')

    # ── HARVEST ──
    harvest_p = sub.add_parser('harvest', help='Bulk download papers (Algorithm J5)')
    harvest_p.add_argument('--query', type=str, help='Search query')
    harvest_p.add_argument('--topic', type=str, help='Topic filter')
    harvest_p.add_argument('--year', type=str, help='Year or year range')
    harvest_p.add_argument('--count', type=int, default=1000,
                           help='Max papers to harvest (default: 1000)')
    harvest_p.add_argument('--export', type=str, default='json',
                           choices=['json', 'csv', 'bibtex'],
                           help='Export format (default: json)')
    harvest_p.add_argument('--output', type=str, default='.', help='Output directory')

    # ── AUTHOR (J6) ──
    author_p = sub.add_parser('author', help='Author disambiguation & network (Algorithm J6)')
    author_p.add_argument('name', type=str, help='Author name to search')
    author_p.add_argument('--count', type=int, default=50,
                          help='Number of papers to fetch for analysis (default: 50)')
    author_p.add_argument('--network', action='store_true',
                          help='Build and analyze collaboration network')
    author_p.add_argument('--year', type=str, help='Year range filter')
    author_p.add_argument('--export', type=str,
                          choices=['json', 'csv', 'markdown'],
                          help='Export format')
    author_p.add_argument('--output', type=str, default='.', help='Output directory')

    # ── INTENT (J7) ──
    intent_p = sub.add_parser('intent', help='Citation intent & sentiment analysis (Algorithm J7)')
    intent_p.add_argument('doi', type=str, help='Paper DOI or Semantic Scholar ID')
    intent_p.add_argument('--count', type=int, default=100,
                          help='Max citations to analyze (default: 100)')
    intent_p.add_argument('--export', type=str, choices=['json'],
                          help='Export format')
    intent_p.add_argument('--output', type=str, default='.', help='Output directory')

    # ── FRONTIER (J8) ──
    front_p = sub.add_parser('frontier', help='Emerging research frontier detection (Algorithm J8)')
    front_p.add_argument('query', type=str, help='Broad research area to scan')
    front_p.add_argument('--topics', type=int, default=10,
                         help='Number of sub-topics to analyze (default: 10)')
    front_p.add_argument('--years', type=str, default='2018-2026',
                         help='Year range (default: 2018-2026)')
    front_p.add_argument('--export', type=str, choices=['json'],
                         help='Export format')
    front_p.add_argument('--output', type=str, default='.', help='Output directory')

    # ── RANK (J9) ──
    rank_p = sub.add_parser('rank', help='Journal impact ranking & prediction (Algorithm J9)')
    rank_p.add_argument('journal', type=str, nargs='?', help='Journal name to analyze')
    rank_p.add_argument('--compare', type=str,
                        help='Comma-separated journal names to compare')
    rank_p.add_argument('--years', type=str, default='2020-2025',
                        help='Year range for analysis (default: 2020-2025)')
    rank_p.add_argument('--year', type=int, default=2025,
                        help='Reference year for comparison (default: 2025)')
    rank_p.add_argument('--export', type=str, choices=['json'],
                        help='Export format')
    rank_p.add_argument('--output', type=str, default='.', help='Output directory')

    return parser


def run(args):
    """Execute journal commands"""
    from .api_client import OpenAlexClient, SemanticScholarClient, CrossRefClient
    from .search_engine import FederatedSearch, CitationCrawler, TrendAnalyzer, PaperRecommender
    from .author_network import AuthorDisambiguator, CollaborationNetwork
    from .citation_analyzer import CitationClassifier, CitationImpactAnalyzer
    from .frontier_detector import ResearchFrontierDetector
    from .journal_ranker import JournalMetricsCalculator, JournalRankPredictor
    from .exporter import JournalExporter

    if not hasattr(args, 'command') or not args.command:
        print("  [!] Gunakan subcommand: search, cite, trend, recommend, harvest, author, intent, frontier, rank")
        print("  💡 python main.py journal search \"machine learning\"")
        return

    # ==================== SEARCH (J1) ====================
    if args.command == 'search':
        sources = None
        if args.source != 'all':
            sources = [args.source]

        engine = FederatedSearch()
        result = engine.search(
            query=args.query,
            count=args.count,
            year_range=args.year,
            sources=sources,
            sort=args.sort,
        )

        # Print results
        print(f"\n  📚 Found {result.total_count} papers ({result.elapsed_seconds:.1f}s)")
        print(f"  {'─' * 70}")

        for i, p in enumerate(result.papers[:args.count], 1):
            authors = ", ".join(p.author_names[:2])
            if len(p.author_names) > 2:
                authors += " et al."
            oa = " 🔓" if p.is_open_access else ""

            print(f"\n  {i:2d}. [{p.year}] {p.title[:70]}{'...' if len(p.title) > 70 else ''}")
            print(f"      {authors} | {p.journal or 'N/A'}")
            print(f"      Citations: {p.citation_count} | DOI: {p.doi or 'N/A'}{oa}")

        # Export
        if args.export:
            exporter = JournalExporter(args.output)
            exporter.export(result.papers, args.export, query=args.query)

    # ==================== CITE (J2) ====================
    elif args.command == 'cite':
        crawler = CitationCrawler()
        result = crawler.crawl(
            seed_doi=args.doi,
            depth=args.depth,
            direction=args.direction,
            max_per_level=args.max_per_level,
        )

        if 'error' not in result:
            if args.export:
                exporter = JournalExporter(args.output)
                exporter.export(result['papers'], args.export, query=f"cite_{args.doi}")

    # ==================== TREND (J3) ====================
    elif args.command == 'trend':
        years = args.years.split('-')
        start_year = int(years[0])
        end_year = int(years[1]) if len(years) > 1 else start_year

        analyzer = TrendAnalyzer()
        result = analyzer.analyze(
            query=args.query,
            start_year=start_year,
            end_year=end_year,
        )

        print(f"\n  Direction: {result['direction']}")
        print(f"  Peak: {result['peak_year']} ({result['peak_count']:,} papers)")
        print(f"  Total: {result['total_publications']:,}")

        if args.export:
            filepath = Path(args.output) / f"trend_{args.query.replace(' ', '_')[:20]}.{args.export}"
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"  [✓] Exported → {filepath}")

    # ==================== RECOMMEND (J4) ====================
    elif args.command == 'recommend':
        recommender = PaperRecommender()
        result = recommender.recommend(
            doi_or_id=args.doi,
            count=args.count,
            min_year=args.min_year,
        )

        if 'error' not in result and args.export:
            from .models import Paper
            papers = [Paper(**p) if isinstance(p, dict) else p
                      for p in result.get('recommendations', [])]
            # Re-parse from dicts
            recs = []
            for p_data in result.get('recommendations', []):
                if isinstance(p_data, dict):
                    recs.append(Paper(
                        title=p_data.get('title', ''),
                        doi=p_data.get('doi', ''),
                        year=p_data.get('year', 0),
                        author_names=p_data.get('author_names', []),
                        journal=p_data.get('journal', ''),
                        citation_count=p_data.get('citation_count', 0),
                        abstract=p_data.get('abstract', ''),
                        url=p_data.get('url', ''),
                        is_open_access=p_data.get('is_open_access', False),
                    ))

            if recs:
                exporter = JournalExporter(args.output)
                exporter.export(recs, args.export, query=f"similar_to_{args.doi}")

    # ==================== HARVEST (J5) ====================
    elif args.command == 'harvest':
        if not args.query and not args.topic:
            print("  [!] Specify --query or --topic for harvest")
            return

        oa = OpenAlexClient()
        exporter = JournalExporter(args.output)

        all_papers = []
        total = 0

        print(f"\n  [🌾] Harvesting papers (max {args.count})...")

        for batch in oa.cursor_harvest(
            query=args.query or '',
            topic=args.topic or '',
            year=args.year,
        ):
            all_papers.extend(batch)
            total += len(batch)

            sys.stdout.write(f"\r  Harvested: {total} papers...")
            sys.stdout.flush()

            if total >= args.count:
                all_papers = all_papers[:args.count]
                break

        print(f"\n  [✓] Harvested {len(all_papers)} papers")

        query_label = args.query or args.topic or 'harvest'
        exporter.export(all_papers, args.export, query=query_label)

    # ==================== AUTHOR NETWORK (J6) ====================
    elif args.command == 'author':
        oa = OpenAlexClient()

        # Search papers by this author
        print(f"\n  [👤] Searching papers by: {args.name}")
        params = {
            'search': args.name,
            'per_page': min(args.count, 200),
            'sort': 'cited_by_count:desc',
        }
        filters = [f'author.search:{args.name}']
        if args.year:
            parts = args.year.split('-')
            if len(parts) == 2:
                filters.append(f'from_publication_date:{parts[0]}-01-01')
                filters.append(f'to_publication_date:{parts[1]}-12-31')
        params['filter'] = ','.join(filters)

        data = oa._request('works', params)
        papers = [oa._parse_work(w) for w in data.get('results', [])]

        if not papers:
            print(f"  [!] No papers found for author: {args.name}")
            return

        print(f"  [✓] Found {len(papers)} papers")

        # Disambiguate
        dis = AuthorDisambiguator()
        disambiguated = dis.disambiguate(papers)

        # Show disambiguation results
        print(f"\n  📋 Disambiguated Authors:")
        print(f"  {'─'*55}")
        for i, (key, author) in enumerate(
            sorted(disambiguated.items(),
                   key=lambda x: x[1].paper_count, reverse=True)[:15], 1
        ):
            aff = author.affiliations[0][:40] if author.affiliations else 'N/A'
            print(f"  {i:2d}. {author.canonical_name} "
                  f"({author.paper_count} papers, {author.year_range()})")
            print(f"      📍 {aff}")

        # Network analysis
        if args.network:
            net = CollaborationNetwork()
            report = net.build_and_analyze(papers, disambiguated)
            report.query = args.name
            net.print_report(report)

            if args.export == 'json':
                filepath = Path(args.output) / f"network_{args.name.replace(' ', '_')[:20]}.json"
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
                print(f"  [✓] Exported → {filepath}")

    # ==================== CITATION INTENT (J7) ====================
    elif args.command == 'intent':
        analyzer = CitationImpactAnalyzer()
        report = analyzer.analyze(
            doi_or_id=args.doi,
            limit=args.count,
        )

        if args.export == 'json' and report.analyzed_citations > 0:
            filepath = Path(args.output) / f"intent_{args.doi.replace('/', '_')[:30]}.json"
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
            print(f"  [✓] Exported → {filepath}")

    # ==================== FRONTIER (J8) ====================
    elif args.command == 'frontier':
        years = args.years.split('-')
        start_year = int(years[0])
        end_year = int(years[1]) if len(years) > 1 else start_year

        detector = ResearchFrontierDetector()
        report = detector.detect(
            query=args.query,
            n_topics=args.topics,
            start_year=start_year,
            end_year=end_year,
        )

        if args.export == 'json' and report.frontiers:
            filepath = Path(args.output) / f"frontier_{args.query.replace(' ', '_')[:20]}.json"
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
            print(f"  [✓] Exported → {filepath}")

    # ==================== RANK (J9) ====================
    elif args.command == 'rank':
        predictor = JournalRankPredictor()

        if args.compare:
            journals = [j.strip() for j in args.compare.split(',')]
            report = predictor.compare(journals, year=args.year)
        elif args.journal:
            years = args.years.split('-')
            start_year = int(years[0])
            end_year = int(years[1]) if len(years) > 1 else start_year
            report = predictor.analyze(args.journal, start_year, end_year)
        else:
            print("  [!] Specify a journal name or use --compare")
            return

        if args.export == 'json':
            name = (args.journal or 'comparison').replace(' ', '_')[:20]
            filepath = Path(args.output) / f"rank_{name}.json"
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
            print(f"  [✓] Exported → {filepath}")

    else:
        print(f"  [!] Unknown command: {args.command}")
