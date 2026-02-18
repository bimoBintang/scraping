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
        help='Journal article research scraper — search, cite, trend, recommend',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py journal search "machine learning" --count 20
  python main.py journal search "NLP transformers" --year 2024-2026 --source openalex
  python main.py journal cite 10.1038/s41586-021-03819-2 --depth 2
  python main.py journal trend "deep learning" --years 2015-2026
  python main.py journal recommend 10.1038/s41586-021-03819-2 --count 15
  python main.py journal harvest --topic "computer vision" --year 2025 --count 500
  python main.py journal export results.json --format bibtex --output refs.bib
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

    return parser


def run(args):
    """Execute journal commands"""
    from .api_client import OpenAlexClient, SemanticScholarClient, CrossRefClient
    from .search_engine import FederatedSearch, CitationCrawler, TrendAnalyzer, PaperRecommender
    from .exporter import JournalExporter

    if not hasattr(args, 'command') or not args.command:
        print("  [!] Gunakan subcommand: search, cite, trend, recommend, harvest")
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

    else:
        print(f"  [!] Unknown command: {args.command}")
