"""
Journal Article API Clients

Three API clients for academic paper retrieval:
  - OpenAlexClient  (primary, 250M+ papers, CC0)
  - SemanticScholarClient (citation graph, AI recommendations)
  - CrossRefClient  (DOI resolver, metadata enrichment)

All clients are free, no mandatory authentication.
"""

import json
import time
import requests
from typing import Any, Dict, Generator, List, Optional
from urllib.parse import quote_plus

from .models import Author, Paper, CitationEdge

# ==================== BASE CONFIG ====================

USER_AGENT = "INSTASCOPE-Journal/1.0 (academic research scraper)"
POLITE_EMAIL = "instascope@research.dev"  # for polite pool access

OPENALEX_BASE = "https://api.openalex.org"
S2_BASE = "https://api.semanticscholar.org/graph/v1"
CROSSREF_BASE = "https://api.crossref.org"


def _safe_get(data: dict, *keys, default=None):
    """Safely traverse nested dicts"""
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key, default)
        else:
            return default
    return data


# ==================== OPENALEX CLIENT ====================

class OpenAlexClient:
    """
    Client for OpenAlex API — primary data source.

    250M+ papers, CC0 license, 100K requests/day.
    Docs: https://docs.openalex.org
    """

    def __init__(self, email: str = POLITE_EMAIL):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': USER_AGENT,
        })
        self.email = email
        self._request_count = 0

    def _request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make a request to OpenAlex API"""
        if params is None:
            params = {}
        params['mailto'] = self.email  # polite pool

        url = f"{OPENALEX_BASE}/{endpoint}"
        self._request_count += 1

        resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def search(
        self,
        query: str,
        per_page: int = 25,
        page: int = 1,
        year_range: Optional[str] = None,
        sort: str = "cited_by_count:desc",
        open_access: Optional[bool] = None,
    ) -> List[Paper]:
        """
        Search for papers by query string.

        Args:
            query: Search query
            per_page: Results per page (max 200)
            page: Page number
            year_range: e.g. "2020-2026"
            sort: Sort order
            open_access: Filter OA papers only

        Returns:
            List of Paper objects
        """
        params = {
            'search': query,
            'per_page': min(per_page, 200),
            'page': page,
            'sort': sort,
        }

        filters = []
        if year_range:
            parts = year_range.split('-')
            if len(parts) == 2:
                filters.append(f"from_publication_date:{parts[0]}-01-01")
                filters.append(f"to_publication_date:{parts[1]}-12-31")
            elif len(parts) == 1:
                filters.append(f"publication_year:{parts[0]}")

        if open_access is True:
            filters.append("is_oa:true")

        if filters:
            params['filter'] = ','.join(filters)

        data = self._request('works', params)
        papers = [self._parse_work(w) for w in data.get('results', [])]
        return papers

    def search_with_count(
        self,
        query: str,
        per_page: int = 25,
        page: int = 1,
        year_range: Optional[str] = None,
        sort: str = "cited_by_count:desc",
    ) -> tuple:
        """Search and return (papers, total_count)"""
        params = {
            'search': query,
            'per_page': min(per_page, 200),
            'page': page,
            'sort': sort,
        }

        filters = []
        if year_range:
            parts = year_range.split('-')
            if len(parts) == 2:
                filters.append(f"from_publication_date:{parts[0]}-01-01")
                filters.append(f"to_publication_date:{parts[1]}-12-31")

        if filters:
            params['filter'] = ','.join(filters)

        data = self._request('works', params)
        papers = [self._parse_work(w) for w in data.get('results', [])]
        total = data.get('meta', {}).get('count', 0)
        return papers, total

    def get_work(self, work_id: str) -> Optional[Paper]:
        """Get a single work by OpenAlex ID or DOI"""
        if work_id.startswith('10.'):
            work_id = f"https://doi.org/{work_id}"

        try:
            data = self._request(f'works/{quote_plus(work_id)}')
            return self._parse_work(data)
        except requests.HTTPError:
            return None

    def get_citations(self, work_id: str, per_page: int = 50) -> List[Paper]:
        """Get papers that cite this work"""
        params = {
            'filter': f'cites:{work_id}',
            'per_page': per_page,
            'sort': 'cited_by_count:desc',
        }
        data = self._request('works', params)
        return [self._parse_work(w) for w in data.get('results', [])]

    def get_references(self, work_id: str) -> List[Paper]:
        """Get papers referenced by this work"""
        try:
            data = self._request(f'works/{work_id}')
            ref_ids = [
                r.get('id', '') for r in data.get('referenced_works_detail', data.get('referenced_works', []))
                if isinstance(r, str) or isinstance(r, dict)
            ]

            # Fetch ref details if they are IDs
            refs = []
            for ref_id in ref_ids[:50]:
                if isinstance(ref_id, str) and ref_id:
                    try:
                        ref_data = self._request(f'works/{ref_id.split("/")[-1]}')
                        refs.append(self._parse_work(ref_data))
                        time.sleep(0.05)
                    except (requests.HTTPError, Exception):
                        continue
            return refs
        except requests.HTTPError:
            return []

    def get_author(self, author_id: str) -> Optional[Author]:
        """Get author details"""
        try:
            data = self._request(f'authors/{author_id}')
            return Author(
                name=data.get('display_name', ''),
                author_id=data.get('id', ''),
                orcid=data.get('orcid', '') or '',
                affiliation=_safe_get(
                    data, 'last_known_institutions', default=[{}]
                )[0].get('display_name', '') if data.get('last_known_institutions') else '',
                h_index=_safe_get(data, 'summary_stats', 'h_index', default=0),
                works_count=data.get('works_count', 0),
                cited_by_count=data.get('cited_by_count', 0),
            )
        except (requests.HTTPError, Exception):
            return None

    def count_by_year(self, query: str, start_year: int, end_year: int) -> List[Dict]:
        """Get publication counts per year for a query (for trend analysis)"""
        params = {
            'search': query,
            'group_by': 'publication_year',
            'per_page': 200,
        }

        filters = [
            f"from_publication_date:{start_year}-01-01",
            f"to_publication_date:{end_year}-12-31",
        ]
        params['filter'] = ','.join(filters)

        data = self._request('works', params)
        groups = data.get('group_by', [])
        return [
            {'year': int(g.get('key', 0)), 'count': g.get('count', 0)}
            for g in groups
            if g.get('key', '').isdigit()
        ]

    def cursor_harvest(
        self,
        query: str = "",
        topic: str = "",
        year: Optional[str] = None,
        per_page: int = 200,
    ) -> Generator[List[Paper], None, None]:
        """
        Cursor-based harvesting for bulk downloads.

        Yields batches of papers using OpenAlex cursor pagination.
        """
        params = {
            'per_page': min(per_page, 200),
            'cursor': '*',
            'sort': 'publication_date:desc',
        }

        if query:
            params['search'] = query

        filters = []
        if topic:
            filters.append(f"concepts.display_name.search:{topic}")
        if year:
            if '-' in year:
                parts = year.split('-')
                filters.append(f"from_publication_date:{parts[0]}-01-01")
                filters.append(f"to_publication_date:{parts[1]}-12-31")
            else:
                filters.append(f"publication_year:{year}")

        if filters:
            params['filter'] = ','.join(filters)

        while True:
            data = self._request('works', params)
            results = data.get('results', [])

            if not results:
                break

            yield [self._parse_work(w) for w in results]

            next_cursor = data.get('meta', {}).get('next_cursor')
            if not next_cursor:
                break
            params['cursor'] = next_cursor

            time.sleep(0.1)  # polite delay

    def _parse_work(self, data: Dict) -> Paper:
        """Parse an OpenAlex work response into a Paper"""
        # Authors
        authorships = data.get('authorships', [])
        author_names = []
        authors = []
        for a in authorships:
            au = a.get('author', {})
            name = au.get('display_name', '')
            if name:
                author_names.append(name)
                inst = ''
                if a.get('institutions'):
                    inst = a['institutions'][0].get('display_name', '')
                authors.append(Author(
                    name=name,
                    author_id=au.get('id', ''),
                    orcid=au.get('orcid', '') or '',
                    affiliation=inst,
                ))

        # Journal / source
        source = data.get('primary_location', {})
        if source is None:
            source = {}
        journal_source = source.get('source', {}) or {}

        # OA
        oa_info = data.get('open_access', {}) or {}

        # Topics / concepts
        topics = []
        for c in data.get('topics', data.get('concepts', []))[:10]:
            if isinstance(c, dict):
                name = c.get('display_name', '')
                if name:
                    topics.append(name)

        # Keywords
        keywords = []
        for kw in data.get('keywords', [])[:10]:
            if isinstance(kw, dict):
                keywords.append(kw.get('display_name', kw.get('keyword', '')))
            elif isinstance(kw, str):
                keywords.append(kw)

        return Paper(
            title=data.get('title', '') or '',
            paper_id=data.get('id', ''),
            doi=(data.get('doi', '') or '').replace('https://doi.org/', ''),
            year=data.get('publication_year', 0) or 0,
            abstract=self._reconstruct_abstract(data.get('abstract_inverted_index')),
            authors=authors,
            author_names=author_names,
            journal=journal_source.get('display_name', '') or '',
            publisher=journal_source.get('host_organization_name', '') or '',
            issn=journal_source.get('issn_l', '') or '',
            citation_count=data.get('cited_by_count', 0),
            reference_count=len(data.get('referenced_works', [])),
            topics=topics,
            keywords=keywords,
            url=data.get('doi', '') or _safe_get(source, 'landing_page_url', default=''),
            pdf_url=_safe_get(oa_info, 'oa_url', default='') or '',
            is_open_access=oa_info.get('is_oa', False),
            open_access_status=oa_info.get('oa_status', ''),
            source_api='openalex',
        )

    @staticmethod
    def _reconstruct_abstract(inverted_index: Optional[Dict]) -> str:
        """Reconstruct abstract from OpenAlex inverted index format"""
        if not inverted_index:
            return ""
        try:
            word_positions = []
            for word, positions in inverted_index.items():
                for pos in positions:
                    word_positions.append((pos, word))
            word_positions.sort()
            return ' '.join(w for _, w in word_positions)
        except (TypeError, AttributeError):
            return ""


# ==================== SEMANTIC SCHOLAR CLIENT ====================

class SemanticScholarClient:
    """
    Client for Semantic Scholar API — citation graph + AI features.

    214M papers, 100 req/s with API key.
    Docs: https://api.semanticscholar.org/api-docs/
    """

    PAPER_FIELDS = (
        "paperId,title,year,abstract,citationCount,referenceCount,"
        "influentialCitationCount,isOpenAccess,openAccessPdf,"
        "authors,journal,externalIds,fieldsOfStudy,s2FieldsOfStudy,"
        "publicationTypes,publicationDate,url"
    )

    def __init__(self, api_key: Optional[str] = None):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': USER_AGENT,
        })
        if api_key:
            self.session.headers['x-api-key'] = api_key
        self._request_count = 0

    def _request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make a request to Semantic Scholar API"""
        url = f"{S2_BASE}/{endpoint}"
        self._request_count += 1

        resp = self.session.get(url, params=params, timeout=30)

        # Rate limit handling
        if resp.status_code == 429:
            retry_after = int(resp.headers.get('Retry-After', 5))
            print(f"  [⏳] S2 rate limited, waiting {retry_after}s...")
            time.sleep(retry_after)
            resp = self.session.get(url, params=params, timeout=30)

        resp.raise_for_status()
        return resp.json()

    def search(self, query: str, limit: int = 25, year: Optional[str] = None) -> List[Paper]:
        """Search papers"""
        params = {
            'query': query,
            'limit': min(limit, 100),
            'fields': self.PAPER_FIELDS,
        }
        if year:
            params['year'] = year

        data = self._request('paper/search', params)
        return [self._parse_paper(p) for p in data.get('data', [])]

    def get_paper(self, paper_id: str) -> Optional[Paper]:
        """
        Get paper by ID. Accepts: S2 paperId, DOI, arXiv ID, etc.

        For DOI: use "DOI:10.1234/example"
        """
        try:
            params = {'fields': self.PAPER_FIELDS}
            data = self._request(f'paper/{paper_id}', params)
            return self._parse_paper(data)
        except requests.HTTPError:
            return None

    def get_citations(self, paper_id: str, limit: int = 50) -> List[Paper]:
        """Get papers that cite this paper"""
        params = {
            'fields': 'title,year,citationCount,authors,externalIds,journal',
            'limit': min(limit, 1000),
        }
        data = self._request(f'paper/{paper_id}/citations', params)
        papers = []
        for item in data.get('data', []):
            citing = item.get('citingPaper', {})
            if citing.get('title'):
                papers.append(self._parse_paper(citing))
        return papers

    def get_references(self, paper_id: str, limit: int = 50) -> List[Paper]:
        """Get papers referenced by this paper"""
        params = {
            'fields': 'title,year,citationCount,authors,externalIds,journal',
            'limit': min(limit, 1000),
        }
        data = self._request(f'paper/{paper_id}/references', params)
        papers = []
        for item in data.get('data', []):
            ref = item.get('citedPaper', {})
            if ref.get('title'):
                papers.append(self._parse_paper(ref))
        return papers

    def get_recommendations(self, paper_id: str, limit: int = 20) -> List[Paper]:
        """Get recommended similar papers"""
        try:
            url = f"https://api.semanticscholar.org/recommendations/v1/papers/forpaper/{paper_id}"
            params = {
                'fields': self.PAPER_FIELDS,
                'limit': min(limit, 500),
            }
            resp = self.session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return [self._parse_paper(p) for p in data.get('recommendedPapers', [])]
        except (requests.HTTPError, Exception):
            return []

    def batch_papers(self, paper_ids: List[str]) -> List[Paper]:
        """Fetch multiple papers in one request"""
        url = f"{S2_BASE}/paper/batch"
        params = {'fields': self.PAPER_FIELDS}
        body = {'ids': paper_ids[:500]}

        resp = self.session.post(url, params=params, json=body, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return [self._parse_paper(p) for p in data if p]

    def _parse_paper(self, data: Dict) -> Paper:
        """Parse a Semantic Scholar paper response"""
        if not data:
            return Paper(title="[Unknown]")

        # Authors
        author_names = []
        authors = []
        for a in data.get('authors', []):
            name = a.get('name', '')
            if name:
                author_names.append(name)
                authors.append(Author(
                    name=name,
                    author_id=a.get('authorId', ''),
                ))

        # External IDs
        ext_ids = data.get('externalIds', {}) or {}
        doi = ext_ids.get('DOI', '')

        # Journal
        journal_info = data.get('journal', {}) or {}
        journal = journal_info.get('name', '') or ''

        # OA
        oa_pdf = data.get('openAccessPdf', {}) or {}

        # Fields
        fields = []
        for f in data.get('s2FieldsOfStudy', data.get('fieldsOfStudy', []) or []):
            if isinstance(f, dict):
                fields.append(f.get('category', ''))
            elif isinstance(f, str):
                fields.append(f)

        return Paper(
            title=data.get('title', '') or '',
            paper_id=data.get('paperId', ''),
            doi=doi,
            year=data.get('year', 0) or 0,
            abstract=data.get('abstract', '') or '',
            authors=authors,
            author_names=author_names,
            journal=journal,
            volume=journal_info.get('volume', '') or '',
            pages=journal_info.get('pages', '') or '',
            citation_count=data.get('citationCount', 0) or 0,
            reference_count=data.get('referenceCount', 0) or 0,
            influential_citation_count=data.get('influentialCitationCount', 0) or 0,
            fields_of_study=fields,
            url=data.get('url', '') or '',
            pdf_url=oa_pdf.get('url', '') or '',
            is_open_access=data.get('isOpenAccess', False) or False,
            source_api='semantic_scholar',
        )


# ==================== CROSSREF CLIENT ====================

class CrossRefClient:
    """
    Client for CrossRef API — DOI resolver + metadata enrichment.

    150M+ records, free REST API.
    Docs: https://api.crossref.org/swagger-ui/index.html
    """

    def __init__(self, email: str = POLITE_EMAIL):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': f"{USER_AGENT}; mailto:{email}",
        })
        self._request_count = 0

    def _request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make a request to CrossRef API"""
        url = f"{CROSSREF_BASE}/{endpoint}"
        self._request_count += 1

        resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def search(
        self,
        query: str,
        rows: int = 25,
        offset: int = 0,
        sort: str = "is-referenced-by-count",
        year: Optional[str] = None,
    ) -> List[Paper]:
        """Search CrossRef for works"""
        params = {
            'query': query,
            'rows': min(rows, 1000),
            'offset': offset,
            'sort': sort,
            'order': 'desc',
        }

        filters = []
        if year:
            if '-' in year:
                parts = year.split('-')
                filters.append(f"from-pub-date:{parts[0]}")
                filters.append(f"until-pub-date:{parts[1]}")
            else:
                filters.append(f"from-pub-date:{year}")
                filters.append(f"until-pub-date:{year}")

        if filters:
            params['filter'] = ','.join(filters)

        data = self._request('works', params)
        items = data.get('message', {}).get('items', [])
        return [self._parse_item(item) for item in items]

    def resolve_doi(self, doi: str) -> Optional[Paper]:
        """Resolve a DOI to full metadata"""
        try:
            data = self._request(f'works/{doi}')
            item = data.get('message', {})
            return self._parse_item(item)
        except requests.HTTPError:
            return None

    def get_journal(self, issn: str) -> Optional[Dict]:
        """Get journal information by ISSN"""
        try:
            data = self._request(f'journals/{issn}')
            msg = data.get('message', {})
            return {
                'title': msg.get('title', ''),
                'publisher': msg.get('publisher', ''),
                'issn': issn,
                'subjects': msg.get('subjects', []),
                'coverage': msg.get('coverage', {}),
            }
        except requests.HTTPError:
            return None

    def _parse_item(self, data: Dict) -> Paper:
        """Parse a CrossRef work item"""
        # Title
        titles = data.get('title', [])
        title = titles[0] if titles else ''

        # Authors
        author_names = []
        authors = []
        for a in data.get('author', []):
            given = a.get('given', '')
            family = a.get('family', '')
            name = f"{given} {family}".strip()
            if name:
                author_names.append(name)
                authors.append(Author(
                    name=name,
                    orcid=a.get('ORCID', '') or '',
                    affiliation=(
                        a['affiliation'][0].get('name', '')
                        if a.get('affiliation') else ''
                    ),
                ))

        # DOI
        doi = data.get('DOI', '')

        # Year
        issued = data.get('issued', {}).get('date-parts', [[0]])
        year = issued[0][0] if issued and issued[0] else 0

        # Journal
        container = data.get('container-title', [])
        journal = container[0] if container else ''

        # ISSN
        issns = data.get('ISSN', [])
        issn = issns[0] if issns else ''

        # Abstract (CrossRef sometimes has it)
        abstract = data.get('abstract', '') or ''
        # Strip JATS XML tags if present
        if abstract.startswith('<'):
            import re
            abstract = re.sub(r'<[^>]+>', '', abstract)

        return Paper(
            title=title,
            doi=doi,
            year=year,
            abstract=abstract,
            authors=authors,
            author_names=author_names,
            journal=journal,
            publisher=data.get('publisher', ''),
            volume=data.get('volume', '') or '',
            issue=data.get('issue', '') or '',
            pages=data.get('page', '') or '',
            issn=issn,
            citation_count=data.get('is-referenced-by-count', 0),
            reference_count=data.get('references-count', 0),
            url=data.get('URL', '') or f"https://doi.org/{doi}",
            is_open_access=bool(data.get('license')),
            source_api='crossref',
        )
