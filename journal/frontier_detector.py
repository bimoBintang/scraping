"""
Algorithm J8: Research Frontier Detection

Identifies emerging research frontiers before they become mainstream.

Detection signals:
  1. Publication growth rate   (weight: 0.35) — YoY volume increase
  2. Citation velocity         (weight: 0.30) — how fast recent papers get cited
  3. Keyword co-occurrence     (weight: 0.20) — new keyword cluster emergence
  4. Author diversity          (weight: 0.15) — institutional spread into the field

Prediction:
  Linear regression on publication counts → 2-3 year trajectory forecast

Usage:
    from journal.frontier_detector import ResearchFrontierDetector

    detector = ResearchFrontierDetector()
    report = detector.detect("artificial intelligence", n_topics=10)
    detector.print_report(report)
"""

import math
import time
from collections import Counter, defaultdict
from itertools import combinations
from typing import Dict, List, Optional, Set, Tuple

from .models import Paper, FrontierTopic, FrontierReport
from .api_client import OpenAlexClient


# ==================== SIGNAL EXTRACTOR ====================

class FrontierSignalExtractor:
    """
    Extract frontier detection signals from publication data.

    Each signal returns a normalized score (0.0–1.0).
    """

    @staticmethod
    def publication_growth(yearly_counts: Dict[int, int], recent_years: int = 3) -> float:
        """
        Calculate publication growth rate.

        Compares average of last `recent_years` to the average of preceding years.
        Returns growth ratio: >1.0 = growing, <1.0 = declining.
        """
        if not yearly_counts or len(yearly_counts) < 2:
            return 0.0

        years = sorted(yearly_counts.keys())
        if len(years) < 3:
            # Not enough data for trend
            vals = [yearly_counts[y] for y in years]
            if vals[0] == 0:
                return 1.0 if vals[-1] > 0 else 0.0
            return (vals[-1] - vals[0]) / max(vals[0], 1)

        recent = years[-recent_years:]
        older = years[:-recent_years]

        if not older:
            return 0.0

        avg_recent = sum(yearly_counts.get(y, 0) for y in recent) / len(recent)
        avg_older = sum(yearly_counts.get(y, 0) for y in older) / len(older)

        if avg_older == 0:
            return 1.0 if avg_recent > 0 else 0.0

        return (avg_recent - avg_older) / avg_older

    @staticmethod
    def citation_velocity(papers: List[Paper], current_year: int = 2026) -> float:
        """
        Calculate citation velocity — how quickly recent papers accumulate citations.

        Focuses on papers from last 3 years.
        Returns avg citations per year of existence.
        """
        recent = [p for p in papers if p.year and p.year >= current_year - 3]

        if not recent:
            return 0.0

        velocities = []
        for p in recent:
            age = max(current_year - p.year, 1)
            vel = p.citation_count / age
            velocities.append(vel)

        return sum(velocities) / len(velocities) if velocities else 0.0

    @staticmethod
    def keyword_cooccurrence(papers: List[Paper], top_n: int = 20) -> Tuple[List[List[str]], float]:
        """
        Build keyword co-occurrence graph and detect emerging clusters.

        Returns:
            (keyword_clusters, novelty_score)
        """
        # Collect keyword pairs from each paper
        edge_counts: Dict[Tuple[str, str], int] = Counter()
        keyword_freq: Counter = Counter()

        for paper in papers:
            kws = list(set(paper.keywords + paper.topics))[:15]
            kws = [k.lower().strip() for k in kws if k]

            for kw in kws:
                keyword_freq[kw] += 1

            for a, b in combinations(sorted(kws), 2):
                edge_counts[(a, b)] += 1

        if not edge_counts:
            return [], 0.0

        # Build adjacency for top keywords
        top_kws = {kw for kw, _ in keyword_freq.most_common(top_n * 3)}
        adj: Dict[str, Set[str]] = defaultdict(set)

        for (a, b), count in edge_counts.items():
            if a in top_kws and b in top_kws and count >= 2:
                adj[a].add(b)
                adj[b].add(a)

        # Simple community detection (connected components)
        visited = set()
        clusters = []

        for node in adj:
            if node in visited:
                continue
            # BFS
            cluster = []
            queue = [node]
            while queue:
                v = queue.pop(0)
                if v in visited:
                    continue
                visited.add(v)
                cluster.append(v)
                for neighbor in adj.get(v, set()):
                    if neighbor not in visited:
                        queue.append(neighbor)
            if len(cluster) >= 2:
                clusters.append(sorted(cluster)[:10])

        # Novelty score: ratio of recent-only keywords
        recent_papers = [p for p in papers if p.year and p.year >= 2024]
        recent_kws = set()
        for p in recent_papers:
            for kw in (p.keywords + p.topics):
                recent_kws.add(kw.lower().strip())

        older_papers = [p for p in papers if p.year and p.year < 2024]
        older_kws = set()
        for p in older_papers:
            for kw in (p.keywords + p.topics):
                older_kws.add(kw.lower().strip())

        new_kws = recent_kws - older_kws
        novelty = len(new_kws) / max(len(recent_kws), 1) if recent_kws else 0.0

        return clusters[:10], novelty

    @staticmethod
    def author_diversity(papers: List[Paper]) -> float:
        """
        Calculate author diversity — how many unique institutions contribute.

        Higher diversity = more mainstream interest → frontier if combined
        with high growth.
        """
        institutions = set()
        for paper in papers:
            for author in paper.authors:
                if author.affiliation:
                    # Normalize institution name
                    inst = author.affiliation.lower().strip()
                    # Take first significant word
                    inst = inst.split(',')[0].strip()
                    institutions.add(inst)

        if not papers:
            return 0.0

        # Score: unique institutions per paper
        diversity = len(institutions) / max(len(papers), 1)
        return min(diversity, 1.0)


# ==================== LINEAR REGRESSION ====================

def _linear_regression(xs: List[float], ys: List[float]) -> Tuple[float, float]:
    """
    Simple linear regression: y = slope * x + intercept

    Returns (slope, intercept)
    """
    n = len(xs)
    if n < 2:
        return (0.0, ys[0] if ys else 0.0)

    sum_x = sum(xs)
    sum_y = sum(ys)
    sum_xy = sum(x * y for x, y in zip(xs, ys))
    sum_x2 = sum(x * x for x in xs)

    denom = n * sum_x2 - sum_x * sum_x
    if denom == 0:
        return (0.0, sum_y / n)

    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n

    return (slope, intercept)


# ==================== FRONTIER DETECTOR ====================

class ResearchFrontierDetector:
    """
    Detect emerging research frontiers from topic analysis.

    Combines 4 signals with weighted scoring to identify
    topics that are rising before becoming mainstream.
    """

    WEIGHTS = {
        'growth': 0.35,
        'velocity': 0.30,
        'novelty': 0.20,
        'diversity': 0.15,
    }

    def __init__(self, openalex: Optional[OpenAlexClient] = None):
        self.oa = openalex or OpenAlexClient()
        self.extractor = FrontierSignalExtractor()

    def detect(
        self,
        query: str,
        n_topics: int = 10,
        start_year: int = 2018,
        end_year: int = 2026,
    ) -> FrontierReport:
        """
        Detect emerging research frontiers related to a query.

        Args:
            query: Broad research area (e.g. "machine learning")
            n_topics: Number of sub-topics to analyze
            start_year: Analysis start year
            end_year: Analysis end year

        Returns:
            FrontierReport with ranked frontier topics
        """
        print(f"\n  [🔭] Research Frontier Detection: \"{query}\"")
        print(f"  [·] Year range: {start_year}–{end_year}")

        # Step 1: Get related topics/concepts from OpenAlex
        print(f"  [·] Discovering sub-topics...")
        subtopics = self._discover_subtopics(query, n_topics)

        if not subtopics:
            print("  [!] No sub-topics found")
            return FrontierReport(query=query, year_range=f"{start_year}-{end_year}")

        print(f"  [✓] Found {len(subtopics)} sub-topics to analyze")

        # Step 2: Analyze each sub-topic
        frontiers = []
        for i, topic in enumerate(subtopics, 1):
            print(f"  [·] Analyzing ({i}/{len(subtopics)}): {topic}...")

            ft = self._analyze_topic(topic, start_year, end_year)
            if ft:
                frontiers.append(ft)

            time.sleep(0.15)  # polite rate limit

        # Step 3: Rank by frontier score
        frontiers.sort(key=lambda f: f.frontier_score, reverse=True)

        # Collect keyword clusters
        all_clusters = []
        for ft in frontiers:
            if ft.emerging_keywords:
                all_clusters.append(ft.emerging_keywords[:5])

        report = FrontierReport(
            query=query,
            year_range=f"{start_year}-{end_year}",
            total_topics_analyzed=len(frontiers),
            frontiers=frontiers,
            keyword_clusters=all_clusters[:10],
            top_emerging=[ft.topic for ft in frontiers[:5] if ft.trajectory in ('emerging', 'surging')],
        )

        self.print_report(report)
        return report

    def _discover_subtopics(self, query: str, n_topics: int) -> List[str]:
        """
        Discover sub-topics related to the query using OpenAlex concepts/topics.
        """
        # Search for papers and extract their topics/keywords
        papers = self.oa.search(query, per_page=100, sort="cited_by_count:desc")

        topic_freq: Counter = Counter()
        for paper in papers:
            for topic in paper.topics:
                topic_lower = topic.lower().strip()
                # Skip overly generic topics
                if topic_lower and topic_lower != query.lower() and len(topic_lower) > 3:
                    topic_freq[topic_lower] += 1
            for kw in paper.keywords:
                kw_lower = kw.lower().strip()
                if kw_lower and kw_lower != query.lower() and len(kw_lower) > 3:
                    topic_freq[kw_lower] += 1

        # Return top topics that appear at least twice
        return [
            topic for topic, count in topic_freq.most_common(n_topics * 2)
            if count >= 2
        ][:n_topics]

    def _analyze_topic(
        self, topic: str, start_year: int, end_year: int
    ) -> Optional[FrontierTopic]:
        """Analyze a single topic for frontier signals"""
        try:
            # 1. Get yearly publication counts
            year_data = self.oa.count_by_year(topic, start_year, end_year)
            yearly_counts = {d['year']: d['count'] for d in year_data if d.get('year')}

            if not yearly_counts or sum(yearly_counts.values()) < 5:
                return None

            # 2. Get recent papers for citation velocity + keyword analysis
            recent_papers = self.oa.search(
                topic,
                per_page=50,
                year_range=f"{end_year-2}-{end_year}",
                sort="cited_by_count:desc",
            )

            # 3. Compute signals
            growth = self.extractor.publication_growth(yearly_counts)
            velocity = self.extractor.citation_velocity(recent_papers, end_year)
            clusters, novelty = self.extractor.keyword_cooccurrence(recent_papers)
            diversity = self.extractor.author_diversity(recent_papers)

            # 4. Normalize signals to 0.0–1.0
            norm_growth = min(max(growth, 0), 5.0) / 5.0      # cap at 500% growth
            norm_velocity = min(velocity / 50, 1.0)            # cap at 50 cites/year
            norm_novelty = novelty
            norm_diversity = diversity

            # 5. Compute frontier score
            frontier_score = (
                norm_growth * self.WEIGHTS['growth'] +
                norm_velocity * self.WEIGHTS['velocity'] +
                norm_novelty * self.WEIGHTS['novelty'] +
                norm_diversity * self.WEIGHTS['diversity']
            )

            # 6. Predict trajectory
            years_list = sorted(yearly_counts.keys())
            counts_list = [yearly_counts[y] for y in years_list]
            slope, intercept = _linear_regression(
                [float(y) for y in years_list],
                [float(c) for c in counts_list],
            )

            predicted = slope * (end_year + 1) + intercept
            predicted = max(predicted, 0)

            # Determine trajectory
            if growth > 0.5 and frontier_score > 0.4:
                trajectory = "surging" if growth > 1.5 else "emerging"
            elif growth > 0.1:
                trajectory = "growing"
            elif growth < -0.1:
                trajectory = "declining"
            else:
                trajectory = "stable"

            # Emerging keywords
            emerging_kws = []
            for cluster in clusters:
                emerging_kws.extend(cluster[:3])

            sample_titles = [p.title for p in recent_papers[:3]]

            return FrontierTopic(
                topic=topic,
                frontier_score=round(frontier_score, 3),
                growth_rate=round(growth * 100, 1),
                citation_velocity=round(velocity, 1),
                author_diversity=round(diversity, 3),
                keyword_novelty=round(novelty, 3),
                yearly_counts=yearly_counts,
                predicted_growth=round(predicted),
                trajectory=trajectory,
                emerging_keywords=emerging_kws[:10],
                sample_papers=sample_titles,
            )

        except Exception as e:
            return None

    @staticmethod
    def print_report(report: FrontierReport):
        """Print formatted frontier detection report"""
        print(f"\n{'='*70}")
        print(f"  🔭 Research Frontier Detection Report")
        print(f"{'='*70}")
        print(f"  Query: \"{report.query}\"")
        print(f"  Period: {report.year_range}")
        print(f"  Topics analyzed: {report.total_topics_analyzed}")

        if report.top_emerging:
            print(f"\n  🚀 Emerging Frontiers:")
            for i, topic in enumerate(report.top_emerging, 1):
                print(f"     {i}. {topic}")

        if report.frontiers:
            # Trajectory icons
            icons = {
                'surging': '🔥', 'emerging': '🚀',
                'growing': '📈', 'stable': '➡️', 'declining': '📉',
            }

            print(f"\n  📊 Frontier Scores (Top {min(15, len(report.frontiers))})")
            print(f"  {'─'*65}")
            print(f"  {'Rank':<5} {'Topic':<30} {'Score':>6} {'Growth':>8} {'Vel':>6} {'Trend':<10}")
            print(f"  {'─'*65}")

            for i, ft in enumerate(report.frontiers[:15], 1):
                icon = icons.get(ft.trajectory, '·')
                bar_len = int(ft.frontier_score * 20)
                bar = '█' * bar_len + '░' * (20 - bar_len)

                print(f"  {i:3d}.  {ft.topic[:28]:<30} {ft.frontier_score:5.3f}"
                      f"  {ft.growth_rate:+6.1f}% {ft.citation_velocity:5.1f}"
                      f"  {icon} {ft.trajectory}")

            # Detail for top 3
            print(f"\n  🔍 Detailed Analysis (Top 3)")
            print(f"  {'─'*65}")

            for i, ft in enumerate(report.frontiers[:3], 1):
                icon = icons.get(ft.trajectory, '·')
                print(f"\n  {i}. {icon} {ft.topic}")
                print(f"     Frontier Score:    {ft.frontier_score:.3f}")
                print(f"     Growth Rate:       {ft.growth_rate:+.1f}%")
                print(f"     Citation Velocity: {ft.citation_velocity:.1f} cites/year")
                print(f"     Author Diversity:  {ft.author_diversity:.3f}")
                print(f"     Keyword Novelty:   {ft.keyword_novelty:.3f}")
                print(f"     Trajectory:        {ft.trajectory}")
                print(f"     Predicted (next):  ~{ft.predicted_growth:.0f} papers")

                # Mini ASCII chart
                if ft.yearly_counts:
                    years = sorted(ft.yearly_counts.keys())
                    max_count = max(ft.yearly_counts.values()) or 1
                    print(f"     Publication Trend:")
                    for y in years[-6:]:
                        cnt = ft.yearly_counts.get(y, 0)
                        bar_len = int(cnt / max_count * 25)
                        bar = '▓' * bar_len
                        print(f"       {y} │{bar} {cnt:,}")

                if ft.emerging_keywords:
                    print(f"     Keywords: {', '.join(ft.emerging_keywords[:5])}")

        # Keyword clusters
        if report.keyword_clusters:
            print(f"\n  🏷️ Emerging Keyword Clusters")
            print(f"  {'─'*65}")
            for i, cluster in enumerate(report.keyword_clusters[:5], 1):
                print(f"  {i}. {' • '.join(cluster[:5])}")

        print(f"\n{'='*70}")
