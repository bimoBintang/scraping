"""
Journal Article Research Scraper

Scraping jurnal artikel penelitian dari 3 API gratis:
  - OpenAlex (250M+ papers, CC0)
  - Semantic Scholar (214M, AI-powered)
  - CrossRef (DOI resolver)

6 Algorithms:
  J1: Federated Search  — multi-source parallel search
  J2: Citation Crawler   — BFS citation graph traversal
  J3: Trend Analyzer     — research trend time-series
  J4: Paper Recommender  — similarity-based recommendations
  J5: Bulk Harvester     — cursor-based streaming harvest
  J6: Author Network     — disambiguation + collaboration graph
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

from .exporter import JournalExporter

__version__ = "1.1.0"
__all__ = [
    # Models
    'Paper', 'Author', 'CitationEdge',
    'SearchResult', 'TrendPoint', 'ResearchReport',
    'DisambiguatedAuthor', 'CollaborationEdge', 'NetworkReport',
    # API Clients
    'OpenAlexClient', 'SemanticScholarClient', 'CrossRefClient',
    # Algorithms
    'FederatedSearch', 'CitationCrawler',
    'TrendAnalyzer', 'PaperRecommender',
    'AuthorDisambiguator', 'CollaborationNetwork',
    # Exporter
    'JournalExporter',
]
