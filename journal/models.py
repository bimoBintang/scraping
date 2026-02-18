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


# ==================== J8: RESEARCH FRONTIER MODELS ====================

@dataclass
class FrontierTopic:
    """An emerging research frontier topic with detection scores"""
    topic: str
    frontier_score: float = 0.0          # composite score 0.0–1.0
    growth_rate: float = 0.0             # year-over-year publication growth %
    citation_velocity: float = 0.0       # avg citations/year for recent papers
    author_diversity: float = 0.0        # institution spread score
    keyword_novelty: float = 0.0         # keyword co-occurrence novelty

    # Time-series data
    yearly_counts: Dict[int, int] = field(default_factory=dict)

    # Prediction
    predicted_growth: float = 0.0        # predicted papers in next year
    trajectory: str = "stable"           # emerging, surging, stable, declining

    # Related keywords
    emerging_keywords: List[str] = field(default_factory=list)
    sample_papers: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class FrontierReport:
    """Full frontier detection report"""
    query: str = ""
    year_range: str = ""
    total_topics_analyzed: int = 0
    frontiers: List[FrontierTopic] = field(default_factory=list)
    keyword_clusters: List[List[str]] = field(default_factory=list)
    top_emerging: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            'query': self.query,
            'year_range': self.year_range,
            'total_topics_analyzed': self.total_topics_analyzed,
            'frontiers': [f.to_dict() for f in self.frontiers],
            'keyword_clusters': self.keyword_clusters,
            'top_emerging': self.top_emerging,
        }


# ==================== J9: JOURNAL RANKING MODELS ====================

@dataclass
class JournalMetrics:
    """Computed metrics for a single journal"""
    journal_name: str = ""
    issn: str = ""
    year: int = 0

    # Core metrics
    impact_factor: float = 0.0        # mean citations (2-year window)
    median_citations: float = 0.0     # median (robust)
    h5_index: int = 0                 # h-index for last 5 years
    total_papers: int = 0
    total_citations: int = 0

    # Distribution metrics
    gini_coefficient: float = 0.0     # citation inequality (0–1)
    top10_share: float = 0.0          # % citations from top 10% papers
    immediacy_index: float = 0.0      # same-year citation rate
    self_citation_rate: float = 0.0   # % self-citations

    # Percentiles
    p25: float = 0.0
    p50: float = 0.0
    p75: float = 0.0
    p90: float = 0.0

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class JournalRankReport:
    """Full journal ranking & prediction report"""
    journal_name: str = ""
    year_range: str = ""
    current_metrics: Optional[JournalMetrics] = None
    yearly_metrics: List[JournalMetrics] = field(default_factory=list)

    # Trajectory prediction
    predicted_impact: float = 0.0
    trajectory: str = "stable"         # rising, stable, declining
    rank_score: float = 0.0            # composite 0.0–1.0

    # Comparison
    compared_journals: List[JournalMetrics] = field(default_factory=list)
    recommendation: str = ""

    def to_dict(self) -> Dict:
        return {
            'journal_name': self.journal_name,
            'year_range': self.year_range,
            'current_metrics': self.current_metrics.to_dict() if self.current_metrics else None,
            'yearly_metrics': [m.to_dict() for m in self.yearly_metrics],
            'predicted_impact': round(self.predicted_impact, 3),
            'trajectory': self.trajectory,
            'rank_score': round(self.rank_score, 3),
            'compared_journals': [j.to_dict() for j in self.compared_journals],
            'recommendation': self.recommendation,
        }


# ==================== J10: LITERATURE REVIEW MODELS ====================

@dataclass
class ReviewSection:
    """A section in a literature review"""
    title: str = ""
    content: str = ""
    papers: List[str] = field(default_factory=list)        # paper titles referenced
    paper_count: int = 0
    theme_keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class LiteratureReview:
    """Complete auto-generated literature review"""
    query: str = ""
    title: str = ""
    total_papers: int = 0
    year_range: str = ""

    # Sections
    introduction: str = ""
    sections: List[ReviewSection] = field(default_factory=list)
    research_gaps: List[str] = field(default_factory=list)
    conclusion: str = ""

    # Bibliography
    bibliography: List[str] = field(default_factory=list)

    # Full markdown
    full_text: str = ""

    def to_dict(self) -> Dict:
        return {
            'query': self.query,
            'title': self.title,
            'total_papers': self.total_papers,
            'year_range': self.year_range,
            'introduction': self.introduction,
            'sections': [s.to_dict() for s in self.sections],
            'research_gaps': self.research_gaps,
            'conclusion': self.conclusion,
            'bibliography': self.bibliography,
        }


# ==================== J11: CROSS-REFERENCE VALIDATOR MODELS ====================

@dataclass
class ValidationIssue:
    """A single validation issue"""
    issue_type: str = ""       # missing_ref, orphan_entry, format_issue, year_mismatch, duplicate
    severity: str = "warning"  # error, warning, info
    description: str = ""
    location: str = ""         # e.g. "line 42" or "citation #3"
    citation_text: str = ""
    suggestion: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ValidationReport:
    """Full cross-reference validation report"""
    total_citations: int = 0
    total_bib_entries: int = 0
    matched: int = 0
    issues: List[ValidationIssue] = field(default_factory=list)

    # Counts by type
    missing_refs: int = 0
    orphan_entries: int = 0
    format_issues: int = 0
    year_mismatches: int = 0
    duplicates: int = 0

    # Score
    accuracy_score: float = 0.0  # 0.0–1.0

    def to_dict(self) -> Dict:
        return {
            'total_citations': self.total_citations,
            'total_bib_entries': self.total_bib_entries,
            'matched': self.matched,
            'issues': [i.to_dict() for i in self.issues],
            'missing_refs': self.missing_refs,
            'orphan_entries': self.orphan_entries,
            'format_issues': self.format_issues,
            'year_mismatches': self.year_mismatches,
            'duplicates': self.duplicates,
            'accuracy_score': round(self.accuracy_score, 3),
        }


# ==================== J12: FUNDING TRACKER MODELS ====================

@dataclass
class FundingEntry:
    """A single funding acknowledgment"""
    funder: str = ""
    grant_id: str = ""
    program: str = ""
    paper_title: str = ""
    paper_year: int = 0
    paper_citations: int = 0

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class FundingReport:
    """Funding analysis report"""
    query: str = ""
    total_papers: int = 0
    papers_with_funding: int = 0
    funding_rate: float = 0.0

    entries: List[FundingEntry] = field(default_factory=list)
    top_funders: List[Dict] = field(default_factory=list)
    yearly_distribution: Dict[int, int] = field(default_factory=dict)
    funder_roi: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            'query': self.query,
            'total_papers': self.total_papers,
            'papers_with_funding': self.papers_with_funding,
            'funding_rate': round(self.funding_rate, 3),
            'entries': [e.to_dict() for e in self.entries],
            'top_funders': self.top_funders,
            'yearly_distribution': self.yearly_distribution,
            'funder_roi': self.funder_roi,
        }


# ==================== J13: OA COMPLIANCE MODELS ====================

@dataclass
class OAStatus:
    """Open Access status of a paper"""
    doi: str = ""
    status: str = "closed"  # gold, green, hybrid, bronze, closed
    license: str = ""
    oa_url: str = ""
    host_type: str = ""     # publisher, repository
    journal: str = ""
    is_oa: bool = False
    embargo_months: int = 0

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ComplianceReport:
    """OA compliance check report"""
    doi: str = ""
    title: str = ""
    oa_status: Optional[OAStatus] = None
    funder: str = ""
    mandate: str = ""
    is_compliant: bool = False
    compliance_details: str = ""
    recommendations: List[str] = field(default_factory=list)
    recommended_repos: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            'doi': self.doi,
            'title': self.title,
            'oa_status': self.oa_status.to_dict() if self.oa_status else None,
            'funder': self.funder,
            'mandate': self.mandate,
            'is_compliant': self.is_compliant,
            'compliance_details': self.compliance_details,
            'recommendations': self.recommendations,
            'recommended_repos': self.recommended_repos,
        }


# ==================== J14: IMPACT FORECASTER MODELS ====================

@dataclass
class PaperFeatures:
    """Computed features for impact prediction"""
    # Author features
    author_h_index: float = 0.0
    author_total_papers: int = 0
    author_total_citations: int = 0
    author_career_years: int = 0
    author_max_single_cites: int = 0
    author_collab_diversity: float = 0.0
    author_count: int = 0
    is_first_author_senior: bool = False

    # Journal features
    journal_impact_factor: float = 0.0
    journal_h5_index: int = 0
    journal_citation_median: float = 0.0
    journal_is_oa: bool = False
    journal_quartile: int = 4  # 1=Q1, 4=Q4
    journal_age_years: int = 0

    # Paper features
    reference_count: int = 0
    abstract_length: int = 0
    title_word_count: int = 0
    keyword_count: int = 0
    has_methodology: bool = False
    has_data_availability: bool = False
    has_code_availability: bool = False
    international_collab: bool = False
    title_novelty_score: float = 0.0
    abstract_readability: float = 0.0

    # Network features
    cross_field_refs: float = 0.0
    self_citation_ratio: float = 0.0
    coauthor_network_size: int = 0
    citation_diversity: float = 0.0

    # Early signals
    early_citations: int = 0
    early_downloads: int = 0
    social_mentions: int = 0
    altmetric_score: float = 0.0

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ImpactForecast:
    """Impact prediction result"""
    doi: str = ""
    title: str = ""
    predicted_percentile: float = 0.0   # 0-100
    confidence: float = 0.0             # 0-1
    predicted_citations_5y: int = 0
    impact_class: str = ""              # exceptional, high, above_avg, average, below_avg

    # Score breakdown
    author_score: float = 0.0
    journal_score: float = 0.0
    paper_score: float = 0.0
    network_score: float = 0.0
    early_score: float = 0.0
    total_score: float = 0.0

    features: Optional[PaperFeatures] = None
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            'doi': self.doi,
            'title': self.title,
            'predicted_percentile': round(self.predicted_percentile, 1),
            'confidence': round(self.confidence, 3),
            'predicted_citations_5y': self.predicted_citations_5y,
            'impact_class': self.impact_class,
            'score_breakdown': {
                'author': round(self.author_score, 3),
                'journal': round(self.journal_score, 3),
                'paper': round(self.paper_score, 3),
                'network': round(self.network_score, 3),
                'early': round(self.early_score, 3),
                'total': round(self.total_score, 3),
            },
            'features': self.features.to_dict() if self.features else None,
            'strengths': self.strengths,
            'weaknesses': self.weaknesses,
        }
