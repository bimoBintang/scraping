"""
Journal Article Search Engine — 4 Algorithms

J1: FederatedSearch   — multi-source parallel search + merge + dedup
J2: CitationCrawler   — BFS citation graph traversal
J3: TrendAnalyzer     — research trend time-series analysis
J4: PaperRecommender  — similarity-based paper recommendations
"""

import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from .models import (
    Author, Paper, CitationEdge,
    SearchResult, TrendPoint, ResearchReport,
)
from .api_client import OpenAlexClient, SemanticScholarClient, CrossRefClient


# ==================== J1: FEDERATED SEARCH ====================

class FederatedSearch:
    """
    Algorithm J1: Multi-Source Federated Search.

    Queries OpenAlex, Semantic Scholar, and CrossRef in parallel,
    merges results, deduplicates by DOI/title, and ranks by
    weighted score (citations × recency × relevance).
    """

    def __init__(
        self,
        openalex: Optional[OpenAlexClient] = None,
        semantic_scholar: Optional[SemanticScholarClient] = None,
        crossref: Optional[CrossRefClient] = None,
    ):
        self.oa = openalex or OpenAlexClient()
        self.s2 = semantic_scholar or SemanticScholarClient()
        self.cr = crossref or CrossRefClient()

    def search(
        self,
        query: str,
        count: int = 25,
        year_range: Optional[str] = None,
        sources: Optional[List[str]] = None,
        sort: str = "relevance",
    ) -> SearchResult:
        """
        Search across multiple APIs and merge results.

        Args:
            query: Search query
            count: Max results per source
            year_range: e.g. "2020-2026"
            sources: List of sources to use (default: all 3)
            sort: "relevance", "citations", "year"

        Returns:
            SearchResult with deduplicated, ranked papers
        """
        if sources is None:
            sources = ['openalex', 'semantic_scholar', 'crossref']

        start = time.time()
        all_papers = []

        # Parallel fetch from all sources
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {}

            if 'openalex' in sources:
                futures[pool.submit(
                    self.oa.search, query, count, 1, year_range
                )] = 'openalex'

            if 'semantic_scholar' in sources:
                s2_year = None
                if year_range and '-' in year_range:
                    s2_year = year_range
                futures[pool.submit(
                    self.s2.search, query, count, s2_year
                )] = 'semantic_scholar'

            if 'crossref' in sources:
                futures[pool.submit(
                    self.cr.search, query, count, 0, "is-referenced-by-count", year_range
                )] = 'crossref'

            for future in as_completed(futures):
                source_name = futures[future]
                try:
                    papers = future.result()
                    all_papers.extend(papers)
                    print(f"  [{source_name}] → {len(papers)} results")
                except Exception as e:
                    print(f"  [{source_name}] Error: {e}")

        # Deduplicate
        deduped = self._deduplicate(all_papers)
        print(f"  [merge] {len(all_papers)} → {len(deduped)} after dedup")

        # Sort/rank
        ranked = self._rank(deduped, sort)

        elapsed = time.time() - start

        return SearchResult(
            query=query,
            papers=ranked[:count],
            total_count=len(ranked),
            source='federated',
            elapsed_seconds=elapsed,
        )

    def _deduplicate(self, papers: List[Paper]) -> List[Paper]:
        """Deduplicate papers by DOI, then by normalized title"""
        seen_dois: Dict[str, Paper] = {}
        seen_titles: Dict[str, Paper] = {}
        result = []

        for p in papers:
            # Prefer papers with DOI
            if p.doi:
                doi_key = p.doi.lower().strip()
                if doi_key in seen_dois:
                    existing = seen_dois[doi_key]
                    # Merge: keep richer version
                    if p.abstract and not existing.abstract:
                        existing.abstract = p.abstract
                    if p.citation_count > existing.citation_count:
                        existing.citation_count = p.citation_count
                    continue
                seen_dois[doi_key] = p
                result.append(p)
            else:
                # Fallback: normalize title
                norm = self._normalize_title(p.title)
                if norm and norm not in seen_titles:
                    seen_titles[norm] = p
                    result.append(p)

        return result

    @staticmethod
    def _normalize_title(title: str) -> str:
        """Normalize title for comparison"""
        import re
        title = title.lower().strip()
        title = re.sub(r'[^a-z0-9\s]', '', title)
        title = re.sub(r'\s+', ' ', title)
        return title

    @staticmethod
    def _rank(papers: List[Paper], sort: str) -> List[Paper]:
        """Rank papers by weighted score"""
        current_year = datetime.now().year

        if sort == "citations":
            return sorted(papers, key=lambda p: p.citation_count, reverse=True)
        elif sort == "year":
            return sorted(papers, key=lambda p: p.year, reverse=True)
        else:
            # Relevance: weighted combo of citations + recency
            def score(p):
                recency = max(0, 1 - (current_year - p.year) / 20)
                cite_score = min(p.citation_count / 100, 10)
                return cite_score * 0.6 + recency * 0.4
            return sorted(papers, key=score, reverse=True)


# ==================== J2: CITATION GRAPH CRAWLER ====================

class CitationCrawler:
    """
    Algorithm J2: BFS Citation Graph Traversal.

    Starting from a seed paper, crawl citation tree with BFS:
    - Forward: papers that cite this paper (cited_by)
    - Backward: papers this paper references
    """

    def __init__(
        self,
        openalex: Optional[OpenAlexClient] = None,
        semantic_scholar: Optional[SemanticScholarClient] = None,
    ):
        self.oa = openalex or OpenAlexClient()
        self.s2 = semantic_scholar or SemanticScholarClient()

    def crawl(
        self,
        seed_doi: str,
        depth: int = 2,
        direction: str = "both",
        max_per_level: int = 20,
    ) -> Dict:
        """
        BFS crawl citation graph.

        Args:
            seed_doi: Starting paper DOI
            depth: How many levels to crawl
            direction: "forward" (cited_by), "backward" (references), "both"
            max_per_level: Max papers per level

        Returns:
            Dict with papers, edges, and stats
        """
        print(f"\n  [🔗] Citation crawl: {seed_doi} (depth={depth}, dir={direction})")

        # Resolve seed paper
        seed = self._resolve_paper(seed_doi)
        if not seed:
            print(f"  [!] Could not resolve paper: {seed_doi}")
            return {'error': 'not_found'}

        print(f"  [✓] Seed: {seed.title[:60]}... ({seed.citation_count} citations)")

        all_papers: Dict[str, Paper] = {self._paper_key(seed): seed}
        all_edges: List[CitationEdge] = []
        queue = [(seed, 0)]  # (paper, current_depth)
        visited: Set[str] = {self._paper_key(seed)}

        while queue:
            current_paper, current_depth = queue.pop(0)

            if current_depth >= depth:
                continue

            paper_key = self._paper_key(current_paper)
            next_depth = current_depth + 1

            # Forward: papers that cite this one
            if direction in ('forward', 'both'):
                citing = self._get_citations(current_paper, max_per_level)
                for p in citing:
                    pk = self._paper_key(p)
                    edge = CitationEdge(
                        source_id=pk,
                        target_id=paper_key,
                        source_title=p.title,
                        target_title=current_paper.title,
                        year=p.year,
                    )
                    all_edges.append(edge)

                    if pk not in visited:
                        visited.add(pk)
                        all_papers[pk] = p
                        if next_depth < depth:
                            queue.append((p, next_depth))

            # Backward: papers this one references
            if direction in ('backward', 'both'):
                refs = self._get_references(current_paper, max_per_level)
                for p in refs:
                    pk = self._paper_key(p)
                    edge = CitationEdge(
                        source_id=paper_key,
                        target_id=pk,
                        source_title=current_paper.title,
                        target_title=p.title,
                        year=p.year,
                    )
                    all_edges.append(edge)

                    if pk not in visited:
                        visited.add(pk)
                        all_papers[pk] = p
                        if next_depth < depth:
                            queue.append((p, next_depth))

            print(f"    depth {current_depth}: +{len(citing) if direction != 'backward' else 0} cited_by, "
                  f"+{len(refs) if direction != 'forward' else 0} refs "
                  f"(total: {len(all_papers)} papers, {len(all_edges)} edges)")

            time.sleep(0.3)  # rate limit

        print(f"  [✓] Graph: {len(all_papers)} papers, {len(all_edges)} edges")

        return {
            'seed': seed.to_dict(),
            'papers': list(all_papers.values()),
            'edges': [e.to_dict() for e in all_edges],
            'stats': {
                'total_papers': len(all_papers),
                'total_edges': len(all_edges),
                'depth': depth,
                'direction': direction,
            },
        }

    def _resolve_paper(self, doi_or_id: str) -> Optional[Paper]:
        """Try to resolve via S2 first (faster), fallback to OpenAlex"""
        s2_id = doi_or_id
        if doi_or_id.startswith('10.'):
            s2_id = f"DOI:{doi_or_id}"

        paper = self.s2.get_paper(s2_id)
        if paper:
            return paper

        return self.oa.get_work(doi_or_id)

    def _get_citations(self, paper: Paper, limit: int) -> List[Paper]:
        """Get citing papers, prefer S2"""
        s2_id = paper.paper_id or (f"DOI:{paper.doi}" if paper.doi else None)
        if s2_id:
            try:
                return self.s2.get_citations(s2_id, limit)
            except Exception:
                pass

        if paper.paper_id and paper.paper_id.startswith('https://openalex.org'):
            oa_id = paper.paper_id.split('/')[-1]
            return self.oa.get_citations(oa_id, limit)

        return []

    def _get_references(self, paper: Paper, limit: int) -> List[Paper]:
        """Get referenced papers"""
        s2_id = paper.paper_id or (f"DOI:{paper.doi}" if paper.doi else None)
        if s2_id:
            try:
                return self.s2.get_references(s2_id, limit)
            except Exception:
                pass
        return []

    @staticmethod
    def _paper_key(paper: Paper) -> str:
        """Unique key for a paper"""
        if paper.doi:
            return paper.doi.lower()
        return paper.paper_id or paper.title.lower()[:80]


# ==================== J3: TREND ANALYZER ====================

class TrendAnalyzer:
    """
    Algorithm J3: Research Trend Analysis.

    Analyze publication trends for a query/topic over time.
    Computes growth rates, detects peaks, and identifies direction.
    """

    def __init__(self, openalex: Optional[OpenAlexClient] = None):
        self.oa = openalex or OpenAlexClient()

    def analyze(
        self,
        query: str,
        start_year: int = 2015,
        end_year: Optional[int] = None,
    ) -> Dict:
        """
        Analyze research trends for a topic.

        Args:
            query: Topic or search term
            start_year: Start year
            end_year: End year (default: current year)

        Returns:
            Dict with trend points, stats, and direction
        """
        if end_year is None:
            end_year = datetime.now().year

        print(f"\n  [📈] Trend analysis: \"{query}\" ({start_year}–{end_year})")

        # Get counts per year from OpenAlex
        raw_counts = self.oa.count_by_year(query, start_year, end_year)

        # Build year → count map (fill missing years with 0)
        count_map = {item['year']: item['count'] for item in raw_counts}
        years = list(range(start_year, end_year + 1))

        # Build trend points
        trend_points = []
        prev_count = 0
        cumulative = 0

        for year in years:
            count = count_map.get(year, 0)
            cumulative += count

            growth = 0.0
            if prev_count > 0:
                growth = ((count - prev_count) / prev_count) * 100

            trend_points.append(TrendPoint(
                year=year,
                count=count,
                growth_rate=round(growth, 1),
                cumulative=cumulative,
            ))
            prev_count = count

        # Find peak
        peak = max(trend_points, key=lambda t: t.count) if trend_points else None

        # Determine direction (based on last 3 years)
        recent = trend_points[-3:] if len(trend_points) >= 3 else trend_points
        if len(recent) >= 2:
            avg_growth = sum(t.growth_rate for t in recent) / len(recent)
            if avg_growth > 10:
                direction = "🚀 rapidly growing"
            elif avg_growth > 2:
                direction = "📈 growing"
            elif avg_growth > -2:
                direction = "➡️ stable"
            elif avg_growth > -10:
                direction = "📉 declining"
            else:
                direction = "⬇️ rapidly declining"
        else:
            direction = "❓ insufficient data"

        # Print summary
        self._print_chart(trend_points, query)

        return {
            'query': query,
            'start_year': start_year,
            'end_year': end_year,
            'trend_points': [t.to_dict() for t in trend_points],
            'peak_year': peak.year if peak else 0,
            'peak_count': peak.count if peak else 0,
            'total_publications': cumulative,
            'direction': direction,
        }

    @staticmethod
    def _print_chart(points: List[TrendPoint], query: str):
        """Print ASCII bar chart"""
        if not points:
            return

        max_count = max(t.count for t in points) or 1
        bar_width = 40

        print(f"\n  📊 Publication Trend: \"{query}\"")
        print(f"  {'─' * 60}")

        for t in points:
            bar_len = int((t.count / max_count) * bar_width)
            bar = '█' * bar_len
            growth_str = ""
            if t.growth_rate > 0:
                growth_str = f" (+{t.growth_rate:.0f}%)"
            elif t.growth_rate < 0:
                growth_str = f" ({t.growth_rate:.0f}%)"

            print(f"  {t.year} │{bar:<{bar_width}} {t.count:>8,}{growth_str}")

        print(f"  {'─' * 60}")
        total = points[-1].cumulative if points else 0
        print(f"  Total: {total:,} publications")


# ==================== J4: PAPER RECOMMENDER ====================

class PaperRecommender:
    """
    Algorithm J4: Paper Similarity & Recommendation.

    Uses Semantic Scholar recommendations API to find similar papers.
    Enriches with OpenAlex metadata for full details.
    """

    def __init__(
        self,
        semantic_scholar: Optional[SemanticScholarClient] = None,
        openalex: Optional[OpenAlexClient] = None,
    ):
        self.s2 = semantic_scholar or SemanticScholarClient()
        self.oa = openalex or OpenAlexClient()

    def recommend(
        self,
        doi_or_id: str,
        count: int = 20,
        min_year: Optional[int] = None,
    ) -> Dict:
        """
        Find similar papers to a given paper.

        Args:
            doi_or_id: DOI or S2 paper ID
            count: Number of recommendations
            min_year: Only show papers from this year onward

        Returns:
            Dict with seed paper and recommendations
        """
        print(f"\n  [🔍] Finding similar papers to: {doi_or_id}")

        # Resolve paper ID for S2
        s2_id = doi_or_id
        if doi_or_id.startswith('10.'):
            s2_id = f"DOI:{doi_or_id}"

        # Get seed paper
        seed = self.s2.get_paper(s2_id)
        if not seed:
            print(f"  [!] Paper not found: {doi_or_id}")
            return {'error': 'not_found'}

        print(f"  [✓] Seed: {seed.title[:60]}...")

        # Get recommendations
        recs = self.s2.get_recommendations(s2_id, count * 2)

        if min_year:
            recs = [p for p in recs if p.year >= min_year]

        recs = recs[:count]
        print(f"  [✓] Found {len(recs)} similar papers")

        # Print results
        for i, p in enumerate(recs[:10], 1):
            oa = " [OA]" if p.is_open_access else ""
            print(f"  {i:2d}. [{p.year}] {p.title[:65]}{'...' if len(p.title) > 65 else ''}")
            print(f"      Citations: {p.citation_count}{oa}")

        return {
            'seed': seed.to_dict(),
            'recommendations': [p.to_dict() for p in recs],
            'count': len(recs),
        }
