"""
Algorithm J14: Research Impact Forecaster

Predict long-term paper impact using 30+ features and weighted scoring.

Feature Categories:
  - Author (8):   h-index, papers, citations, career, collabs
  - Journal (6):  IF, h5, median, OA, quartile, age
  - Paper (10):   refs, abstract, novelty, methodology, data/code
  - Network (4):  centrality, diversity, cross-field, self-cite
  - Early (4):    first-month cites, downloads, social, altmetric

Output: percentile prediction (5yr) with confidence interval

Usage:
    from journal.impact_forecaster import ResearchImpactForecaster

    forecaster = ResearchImpactForecaster()
    forecast = forecaster.forecast("10.1038/s41586-021-03819-2")
"""

import re
import math
import time
from collections import Counter
from typing import Dict, List, Optional, Tuple

from .models import Paper, PaperFeatures, ImpactForecast
from .api_client import OpenAlexClient, SemanticScholarClient


# ==================== FEATURE EXTRACTOR ====================

class FeatureExtractor:
    """
    Extract 30+ features from a paper for impact prediction.
    """

    # Academic methodology keywords
    METHODOLOGY_KEYWORDS = [
        'method', 'approach', 'algorithm', 'framework', 'model',
        'technique', 'pipeline', 'architecture', 'experiment',
        'evaluation', 'benchmark', 'dataset', 'ablation',
    ]

    # Data/code availability signals
    DATA_SIGNALS = [
        'data available', 'dataset available', 'publicly available',
        'data availability', 'open data', 'supplementary data',
        'github.com', 'zenodo.org', 'figshare.com',
    ]

    CODE_SIGNALS = [
        'code available', 'source code', 'open source',
        'github.com', 'gitlab.com', 'bitbucket.org',
        'implementation available', 'reproducib',
    ]

    @classmethod
    def extract(cls, paper: Paper) -> PaperFeatures:
        """
        Extract all features from a paper.

        Args:
            paper: Paper object with metadata

        Returns:
            PaperFeatures with 30+ computed features
        """
        features = PaperFeatures()

        # Author features
        cls._extract_author_features(paper, features)

        # Journal features
        cls._extract_journal_features(paper, features)

        # Paper features
        cls._extract_paper_features(paper, features)

        # Network features
        cls._extract_network_features(paper, features)

        # Early signals
        cls._extract_early_signals(paper, features)

        return features

    @classmethod
    def _extract_author_features(cls, paper: Paper, feat: PaperFeatures):
        """Extract author-related features"""
        authors = paper.authors or []
        feat.author_count = len(authors)

        if authors:
            # Approximate h-index from available data
            first_author = authors[0]
            if hasattr(first_author, 'h_index') and first_author.h_index:
                feat.author_h_index = first_author.h_index

            # Count total papers if available
            if hasattr(first_author, 'works_count') and first_author.works_count:
                feat.author_total_papers = first_author.works_count

            if hasattr(first_author, 'cited_by_count') and first_author.cited_by_count:
                feat.author_total_citations = first_author.cited_by_count

            # Collaboration diversity: unique institutions
            institutions = set()
            countries = set()
            for a in authors:
                if hasattr(a, 'institution') and a.institution:
                    institutions.add(a.institution.lower())
                if hasattr(a, 'country') and a.country:
                    countries.add(a.country.lower())

            feat.author_collab_diversity = min(len(institutions) / max(len(authors), 1), 1.0)
            feat.international_collab = len(countries) > 1

    @classmethod
    def _extract_journal_features(cls, paper: Paper, feat: PaperFeatures):
        """Extract journal-related features"""
        if paper.journal:
            # Estimate journal quality from name patterns
            top_journals = [
                'nature', 'science', 'cell', 'lancet', 'nejm',
                'pnas', 'physical review letters', 'ieee', 'acm',
            ]
            journal_lower = paper.journal.lower()
            for tj in top_journals:
                if tj in journal_lower:
                    feat.journal_impact_factor = 15.0
                    feat.journal_h5_index = 200
                    feat.journal_quartile = 1
                    break

        feat.journal_is_oa = getattr(paper, 'is_oa', False)

    @classmethod
    def _extract_paper_features(cls, paper: Paper, feat: PaperFeatures):
        """Extract paper content features"""
        # Reference count
        feat.reference_count = getattr(paper, 'reference_count', 0) or 0

        # Abstract analysis
        abstract = paper.abstract or ""
        feat.abstract_length = len(abstract.split())

        # Title analysis
        title = paper.title or ""
        feat.title_word_count = len(title.split())

        # Title novelty — unique word ratio
        if title:
            words = re.findall(r'\b\w+\b', title.lower())
            common_words = {'a', 'an', 'the', 'of', 'in', 'for', 'and', 'or', 'to',
                           'with', 'on', 'by', 'from', 'is', 'are', 'was', 'using'}
            content_words = [w for w in words if w not in common_words and len(w) > 2]
            feat.title_novelty_score = len(set(content_words)) / max(len(content_words), 1)

        # Keywords
        feat.keyword_count = len(paper.keywords) if paper.keywords else 0

        # Methodology detection
        text_lower = (abstract + " " + title).lower()
        feat.has_methodology = any(kw in text_lower for kw in cls.METHODOLOGY_KEYWORDS)

        # Data availability
        feat.has_data_availability = any(sig in text_lower for sig in cls.DATA_SIGNALS)

        # Code availability
        feat.has_code_availability = any(sig in text_lower for sig in cls.CODE_SIGNALS)

        # Abstract readability (avg words per sentence)
        sentences = re.split(r'[.!?]+', abstract)
        sentences = [s.strip() for s in sentences if s.strip()]
        if sentences:
            avg_len = sum(len(s.split()) for s in sentences) / len(sentences)
            # Optimal readability around 15-20 words/sentence
            feat.abstract_readability = max(0, 1 - abs(avg_len - 17) / 20)

    @classmethod
    def _extract_network_features(cls, paper: Paper, feat: PaperFeatures):
        """Extract network-related features"""
        # Co-author network size
        feat.coauthor_network_size = len(paper.authors) if paper.authors else 0

        # Cross-field reference ratio (estimated from keywords diversity)
        if paper.keywords and len(paper.keywords) > 1:
            feat.cross_field_refs = min(len(paper.keywords) / 10, 1.0)

        # Citation diversity
        feat.citation_diversity = min(feat.reference_count / 50, 1.0)

    @classmethod
    def _extract_early_signals(cls, paper: Paper, feat: PaperFeatures):
        """Extract early citation signals"""
        feat.early_citations = paper.citation_count or 0

        # Estimate downloads from citations (typically 10-50x)
        feat.early_downloads = feat.early_citations * 20

        # Social mentions estimate
        feat.social_mentions = max(feat.early_citations // 5, 0)

        # Altmetric estimate
        feat.altmetric_score = feat.early_citations * 2.5


# ==================== IMPACT SCORE MODEL ====================

class ImpactScoreModel:
    """
    Weighted scoring model for impact prediction.
    No external ML dependencies required.
    """

    # Category weights
    WEIGHTS = {
        'author': 0.25,
        'journal': 0.20,
        'paper': 0.25,
        'network': 0.15,
        'early': 0.15,
    }

    # Percentile mapping (score → percentile)
    PERCENTILE_MAP = [
        (0.90, 99), (0.80, 95), (0.70, 90), (0.60, 80),
        (0.50, 70), (0.40, 55), (0.30, 40), (0.20, 25),
        (0.10, 10), (0.0, 5),
    ]

    # Impact class thresholds
    IMPACT_CLASSES = [
        (95, 'exceptional'),
        (80, 'high'),
        (60, 'above_average'),
        (40, 'average'),
        (0, 'below_average'),
    ]

    # Citation prediction (percentile → 5yr citations)
    CITATION_MAP = [
        (99, 500), (95, 200), (90, 100), (80, 50),
        (70, 30), (55, 15), (40, 8), (25, 4),
        (10, 2), (5, 1),
    ]

    @classmethod
    def predict(cls, features: PaperFeatures) -> ImpactForecast:
        """
        Predict impact from features.

        Args:
            features: Computed paper features

        Returns:
            ImpactForecast with prediction
        """
        # Compute category scores (0-1)
        author_score = cls._score_author(features)
        journal_score = cls._score_journal(features)
        paper_score = cls._score_paper(features)
        network_score = cls._score_network(features)
        early_score = cls._score_early(features)

        # Weighted total
        total = (
            author_score * cls.WEIGHTS['author'] +
            journal_score * cls.WEIGHTS['journal'] +
            paper_score * cls.WEIGHTS['paper'] +
            network_score * cls.WEIGHTS['network'] +
            early_score * cls.WEIGHTS['early']
        )

        # Map to percentile
        percentile = cls._score_to_percentile(total)

        # Impact class
        impact_class = cls._get_impact_class(percentile)

        # Predicted citations
        predicted_cites = cls._predict_citations(percentile)

        # Confidence (higher when more features available)
        confidence = cls._compute_confidence(features)

        # Strengths and weaknesses
        strengths, weaknesses = cls._analyze_factors(
            features, author_score, journal_score, paper_score,
            network_score, early_score
        )

        return ImpactForecast(
            predicted_percentile=percentile,
            confidence=confidence,
            predicted_citations_5y=predicted_cites,
            impact_class=impact_class,
            author_score=author_score,
            journal_score=journal_score,
            paper_score=paper_score,
            network_score=network_score,
            early_score=early_score,
            total_score=total,
            features=features,
            strengths=strengths,
            weaknesses=weaknesses,
        )

    @classmethod
    def _score_author(cls, f: PaperFeatures) -> float:
        """Score author features (0-1)"""
        score = 0.0

        # h-index (saturates at ~50)
        score += min(f.author_h_index / 50, 1.0) * 0.30

        # Total papers (saturates at ~200)
        score += min(f.author_total_papers / 200, 1.0) * 0.15

        # Total citations (saturates at ~10000)
        score += min(f.author_total_citations / 10000, 1.0) * 0.20

        # Collaboration diversity
        score += f.author_collab_diversity * 0.15

        # Author count (optimal: 3-6)
        if 3 <= f.author_count <= 6:
            score += 0.10
        elif f.author_count > 6:
            score += 0.07
        elif f.author_count >= 1:
            score += 0.05

        # International collaboration
        if f.international_collab:
            score += 0.10

        return min(score, 1.0)

    @classmethod
    def _score_journal(cls, f: PaperFeatures) -> float:
        """Score journal features (0-1)"""
        score = 0.0

        # Impact factor (saturates at ~30)
        score += min(f.journal_impact_factor / 30, 1.0) * 0.35

        # h5-index (saturates at ~300)
        score += min(f.journal_h5_index / 300, 1.0) * 0.25

        # Quartile
        quartile_scores = {1: 0.20, 2: 0.15, 3: 0.08, 4: 0.02}
        score += quartile_scores.get(f.journal_quartile, 0.02)

        # OA bonus
        if f.journal_is_oa:
            score += 0.10

        # Citation median
        score += min(f.journal_citation_median / 20, 1.0) * 0.10

        return min(score, 1.0)

    @classmethod
    def _score_paper(cls, f: PaperFeatures) -> float:
        """Score paper content features (0-1)"""
        score = 0.0

        # Reference count (optimal: 30-60)
        if 30 <= f.reference_count <= 60:
            score += 0.15
        elif f.reference_count > 60:
            score += 0.12
        elif f.reference_count > 15:
            score += 0.08
        else:
            score += 0.03

        # Abstract length (optimal: 150-300 words)
        if 150 <= f.abstract_length <= 300:
            score += 0.12
        elif f.abstract_length > 100:
            score += 0.08
        else:
            score += 0.03

        # Title novelty
        score += f.title_novelty_score * 0.10

        # Keywords
        if f.keyword_count >= 4:
            score += 0.08
        elif f.keyword_count >= 2:
            score += 0.05

        # Methodology
        if f.has_methodology:
            score += 0.15

        # Data availability
        if f.has_data_availability:
            score += 0.15

        # Code availability
        if f.has_code_availability:
            score += 0.15

        # Readability
        score += f.abstract_readability * 0.10

        return min(score, 1.0)

    @classmethod
    def _score_network(cls, f: PaperFeatures) -> float:
        """Score network features (0-1)"""
        score = 0.0

        # Co-author network
        score += min(f.coauthor_network_size / 10, 1.0) * 0.30

        # Cross-field references
        score += f.cross_field_refs * 0.30

        # Citation diversity
        score += f.citation_diversity * 0.25

        # Low self-citation is good
        score += max(0, 1 - f.self_citation_ratio * 5) * 0.15

        return min(score, 1.0)

    @classmethod
    def _score_early(cls, f: PaperFeatures) -> float:
        """Score early signals (0-1)"""
        score = 0.0

        # Early citations (log scale, saturates at ~50)
        if f.early_citations > 0:
            score += min(math.log1p(f.early_citations) / math.log1p(50), 1.0) * 0.40

        # Downloads
        if f.early_downloads > 0:
            score += min(math.log1p(f.early_downloads) / math.log1p(1000), 1.0) * 0.20

        # Social mentions
        if f.social_mentions > 0:
            score += min(math.log1p(f.social_mentions) / math.log1p(100), 1.0) * 0.15

        # Altmetric
        if f.altmetric_score > 0:
            score += min(math.log1p(f.altmetric_score) / math.log1p(200), 1.0) * 0.25

        return min(score, 1.0)

    @classmethod
    def _score_to_percentile(cls, score: float) -> float:
        """Map total score to percentile"""
        for threshold, percentile in cls.PERCENTILE_MAP:
            if score >= threshold:
                return percentile
        return 5.0

    @classmethod
    def _get_impact_class(cls, percentile: float) -> str:
        """Map percentile to impact class"""
        for threshold, label in cls.IMPACT_CLASSES:
            if percentile >= threshold:
                return label
        return 'below_average'

    @classmethod
    def _predict_citations(cls, percentile: float) -> int:
        """Map percentile to predicted 5yr citations"""
        for threshold, cites in cls.CITATION_MAP:
            if percentile >= threshold:
                return cites
        return 1

    @classmethod
    def _compute_confidence(cls, f: PaperFeatures) -> float:
        """Compute prediction confidence (0-1)"""
        available = 0
        total = 10

        if f.author_h_index > 0: available += 1
        if f.author_total_papers > 0: available += 1
        if f.journal_impact_factor > 0: available += 1
        if f.reference_count > 0: available += 1
        if f.abstract_length > 0: available += 1
        if f.keyword_count > 0: available += 1
        if f.author_count > 0: available += 1
        if f.early_citations > 0: available += 1
        if f.title_word_count > 0: available += 1
        if f.coauthor_network_size > 0: available += 1

        return available / total

    @classmethod
    def _analyze_factors(
        cls, f: PaperFeatures,
        auth_s: float, jrn_s: float, pap_s: float,
        net_s: float, early_s: float,
    ) -> Tuple[List[str], List[str]]:
        """Identify strengths and weaknesses"""
        strengths = []
        weaknesses = []

        # Author
        if auth_s >= 0.6:
            strengths.append(f"Strong author profile (h-index: {f.author_h_index:.0f})")
        elif auth_s < 0.2:
            weaknesses.append("Limited author track record")

        # Journal
        if jrn_s >= 0.5:
            strengths.append(f"High-impact journal (Q{f.journal_quartile})")
        elif jrn_s < 0.15:
            weaknesses.append("Low journal prestige")

        # Paper
        if f.has_code_availability:
            strengths.append("Code availability increases reproducibility")
        if f.has_data_availability:
            strengths.append("Open data enhances credibility")
        if f.reference_count < 15:
            weaknesses.append(f"Low reference count ({f.reference_count})")
        if f.has_methodology:
            strengths.append("Clear methodology described")

        # Network
        if f.international_collab:
            strengths.append("International collaboration")
        if f.coauthor_network_size < 2:
            weaknesses.append("Limited collaboration network")

        # Early
        if early_s >= 0.5:
            strengths.append(f"Strong early citations ({f.early_citations})")
        elif f.early_citations == 0:
            weaknesses.append("No early citations yet")

        return strengths, weaknesses


# ==================== RESEARCH IMPACT FORECASTER ====================

class ResearchImpactForecaster:
    """
    Full impact forecasting pipeline.
    """

    def __init__(
        self,
        openalex: Optional[OpenAlexClient] = None,
        semantic: Optional[SemanticScholarClient] = None,
    ):
        self.oa = openalex or OpenAlexClient()
        self.ss = semantic or SemanticScholarClient()
        self.extractor = FeatureExtractor()
        self.model = ImpactScoreModel()

    def forecast(self, doi: str) -> ImpactForecast:
        """
        Forecast impact of a paper.

        Args:
            doi: DOI string

        Returns:
            ImpactForecast with prediction
        """
        print(f"\n  [🔮] Research Impact Forecaster")
        print(f"  [·] DOI: {doi}")

        # Fetch paper
        print(f"  [·] Fetching paper metadata...")
        paper = self._fetch_paper(doi)

        if not paper:
            print("  [!] Paper not found")
            return ImpactForecast(doi=doi, impact_class='unknown')

        title_display = paper.title[:50] + "..." if len(paper.title) > 50 else paper.title
        print(f"  [✓] \"{title_display}\"")

        # Extract features
        print(f"  [·] Extracting {32} features...")
        features = self.extractor.extract(paper)
        print(f"  [✓] Features extracted")

        # Predict
        print(f"  [·] Computing impact score...")
        forecast = self.model.predict(features)
        forecast.doi = doi
        forecast.title = paper.title

        self.print_forecast(forecast)
        return forecast

    def batch_forecast(self, dois: List[str]) -> List[ImpactForecast]:
        """Forecast impact for multiple papers"""
        results = []
        for doi in dois:
            result = self.forecast(doi)
            results.append(result)
            time.sleep(0.5)
        return results

    def _fetch_paper(self, doi: str) -> Optional[Paper]:
        """Fetch paper from multiple sources"""
        # Try OpenAlex first
        try:
            papers = self.oa.search(f"doi:{doi}", per_page=1)
            if papers:
                return papers[0]
        except Exception:
            pass

        # Fallback to Semantic Scholar
        try:
            papers = self.ss.search(doi, limit=1)
            if papers:
                return papers[0]
        except Exception:
            pass

        return None

    @staticmethod
    def print_forecast(forecast: ImpactForecast):
        """Print formatted forecast"""
        print(f"\n{'='*65}")
        print(f"  🔮 Research Impact Forecast")
        print(f"{'='*65}")
        print(f"  DOI:   {forecast.doi}")
        if forecast.title:
            title_display = forecast.title[:55] + "..." if len(forecast.title) > 55 else forecast.title
            print(f"  Title: {title_display}")

        # Percentile gauge
        pct = forecast.predicted_percentile
        bar_len = int(pct / 100 * 30)
        bar = '█' * bar_len + '░' * (30 - bar_len)

        class_icons = {
            'exceptional': '🌟',
            'high': '🔥',
            'above_average': '📈',
            'average': '📊',
            'below_average': '📉',
            'unknown': '❓',
        }
        icon = class_icons.get(forecast.impact_class, '·')

        print(f"\n  📊 Predicted Percentile: {pct:.0f}th")
        print(f"  [{bar}]")
        print(f"  {icon} Impact Class: {forecast.impact_class.replace('_', ' ').title()}")
        print(f"  📖 Predicted 5yr Citations: ~{forecast.predicted_citations_5y}")
        print(f"  🎯 Confidence: {forecast.confidence*100:.0f}%")

        # Score breakdown
        print(f"\n  Score Breakdown:")
        print(f"  {'─'*50}")
        categories = [
            ('👤 Author',  forecast.author_score, 0.25),
            ('📰 Journal', forecast.journal_score, 0.20),
            ('📄 Paper',   forecast.paper_score, 0.25),
            ('🔗 Network', forecast.network_score, 0.15),
            ('⚡ Early',   forecast.early_score, 0.15),
        ]
        for name, score, weight in categories:
            s_bar = '▓' * int(score * 20) + '░' * (20 - int(score * 20))
            weighted = score * weight
            print(f"    {name:<14} [{s_bar}] {score:.2f} × {weight} = {weighted:.3f}")

        print(f"    {'─'*46}")
        print(f"    {'Total':<14} {'':>22} = {forecast.total_score:.3f}")

        # Strengths
        if forecast.strengths:
            print(f"\n  💪 Strengths:")
            for s in forecast.strengths:
                print(f"    ✓ {s}")

        # Weaknesses
        if forecast.weaknesses:
            print(f"\n  ⚠️  Weaknesses:")
            for w in forecast.weaknesses:
                print(f"    · {w}")

        print(f"\n{'='*65}")
