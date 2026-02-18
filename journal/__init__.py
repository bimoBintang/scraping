"""
Journal Article Research Scraper

Scraping jurnal artikel penelitian dari 3 API gratis:
  - OpenAlex (250M+ papers, CC0)
  - Semantic Scholar (214M, AI-powered)
  - CrossRef (DOI resolver)

7 Algorithms:
  J1: Federated Search  — multi-source parallel search
  J2: Citation Crawler   — BFS citation graph traversal
  J3: Trend Analyzer     — research trend time-series
  J4: Paper Recommender  — similarity-based recommendations
  J5: Bulk Harvester     — cursor-based streaming harvest
  J6: Author Network     — disambiguation + collaboration graph
  J7: Citation Intent    — citation sentiment & impact analysis
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

from .exporter import JournalExporter

__version__ = "1.2.0"
__all__ = [
    # Models
    'Paper', 'Author', 'CitationEdge',
    'SearchResult', 'TrendPoint', 'ResearchReport',
    'DisambiguatedAuthor', 'CollaborationEdge', 'NetworkReport',
    'CitationContext', 'CitationImpactReport',
    # API Clients
    'OpenAlexClient', 'SemanticScholarClient', 'CrossRefClient',
    # Algorithms
    'FederatedSearch', 'CitationCrawler',
    'TrendAnalyzer', 'PaperRecommender',
    'AuthorDisambiguator', 'CollaborationNetwork',
    'CitationClassifier', 'CitationImpactAnalyzer',
    # Exporter
    'JournalExporter',
]
