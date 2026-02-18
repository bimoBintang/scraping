"""
Algorithm J15: Systematic Review Assistant

Full systematic review workflow:
  1. Query Expansion  — synonyms, MeSH terms, Boolean queries
  2. Abstract Screening — inclusion/exclusion criteria, PICO
  3. Risk of Bias      — 7-domain methodology assessment
  4. Data Extraction   — sample sizes, effect sizes, p-values

Usage:
    from journal.systematic_review import SystematicReviewAssistant

    assistant = SystematicReviewAssistant()
    report = assistant.review(
        query="COVID-19 vaccine efficacy",
        inclusion=["RCT", "clinical trial"],
        exclusion=["animal", "review"],
    )
"""

import re
import math
from collections import Counter
from typing import Dict, List, Optional, Set, Tuple

from .models import (
    Paper,
    ScreeningResult,
    BiasAssessment,
    SystematicReviewReport,
)
from .api_client import OpenAlexClient


# ==================== SYNONYM DATABASE ====================

SYNONYM_DB = {
    # Medical terms
    'covid-19': ['SARS-CoV-2', 'coronavirus', 'COVID', 'pandemic'],
    'vaccine': ['vaccination', 'immunization', 'inoculation'],
    'efficacy': ['effectiveness', 'potency', 'protective effect'],
    'cancer': ['tumor', 'neoplasm', 'malignancy', 'carcinoma', 'oncology'],
    'diabetes': ['diabetic', 'glycemic', 'insulin resistance', 'hyperglycemia'],
    'hypertension': ['high blood pressure', 'arterial pressure', 'HTN'],
    'depression': ['depressive disorder', 'MDD', 'major depression'],
    'anxiety': ['anxious', 'anxiety disorder', 'GAD'],
    'obesity': ['overweight', 'BMI', 'body mass index', 'adiposity'],
    'stroke': ['cerebrovascular', 'ischemic', 'hemorrhagic'],
    'heart failure': ['cardiac failure', 'HF', 'cardiomyopathy'],
    'alzheimer': ['dementia', 'cognitive decline', 'neurodegeneration'],
    'asthma': ['bronchial', 'airway inflammation', 'wheezing'],
    'pain': ['analgesic', 'nociceptive', 'chronic pain', 'acute pain'],
    'infection': ['infectious', 'pathogen', 'antimicrobial', 'antibiotic'],

    # Methodology terms
    'randomized': ['randomised', 'RCT', 'random allocation'],
    'clinical trial': ['clinical study', 'intervention study', 'trial'],
    'cohort': ['prospective study', 'longitudinal', 'follow-up study'],
    'meta-analysis': ['systematic review', 'pooled analysis', 'evidence synthesis'],
    'case-control': ['case control', 'retrospective study'],
    'cross-sectional': ['survey', 'prevalence study'],
    'placebo': ['sham', 'control group', 'inactive treatment'],
    'blinding': ['masking', 'double-blind', 'single-blind'],
    'sample size': ['participants', 'subjects', 'n=', 'enrolled'],

    # Computer Science terms
    'deep learning': ['neural network', 'DNN', 'CNN', 'RNN', 'transformer'],
    'machine learning': ['ML', 'supervised learning', 'classification', 'prediction model'],
    'natural language processing': ['NLP', 'text mining', 'language model'],
    'computer vision': ['image recognition', 'object detection', 'visual'],
    'reinforcement learning': ['RL', 'reward-based', 'policy optimization'],
    'artificial intelligence': ['AI', 'intelligent system', 'automated'],
    'neural network': ['ANN', 'deep neural', 'multilayer perceptron'],
    'transfer learning': ['fine-tuning', 'pretrained', 'domain adaptation'],
    'generative': ['GAN', 'VAE', 'diffusion model', 'generative AI'],

    # Social science terms
    'education': ['educational', 'learning outcomes', 'pedagogy', 'teaching'],
    'behavior': ['behaviour', 'behavioral', 'behavioural'],
    'psychology': ['psychological', 'mental health', 'well-being'],
    'intervention': ['program', 'treatment', 'therapy'],
    'outcome': ['result', 'effect', 'endpoint', 'measure'],
    'diagnosis': ['diagnostic', 'detection', 'screening', 'identification'],
    'treatment': ['therapy', 'therapeutic', 'management', 'medication'],
    'prognosis': ['prediction', 'prognostic', 'survival', 'outcome'],
}


# ==================== QUERY EXPANDER ====================

class QueryExpander:
    """
    Expand search queries with synonyms and related terms.
    """

    @classmethod
    def expand(
        cls,
        query: str,
        max_synonyms: int = 3,
    ) -> Tuple[str, List[str]]:
        """
        Expand query with synonyms.

        Args:
            query: Original search query
            max_synonyms: Max synonyms per term

        Returns:
            (expanded_query_string, list_of_all_terms)
        """
        terms = cls._tokenize(query)
        expanded_groups = []
        all_terms = list(terms)

        for term in terms:
            group = [term]
            term_lower = term.lower()

            # Direct synonym lookup
            if term_lower in SYNONYM_DB:
                syns = SYNONYM_DB[term_lower][:max_synonyms]
                group.extend(syns)
                all_terms.extend(syns)

            # Partial match
            for key, syns in SYNONYM_DB.items():
                if key != term_lower and (term_lower in key or key in term_lower):
                    added = syns[:max_synonyms - len(group) + 1]
                    group.extend(added)
                    all_terms.extend(added)
                    break

            expanded_groups.append(group)

        # Build Boolean query
        parts = []
        for group in expanded_groups:
            if len(group) > 1:
                inner = ' OR '.join(f'"{g}"' for g in group)
                parts.append(f"({inner})")
            else:
                parts.append(f'"{group[0]}"')

        expanded_query = ' AND '.join(parts)

        return expanded_query, list(set(all_terms))

    @classmethod
    def _tokenize(cls, query: str) -> List[str]:
        """Split query into meaningful terms"""
        # Keep quoted phrases
        phrases = re.findall(r'"([^"]+)"', query)
        remaining = re.sub(r'"[^"]+"', '', query)

        # Split remaining
        words = remaining.strip().split()

        # Combine multi-word terms
        terms = list(phrases)
        skip = set()
        for i, word in enumerate(words):
            if i in skip:
                continue
            # Check if two consecutive words form a known term
            if i + 1 < len(words):
                bigram = f"{word} {words[i+1]}".lower()
                if bigram in SYNONYM_DB:
                    terms.append(f"{word} {words[i+1]}")
                    skip.add(i + 1)
                    continue
            if word.lower() not in ('and', 'or', 'not', 'the', 'a', 'an', 'of', 'in', 'for'):
                terms.append(word)

        return terms if terms else [query]


# ==================== ABSTRACT SCREENER ====================

class AbstractScreener:
    """
    Screen abstracts against inclusion/exclusion criteria.
    Supports PICO framework.
    """

    # Study type patterns
    STUDY_PATTERNS = {
        'rct': [r'\brandomiz', r'\brandomis', r'\bRCT\b', r'random\s*(?:ized|ised)\s*controlled'],
        'meta_analysis': [r'\bmeta.?analy', r'\bsystematic\s+review', r'\bpooled\s+analy'],
        'cohort': [r'\bcohort\b', r'\bprospective\b', r'\blongitudinal\b', r'\bfollow.?up\s+study'],
        'case_control': [r'\bcase.?control', r'\bretrospective\b'],
        'cross_sectional': [r'\bcross.?sectional', r'\bsurvey\b', r'\bprevalence\b'],
        'case_report': [r'\bcase\s+report', r'\bcase\s+series'],
        'review': [r'\breview\b', r'\boverview\b', r'\bnarrative\b'],
        'experimental': [r'\bexperiment', r'\blaboratory\b', r'\bin\s+vitro', r'\bin\s+vivo'],
    }

    @classmethod
    def screen(
        cls,
        paper: Paper,
        inclusion: Optional[List[str]] = None,
        exclusion: Optional[List[str]] = None,
        pico: Optional[Dict[str, List[str]]] = None,
    ) -> ScreeningResult:
        """
        Screen a paper abstract.

        Args:
            paper: Paper to screen
            inclusion: Keywords that must be present
            exclusion: Keywords that must be absent
            pico: PICO criteria dict {P:[], I:[], C:[], O:[]}

        Returns:
            ScreeningResult with decision
        """
        text = f"{paper.title or ''} {paper.abstract or ''}".lower()
        result = ScreeningResult(
            paper_title=paper.title or '',
            paper_doi=getattr(paper, 'doi', '') or '',
        )

        score = 0.0
        inclusion = inclusion or []
        exclusion = exclusion or []

        # Check inclusion criteria
        for criterion in inclusion:
            if criterion.lower() in text:
                score += 1.0
                result.matched_inclusion.append(criterion)

        # Check exclusion criteria
        for criterion in exclusion:
            if criterion.lower() in text:
                score -= 2.0
                result.matched_exclusion.append(criterion)

        # PICO matching
        if pico:
            pico_score = cls._check_pico(text, pico)
            score += pico_score

        # Study type detection
        study_type = cls.detect_study_type(text)

        # Bonus for high-evidence study types
        evidence_bonus = {
            'meta_analysis': 2.0, 'rct': 1.5, 'cohort': 1.0,
            'case_control': 0.5, 'experimental': 0.5,
        }
        score += evidence_bonus.get(study_type, 0.0)

        # Decide
        result.score = score

        if result.matched_exclusion:
            result.decision = 'exclude'
            result.reason = f"Matched exclusion: {', '.join(result.matched_exclusion)}"
        elif score >= 2.0:
            result.decision = 'include'
            result.reason = f"Score {score:.1f}: matched inclusion criteria"
        elif score >= 0.5:
            result.decision = 'uncertain'
            result.reason = f"Score {score:.1f}: needs manual review"
        else:
            result.decision = 'exclude'
            result.reason = f"Score {score:.1f}: insufficient evidence of relevance"

        return result

    @classmethod
    def _check_pico(cls, text: str, pico: Dict[str, List[str]]) -> float:
        """Check PICO criteria"""
        score = 0.0
        for category, terms in pico.items():
            for term in terms:
                if term.lower() in text:
                    score += 0.5
                    break
        return score

    @classmethod
    def detect_study_type(cls, text: str) -> str:
        """Detect study type from text"""
        for study_type, patterns in cls.STUDY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return study_type
        return 'unknown'


# ==================== BIAS ASSESSOR ====================

class BiasAssessor:
    """
    Assess risk of bias across 7 domains.
    """

    BIAS_DOMAINS = {
        'randomization': {
            'low_signals': [r'\brandom', r'\ballocation\s+conceal', r'\bsequence\s+generat'],
            'high_signals': [r'\bconvenience\s+sampl', r'\bnon.?random', r'\bselected\b'],
        },
        'blinding': {
            'low_signals': [r'\bdouble.?blind', r'\bmasked\b', r'\bblinded\b'],
            'high_signals': [r'\bopen.?label', r'\bunblinded', r'\bnot\s+blind'],
        },
        'attrition': {
            'low_signals': [r'\bintention.?to.?treat', r'\bITT\b', r'\blow\s+dropout', r'\bcomplete\s+follow'],
            'high_signals': [r'\bhigh\s+dropout', r'\blost\s+to\s+follow', r'\battrition'],
        },
        'reporting': {
            'low_signals': [r'\bpre.?registr', r'\bprotocol\b', r'\bCONSORT', r'\bPRISMA', r'\bSTROBE'],
            'high_signals': [r'\bselective\s+report', r'\bnot\s+report'],
        },
        'measurement': {
            'low_signals': [r'\bvalidated\b', r'\breliab', r'\bstandard\s+(?:ized|ised)'],
            'high_signals': [r'\bself.?report', r'\bunvalidated', r'\bsubjective\b'],
        },
        'confounding': {
            'low_signals': [r'\badjusted\b', r'\bcontrolled\s+for', r'\bcovariate', r'\bpropensity'],
            'high_signals': [r'\bunadjusted', r'\bconfound', r'\bbias'],
        },
        'sample_size': {
            'low_signals': [r'\bpower\s+(?:analy|calcul)', r'\blarge\s+sample', r'n\s*[=>]\s*\d{3,}'],
            'high_signals': [r'\bsmall\s+sample', r'\bpilot\b', r'\bpreliminary', r'n\s*[=<]\s*[1-3]\d\b'],
        },
    }

    @classmethod
    def assess(cls, paper: Paper) -> BiasAssessment:
        """
        Assess risk of bias.

        Args:
            paper: Paper to assess

        Returns:
            BiasAssessment with per-domain ratings
        """
        text = f"{paper.title or ''} {paper.abstract or ''}".lower()
        assessment = BiasAssessment(
            paper_title=paper.title or '',
            paper_doi=getattr(paper, 'doi', '') or '',
        )

        # Detect study type
        assessment.study_type = AbstractScreener.detect_study_type(text)

        # Assess each domain
        domain_risks = {}
        high_count = 0
        low_count = 0

        for domain, signals in cls.BIAS_DOMAINS.items():
            risk = cls._assess_domain(text, signals)
            domain_risks[domain] = risk
            if risk == 'high':
                high_count += 1
            elif risk == 'low':
                low_count += 1

        assessment.domains = domain_risks

        # Overall risk
        if high_count >= 3:
            assessment.overall_risk = 'high'
        elif low_count >= 4:
            assessment.overall_risk = 'low'
        else:
            assessment.overall_risk = 'unclear'

        # Extract sample size
        assessment.sample_size = cls._extract_sample_size(text)

        # Extract basic data
        assessment.extracted_data = DataExtractor.extract(text)

        return assessment

    @classmethod
    def _assess_domain(cls, text: str, signals: Dict) -> str:
        """Assess a single bias domain"""
        low_found = any(
            re.search(p, text, re.IGNORECASE)
            for p in signals.get('low_signals', [])
        )
        high_found = any(
            re.search(p, text, re.IGNORECASE)
            for p in signals.get('high_signals', [])
        )

        if low_found and not high_found:
            return 'low'
        elif high_found and not low_found:
            return 'high'
        elif low_found and high_found:
            return 'unclear'
        return 'unclear'

    @classmethod
    def _extract_sample_size(cls, text: str) -> int:
        """Extract sample size"""
        patterns = [
            r'n\s*=\s*(\d[\d,]*)',
            r'(\d[\d,]*)\s*participants',
            r'(\d[\d,]*)\s*patients',
            r'(\d[\d,]*)\s*subjects',
            r'sample\s+(?:size|of)\s+(\d[\d,]*)',
            r'enrolled\s+(\d[\d,]*)',
        ]
        sizes = []
        for pat in patterns:
            matches = re.findall(pat, text, re.IGNORECASE)
            for m in matches:
                try:
                    sizes.append(int(m.replace(',', '')))
                except ValueError:
                    pass

        return max(sizes) if sizes else 0


# ==================== DATA EXTRACTOR ====================

class DataExtractor:
    """
    Extract quantitative data from text.
    """

    @classmethod
    def extract(cls, text: str) -> Dict:
        """
        Extract effect sizes, p-values, sample sizes, CIs.

        Args:
            text: Paper text or abstract

        Returns:
            Dict of extracted data
        """
        data = {}

        # P-values
        p_values = cls._extract_p_values(text)
        if p_values:
            data['p_values'] = p_values

        # Confidence intervals
        cis = cls._extract_confidence_intervals(text)
        if cis:
            data['confidence_intervals'] = cis

        # Effect sizes (OR, RR, HR, d, r)
        effects = cls._extract_effect_sizes(text)
        if effects:
            data['effect_sizes'] = effects

        # Sample sizes
        samples = cls._extract_sample_sizes(text)
        if samples:
            data['sample_sizes'] = samples

        # Percentages
        percentages = cls._extract_percentages(text)
        if percentages:
            data['percentages'] = percentages

        return data

    @classmethod
    def _extract_p_values(cls, text: str) -> List[Dict]:
        """Extract p-values"""
        results = []
        patterns = [
            r'p\s*[=<>]\s*(0?\.\d+)',
            r'p\s*-?\s*value\s*[=<>:]\s*(0?\.\d+)',
            r'p\s*<\s*(0?\.\d+)',
            r'significance.*?(0?\.\d+)',
        ]
        for pat in patterns:
            for m in re.finditer(pat, text, re.IGNORECASE):
                try:
                    val = float(m.group(1))
                    if 0 < val < 1:
                        context = text[max(0, m.start()-30):m.end()+30].strip()
                        results.append({'value': val, 'context': context})
                except ValueError:
                    pass

        # Deduplicate
        seen = set()
        unique = []
        for r in results:
            if r['value'] not in seen:
                seen.add(r['value'])
                unique.append(r)
        return unique[:10]

    @classmethod
    def _extract_confidence_intervals(cls, text: str) -> List[Dict]:
        """Extract confidence intervals"""
        results = []
        patterns = [
            r'(\d+)%\s*CI\s*[:\s]*\[?\(?([\d.]+)\s*[,–-]\s*([\d.]+)\)?\]?',
            r'CI\s*[:\s]*\(?([\d.]+)\s*[,–-]\s*([\d.]+)\)?',
            r'confidence\s+interval\s*[:\s]*\(?([\d.]+)\s*[,–-]\s*([\d.]+)\)?',
        ]
        for pat in patterns:
            for m in re.finditer(pat, text, re.IGNORECASE):
                groups = m.groups()
                try:
                    if len(groups) == 3:
                        results.append({
                            'level': f"{groups[0]}%",
                            'lower': float(groups[1]),
                            'upper': float(groups[2]),
                        })
                    elif len(groups) == 2:
                        results.append({
                            'level': '95%',
                            'lower': float(groups[0]),
                            'upper': float(groups[1]),
                        })
                except ValueError:
                    pass

        return results[:10]

    @classmethod
    def _extract_effect_sizes(cls, text: str) -> List[Dict]:
        """Extract effect sizes"""
        results = []
        patterns = [
            (r'\bOR\s*[=:]\s*([\d.]+)', 'odds_ratio'),
            (r'odds\s+ratio\s*[=:]\s*([\d.]+)', 'odds_ratio'),
            (r'\bRR\s*[=:]\s*([\d.]+)', 'risk_ratio'),
            (r'risk\s+ratio\s*[=:]\s*([\d.]+)', 'risk_ratio'),
            (r'\bHR\s*[=:]\s*([\d.]+)', 'hazard_ratio'),
            (r'hazard\s+ratio\s*[=:]\s*([\d.]+)', 'hazard_ratio'),
            (r"Cohen'?s?\s+d\s*[=:]\s*([\d.]+)", 'cohens_d'),
            (r'\bd\s*=\s*([\d.]+)', 'cohens_d'),
            (r'\br\s*=\s*(0?\.\d+)', 'correlation'),
            (r'AUC\s*[=:]\s*(0?\.\d+)', 'auc'),
        ]
        for pat, name in patterns:
            for m in re.finditer(pat, text, re.IGNORECASE):
                try:
                    results.append({
                        'type': name,
                        'value': float(m.group(1)),
                    })
                except ValueError:
                    pass

        return results[:10]

    @classmethod
    def _extract_sample_sizes(cls, text: str) -> List[int]:
        """Extract sample sizes"""
        results = []
        patterns = [
            r'n\s*=\s*(\d[\d,]*)',
            r'(\d[\d,]*)\s*(?:participants|patients|subjects|individuals)',
            r'sample\s+(?:size|of)\s+(\d[\d,]*)',
        ]
        for pat in patterns:
            for m in re.finditer(pat, text, re.IGNORECASE):
                try:
                    results.append(int(m.group(1).replace(',', '')))
                except ValueError:
                    pass

        return sorted(set(results), reverse=True)[:5]

    @classmethod
    def _extract_percentages(cls, text: str) -> List[Dict]:
        """Extract key percentages"""
        results = []
        pattern = r'([\d.]+)\s*%'
        for m in re.finditer(pattern, text):
            try:
                val = float(m.group(1))
                if 0 < val <= 100:
                    context = text[max(0, m.start()-40):m.end()+20].strip()
                    results.append({'value': val, 'context': context})
            except ValueError:
                pass

        return results[:10]


# ==================== SYSTEMATIC REVIEW ASSISTANT ====================

class SystematicReviewAssistant:
    """
    Full systematic review pipeline.
    """

    def __init__(self, openalex: Optional[OpenAlexClient] = None):
        self.oa = openalex or OpenAlexClient()
        self.expander = QueryExpander()
        self.screener = AbstractScreener()
        self.assessor = BiasAssessor()

    def review(
        self,
        query: str,
        n_papers: int = 50,
        inclusion: Optional[List[str]] = None,
        exclusion: Optional[List[str]] = None,
        pico: Optional[Dict[str, List[str]]] = None,
    ) -> SystematicReviewReport:
        """
        Run systematic review pipeline.

        Args:
            query: Research question
            n_papers: Number of papers to screen
            inclusion: Inclusion criteria keywords
            exclusion: Exclusion criteria keywords
            pico: PICO criteria

        Returns:
            SystematicReviewReport
        """
        print(f"\n  [📋] Systematic Review Assistant")
        print(f"  [·] Query: \"{query}\"")

        # 1. Query expansion
        print(f"  [·] Expanding query...")
        expanded_query, all_terms = self.expander.expand(query)
        print(f"  [✓] Expanded → {len(all_terms)} terms")
        print(f"  [·] Boolean: {expanded_query[:80]}...")

        # 2. Search
        print(f"\n  [·] Searching for papers...")
        papers = self._fetch_papers(query, n_papers)
        print(f"  [✓] Found {len(papers)} papers")

        if not papers:
            return SystematicReviewReport(
                query=query, expanded_query=expanded_query
            )

        # 3. Screening
        print(f"\n  [·] Screening abstracts...")
        screening_results = []
        included, excluded, uncertain = 0, 0, 0
        for paper in papers:
            result = self.screener.screen(
                paper, inclusion=inclusion,
                exclusion=exclusion, pico=pico,
            )
            screening_results.append(result)
            if result.decision == 'include':
                included += 1
            elif result.decision == 'exclude':
                excluded += 1
            else:
                uncertain += 1

        print(f"  [✓] Screening: {included} include, {excluded} exclude, {uncertain} uncertain")

        # 4. Bias assessment (for included papers)
        print(f"\n  [·] Assessing risk of bias...")
        bias_assessments = []
        included_papers = [p for p, s in zip(papers, screening_results) if s.decision == 'include']
        for paper in included_papers:
            assessment = self.assessor.assess(paper)
            bias_assessments.append(assessment)

        # Risk distribution
        risk_counts = Counter(a.overall_risk for a in bias_assessments)
        print(f"  [✓] Risk: {dict(risk_counts)}")

        # 5. Study type distribution
        study_types = Counter(
            self.screener.detect_study_type(
                f"{p.title or ''} {p.abstract or ''}".lower()
            )
            for p in included_papers
        )

        # 6. PRISMA flow
        prisma_flow = {
            'identification': len(papers),
            'screening': len(papers),
            'eligibility': included + uncertain,
            'included': included,
        }

        report = SystematicReviewReport(
            query=query,
            expanded_query=expanded_query,
            total_found=len(papers),
            total_screened=len(papers),
            included=included,
            excluded=excluded,
            uncertain=uncertain,
            screening_results=screening_results,
            bias_assessments=bias_assessments,
            study_types=dict(study_types),
            prisma_flow=prisma_flow,
        )

        self.print_report(report)
        return report

    def _fetch_papers(self, query: str, n: int) -> List[Paper]:
        """Fetch papers from OpenAlex"""
        try:
            return self.oa.search(query, per_page=min(n, 200))
        except Exception as e:
            print(f"  [!] Search failed: {e}")
            return []

    @staticmethod
    def print_report(report: SystematicReviewReport):
        """Print formatted report"""
        print(f"\n{'='*65}")
        print(f"  📋 Systematic Review Report")
        print(f"{'='*65}")
        print(f"  Query: \"{report.query}\"")

        # PRISMA Flow
        print(f"\n  📊 PRISMA Flow:")
        pf = report.prisma_flow
        print(f"    Identification → {pf.get('identification', 0)} records")
        print(f"    Screening      → {pf.get('screening', 0)} screened")
        print(f"    Eligibility    → {pf.get('eligibility', 0)} eligible")
        print(f"    Included       → {pf.get('included', 0)} included")

        # Screening stats
        total = report.total_screened or 1
        print(f"\n  🔍 Screening Results:")
        print(f"    ✅ Include:   {report.included:>4} ({report.included/total*100:.0f}%)")
        print(f"    ❌ Exclude:   {report.excluded:>4} ({report.excluded/total*100:.0f}%)")
        print(f"    ❓ Uncertain: {report.uncertain:>4} ({report.uncertain/total*100:.0f}%)")

        # Study types
        if report.study_types:
            print(f"\n  📐 Study Types:")
            for stype, count in sorted(report.study_types.items(), key=lambda x: -x[1]):
                bar = '█' * min(count * 2, 30)
                print(f"    {stype:<18} {bar} {count}")

        # Bias
        if report.bias_assessments:
            risks = Counter(a.overall_risk for a in report.bias_assessments)
            print(f"\n  ⚠️  Risk of Bias (included papers):")
            risk_icons = {'low': '🟢', 'unclear': '🟡', 'high': '🔴'}
            for risk, count in sorted(risks.items()):
                icon = risk_icons.get(risk, '·')
                print(f"    {icon} {risk:<10} {count}")

        print(f"\n{'='*65}")
