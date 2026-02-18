"""
Algorithm J12: Funding Acknowledgment Tracker

Extract funding information from paper acknowledgments and analyze
research investment patterns.

Extracts:
  - Funder names (NSF, NIH, ERC, JSPS, ...)
  - Grant/award numbers
  - Program names
  - Funding amounts (when available)

Analysis:
  - Top funders by paper count
  - Funding distribution by year
  - ROI metrics (citations per funded paper)

Usage:
    from journal.funding_tracker import FunderAnalyzer

    analyzer = FunderAnalyzer()
    report = analyzer.analyze("deep learning", n_papers=50)
"""

import re
import time
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

from .models import Paper, FundingEntry, FundingReport
from .api_client import OpenAlexClient


# ==================== KNOWN FUNDERS DATABASE ====================

KNOWN_FUNDERS = {
    # US
    'nsf': 'National Science Foundation (NSF)',
    'national science foundation': 'National Science Foundation (NSF)',
    'nih': 'National Institutes of Health (NIH)',
    'national institutes of health': 'National Institutes of Health (NIH)',
    'darpa': 'DARPA',
    'doe': 'Department of Energy (DOE)',
    'department of energy': 'Department of Energy (DOE)',
    'nasa': 'NASA',
    'ons': 'Office of Naval Research (ONR)',
    'office of naval research': 'Office of Naval Research (ONR)',
    'afosr': 'Air Force Office of Scientific Research (AFOSR)',
    'army research': 'Army Research Office (ARO)',

    # Europe
    'erc': 'European Research Council (ERC)',
    'european research council': 'European Research Council (ERC)',
    'horizon 2020': 'EU Horizon 2020',
    'horizon europe': 'EU Horizon Europe',
    'european union': 'European Union',
    'fp7': 'EU Framework Programme 7',
    'dfg': 'German Research Foundation (DFG)',
    'deutsche forschungsgemeinschaft': 'German Research Foundation (DFG)',
    'anr': 'French National Research Agency (ANR)',
    'epsrc': 'UK EPSRC',
    'ukri': 'UK Research and Innovation (UKRI)',
    'wellcome': 'Wellcome Trust',

    # Asia
    'jsps': 'Japan Society for the Promotion of Science (JSPS)',
    'kakenhi': 'JSPS KAKENHI',
    'nsfc': 'National Natural Science Foundation of China (NSFC)',
    'national natural science foundation of china': 'National Natural Science Foundation of China (NSFC)',
    'nrf': 'National Research Foundation (NRF)',
    'most': 'Ministry of Science and Technology',
    'csa': 'Chinese Academy of Sciences (CAS)',
    'chinese academy of sciences': 'Chinese Academy of Sciences (CAS)',

    # Tech / Private
    'google': 'Google Research',
    'microsoft': 'Microsoft Research',
    'facebook': 'Meta Research',
    'meta': 'Meta Research',
    'amazon': 'Amazon Science',
    'ibm': 'IBM Research',
    'nvidia': 'NVIDIA',
    'samsung': 'Samsung',
    'intel': 'Intel',
    'huawei': 'Huawei',

    # International
    'who': 'World Health Organization (WHO)',
    'world bank': 'World Bank',
    'gates foundation': 'Bill & Melinda Gates Foundation',
    'bill and melinda gates': 'Bill & Melinda Gates Foundation',
}


# ==================== FUNDING EXTRACTOR ====================

class FundingExtractor:
    """
    Extract funding information from text using regex patterns.
    """

    # Patterns that precede funder mentions
    FUNDING_PATTERNS = [
        # "supported by X"
        re.compile(
            r'(?:supported|funded|sponsored|financed)\s+(?:in\s+part\s+)?by\s+'
            r'(?:the\s+)?(.+?)(?:\.|;|\n|$)',
            re.IGNORECASE,
        ),
        # "grant from X"
        re.compile(
            r'(?:grants?|awards?|fellowships?|funding)\s+(?:from|by)\s+'
            r'(?:the\s+)?(.+?)(?:\.|;|\n|$)',
            re.IGNORECASE,
        ),
        # "under grant No. X"
        re.compile(
            r'under\s+(?:grant|contract|award)\s+(?:No\.?\s*)?(.+?)(?:\.|;|\n|$)',
            re.IGNORECASE,
        ),
        # "acknowledge(s) X"
        re.compile(
            r'(?:acknowledge|acknowledges|grateful\s+to)\s+'
            r'(?:the\s+)?(?:support\s+(?:of|from)\s+)?(.+?)(?:\.|;|\n|$)',
            re.IGNORECASE,
        ),
        # "X Grant/Award No."
        re.compile(
            r'([A-Z][A-Za-z\s]+(?:Foundation|Council|Agency|Institute|Ministry))\s+'
            r'(?:grant|award)\s+(?:No\.?\s*)?([A-Z0-9\-/]+)',
            re.IGNORECASE,
        ),
    ]

    # Grant number patterns
    GRANT_PATTERNS = [
        re.compile(r'(?:grant|award|contract|project)\s*(?:No\.?\s*|#\s*)?([A-Z0-9][\w\-/\.]+)', re.IGNORECASE),
        re.compile(r'(?:No\.?\s*|#\s*)([A-Z0-9][\w\-/\.]{3,})', re.IGNORECASE),
        re.compile(r'\b([A-Z]{2,}\-\d{4,})\b'),  # NSF-2024567
        re.compile(r'\b(\d{2}[A-Z]{2,}\d{3,})\b'),  # 21ERC001
    ]

    @classmethod
    def extract(cls, text: str, paper: Optional[Paper] = None) -> List[FundingEntry]:
        """
        Extract funding entries from acknowledgment text.

        Args:
            text: Acknowledgment text
            paper: Optional associated paper

        Returns:
            List of FundingEntry
        """
        if not text:
            return []

        entries = []
        seen_funders = set()

        # 1. Match funding patterns
        for pattern in cls.FUNDING_PATTERNS:
            for match in pattern.finditer(text):
                raw = match.group(1).strip()
                funder, grant_id, program = cls._parse_funding_mention(raw)

                if funder and funder.lower() not in seen_funders:
                    seen_funders.add(funder.lower())
                    entries.append(FundingEntry(
                        funder=funder,
                        grant_id=grant_id,
                        program=program,
                        paper_title=paper.title if paper else "",
                        paper_year=paper.year if paper else 0,
                        paper_citations=paper.citation_count if paper else 0,
                    ))

        # 2. Scan for known funders directly
        text_lower = text.lower()
        for key, canonical in KNOWN_FUNDERS.items():
            if key in text_lower and canonical.lower() not in seen_funders:
                seen_funders.add(canonical.lower())

                # Try to find grant number near the funder mention
                grant_id = ""
                pos = text_lower.index(key)
                context = text[max(0, pos - 20):pos + len(key) + 80]
                for gp in cls.GRANT_PATTERNS:
                    gm = gp.search(context)
                    if gm:
                        grant_id = gm.group(1)
                        break

                entries.append(FundingEntry(
                    funder=canonical,
                    grant_id=grant_id,
                    paper_title=paper.title if paper else "",
                    paper_year=paper.year if paper else 0,
                    paper_citations=paper.citation_count if paper else 0,
                ))

        return entries

    @classmethod
    def _parse_funding_mention(cls, raw: str) -> Tuple[str, str, str]:
        """
        Parse a raw funding mention into (funder, grant_id, program).
        """
        funder = ""
        grant_id = ""
        program = ""

        # Clean up
        raw = raw.strip().rstrip(',').rstrip(';')

        # Check against known funders
        raw_lower = raw.lower()
        for key, canonical in KNOWN_FUNDERS.items():
            if key in raw_lower:
                funder = canonical
                break

        # If no known funder, use raw text (first ~60 chars)
        if not funder:
            # Extract organization name (up to first number or parenthesis)
            org_match = re.match(r'^([A-Za-z\s\.\&\-]+)', raw)
            if org_match:
                funder = org_match.group(1).strip()
                if len(funder) > 60:
                    funder = funder[:60] + "..."

        # Extract grant number
        for gp in cls.GRANT_PATTERNS:
            gm = gp.search(raw)
            if gm:
                grant_id = gm.group(1)
                break

        # Extract program name (text in parentheses)
        prog_match = re.search(r'\(([^)]+)\)', raw)
        if prog_match:
            program = prog_match.group(1)

        return funder, grant_id, program


# ==================== FUNDER ANALYZER ====================

class FunderAnalyzer:
    """
    Analyze funding patterns across a collection of papers.
    """

    def __init__(self, openalex: Optional[OpenAlexClient] = None):
        self.oa = openalex or OpenAlexClient()
        self.extractor = FundingExtractor()

    def analyze(
        self,
        query: str,
        n_papers: int = 50,
    ) -> FundingReport:
        """
        Analyze funding patterns for a research topic.

        Args:
            query: Research topic
            n_papers: Number of papers to analyze

        Returns:
            FundingReport with funding analysis
        """
        print(f"\n  [💰] Funding Acknowledgment Tracker")
        print(f"  [·] Topic: \"{query}\"")
        print(f"  [·] Papers to analyze: {n_papers}")

        # Fetch papers
        print(f"  [·] Fetching papers...")
        papers = self.oa.search(
            query,
            per_page=min(n_papers, 200),
            sort="cited_by_count:desc",
        )

        if not papers:
            print("  [!] No papers found")
            return FundingReport(query=query)

        papers = papers[:n_papers]
        print(f"  [✓] {len(papers)} papers fetched")

        # Extract funding from each paper
        print(f"  [·] Extracting funding information...")
        all_entries = []
        papers_with_funding = 0

        for paper in papers:
            # Use abstract as proxy for acknowledgment
            text = paper.abstract or ""
            # Also check title for grant mentions
            text += " " + paper.title

            entries = self.extractor.extract(text, paper)
            if entries:
                papers_with_funding += 1
                all_entries.extend(entries)

        print(f"  [✓] {len(all_entries)} funding mentions extracted")
        print(f"  [·] {papers_with_funding}/{len(papers)} papers have funding info")

        # Aggregate
        top_funders = self._aggregate_funders(all_entries)
        yearly_dist = self._yearly_distribution(all_entries)
        roi = self._compute_roi(all_entries)

        funding_rate = papers_with_funding / len(papers) if papers else 0

        report = FundingReport(
            query=query,
            total_papers=len(papers),
            papers_with_funding=papers_with_funding,
            funding_rate=round(funding_rate, 3),
            entries=all_entries,
            top_funders=top_funders,
            yearly_distribution=yearly_dist,
            funder_roi=roi,
        )

        self.print_report(report)
        return report

    @staticmethod
    def _aggregate_funders(entries: List[FundingEntry]) -> List[Dict]:
        """Aggregate funding by funder"""
        funder_data = defaultdict(lambda: {
            'count': 0,
            'total_citations': 0,
            'papers': [],
            'grants': set(),
        })

        for e in entries:
            key = e.funder
            funder_data[key]['count'] += 1
            funder_data[key]['total_citations'] += e.paper_citations
            funder_data[key]['papers'].append(e.paper_title)
            if e.grant_id:
                funder_data[key]['grants'].add(e.grant_id)

        result = []
        for funder, data in sorted(funder_data.items(), key=lambda x: x[1]['count'], reverse=True):
            result.append({
                'funder': funder,
                'paper_count': data['count'],
                'total_citations': data['total_citations'],
                'avg_citations': round(data['total_citations'] / max(data['count'], 1), 1),
                'unique_grants': len(data['grants']),
            })

        return result

    @staticmethod
    def _yearly_distribution(entries: List[FundingEntry]) -> Dict[int, int]:
        """Count funding mentions by year"""
        yearly = Counter()
        for e in entries:
            if e.paper_year:
                yearly[e.paper_year] += 1
        return dict(sorted(yearly.items()))

    @staticmethod
    def _compute_roi(entries: List[FundingEntry]) -> List[Dict]:
        """Compute ROI metrics per funder (citations per paper)"""
        funder_stats = defaultdict(lambda: {'papers': 0, 'citations': 0})

        for e in entries:
            funder_stats[e.funder]['papers'] += 1
            funder_stats[e.funder]['citations'] += e.paper_citations

        roi = []
        for funder, stats in funder_stats.items():
            roi.append({
                'funder': funder,
                'papers': stats['papers'],
                'total_citations': stats['citations'],
                'citations_per_paper': round(
                    stats['citations'] / max(stats['papers'], 1), 1
                ),
            })

        # Sort by citations per paper
        roi.sort(key=lambda x: x['citations_per_paper'], reverse=True)
        return roi

    @staticmethod
    def print_report(report: FundingReport):
        """Print formatted funding report"""
        print(f"\n{'='*65}")
        print(f"  💰 Funding Acknowledgment Report")
        print(f"{'='*65}")
        print(f"  Query:     \"{report.query}\"")
        print(f"  Papers:    {report.total_papers}")
        print(f"  With funding: {report.papers_with_funding}"
              f"  ({report.funding_rate*100:.1f}%)")
        print(f"  Total mentions: {len(report.entries)}")

        # Top funders
        if report.top_funders:
            print(f"\n  🏛️ Top Funders:")
            print(f"  {'─'*55}")
            print(f"  {'#':<4} {'Funder':<35} {'Papers':>6} {'Cites':>7}")
            print(f"  {'─'*55}")

            for i, f in enumerate(report.top_funders[:15], 1):
                name = f['funder'][:34]
                print(f"  {i:<4} {name:<35} {f['paper_count']:>6}"
                      f" {f['total_citations']:>7}")

        # Yearly distribution
        if report.yearly_distribution:
            print(f"\n  📅 Funding by Year:")
            print(f"  {'─'*55}")
            max_count = max(report.yearly_distribution.values()) or 1
            for year, count in sorted(report.yearly_distribution.items()):
                bar_len = int(count / max_count * 25)
                bar = '▓' * bar_len
                print(f"    {year} │{bar} {count}")

        # ROI
        if report.funder_roi:
            print(f"\n  📊 ROI (Citations per Paper):")
            print(f"  {'─'*55}")
            for f in report.funder_roi[:10]:
                name = f['funder'][:30]
                print(f"    {name:<32} {f['citations_per_paper']:>8.1f}"
                      f" cites/paper")

        print(f"\n{'='*65}")
