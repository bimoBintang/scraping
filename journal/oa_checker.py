"""
Algorithm J13: Open Access Compliance Checker

Check OA compliance by combining Unpaywall data, OpenAlex OA status,
and funder mandate databases.

OA Status Types:
  - gold:   Published in full OA journal
  - green:  Self-archived in repository
  - hybrid: OA in subscription journal (APC paid)
  - bronze: Free to read but no license
  - closed: Paywalled

Usage:
    from journal.oa_checker import OAComplianceChecker

    checker = OAComplianceChecker()
    report = checker.check("10.1038/s41586-021-03819-2")
"""

import re
import time
import urllib.request
import json as json_lib
from typing import Dict, List, Optional, Tuple

from .models import Paper, OAStatus, ComplianceReport
from .api_client import OpenAlexClient, CrossRefClient


# ==================== FUNDER MANDATES DATABASE ====================

FUNDER_MANDATES = {
    'plan_s': {
        'name': 'Plan S (cOAlition S)',
        'requires': 'immediate_oa',
        'accepted_licenses': ['cc-by', 'cc-by-sa', 'cc0'],
        'max_embargo': 0,
        'allows_green': True,
        'requires_cc_by': True,
        'description': 'Immediate OA with CC BY license required',
    },
    'nsf': {
        'name': 'National Science Foundation (NSF)',
        'requires': 'oa_within_12',
        'accepted_licenses': ['cc-by', 'cc-by-sa', 'cc-by-nc', 'cc0'],
        'max_embargo': 12,
        'allows_green': True,
        'requires_cc_by': False,
        'description': 'OA within 12 months, green OA acceptable',
    },
    'nih': {
        'name': 'National Institutes of Health (NIH)',
        'requires': 'oa_within_12',
        'accepted_licenses': ['cc-by', 'cc-by-sa', 'cc-by-nc', 'cc0'],
        'max_embargo': 12,
        'allows_green': True,
        'requires_cc_by': False,
        'description': 'Deposit in PubMed Central within 12 months',
    },
    'erc': {
        'name': 'European Research Council (ERC)',
        'requires': 'immediate_oa',
        'accepted_licenses': ['cc-by', 'cc-by-sa', 'cc0'],
        'max_embargo': 6,
        'allows_green': True,
        'requires_cc_by': True,
        'description': 'Immediate OA, CC BY, or green within 6 months',
    },
    'ukri': {
        'name': 'UK Research and Innovation (UKRI)',
        'requires': 'immediate_oa',
        'accepted_licenses': ['cc-by', 'cc-by-sa', 'cc0'],
        'max_embargo': 0,
        'allows_green': False,
        'requires_cc_by': True,
        'description': 'Immediate gold OA with CC BY required',
    },
    'gates': {
        'name': 'Bill & Melinda Gates Foundation',
        'requires': 'immediate_oa',
        'accepted_licenses': ['cc-by'],
        'max_embargo': 0,
        'allows_green': False,
        'requires_cc_by': True,
        'description': 'Immediate OA with CC BY only',
    },
    'wellcome': {
        'name': 'Wellcome Trust',
        'requires': 'immediate_oa',
        'accepted_licenses': ['cc-by'],
        'max_embargo': 0,
        'allows_green': True,
        'requires_cc_by': True,
        'description': 'Immediate OA with CC BY, Europe PMC deposit',
    },
    'dfg': {
        'name': 'German Research Foundation (DFG)',
        'requires': 'oa_within_12',
        'accepted_licenses': ['cc-by', 'cc-by-sa', 'cc-by-nc', 'cc0'],
        'max_embargo': 12,
        'allows_green': True,
        'requires_cc_by': False,
        'description': 'OA encouraged, green OA within 12 months acceptable',
    },
    'anr': {
        'name': 'French National Research Agency (ANR)',
        'requires': 'oa_within_12',
        'accepted_licenses': ['cc-by', 'cc-by-sa', 'cc-by-nc', 'cc0'],
        'max_embargo': 12,
        'allows_green': True,
        'requires_cc_by': False,
        'description': 'OA within 12 months via HAL or publisher',
    },
}


# ==================== REPOSITORY DATABASE ====================

REPOSITORIES = [
    {
        'name': 'arXiv',
        'url': 'https://arxiv.org',
        'fields': ['physics', 'mathematics', 'computer science', 'statistics',
                   'electrical engineering', 'machine learning', 'AI',
                   'quantitative biology', 'quantitative finance', 'economics'],
        'accepts_preprint': True,
        'accepts_postprint': True,
        'embargo': 0,
        'license_required': False,
    },
    {
        'name': 'PubMed Central (PMC)',
        'url': 'https://www.ncbi.nlm.nih.gov/pmc/',
        'fields': ['biomedical', 'medicine', 'biology', 'health',
                   'life sciences', 'neuroscience', 'genetics', 'NIH'],
        'accepts_preprint': False,
        'accepts_postprint': True,
        'embargo': 0,
        'license_required': False,
    },
    {
        'name': 'Zenodo',
        'url': 'https://zenodo.org',
        'fields': ['general', 'all'],
        'accepts_preprint': True,
        'accepts_postprint': True,
        'embargo': 0,
        'license_required': False,
    },
    {
        'name': 'SSRN',
        'url': 'https://www.ssrn.com',
        'fields': ['social sciences', 'economics', 'law', 'management',
                   'finance', 'accounting', 'political science'],
        'accepts_preprint': True,
        'accepts_postprint': True,
        'embargo': 0,
        'license_required': False,
    },
    {
        'name': 'bioRxiv',
        'url': 'https://www.biorxiv.org',
        'fields': ['biology', 'biomedical', 'biochemistry', 'biophysics',
                   'cell biology', 'genomics', 'neuroscience'],
        'accepts_preprint': True,
        'accepts_postprint': False,
        'embargo': 0,
        'license_required': False,
    },
    {
        'name': 'medRxiv',
        'url': 'https://www.medrxiv.org',
        'fields': ['medicine', 'clinical', 'health', 'epidemiology',
                   'public health'],
        'accepts_preprint': True,
        'accepts_postprint': False,
        'embargo': 0,
        'license_required': False,
    },
    {
        'name': 'HAL',
        'url': 'https://hal.science',
        'fields': ['general', 'all', 'french research'],
        'accepts_preprint': True,
        'accepts_postprint': True,
        'embargo': 0,
        'license_required': False,
    },
    {
        'name': 'EuropePMC',
        'url': 'https://europepmc.org',
        'fields': ['biomedical', 'life sciences', 'medicine'],
        'accepts_preprint': True,
        'accepts_postprint': True,
        'embargo': 0,
        'license_required': False,
    },
]


# ==================== UNPAYWALL CHECKER ====================

class UnpaywallChecker:
    """
    Check OA status via Unpaywall API.

    Unpaywall (https://unpaywall.org/products/api) is free with email.
    """

    BASE_URL = "https://api.unpaywall.org/v2"

    def __init__(self, email: str = "scraper@research.edu"):
        self.email = email

    def check_doi(self, doi: str) -> Optional[OAStatus]:
        """
        Check OA status for a DOI via Unpaywall.

        Args:
            doi: DOI string (e.g. '10.1038/s41586-021-03819-2')

        Returns:
            OAStatus or None if not found
        """
        url = f"{self.BASE_URL}/{doi}?email={self.email}"

        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'JournalScraper/1.8 (research)',
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json_lib.loads(resp.read().decode('utf-8'))

            return self._parse_response(data, doi)

        except Exception as e:
            print(f"  [·] Unpaywall lookup failed: {e}")
            return None

    def _parse_response(self, data: Dict, doi: str) -> OAStatus:
        """Parse Unpaywall API response"""
        is_oa = data.get('is_oa', False)
        oa_status = data.get('oa_status', 'closed')

        # Best OA location
        best = data.get('best_oa_location', {}) or {}
        oa_url = best.get('url_for_pdf') or best.get('url') or ''
        license_val = best.get('license') or ''
        host_type = best.get('host_type') or ''

        journal = data.get('journal_name') or ''

        return OAStatus(
            doi=doi,
            status=oa_status,
            license=license_val,
            oa_url=oa_url,
            host_type=host_type,
            journal=journal,
            is_oa=is_oa,
        )


# ==================== MANDATE CHECKER ====================

class MandateChecker:
    """
    Check compliance with funder OA mandates.
    """

    @classmethod
    def check(
        cls,
        oa_status: OAStatus,
        funder_key: str = '',
    ) -> Tuple[bool, str, str]:
        """
        Check if paper complies with funder mandate.

        Args:
            oa_status: Paper's OA status
            funder_key: Funder key (e.g. 'nsf', 'plan_s')

        Returns:
            (is_compliant, mandate_name, details)
        """
        if not funder_key or funder_key not in FUNDER_MANDATES:
            # No specific mandate → just report OA status
            if oa_status.is_oa:
                return True, 'None', f"Paper is open access ({oa_status.status})"
            return False, 'None', "Paper is not open access"

        mandate = FUNDER_MANDATES[funder_key]
        mandate_name = mandate['name']
        reasons = []

        # Check if OA
        if not oa_status.is_oa:
            return False, mandate_name, (
                f"Non-compliant: Paper is closed access. "
                f"{mandate['description']}"
            )

        # Check OA type
        is_compliant = True

        # Gold/hybrid check
        if mandate['requires'] == 'immediate_oa':
            if oa_status.status == 'closed':
                is_compliant = False
                reasons.append("Immediate OA required but paper is closed")
            elif oa_status.status == 'bronze':
                is_compliant = False
                reasons.append("Bronze OA (no proper license) not accepted")

        # Green OA check
        if oa_status.status == 'green' and not mandate['allows_green']:
            is_compliant = False
            reasons.append("Green OA not accepted, gold OA required")

        # License check
        if mandate['requires_cc_by']:
            paper_license = oa_status.license.lower()
            accepted = [l.lower() for l in mandate['accepted_licenses']]
            if paper_license and not any(a in paper_license for a in accepted):
                is_compliant = False
                reasons.append(
                    f"License '{oa_status.license}' not accepted. "
                    f"Required: {', '.join(mandate['accepted_licenses'])}"
                )

        # Embargo check
        if oa_status.embargo_months > mandate['max_embargo']:
            is_compliant = False
            reasons.append(
                f"Embargo {oa_status.embargo_months} months exceeds "
                f"max {mandate['max_embargo']} months"
            )

        if is_compliant:
            details = f"Compliant with {mandate_name}: {oa_status.status} OA"
            if oa_status.license:
                details += f" ({oa_status.license})"
        else:
            details = f"Non-compliant: {'; '.join(reasons)}"

        return is_compliant, mandate_name, details


# ==================== REPOSITORY RECOMMENDER ====================

class RepositoryRecommender:
    """
    Recommend self-archiving repositories based on paper subject.
    """

    @classmethod
    def recommend(
        cls,
        paper: Optional[Paper] = None,
        keywords: Optional[List[str]] = None,
        oa_status: Optional[OAStatus] = None,
    ) -> List[Dict]:
        """
        Recommend repositories for self-archiving.

        Args:
            paper: Paper object
            keywords: Optional keyword list
            oa_status: Current OA status

        Returns:
            List of recommended repositories with reasons
        """
        query_terms = set()

        if paper:
            if paper.title:
                query_terms.update(paper.title.lower().split())
            if paper.keywords:
                query_terms.update(k.lower() for k in paper.keywords)
        if keywords:
            query_terms.update(k.lower() for k in keywords)

        recommendations = []

        for repo in REPOSITORIES:
            score = 0
            reasons = []

            # Check field match
            for field in repo['fields']:
                if field.lower() in ('general', 'all'):
                    score += 1
                    reasons.append("General-purpose repository")
                    break
                elif any(field.lower() in term for term in query_terms):
                    score += 3
                    reasons.append(f"Matches field: {field}")

            # Prefer repos that accept postprints if already published
            if oa_status and oa_status.status == 'closed' and repo['accepts_postprint']:
                score += 2
                reasons.append("Accepts postprint (self-archiving)")

            # Prefer repos with no embargo
            if repo['embargo'] == 0:
                score += 1
                reasons.append("No embargo period")

            if score > 0:
                recommendations.append({
                    'name': repo['name'],
                    'url': repo['url'],
                    'score': score,
                    'reasons': reasons,
                    'accepts_preprint': repo['accepts_preprint'],
                    'accepts_postprint': repo['accepts_postprint'],
                })

        # Sort by score
        recommendations.sort(key=lambda x: x['score'], reverse=True)
        return recommendations[:5]


# ==================== OA COMPLIANCE CHECKER ====================

class OAComplianceChecker:
    """
    Full OA compliance checking pipeline.
    """

    def __init__(
        self,
        email: str = "scraper@research.edu",
        openalex: Optional[OpenAlexClient] = None,
    ):
        self.unpaywall = UnpaywallChecker(email=email)
        self.oa = openalex or OpenAlexClient()
        self.mandate_checker = MandateChecker()
        self.recommender = RepositoryRecommender()

    def check(
        self,
        doi: str,
        funder: str = '',
    ) -> ComplianceReport:
        """
        Check OA compliance for a single DOI.

        Args:
            doi: DOI string
            funder: Funder key for mandate checking

        Returns:
            ComplianceReport
        """
        print(f"\n  [🔓] Open Access Compliance Checker")
        print(f"  [·] DOI: {doi}")

        # 1. Check Unpaywall
        print(f"  [·] Checking Unpaywall...")
        oa_status = self.unpaywall.check_doi(doi)

        # 2. Fallback: check OpenAlex
        title = ""
        paper = None
        if not oa_status:
            print(f"  [·] Fallback to OpenAlex...")
            oa_status, title, paper = self._check_openalex(doi)

        if not oa_status:
            oa_status = OAStatus(doi=doi, status='unknown', is_oa=False)

        # Get paper title
        if not title:
            title = self._get_title(doi, paper)

        status_icons = {
            'gold': '🥇', 'green': '🟢', 'hybrid': '🔶',
            'bronze': '🟤', 'closed': '🔒', 'unknown': '❓',
        }
        icon = status_icons.get(oa_status.status, '·')
        print(f"  [✓] OA Status: {icon} {oa_status.status}")
        if oa_status.license:
            print(f"  [·] License: {oa_status.license}")

        # 3. Mandate check
        is_compliant, mandate_name, details = self.mandate_checker.check(
            oa_status, funder
        )

        # 4. Generate recommendations
        recommendations = []
        recommended_repos = []

        if not oa_status.is_oa or oa_status.status == 'closed':
            recommendations.append("Consider self-archiving a postprint")
            recommendations.append("Check publisher's self-archiving policy (SHERPA/RoMEO)")
            recommended_repos = self.recommender.recommend(
                paper=paper,
                oa_status=oa_status,
            )
        elif oa_status.status == 'bronze':
            recommendations.append("Bronze OA lacks formal license — request CC BY from publisher")
            recommendations.append("Self-archive with proper license")
        elif oa_status.status == 'green':
            recommendations.append("Paper is green OA — also consider gold OA for wider reach")

        if funder and not is_compliant:
            mandate = FUNDER_MANDATES.get(funder, {})
            if mandate.get('allows_green'):
                recommendations.append(f"Deposit postprint in repository within {mandate.get('max_embargo', 12)} months")
            else:
                recommendations.append("Publish in gold OA journal or pay APC for hybrid OA")

        report = ComplianceReport(
            doi=doi,
            title=title,
            oa_status=oa_status,
            funder=funder,
            mandate=mandate_name,
            is_compliant=is_compliant,
            compliance_details=details,
            recommendations=recommendations,
            recommended_repos=recommended_repos,
        )

        self.print_report(report)
        return report

    def batch_check(
        self,
        dois: List[str],
        funder: str = '',
    ) -> List[ComplianceReport]:
        """Check multiple DOIs"""
        reports = []
        for doi in dois:
            report = self.check(doi, funder)
            reports.append(report)
            time.sleep(0.5)  # Rate limiting
        return reports

    def _check_openalex(
        self, doi: str
    ) -> Tuple[Optional[OAStatus], str, Optional[Paper]]:
        """Fallback OA check via OpenAlex"""
        try:
            papers = self.oa.search(f"doi:{doi}", per_page=1)
            if papers:
                paper = papers[0]
                status = 'closed'
                if hasattr(paper, 'is_oa') and paper.is_oa:
                    status = 'gold'

                oa_status = OAStatus(
                    doi=doi,
                    status=status,
                    is_oa=(status != 'closed'),
                    journal=paper.journal or '',
                )
                return oa_status, paper.title, paper
        except Exception:
            pass
        return None, '', None

    def _get_title(self, doi: str, paper: Optional[Paper] = None) -> str:
        """Get paper title"""
        if paper and paper.title:
            return paper.title
        try:
            crossref = CrossRefClient()
            papers = crossref.search(f"doi:{doi}", rows=1)
            if papers:
                return papers[0].title
        except Exception:
            pass
        return doi

    @staticmethod
    def print_report(report: ComplianceReport):
        """Print formatted compliance report"""
        print(f"\n{'='*65}")
        print(f"  🔓 Open Access Compliance Report")
        print(f"{'='*65}")
        print(f"  DOI:   {report.doi}")
        if report.title != report.doi:
            title_display = report.title[:55] + "..." if len(report.title) > 55 else report.title
            print(f"  Title: {title_display}")

        # OA Status
        if report.oa_status:
            status = report.oa_status
            status_icons = {
                'gold': '🥇', 'green': '🟢', 'hybrid': '🔶',
                'bronze': '🟤', 'closed': '🔒', 'unknown': '❓',
            }
            icon = status_icons.get(status.status, '·')
            print(f"\n  OA Status: {icon} {status.status.upper()}")
            if status.license:
                print(f"  License:   {status.license}")
            if status.oa_url:
                url_display = status.oa_url[:50] + "..." if len(status.oa_url) > 50 else status.oa_url
                print(f"  OA URL:    {url_display}")
            if status.journal:
                print(f"  Journal:   {status.journal}")

        # Compliance
        if report.funder:
            comp_icon = '✅' if report.is_compliant else '❌'
            print(f"\n  {comp_icon} Mandate: {report.mandate}")
            print(f"  {report.compliance_details}")

        # Recommendations
        if report.recommendations:
            print(f"\n  💡 Recommendations:")
            for i, rec in enumerate(report.recommendations, 1):
                print(f"    {i}. {rec}")

        # Repos
        if report.recommended_repos:
            print(f"\n  📦 Recommended Repositories:")
            print(f"  {'─'*55}")
            for repo in report.recommended_repos[:5]:
                types = []
                if repo.get('accepts_preprint'):
                    types.append('preprint')
                if repo.get('accepts_postprint'):
                    types.append('postprint')
                print(f"    • {repo['name']:<25} ({', '.join(types)})")
                print(f"      {repo['url']}")

        print(f"\n{'='*65}")
