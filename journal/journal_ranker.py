"""
Algorithm J9: Journal Ranking & Impact Predictor

Advanced journal impact analysis beyond simple Impact Factor.

Metrics computed:
  - Impact Factor (mean, 2-year window)
  - Median citations (robust against outliers)
  - h5-index (h-index for last 5 years)
  - Citation Gini coefficient (inequality: 0=equal, 1=one paper dominates)
  - Top-10% share (% of total citations from top 10% papers)
  - Immediacy index (same-year citation rate)
  - Percentiles (p25, p50, p75, p90)

Prediction:
  Linear regression on yearly Impact Factor → 3-year trajectory

Usage:
    from journal.journal_ranker import JournalRankPredictor

    predictor = JournalRankPredictor()
    report = predictor.analyze("Nature")
    predictor.print_report(report)
"""

import math
import time
from collections import Counter
from typing import Dict, List, Optional, Tuple

from .models import Paper, JournalMetrics, JournalRankReport
from .api_client import OpenAlexClient


# ==================== METRICS CALCULATOR ====================

class JournalMetricsCalculator:
    """
    Compute advanced citation metrics for a journal.

    Goes beyond Impact Factor to analyze the full citation distribution.
    """

    @staticmethod
    def compute_metrics(
        papers: List[Paper],
        journal_name: str = "",
        year: int = 0,
    ) -> JournalMetrics:
        """
        Compute all metrics from a list of papers.

        Args:
            papers: Papers from the journal
            journal_name: Journal name
            year: Reference year

        Returns:
            JournalMetrics with all computed metrics
        """
        if not papers:
            return JournalMetrics(journal_name=journal_name, year=year)

        citations = sorted([p.citation_count for p in papers])
        n = len(citations)
        total_cites = sum(citations)

        # Impact Factor (mean)
        impact_factor = total_cites / n if n > 0 else 0.0

        # Median
        median = JournalMetricsCalculator._median(citations)

        # Percentiles
        p25 = JournalMetricsCalculator._percentile(citations, 25)
        p50 = median
        p75 = JournalMetricsCalculator._percentile(citations, 75)
        p90 = JournalMetricsCalculator._percentile(citations, 90)

        # h5-index
        h5 = JournalMetricsCalculator._h_index(citations)

        # Gini coefficient
        gini = JournalMetricsCalculator._gini_coefficient(citations)

        # Top-10% share
        top10_share = JournalMetricsCalculator._top_percent_share(citations, 10)

        # Immediacy index (papers cited in their publication year)
        immediacy = JournalMetricsCalculator._immediacy_index(papers, year)

        return JournalMetrics(
            journal_name=journal_name,
            year=year,
            impact_factor=round(impact_factor, 3),
            median_citations=round(median, 1),
            h5_index=h5,
            total_papers=n,
            total_citations=total_cites,
            gini_coefficient=round(gini, 3),
            top10_share=round(top10_share, 3),
            immediacy_index=round(immediacy, 3),
            p25=round(p25, 1),
            p50=round(p50, 1),
            p75=round(p75, 1),
            p90=round(p90, 1),
        )

    @staticmethod
    def _median(values: List[int]) -> float:
        """Compute median of sorted list"""
        n = len(values)
        if n == 0:
            return 0.0
        mid = n // 2
        if n % 2 == 0:
            return (values[mid - 1] + values[mid]) / 2.0
        return float(values[mid])

    @staticmethod
    def _percentile(values: List[int], pct: int) -> float:
        """Compute percentile of sorted list"""
        n = len(values)
        if n == 0:
            return 0.0
        k = (pct / 100) * (n - 1)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return float(values[int(k)])
        return values[int(f)] * (c - k) + values[int(c)] * (k - f)

    @staticmethod
    def _h_index(sorted_citations: List[int]) -> int:
        """
        Compute h-index from sorted (ascending) citation counts.

        h-index = largest h such that h papers have >= h citations
        """
        n = len(sorted_citations)
        h = 0
        for i in range(n):
            # From index i to end, there are (n - i) papers
            # all with >= sorted_citations[i] citations
            remaining = n - i
            if sorted_citations[i] >= remaining:
                return remaining
            h = max(h, min(sorted_citations[i], remaining))
        return h

    @staticmethod
    def _gini_coefficient(sorted_citations: List[int]) -> float:
        """
        Compute Gini coefficient of citation distribution.

        0 = perfectly equal (all papers have same citations)
        1 = perfectly unequal (one paper has all citations)
        """
        n = len(sorted_citations)
        if n == 0 or sum(sorted_citations) == 0:
            return 0.0

        total = sum(sorted_citations)
        cum_sum = 0
        area_under = 0

        for i, c in enumerate(sorted_citations):
            cum_sum += c
            area_under += cum_sum

        # Normalize
        area_perfect = total * n / 2
        if area_perfect == 0:
            return 0.0

        gini = 1.0 - (area_under / (total * n))
        return max(0.0, min(1.0, gini + (1 / (2 * n))))

    @staticmethod
    def _top_percent_share(sorted_citations: List[int], pct: int) -> float:
        """
        What % of total citations come from the top pct% of papers?
        """
        n = len(sorted_citations)
        if n == 0:
            return 0.0

        total = sum(sorted_citations)
        if total == 0:
            return 0.0

        top_n = max(1, int(n * pct / 100))
        top_cites = sum(sorted_citations[-top_n:])

        return top_cites / total

    @staticmethod
    def _immediacy_index(papers: List[Paper], ref_year: int) -> float:
        """
        Compute immediacy index: avg citations for papers published in ref_year,
        counted only within that same year.
        """
        if not ref_year:
            return 0.0

        same_year = [p for p in papers if p.year == ref_year]
        if not same_year:
            return 0.0

        # Approximation: use citation_count (real immediacy needs per-year data)
        # We use papers with very low age as proxy
        total = sum(p.citation_count for p in same_year)
        return total / len(same_year)


# ==================== LINEAR REGRESSION ====================

def _linear_regression(xs: List[float], ys: List[float]) -> Tuple[float, float]:
    """Simple linear regression: y = slope * x + intercept"""
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


# ==================== JOURNAL RANK PREDICTOR ====================

class JournalRankPredictor:
    """
    Analyze and predict journal impact trajectory.

    Combines advanced metrics with temporal trend analysis
    to rank journals and predict future impact.
    """

    def __init__(self, openalex: Optional[OpenAlexClient] = None):
        self.oa = openalex or OpenAlexClient()
        self.calc = JournalMetricsCalculator()

    def analyze(
        self,
        journal_name: str,
        start_year: int = 2020,
        end_year: int = 2025,
    ) -> JournalRankReport:
        """
        Analyze a journal's impact and predict trajectory.

        Args:
            journal_name: Journal name or ISSN
            start_year: Analysis start year
            end_year: Analysis end year

        Returns:
            JournalRankReport with metrics + prediction
        """
        print(f"\n  [🏆] Journal Impact Analysis: \"{journal_name}\"")
        print(f"  [·] Period: {start_year}–{end_year}")

        yearly_metrics = []

        for year in range(start_year, end_year + 1):
            print(f"  [·] Fetching {year}...")

            papers = self.oa.search(
                f'"{journal_name}"',
                per_page=200,
                year_range=f"{year}-{year}",
                sort="cited_by_count:desc",
            )

            if papers:
                metrics = self.calc.compute_metrics(papers, journal_name, year)
                yearly_metrics.append(metrics)
            else:
                yearly_metrics.append(JournalMetrics(
                    journal_name=journal_name, year=year
                ))

            time.sleep(0.15)

        # Current = last year with data
        current = yearly_metrics[-1] if yearly_metrics else None

        # Predict trajectory
        impact_series = [
            (m.year, m.impact_factor) for m in yearly_metrics
            if m.impact_factor > 0
        ]

        predicted_impact = 0.0
        trajectory = "stable"

        if len(impact_series) >= 3:
            xs = [float(y) for y, _ in impact_series]
            ys = [v for _, v in impact_series]
            slope, intercept = _linear_regression(xs, ys)

            predicted_impact = slope * (end_year + 1) + intercept
            predicted_impact = max(0, predicted_impact)

            # Determine trajectory
            rel_slope = slope / max(ys[-1], 0.1)
            if rel_slope > 0.05:
                trajectory = "rising"
            elif rel_slope < -0.05:
                trajectory = "declining"
            else:
                trajectory = "stable"

        # Compute composite rank score (0.0–1.0)
        rank_score = self._compute_rank_score(current) if current else 0.0

        # Recommendation
        recommendation = self._generate_recommendation(
            current, trajectory, rank_score
        )

        report = JournalRankReport(
            journal_name=journal_name,
            year_range=f"{start_year}-{end_year}",
            current_metrics=current,
            yearly_metrics=yearly_metrics,
            predicted_impact=round(predicted_impact, 3),
            trajectory=trajectory,
            rank_score=round(rank_score, 3),
            recommendation=recommendation,
        )

        self.print_report(report)
        return report

    def compare(
        self,
        journal_names: List[str],
        year: int = 2025,
    ) -> JournalRankReport:
        """
        Compare multiple journals side by side.

        Args:
            journal_names: List of journal names
            year: Reference year

        Returns:
            JournalRankReport with comparison
        """
        print(f"\n  [⚖️] Journal Comparison ({year})")
        print(f"  [·] Journals: {', '.join(journal_names)}")

        compared = []
        for name in journal_names:
            print(f"  [·] Fetching: {name}...")
            papers = self.oa.search(
                f'"{name}"',
                per_page=200,
                year_range=f"{year}-{year}",
                sort="cited_by_count:desc",
            )
            metrics = self.calc.compute_metrics(papers, name, year)
            compared.append(metrics)
            time.sleep(0.15)

        # Sort by impact factor
        compared.sort(key=lambda m: m.impact_factor, reverse=True)

        best = compared[0] if compared else None
        recommendation = (
            f"Top journal by impact: {best.journal_name} "
            f"(IF={best.impact_factor:.2f})"
            if best else ""
        )

        report = JournalRankReport(
            journal_name="Comparison",
            year_range=str(year),
            current_metrics=best,
            compared_journals=compared,
            recommendation=recommendation,
        )

        self._print_comparison(report)
        return report

    @staticmethod
    def _compute_rank_score(metrics: JournalMetrics) -> float:
        """
        Compute composite rank score from metrics.

        Weights:
          - Impact Factor: 0.25 (normalized to ~50 max)
          - Median:        0.25 (more robust)
          - h5-index:      0.20 (consistency)
          - Low Gini:      0.15 (equality → healthy distribution)
          - Total Papers:  0.15 (productivity)
        """
        norm_if = min(metrics.impact_factor / 50, 1.0)
        norm_med = min(metrics.median_citations / 30, 1.0)
        norm_h5 = min(metrics.h5_index / 200, 1.0)
        norm_gini = 1.0 - metrics.gini_coefficient  # lower Gini = better
        norm_papers = min(metrics.total_papers / 5000, 1.0)

        score = (
            norm_if * 0.25 +
            norm_med * 0.25 +
            norm_h5 * 0.20 +
            norm_gini * 0.15 +
            norm_papers * 0.15
        )
        return min(max(score, 0.0), 1.0)

    @staticmethod
    def _generate_recommendation(
        metrics: Optional[JournalMetrics],
        trajectory: str,
        rank_score: float,
    ) -> str:
        """Generate recommendation text"""
        if not metrics:
            return "Insufficient data for recommendation"

        parts = []

        if rank_score >= 0.7:
            parts.append("🏆 Top-tier journal")
        elif rank_score >= 0.4:
            parts.append("✅ Good journal")
        else:
            parts.append("📝 Moderate journal")

        if trajectory == "rising":
            parts.append("with rising impact — good time to submit")
        elif trajectory == "declining":
            parts.append("with declining trend — consider alternatives")
        else:
            parts.append("with stable trajectory")

        if metrics.gini_coefficient > 0.7:
            parts.append("⚠️ High citation inequality (few papers dominate)")
        elif metrics.gini_coefficient < 0.4:
            parts.append("✅ Healthy citation distribution")

        return " | ".join(parts)

    @staticmethod
    def print_report(report: JournalRankReport):
        """Print formatted journal ranking report"""
        print(f"\n{'='*65}")
        print(f"  🏆 Journal Impact Analysis")
        print(f"{'='*65}")
        print(f"  Journal:  {report.journal_name}")
        print(f"  Period:   {report.year_range}")

        m = report.current_metrics
        if m:
            print(f"\n  📊 Current Metrics ({m.year})")
            print(f"  {'─'*55}")
            print(f"  Impact Factor:     {m.impact_factor:8.3f}")
            print(f"  Median Citations:  {m.median_citations:8.1f}")
            print(f"  h5-index:          {m.h5_index:8d}")
            print(f"  Papers:            {m.total_papers:8d}")
            print(f"  Total Citations:   {m.total_citations:8,d}")

            print(f"\n  📈 Distribution")
            print(f"  {'─'*55}")
            print(f"  Gini Coefficient:  {m.gini_coefficient:8.3f}  ", end="")
            if m.gini_coefficient > 0.7:
                print("(⚠️ high inequality)")
            elif m.gini_coefficient > 0.5:
                print("(moderate inequality)")
            else:
                print("(✅ healthy)")

            print(f"  Top-10% Share:     {m.top10_share*100:7.1f}%")
            print(f"  Immediacy Index:   {m.immediacy_index:8.3f}")
            print(f"  Percentiles: P25={m.p25:.0f}  P50={m.p50:.0f}"
                  f"  P75={m.p75:.0f}  P90={m.p90:.0f}")

        # Trajectory
        traj_icons = {'rising': '📈', 'stable': '➡️', 'declining': '📉'}
        icon = traj_icons.get(report.trajectory, '·')

        print(f"\n  🔮 Prediction")
        print(f"  {'─'*55}")
        print(f"  Trajectory:        {icon} {report.trajectory}")
        print(f"  Predicted IF:      {report.predicted_impact:.3f}")

        # Rank score bar
        bar_len = int(report.rank_score * 30)
        bar = '█' * bar_len + '░' * (30 - bar_len)
        pct = report.rank_score * 100
        print(f"  Rank Score:        {pct:.1f}%")
        print(f"  [{bar}]")

        # Yearly trend
        if report.yearly_metrics:
            print(f"\n  📅 Yearly Impact Factor Trend")
            print(f"  {'─'*55}")
            max_if = max(m.impact_factor for m in report.yearly_metrics) or 1
            for m in report.yearly_metrics:
                bar_len = int(m.impact_factor / max_if * 25) if max_if else 0
                bar = '▓' * bar_len
                print(f"    {m.year} │{bar} {m.impact_factor:.2f}"
                      f"  (n={m.total_papers}, h={m.h5_index})")

        # Recommendation
        if report.recommendation:
            print(f"\n  💡 {report.recommendation}")

        print(f"\n{'='*65}")

    @staticmethod
    def _print_comparison(report: JournalRankReport):
        """Print journal comparison table"""
        print(f"\n{'='*80}")
        print(f"  ⚖️ Journal Comparison ({report.year_range})")
        print(f"{'='*80}")

        journals = report.compared_journals
        if not journals:
            print("  No data available")
            return

        print(f"\n  {'#':<4} {'Journal':<25} {'IF':>7} {'Med':>5} {'h5':>4}"
              f" {'Gini':>5} {'T10%':>5} {'Papers':>7}")
        print(f"  {'─'*75}")

        for i, m in enumerate(journals, 1):
            print(f"  {i:<4} {m.journal_name[:24]:<25}"
                  f" {m.impact_factor:7.2f} {m.median_citations:5.1f}"
                  f" {m.h5_index:4d} {m.gini_coefficient:5.3f}"
                  f" {m.top10_share*100:4.0f}% {m.total_papers:7d}")

        if report.recommendation:
            print(f"\n  💡 {report.recommendation}")

        print(f"\n{'='*80}")
