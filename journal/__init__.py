"""
Journal Article Research Scraper

Scraping jurnal artikel penelitian dari 3 API gratis:
  - OpenAlex (250M+ papers, CC0)
  - Semantic Scholar (214M, AI-powered)
  - CrossRef (DOI resolver)

14 Algorithms:
  J1:  Federated Search   — multi-source parallel search
  J2:  Citation Crawler    — BFS citation graph traversal
  J3:  Trend Analyzer      — research trend time-series
  J4:  Paper Recommender   — similarity-based recommendations
  J5:  Bulk Harvester      — cursor-based streaming harvest
  J6:  Author Network      — disambiguation + collaboration graph
  J7:  Citation Intent     — citation sentiment & impact analysis
  J8:  Frontier Detector   — emerging research frontier detection
  J9:  Journal Ranker      — journal impact metrics & prediction
  J10: Review Generator    — auto literature review generation
  J11: Reference Validator — cross-reference accuracy checking
  J12: Funding Tracker     — funding acknowledgment extraction
  J13: OA Checker          — open access compliance checking
  J14: Impact Forecaster   — research impact prediction
"""

from .models import (
    Paper,
    Author,
    CitationEdge,
    SearchResult,
    TrendPoint,
    ResearchReport,
    DisambiguatedAuthor,
    CollaborationEdge,
    NetworkReport,
    CitationContext,
    CitationImpactReport,
    FrontierTopic,
    FrontierReport,
    JournalMetrics,
    JournalRankReport,
    ReviewSection,
    LiteratureReview,
    ValidationIssue,
    ValidationReport,
    FundingEntry,
    FundingReport,
    OAStatus,
    ComplianceReport,
    PaperFeatures,
    ImpactForecast,
)

from .api_client import (
    OpenAlexClient,
    SemanticScholarClient,
    CrossRefClient,
)

from .search_engine import (
    FederatedSearch,
    CitationCrawler,
    TrendAnalyzer,
    PaperRecommender,
)

from .author_network import (
    AuthorDisambiguator,
    CollaborationNetwork,
)

from .citation_analyzer import (
    CitationClassifier,
    CitationImpactAnalyzer,
)

from .frontier_detector import (
    FrontierSignalExtractor,
    ResearchFrontierDetector,
)

from .journal_ranker import (
    JournalMetricsCalculator,
    JournalRankPredictor,
)

from .review_generator import (
    SentenceExtractor,
    ThematicClusterer,
    GapDetector,
    LiteratureReviewGenerator,
)

from .reference_validator import (
    CitationExtractor,
    BibliographyParser,
    FuzzyMatcher,
    CrossReferenceValidator,
)

from .funding_tracker import (
    FundingExtractor,
    FunderAnalyzer,
)

from .oa_checker import (
    UnpaywallChecker,
    MandateChecker,
    RepositoryRecommender,
    OAComplianceChecker,
)

from .impact_forecaster import (
    FeatureExtractor,
    ImpactScoreModel,
    ResearchImpactForecaster,
)

from .exporter import JournalExporter

__version__ = "1.9.0"
__all__ = [
    # Models
    'Paper', 'Author', 'CitationEdge',
    'SearchResult', 'TrendPoint', 'ResearchReport',
    'DisambiguatedAuthor', 'CollaborationEdge', 'NetworkReport',
    'CitationContext', 'CitationImpactReport',
    'FrontierTopic', 'FrontierReport',
    'JournalMetrics', 'JournalRankReport',
    'ReviewSection', 'LiteratureReview',
    'ValidationIssue', 'ValidationReport',
    'FundingEntry', 'FundingReport',
    'OAStatus', 'ComplianceReport',
    'PaperFeatures', 'ImpactForecast',
    # API Clients
    'OpenAlexClient', 'SemanticScholarClient', 'CrossRefClient',
    # Algorithms
    'FederatedSearch', 'CitationCrawler',
    'TrendAnalyzer', 'PaperRecommender',
    'AuthorDisambiguator', 'CollaborationNetwork',
    'CitationClassifier', 'CitationImpactAnalyzer',
    'FrontierSignalExtractor', 'ResearchFrontierDetector',
    'JournalMetricsCalculator', 'JournalRankPredictor',
    'SentenceExtractor', 'ThematicClusterer',
    'GapDetector', 'LiteratureReviewGenerator',
    'CitationExtractor', 'BibliographyParser',
    'FuzzyMatcher', 'CrossReferenceValidator',
    'FundingExtractor', 'FunderAnalyzer',
    'UnpaywallChecker', 'MandateChecker',
    'RepositoryRecommender', 'OAComplianceChecker',
    'FeatureExtractor', 'ImpactScoreModel',
    'ResearchImpactForecaster',
    # Exporter
    'JournalExporter',
]
