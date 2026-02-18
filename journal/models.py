"""
Journal Article Data Models

Dataclasses for representing academic papers, authors, citations,
and search results from OpenAlex, Semantic Scholar, and CrossRef.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any


@dataclass
class Author:
    """An academic researcher / paper author"""
    name: str
    author_id: str = ""           # OpenAlex or S2 ID
    orcid: str = ""
    affiliation: str = ""
    h_index: int = 0
    works_count: int = 0
    cited_by_count: int = 0

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class Paper:
    """A published research paper / journal article"""
    title: str
    paper_id: str = ""            # OpenAlex W-id or S2 paperId
    doi: str = ""
    year: int = 0
    abstract: str = ""

    # Authors
    authors: List[Author] = field(default_factory=list)
    author_names: List[str] = field(default_factory=list)

    # Publication info
    journal: str = ""
    publisher: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""
    issn: str = ""

    # Metrics
    citation_count: int = 0
    reference_count: int = 0
    influential_citation_count: int = 0

    # Classification
    topics: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    fields_of_study: List[str] = field(default_factory=list)

    # Access
    url: str = ""
    pdf_url: str = ""
    is_open_access: bool = False
    open_access_status: str = ""

    # Source tracking
    source_api: str = ""  # openalex, semantic_scholar, crossref

    def to_dict(self) -> Dict:
        d = asdict(self)
        d['authors'] = [a.to_dict() if isinstance(a, Author) else a for a in self.authors]
        return d

    def to_bibtex_key(self) -> str:
        """Generate a BibTeX citation key"""
        first_author = self.author_names[0].split()[-1] if self.author_names else "unknown"
        first_word = self.title.split()[0].lower() if self.title else "untitled"
        return f"{first_author}{self.year}{first_word}"

    def __str__(self) -> str:
        authors_str = ", ".join(self.author_names[:3])
        if len(self.author_names) > 3:
            authors_str += " et al."
        oa = " [OA]" if self.is_open_access else ""
        return (
            f"[{self.year}] {self.title}\n"
            f"  Authors: {authors_str}\n"
            f"  Journal: {self.journal or 'N/A'} | DOI: {self.doi or 'N/A'}\n"
            f"  Citations: {self.citation_count}{oa}"
        )


@dataclass
class CitationEdge:
    """A citation relationship: source_paper cites target_paper"""
    source_id: str
    target_id: str
    source_title: str = ""
    target_title: str = ""
    context: str = ""           # citation context snippet
    is_influential: bool = False
    year: int = 0

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class SearchResult:
    """Result from a search query across one or more APIs"""
    query: str
    papers: List[Paper] = field(default_factory=list)
    total_count: int = 0
    source: str = ""            # openalex, semantic_scholar, crossref, federated
    page: int = 1
    per_page: int = 25
    elapsed_seconds: float = 0.0

    def to_dict(self) -> Dict:
        return {
            'query': self.query,
            'total_count': self.total_count,
            'source': self.source,
            'page': self.page,
            'per_page': self.per_page,
            'elapsed_seconds': round(self.elapsed_seconds, 2),
            'papers': [p.to_dict() for p in self.papers],
        }


@dataclass
class TrendPoint:
    """A single data point in a research trend time series"""
    year: int
    count: int = 0
    growth_rate: float = 0.0     # % change from previous year
    cumulative: int = 0

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ResearchReport:
    """Full analysis output for a research query"""
    query: str
    timestamp: str = ""

    # Search results
    papers: List[Paper] = field(default_factory=list)
    total_found: int = 0

    # Trend analysis
    trend_points: List[TrendPoint] = field(default_factory=list)
    peak_year: int = 0
    growth_direction: str = ""   # growing, stable, declining

    # Citation graph
    citation_edges: List[CitationEdge] = field(default_factory=list)
    citation_depth: int = 0

    # Top items
    top_authors: List[Author] = field(default_factory=list)
    top_journals: List[str] = field(default_factory=list)
    top_keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            'query': self.query,
            'timestamp': self.timestamp,
            'total_found': self.total_found,
            'papers': [p.to_dict() for p in self.papers],
            'trend_points': [t.to_dict() for t in self.trend_points],
            'peak_year': self.peak_year,
            'growth_direction': self.growth_direction,
            'citation_edges': [e.to_dict() for e in self.citation_edges],
            'top_authors': [a.to_dict() for a in self.top_authors],
            'top_journals': self.top_journals,
            'top_keywords': self.top_keywords,
        }


# ==================== J6: AUTHOR NETWORK MODELS ====================

@dataclass
class DisambiguatedAuthor:
    """A disambiguated author identity — merged from multiple paper records"""
    canonical_name: str
    author_ids: List[str] = field(default_factory=list)       # OpenAlex/S2 IDs
    orcids: List[str] = field(default_factory=list)
    affiliations: List[str] = field(default_factory=list)
    paper_count: int = 0
    paper_titles: List[str] = field(default_factory=list)
    paper_years: List[int] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    coauthors: List[str] = field(default_factory=list)        # names of co-authors
    total_citations: int = 0
    h_index: int = 0

    # Centrality scores (filled by network analysis)
    degree_centrality: float = 0.0
    betweenness_centrality: float = 0.0
    closeness_centrality: float = 0.0

    def to_dict(self) -> Dict:
        return asdict(self)

    def year_range(self) -> str:
        if not self.paper_years:
            return "N/A"
        return f"{min(self.paper_years)}–{max(self.paper_years)}"


@dataclass
class CollaborationEdge:
    """A co-authorship link between two authors"""
    author_a: str
    author_b: str
    weight: int = 1               # number of co-authored papers
    shared_papers: List[str] = field(default_factory=list)    # paper titles
    years: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class NetworkReport:
    """Full network analysis output"""
    query: str = ""
    total_authors: int = 0
    total_edges: int = 0
    total_papers_analyzed: int = 0
    disambiguated_authors: List[DisambiguatedAuthor] = field(default_factory=list)
    collaboration_edges: List[CollaborationEdge] = field(default_factory=list)
    top_authors_by_degree: List[str] = field(default_factory=list)
    top_authors_by_betweenness: List[str] = field(default_factory=list)
    top_collaboration_pairs: List[Dict] = field(default_factory=list)
    communities: List[List[str]] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            'query': self.query,
            'total_authors': self.total_authors,
            'total_edges': self.total_edges,
            'total_papers_analyzed': self.total_papers_analyzed,
            'disambiguated_authors': [a.to_dict() for a in self.disambiguated_authors],
            'collaboration_edges': [e.to_dict() for e in self.collaboration_edges],
            'top_authors_by_degree': self.top_authors_by_degree,
            'top_authors_by_betweenness': self.top_authors_by_betweenness,
            'top_collaboration_pairs': self.top_collaboration_pairs,
            'communities': self.communities,
        }


# ==================== J7: CITATION INTENT MODELS ====================

@dataclass
class CitationContext:
    """A single citation context with classified intent and sentiment"""
    text: str
    intent: str = "background"         # background, methodology, extension, comparison, support, contrast
    sentiment: str = "neutral"         # positive, negative, neutral
    confidence: float = 0.0
    citing_paper_title: str = ""
    citing_paper_doi: str = ""
    citing_paper_year: int = 0
    is_influential: bool = False

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class CitationImpactReport:
    """Aggregate citation impact analysis for a paper"""
    paper_title: str = ""
    paper_doi: str = ""
    total_citations: int = 0
    analyzed_citations: int = 0

    # Sentiment counts
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0

    # Intent breakdown
    intent_breakdown: Dict[str, int] = field(default_factory=dict)

    # Impact quality score (0.0 – 1.0)
    quality_score: float = 0.0
    influential_count: int = 0

    # Context details
    contexts: List[CitationContext] = field(default_factory=list)
    top_supporters: List[str] = field(default_factory=list)
    top_critics: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            'paper_title': self.paper_title,
            'paper_doi': self.paper_doi,
            'total_citations': self.total_citations,
            'analyzed_citations': self.analyzed_citations,
            'positive_count': self.positive_count,
            'negative_count': self.negative_count,
            'neutral_count': self.neutral_count,
            'intent_breakdown': self.intent_breakdown,
            'quality_score': round(self.quality_score, 3),
            'influential_count': self.influential_count,
            'contexts': [c.to_dict() for c in self.contexts],
            'top_supporters': self.top_supporters,
            'top_critics': self.top_critics,
        }
