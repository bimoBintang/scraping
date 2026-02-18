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
