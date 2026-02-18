"""
Journal Article Research Scraper

Scraping jurnal artikel penelitian dari 3 API gratis:
  - OpenAlex (250M+ papers, CC0)
  - Semantic Scholar (214M, AI-powered)
  - CrossRef (DOI resolver)

8 Algorithms:
  J1: Federated Search  — multi-source parallel search
  J2: Citation Crawler   — BFS citation graph traversal
  J3: Trend Analyzer     — research trend time-series
  J4: Paper Recommender  — similarity-based recommendations
  J5: Bulk Harvester     — cursor-based streaming harvest
  J6: Author Network     — disambiguation + collaboration graph
  J7: Citation Intent    — citation sentiment & impact analysis
  J8: Frontier Detector  — emerging research frontier detection
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

from .exporter import JournalExporter

__version__ = "1.3.0"
__all__ = [
    # Models
    'Paper', 'Author', 'CitationEdge',
    'SearchResult', 'TrendPoint', 'ResearchReport',
    'DisambiguatedAuthor', 'CollaborationEdge', 'NetworkReport',
    'CitationContext', 'CitationImpactReport',
    'FrontierTopic', 'FrontierReport',
    # API Clients
    'OpenAlexClient', 'SemanticScholarClient', 'CrossRefClient',
    # Algorithms
    'FederatedSearch', 'CitationCrawler',
    'TrendAnalyzer', 'PaperRecommender',
    'AuthorDisambiguator', 'CollaborationNetwork',
    'CitationClassifier', 'CitationImpactAnalyzer',
    'FrontierSignalExtractor', 'ResearchFrontierDetector',
    # Exporter
    'JournalExporter',
]
