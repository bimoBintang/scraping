"""
Algorithm J17: Plagiarism Pattern Detection

Detect potential plagiarism via:
  1. Citation Pattern Analysis — anomalous reference behavior
  2. Text Similarity           — n-gram fingerprinting
  3. Self-Citation Detection   — excessive self-citation & rings
  4. Suspicion Scoring         — weighted aggregate score

Usage:
    from journal.plagiarism_detector import PlagiarismDetector

    detector = PlagiarismDetector()
    report = detector.analyze(text="...", doi="10.1234/...")
"""

import re
import math
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Set, Tuple

from .models import Paper, PlagiarismFlag, PlagiarismReport
from .api_client import OpenAlexClient


# ==================== CITATION PATTERN ANALYZER ====================

class CitationPatternAnalyzer:
    """
    Analyze citation patterns for anomalies.
    """

    # Expected citation density per 1000 words by field
    EXPECTED_DENSITY = {
        'default': (15, 50),  # min, max refs per paper
        'medical': (20, 60),
        'engineering': (10, 40),
        'social_science': (15, 50),
        'computer_science': (10, 45),
    }

    @classmethod
    def analyze(
        cls,
        text: str,
        references: Optional[List[str]] = None,
        paper_keywords: Optional[List[str]] = None,
    ) -> Tuple[float, List[PlagiarismFlag]]:
        """
        Analyze citation patterns.

        Args:
            text: Paper text
            references: List of reference strings
            paper_keywords: Paper topic keywords

        Returns:
            (anomaly_score 0-100, list of flags)
        """
        flags = []
        scores = []

        # 1. Citation density check
        density_score, density_flags = cls._check_citation_density(text, references)
        scores.append(density_score)
        flags.extend(density_flags)

        # 2. In-text citation pattern analysis
        pattern_score, pattern_flags = cls._check_citation_patterns(text)
        scores.append(pattern_score)
        flags.extend(pattern_flags)

        # 3. Reference age distribution
        age_score, age_flags = cls._check_reference_ages(references)
        scores.append(age_score)
        flags.extend(age_flags)

        # 4. Topic relevance of citations
        if paper_keywords and references:
            relevance_score, relevance_flags = cls._check_relevance(
                references, paper_keywords
            )
            scores.append(relevance_score)
            flags.extend(relevance_flags)

        anomaly_score = sum(scores) / len(scores) if scores else 0
        return anomaly_score, flags

    @classmethod
    def _check_citation_density(
        cls, text: str, references: Optional[List[str]]
    ) -> Tuple[float, List[PlagiarismFlag]]:
        """Check if citation density is anomalous"""
        flags = []

        # Count in-text citations
        inline_count = len(re.findall(
            r'\[[\d,\s–-]+\]|\((?:[A-Z][a-z]+(?:\s+(?:et\s+al\.?|&)\s+[A-Z][a-z]+)?,?\s*\d{4}(?:;\s*)?)+\)',
            text
        ))

        # Count references
        ref_count = len(references) if references else 0

        word_count = len(text.split())
        min_refs, max_refs = cls.EXPECTED_DENSITY['default']

        # Too few citations
        if word_count > 2000 and inline_count < 5:
            flags.append(PlagiarismFlag(
                flag_type='citation_density',
                severity='high',
                evidence=f'Only {inline_count} in-text citations in {word_count} words',
                score=30.0,
            ))
            return 30.0, flags

        # Too few references
        if ref_count > 0 and ref_count < min_refs // 2:
            flags.append(PlagiarismFlag(
                flag_type='citation_density',
                severity='medium',
                evidence=f'Only {ref_count} references (expected {min_refs}-{max_refs})',
                score=20.0,
            ))
            return 20.0, flags

        # Mismatch between in-text and reference list
        if ref_count > 0 and inline_count > 0:
            ratio = inline_count / ref_count if ref_count > 0 else 0
            if ratio > 3.0:
                flags.append(PlagiarismFlag(
                    flag_type='citation_density',
                    severity='medium',
                    evidence=f'Citation/reference ratio unusually high: {ratio:.1f}',
                    score=15.0,
                ))
                return 15.0, flags

        return 0.0, flags

    @classmethod
    def _check_citation_patterns(cls, text: str) -> Tuple[float, List[PlagiarismFlag]]:
        """Check for suspicious citation patterns"""
        flags = []
        score = 0.0

        # Detect citation clusters (many citations grouped together)
        clusters = re.findall(r'\[[\d,\s–-]{10,}\]', text)
        if len(clusters) > 5:
            flags.append(PlagiarismFlag(
                flag_type='citation_density',
                severity='medium',
                evidence=f'{len(clusters)} large citation clusters (possible padding)',
                score=15.0,
            ))
            score += 15.0

        # Check for sequential numbering gaps
        numbered_refs = re.findall(r'\[(\d+)\]', text)
        if numbered_refs:
            nums = sorted(set(int(n) for n in numbered_refs))
            gaps = sum(1 for i in range(len(nums) - 1) if nums[i+1] - nums[i] > 1)
            if gaps > 3:
                flags.append(PlagiarismFlag(
                    flag_type='missing_citation',
                    severity='medium',
                    evidence=f'{gaps} gaps in citation numbering',
                    score=10.0,
                ))
                score += 10.0

        return score, flags

    @classmethod
    def _check_reference_ages(
        cls, references: Optional[List[str]]
    ) -> Tuple[float, List[PlagiarismFlag]]:
        """Check reference age distribution"""
        if not references:
            return 0.0, []

        flags = []
        years = []
        for ref in references:
            year_match = re.search(r'\b(19\d{2}|20[0-2]\d)\b', ref)
            if year_match:
                years.append(int(year_match.group(1)))

        if not years:
            return 0.0, []

        # Check for unusual concentration of old references
        current_year = 2026
        old_count = sum(1 for y in years if current_year - y > 20)
        old_ratio = old_count / len(years)

        if old_ratio > 0.6:
            flags.append(PlagiarismFlag(
                flag_type='age_anomaly',
                severity='medium',
                evidence=f'{old_ratio*100:.0f}% of references are >20 years old',
                score=15.0,
            ))
            return 15.0, flags

        # Check for suspicious uniformity (all refs from same narrow period)
        if len(years) >= 5:
            year_range = max(years) - min(years)
            if year_range <= 2:
                flags.append(PlagiarismFlag(
                    flag_type='age_anomaly',
                    severity='high',
                    evidence=f'All references from {min(years)}-{max(years)} (suspiciously narrow)',
                    score=20.0,
                ))
                return 20.0, flags

        return 0.0, flags

    @classmethod
    def _check_relevance(
        cls,
        references: List[str],
        keywords: List[str],
    ) -> Tuple[float, List[PlagiarismFlag]]:
        """Check if references match paper topic"""
        flags = []
        kw_lower = {k.lower() for k in keywords}

        # Check how many references contain at least one keyword
        relevant = 0
        for ref in references:
            ref_lower = ref.lower()
            if any(kw in ref_lower for kw in kw_lower):
                relevant += 1

        if len(references) >= 10:
            relevance_ratio = relevant / len(references)
            if relevance_ratio < 0.1:
                flags.append(PlagiarismFlag(
                    flag_type='irrelevant_citation',
                    severity='high',
                    evidence=f'Only {relevance_ratio*100:.0f}% of references match paper keywords',
                    score=25.0,
                ))
                return 25.0, flags

        return 0.0, flags


# ==================== TEXT SIMILARITY CHECKER ====================

class TextSimilarityChecker:
    """
    Check text similarity using n-gram fingerprinting.
    """

    @classmethod
    def compute_similarity(
        cls,
        text_a: str,
        text_b: str,
        n: int = 5,
    ) -> Dict:
        """
        Compute similarity between two texts.

        Args:
            text_a: First text
            text_b: Second text
            n: N-gram size (shingle size)

        Returns:
            Dict with jaccard, overlap, lcs_ratio scores
        """
        # Normalize texts
        norm_a = cls._normalize(text_a)
        norm_b = cls._normalize(text_b)

        if not norm_a or not norm_b:
            return {'jaccard': 0.0, 'overlap': 0.0, 'lcs_ratio': 0.0}

        # N-gram fingerprints
        shingles_a = cls._get_shingles(norm_a, n)
        shingles_b = cls._get_shingles(norm_b, n)

        # Jaccard similarity
        intersection = shingles_a & shingles_b
        union = shingles_a | shingles_b
        jaccard = len(intersection) / len(union) if union else 0.0

        # Overlap coefficient (good for different-length texts)
        min_size = min(len(shingles_a), len(shingles_b))
        overlap = len(intersection) / min_size if min_size > 0 else 0.0

        # LCS ratio (approximate via word-level)
        words_a = norm_a.split()
        words_b = norm_b.split()
        lcs_len = cls._lcs_length(words_a[:200], words_b[:200])  # limit for performance
        max_len = max(len(words_a), len(words_b))
        lcs_ratio = lcs_len / max_len if max_len > 0 else 0.0

        return {
            'jaccard': round(jaccard, 4),
            'overlap': round(overlap, 4),
            'lcs_ratio': round(lcs_ratio, 4),
        }

    @classmethod
    def check_text(cls, text: str) -> Tuple[float, List[PlagiarismFlag]]:
        """
        Check text for internal suspicious patterns.

        Args:
            text: Paper text to check

        Returns:
            (score, flags)
        """
        flags = []
        score = 0.0

        # Check for style inconsistencies (sudden vocabulary changes)
        paragraphs = [p.strip() for p in text.split('\n\n') if len(p.strip()) > 50]
        if len(paragraphs) >= 3:
            vocab_sizes = []
            for para in paragraphs:
                words = set(para.lower().split())
                vocab_sizes.append(len(words))

            if vocab_sizes:
                avg_vocab = sum(vocab_sizes) / len(vocab_sizes)
                variance = sum((v - avg_vocab) ** 2 for v in vocab_sizes) / len(vocab_sizes)
                std_dev = math.sqrt(variance)

                if std_dev > avg_vocab * 0.6:
                    flags.append(PlagiarismFlag(
                        flag_type='text_similarity',
                        severity='medium',
                        evidence=f'High vocabulary variance across paragraphs (σ={std_dev:.1f}, μ={avg_vocab:.1f})',
                        score=15.0,
                    ))
                    score += 15.0

        # Check for duplicated sentences
        sentences = re.split(r'[.!?]+', text)
        sentence_set = set()
        duplicates = 0
        for sent in sentences:
            clean = sent.strip().lower()
            if len(clean) > 30:
                if clean in sentence_set:
                    duplicates += 1
                sentence_set.add(clean)

        if duplicates > 2:
            flags.append(PlagiarismFlag(
                flag_type='text_similarity',
                severity='high',
                evidence=f'{duplicates} duplicated sentences detected',
                score=20.0,
            ))
            score += 20.0

        return score, flags

    @classmethod
    def _normalize(cls, text: str) -> str:
        """Normalize text for comparison"""
        text = text.lower()
        text = re.sub(r'[^\w\s]', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    @classmethod
    def _get_shingles(cls, text: str, n: int) -> Set[str]:
        """Get n-gram shingles"""
        words = text.split()
        if len(words) < n:
            return {text}
        return {' '.join(words[i:i+n]) for i in range(len(words) - n + 1)}

    @classmethod
    def _lcs_length(cls, a: List[str], b: List[str]) -> int:
        """Longest common subsequence length (DP)"""
        m, n = len(a), len(b)
        if m == 0 or n == 0:
            return 0

        # Space-optimized LCS
        prev = [0] * (n + 1)
        curr = [0] * (n + 1)

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if a[i-1] == b[j-1]:
                    curr[j] = prev[j-1] + 1
                else:
                    curr[j] = max(prev[j], curr[j-1])
            prev, curr = curr, [0] * (n + 1)

        return prev[n]


# ==================== SELF-CITATION DETECTOR ====================

class SelfCitationDetector:
    """
    Detect excessive self-citation and citation rings.
    """

    # Thresholds
    NORMAL_SELF_CITE_RATIO = 0.15   # <15% is normal
    HIGH_SELF_CITE_RATIO = 0.30     # >30% is suspicious
    CRITICAL_SELF_CITE_RATIO = 0.50 # >50% is very suspicious

    @classmethod
    def detect(
        cls,
        author_names: List[str],
        references: List[str],
    ) -> Tuple[float, float, List[PlagiarismFlag]]:
        """
        Detect self-citation patterns.

        Args:
            author_names: Paper's author names
            references: Reference list strings

        Returns:
            (self_cite_ratio, score, flags)
        """
        if not author_names or not references:
            return 0.0, 0.0, []

        flags = []
        self_cite_count = 0

        # Normalize author names
        author_parts = set()
        for name in author_names:
            parts = name.lower().split()
            for part in parts:
                if len(part) > 2:  # skip initials
                    author_parts.add(part)

        # Count self-citations
        for ref in references:
            ref_lower = ref.lower()
            matches = sum(1 for part in author_parts if part in ref_lower)
            if matches >= 1:
                self_cite_count += 1

        ratio = self_cite_count / len(references) if references else 0
        score = 0.0

        if ratio >= cls.CRITICAL_SELF_CITE_RATIO:
            flags.append(PlagiarismFlag(
                flag_type='self_citation',
                severity='high',
                evidence=f'Self-citation ratio: {ratio*100:.0f}% ({self_cite_count}/{len(references)})',
                score=30.0,
            ))
            score = 30.0
        elif ratio >= cls.HIGH_SELF_CITE_RATIO:
            flags.append(PlagiarismFlag(
                flag_type='self_citation',
                severity='medium',
                evidence=f'High self-citation ratio: {ratio*100:.0f}% ({self_cite_count}/{len(references)})',
                score=15.0,
            ))
            score = 15.0
        elif ratio >= cls.NORMAL_SELF_CITE_RATIO:
            flags.append(PlagiarismFlag(
                flag_type='self_citation',
                severity='low',
                evidence=f'Moderate self-citation: {ratio*100:.0f}%',
                score=5.0,
            ))
            score = 5.0

        # Check for citation ring patterns (same co-author combinations)
        ring_score, ring_flags = cls._detect_rings(references)
        flags.extend(ring_flags)
        score += ring_score

        return ratio, score, flags

    @classmethod
    def _detect_rings(cls, references: List[str]) -> Tuple[float, List[PlagiarismFlag]]:
        """Detect citation ring patterns"""
        flags = []

        # Extract author groups from references
        author_groups = []
        for ref in references:
            # Extract names (simple heuristic: capitalized words before year)
            names = re.findall(r'\b([A-Z][a-z]+)\b', ref)
            if names:
                author_groups.append(frozenset(n.lower() for n in names[:5]))

        # Find repeated author groups
        group_counts = Counter(author_groups)
        repeated = {g: c for g, c in group_counts.items() if c >= 3 and len(g) >= 2}

        if repeated:
            most_common = max(repeated.items(), key=lambda x: x[1])
            flags.append(PlagiarismFlag(
                flag_type='citation_ring',
                severity='high',
                evidence=f'Same author group cited {most_common[1]} times: {set(most_common[0])}',
                score=20.0,
            ))
            return 20.0, flags

        return 0.0, flags


# ==================== PLAGIARISM DETECTOR ====================

class PlagiarismDetector:
    """
    Full plagiarism detection pipeline.
    """

    # Weight for each component
    WEIGHTS = {
        'citation_pattern': 0.30,
        'text_analysis': 0.30,
        'self_citation': 0.25,
        'text_comparison': 0.15,
    }

    def __init__(self, openalex: Optional[OpenAlexClient] = None):
        self.oa = openalex or OpenAlexClient()

    def analyze(
        self,
        text: str = "",
        doi: str = "",
        references: Optional[List[str]] = None,
        author_names: Optional[List[str]] = None,
        compare_texts: Optional[List[str]] = None,
    ) -> PlagiarismReport:
        """
        Run plagiarism detection pipeline.

        Args:
            text: Paper text/abstract
            doi: Paper DOI (for metadata lookup)
            references: Reference list
            author_names: Author names
            compare_texts: Other texts to compare against

        Returns:
            PlagiarismReport
        """
        print(f"\n  [🔍] Plagiarism Pattern Detector")

        report = PlagiarismReport(paper_doi=doi)

        # Try to fetch metadata if DOI provided
        if doi and not text:
            paper = self._fetch_paper(doi)
            if paper:
                text = f"{paper.title or ''} {paper.abstract or ''}"
                report.paper_title = paper.title or ''
                if paper.author_names and not author_names:
                    author_names = paper.author_names

        if text and not report.paper_title:
            report.paper_title = text[:60] + "..."

        print(f"  [·] Analyzing: \"{report.paper_title[:50]}\"")

        component_scores = {}

        # 1. Citation pattern analysis
        print(f"  [·] Checking citation patterns...")
        citation_score, citation_flags = CitationPatternAnalyzer.analyze(
            text, references, None
        )
        component_scores['citation_pattern'] = citation_score
        report.flags.extend(citation_flags)
        report.citation_anomaly_score = citation_score
        print(f"  [✓] Citation anomaly: {citation_score:.0f}/100")

        # 2. Text analysis
        print(f"  [·] Analyzing text patterns...")
        text_score, text_flags = TextSimilarityChecker.check_text(text)
        component_scores['text_analysis'] = text_score
        report.flags.extend(text_flags)
        print(f"  [✓] Text analysis: {text_score:.0f}/100")

        # 3. Self-citation detection
        if author_names and references:
            print(f"  [·] Checking self-citations...")
            self_ratio, self_score, self_flags = SelfCitationDetector.detect(
                author_names, references
            )
            component_scores['self_citation'] = self_score
            report.self_citation_ratio = self_ratio
            report.flags.extend(self_flags)
            print(f"  [✓] Self-citation ratio: {self_ratio*100:.0f}%")
        else:
            component_scores['self_citation'] = 0.0

        # 4. Text comparison
        if compare_texts:
            print(f"  [·] Comparing against {len(compare_texts)} texts...")
            max_sim = 0.0
            for i, comp_text in enumerate(compare_texts):
                sim = TextSimilarityChecker.compute_similarity(text, comp_text)
                report.text_similarity_scores.append({
                    'compared_with': f'text_{i}',
                    **sim,
                })
                max_sim = max(max_sim, sim['jaccard'])

            if max_sim > 0.5:
                report.flags.append(PlagiarismFlag(
                    flag_type='text_similarity',
                    severity='critical' if max_sim > 0.8 else 'high',
                    evidence=f'High text similarity detected: {max_sim*100:.0f}%',
                    score=max_sim * 50,
                ))
            component_scores['text_comparison'] = max_sim * 50
            print(f"  [✓] Max similarity: {max_sim*100:.1f}%")
        else:
            component_scores['text_comparison'] = 0.0

        # Compute final suspicion score
        total = 0.0
        for key, weight in self.WEIGHTS.items():
            total += component_scores.get(key, 0) * weight

        report.suspicion_score = min(total, 100)
        report.risk_level = self._get_risk_level(report.suspicion_score)

        # Generate recommendations
        report.recommendations = self._generate_recommendations(report)

        self.print_report(report)
        return report

    def _fetch_paper(self, doi: str) -> Optional[Paper]:
        """Fetch paper metadata"""
        try:
            results = self.oa.search(doi, per_page=1)
            return results[0] if results else None
        except Exception:
            return None

    @staticmethod
    def _get_risk_level(score: float) -> str:
        """Map score to risk level"""
        if score >= 50:
            return 'critical'
        elif score >= 30:
            return 'high'
        elif score >= 15:
            return 'medium'
        return 'low'

    @staticmethod
    def _generate_recommendations(report: PlagiarismReport) -> List[str]:
        """Generate recommendations based on flags"""
        recs = []
        flag_types = {f.flag_type for f in report.flags}

        if 'missing_citation' in flag_types:
            recs.append('Review citation numbering for missing references')
        if 'irrelevant_citation' in flag_types:
            recs.append('Verify topic relevance of cited references')
        if 'self_citation' in flag_types:
            recs.append('Review self-citation ratio; consider citing more external work')
        if 'citation_ring' in flag_types:
            recs.append('Investigate possible citation ring among co-authors')
        if 'text_similarity' in flag_types:
            recs.append('Check for copied text; paraphrase or properly attribute')
        if 'citation_density' in flag_types:
            recs.append('Adjust citation density to match field norms')
        if 'age_anomaly' in flag_types:
            recs.append('Include more recent references to show awareness of current work')

        if not recs:
            recs.append('No significant plagiarism indicators detected')

        return recs

    @staticmethod
    def print_report(report: PlagiarismReport):
        """Print formatted report"""
        risk_icons = {'low': '🟢', 'medium': '🟡', 'high': '🔴', 'critical': '🚨'}
        icon = risk_icons.get(report.risk_level, '·')

        print(f"\n{'='*65}")
        print(f"  🔍 Plagiarism Pattern Report")
        print(f"{'='*65}")
        print(f"  Paper: \"{report.paper_title[:50]}\"")
        print(f"  DOI:   {report.paper_doi or 'N/A'}")

        print(f"\n  {icon} Suspicion Score: {report.suspicion_score:.0f}/100 ({report.risk_level.upper()})")

        if report.flags:
            print(f"\n  ⚠️  Flags ({len(report.flags)}):")
            severity_icons = {'low': '🔵', 'medium': '🟡', 'high': '🔴', 'critical': '🚨'}
            for flag in sorted(report.flags, key=lambda f: -f.score):
                si = severity_icons.get(flag.severity, '·')
                print(f"    {si} [{flag.flag_type}] {flag.evidence}")

        if report.self_citation_ratio > 0:
            print(f"\n  📊 Self-citation ratio: {report.self_citation_ratio*100:.0f}%")

        if report.text_similarity_scores:
            print(f"\n  📝 Text Similarity:")
            for sim in report.text_similarity_scores:
                print(f"    vs {sim['compared_with']}: Jaccard={sim['jaccard']:.2f}, Overlap={sim['overlap']:.2f}")

        if report.recommendations:
            print(f"\n  💡 Recommendations:")
            for rec in report.recommendations:
                print(f"    • {rec}")

        print(f"\n{'='*65}")
