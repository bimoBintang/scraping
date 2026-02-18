"""
Algorithm J11: Cross-Reference Validator

Verify citation accuracy by matching in-text citations to bibliography entries
using string matching and fuzzy logic.

Detections:
  - Missing references (cited but not in bibliography)
  - Orphan entries (in bibliography but never cited)
  - Format inconsistency (mixed APA/IEEE styles)
  - Year mismatch (citation year ≠ bibliography year)
  - Duplicate bibliography entries
  - DOI verification via CrossRef

Usage:
    from journal.reference_validator import CrossReferenceValidator

    validator = CrossReferenceValidator()
    report = validator.validate(paper_text, bibliography_text)
    validator.print_report(report)
"""

import re
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Set, Tuple

from .models import ValidationIssue, ValidationReport
from .api_client import CrossRefClient


# ==================== CITATION EXTRACTOR ====================

class CitationExtractor:
    """
    Extract in-text citations from paper text.

    Supports:
      - APA: (Author, 2024), (Author & Author, 2024), Author (2024)
      - et al.: (Author et al., 2024)
      - Numbered: [1], [1,2], [1-3]
    """

    # APA patterns
    APA_PAREN = re.compile(
        r'\(([A-Z][a-zA-Z\'\-]+(?:\s+(?:&|and)\s+[A-Z][a-zA-Z\'\-]+)?'
        r'(?:\s+et\s+al\.?)?),?\s*(\d{4}[a-z]?)\)',
    )

    APA_NARRATIVE = re.compile(
        r'([A-Z][a-zA-Z\'\-]+(?:\s+(?:&|and)\s+[A-Z][a-zA-Z\'\-]+)?'
        r'(?:\s+et\s+al\.?)?)\s+\((\d{4}[a-z]?)\)',
    )

    # Multi-citation: (Author, 2020; Author, 2021)
    APA_MULTI = re.compile(
        r'\(([^)]+;\s*[^)]+)\)',
    )

    # Numbered: [1], [1, 2], [1-3]
    NUMBERED = re.compile(
        r'\[(\d+(?:\s*[,\-–]\s*\d+)*)\]',
    )

    @classmethod
    def extract(cls, text: str) -> List[Dict]:
        """
        Extract all citations from text.

        Returns:
            List of dicts with 'author', 'year', 'style', 'raw' keys
        """
        citations = []
        seen = set()

        # 1. APA parenthetical: (Author, 2024)
        for m in cls.APA_PAREN.finditer(text):
            author = m.group(1).strip()
            year = m.group(2).strip()
            key = (author.lower(), year)
            if key not in seen:
                seen.add(key)
                citations.append({
                    'author': author,
                    'year': year,
                    'style': 'apa',
                    'raw': m.group(0),
                    'start': m.start(),
                })

        # 2. APA narrative: Author (2024)
        for m in cls.APA_NARRATIVE.finditer(text):
            author = m.group(1).strip()
            year = m.group(2).strip()
            key = (author.lower(), year)
            if key not in seen:
                seen.add(key)
                citations.append({
                    'author': author,
                    'year': year,
                    'style': 'apa',
                    'raw': m.group(0),
                    'start': m.start(),
                })

        # 3. Multi-citation: (Smith, 2020; Jones, 2021)
        for m in cls.APA_MULTI.finditer(text):
            inner = m.group(1)
            parts = inner.split(';')
            for part in parts:
                sub_match = re.match(
                    r'\s*([A-Z][a-zA-Z\'\-]+(?:\s+et\s+al\.?)?),?\s*(\d{4}[a-z]?)',
                    part.strip(),
                )
                if sub_match:
                    author = sub_match.group(1).strip()
                    year = sub_match.group(2).strip()
                    key = (author.lower(), year)
                    if key not in seen:
                        seen.add(key)
                        citations.append({
                            'author': author,
                            'year': year,
                            'style': 'apa',
                            'raw': part.strip(),
                            'start': m.start(),
                        })

        # 4. Numbered: [1], [2,3], [4-6]
        for m in cls.NUMBERED.finditer(text):
            raw = m.group(1)
            nums = cls._parse_numbers(raw)
            for num in nums:
                key = ('__num__', str(num))
                if key not in seen:
                    seen.add(key)
                    citations.append({
                        'author': '',
                        'year': '',
                        'number': num,
                        'style': 'numbered',
                        'raw': m.group(0),
                        'start': m.start(),
                    })

        return citations

    @staticmethod
    def _parse_numbers(raw: str) -> List[int]:
        """Parse '1, 2, 4-6' into [1, 2, 4, 5, 6]"""
        nums = []
        parts = re.split(r'[,\s]+', raw)
        for part in parts:
            if '-' in part or '–' in part:
                bounds = re.split(r'[\-–]', part)
                if len(bounds) == 2 and bounds[0].strip().isdigit() and bounds[1].strip().isdigit():
                    start = int(bounds[0].strip())
                    end = int(bounds[1].strip())
                    nums.extend(range(start, end + 1))
            elif part.strip().isdigit():
                nums.append(int(part.strip()))
        return nums

    @classmethod
    def detect_style(cls, citations: List[Dict]) -> str:
        """Detect dominant citation style"""
        styles = Counter(c['style'] for c in citations)
        if not styles:
            return 'unknown'
        return styles.most_common(1)[0][0]


# ==================== BIBLIOGRAPHY PARSER ====================

class BibliographyParser:
    """
    Parse bibliography/reference list entries.

    Auto-detects: APA, IEEE numbered, generic
    """

    @classmethod
    def parse(cls, text: str) -> List[Dict]:
        """
        Parse bibliography text into structured entries.

        Returns:
            List of dicts with 'author', 'year', 'title', 'number', 'raw'
        """
        lines = text.strip().split('\n')
        entries = []
        current = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if current:
                    entries.append(' '.join(current))
                    current = []
                continue

            # Check if new entry starts (numbered or author)
            if re.match(r'^\[\d+\]', stripped) or re.match(r'^\d+\.', stripped):
                if current:
                    entries.append(' '.join(current))
                    current = []
            elif current and re.match(r'^[A-Z][a-zA-Z]', stripped):
                # Possible new APA entry
                if len(current) >= 1 and re.search(r'\d{4}', ' '.join(current)):
                    entries.append(' '.join(current))
                    current = []

            current.append(stripped)

        if current:
            entries.append(' '.join(current))

        # Parse each entry
        parsed = []
        for i, entry_text in enumerate(entries):
            parsed_entry = cls._parse_entry(entry_text, i + 1)
            if parsed_entry:
                parsed.append(parsed_entry)

        return parsed

    @classmethod
    def _parse_entry(cls, text: str, index: int) -> Optional[Dict]:
        """Parse a single bibliography entry"""
        entry = {
            'raw': text,
            'index': index,
            'author': '',
            'year': '',
            'title': '',
            'number': None,
        }

        # Check for numbered: [1] or 1.
        num_match = re.match(r'^\[(\d+)\]\s*', text)
        if num_match:
            entry['number'] = int(num_match.group(1))
            text = text[num_match.end():]
        else:
            num_match = re.match(r'^(\d+)\.\s*', text)
            if num_match:
                entry['number'] = int(num_match.group(1))
                text = text[num_match.end():]

        # Extract year
        year_match = re.search(r'\((\d{4}[a-z]?)\)', text)
        if year_match:
            entry['year'] = year_match.group(1)

        # Extract author (text before year or first period)
        if year_match:
            author_part = text[:year_match.start()].strip().rstrip(',').rstrip('.')
        else:
            # Try to find author before title
            period_pos = text.find('.')
            if period_pos > 0:
                author_part = text[:period_pos].strip()
            else:
                author_part = text[:30].strip()
        entry['author'] = author_part

        # Extract title
        title_match = re.search(r'["\u201c](.+?)["\u201d]', text)
        if title_match:
            entry['title'] = title_match.group(1)
        elif year_match:
            after_year = text[year_match.end():].strip().lstrip('.')
            period = after_year.find('.')
            if period > 0:
                entry['title'] = after_year[:period].strip()
            else:
                entry['title'] = after_year[:80].strip()

        # Extract DOI
        doi_match = re.search(r'(?:doi:\s*|https?://doi\.org/)(10\.\d{4,}/\S+)', text, re.IGNORECASE)
        if doi_match:
            entry['doi'] = doi_match.group(1).rstrip('.')

        return entry


# ==================== FUZZY MATCHER ====================

class FuzzyMatcher:
    """
    Fuzzy string matching for citation-bibliography matching.

    Uses combined Levenshtein-like distance + token overlap.
    """

    @staticmethod
    def similarity(s1: str, s2: str) -> float:
        """
        Compute similarity between two strings (0.0–1.0).

        Combines:
          - Token-based Jaccard similarity (60%)
          - Character-level subsequence similarity (40%)
        """
        if not s1 or not s2:
            return 0.0

        s1_lower = s1.lower().strip()
        s2_lower = s2.lower().strip()

        if s1_lower == s2_lower:
            return 1.0

        # Token Jaccard
        tokens1 = set(re.findall(r'\b\w+\b', s1_lower))
        tokens2 = set(re.findall(r'\b\w+\b', s2_lower))
        if tokens1 and tokens2:
            jaccard = len(tokens1 & tokens2) / len(tokens1 | tokens2)
        else:
            jaccard = 0.0

        # Longest common subsequence ratio
        lcs_len = FuzzyMatcher._lcs_length(s1_lower, s2_lower)
        lcs_ratio = (2 * lcs_len) / (len(s1_lower) + len(s2_lower))

        return jaccard * 0.6 + lcs_ratio * 0.4

    @staticmethod
    def _lcs_length(s1: str, s2: str) -> int:
        """Compute length of longest common subsequence"""
        m, n = len(s1), len(s2)
        # Optimize: use two rows instead of full matrix
        if m > n:
            s1, s2 = s2, s1
            m, n = n, m

        prev = [0] * (n + 1)
        curr = [0] * (n + 1)

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if s1[i - 1] == s2[j - 1]:
                    curr[j] = prev[j - 1] + 1
                else:
                    curr[j] = max(prev[j], curr[j - 1])
            prev, curr = curr, [0] * (n + 1)

        return prev[n]

    @classmethod
    def best_match(
        cls,
        citation_author: str,
        bib_entries: List[Dict],
        threshold: float = 0.4,
    ) -> Optional[Tuple[Dict, float]]:
        """
        Find best matching bibliography entry for a citation.

        Args:
            citation_author: Author string from citation
            bib_entries: Parsed bibliography entries
            threshold: Minimum similarity to consider a match

        Returns:
            (best_entry, confidence) or None
        """
        if not citation_author or not bib_entries:
            return None

        best = None
        best_score = 0.0

        # Normalize citation author
        cite_norm = citation_author.replace(' et al.', '').replace(' et al', '').strip()

        for entry in bib_entries:
            bib_author = entry.get('author', '')

            # Author similarity
            score = cls.similarity(cite_norm, bib_author)

            # Check if citation author's last name appears in bib author
            last_name = cite_norm.split()[-1] if cite_norm.split() else ''
            if last_name and last_name.lower() in bib_author.lower():
                score = max(score, 0.6)

            # First author last name match → strong signal
            bib_first_last = bib_author.split(',')[0].strip().split()[-1] if bib_author else ''
            if last_name and bib_first_last and last_name.lower() == bib_first_last.lower():
                score = max(score, 0.85)

            if score > best_score:
                best_score = score
                best = entry

        if best_score >= threshold:
            return (best, best_score)
        return None


# ==================== CROSS-REFERENCE VALIDATOR ====================

class CrossReferenceValidator:
    """
    Validate cross-references between citations and bibliography.
    """

    def __init__(self, crossref: Optional[CrossRefClient] = None):
        self.crossref = crossref or CrossRefClient()
        self.extractor = CitationExtractor()
        self.parser = BibliographyParser()
        self.matcher = FuzzyMatcher()

    def validate(
        self,
        paper_text: str,
        bibliography_text: Optional[str] = None,
        verify_doi: bool = False,
    ) -> ValidationReport:
        """
        Validate cross-references in a paper.

        Args:
            paper_text: Full paper text (or body text)
            bibliography_text: Bibliography section (auto-extracted if None)
            verify_doi: Whether to verify DOIs via CrossRef

        Returns:
            ValidationReport with all issues found
        """
        print(f"\n  [🔍] Cross-Reference Validator")

        # Auto-split if bibliography not provided
        if bibliography_text is None:
            paper_text, bibliography_text = self._split_paper(paper_text)

        # Extract citations
        citations = self.extractor.extract(paper_text)
        print(f"  [✓] {len(citations)} in-text citations found")

        # Parse bibliography
        bib_entries = self.parser.parse(bibliography_text)
        print(f"  [✓] {len(bib_entries)} bibliography entries parsed")

        # Detect citation style
        style = self.extractor.detect_style(citations)
        print(f"  [·] Citation style: {style}")

        issues = []
        matched = 0
        matched_bib_indices = set()

        if style == 'numbered':
            matched, issues, matched_bib_indices = self._validate_numbered(
                citations, bib_entries
            )
        else:
            matched, issues, matched_bib_indices = self._validate_apa(
                citations, bib_entries
            )

        # Check for orphan bibliography entries
        for entry in bib_entries:
            idx = entry.get('index', 0)
            if idx not in matched_bib_indices:
                issues.append(ValidationIssue(
                    issue_type='orphan_entry',
                    severity='warning',
                    description=f"Bibliography entry never cited in text",
                    location=f"bib entry #{idx}",
                    citation_text=entry.get('raw', '')[:80],
                    suggestion="Remove unused entry or add citation in text",
                ))

        # Check for format inconsistency
        format_issues = self._check_format_consistency(citations)
        issues.extend(format_issues)

        # Check for duplicates in bibliography
        dup_issues = self._check_duplicates(bib_entries)
        issues.extend(dup_issues)

        # DOI verification
        if verify_doi:
            doi_issues = self._verify_dois(bib_entries)
            issues.extend(doi_issues)

        # Count by type
        type_counts = Counter(i.issue_type for i in issues)

        # Compute accuracy score
        total = max(len(citations), 1)
        accuracy = matched / total

        report = ValidationReport(
            total_citations=len(citations),
            total_bib_entries=len(bib_entries),
            matched=matched,
            issues=issues,
            missing_refs=type_counts.get('missing_ref', 0),
            orphan_entries=type_counts.get('orphan_entry', 0),
            format_issues=type_counts.get('format_issue', 0),
            year_mismatches=type_counts.get('year_mismatch', 0),
            duplicates=type_counts.get('duplicate', 0),
            accuracy_score=round(accuracy, 3),
        )

        self.print_report(report)
        return report

    def _validate_numbered(
        self,
        citations: List[Dict],
        bib_entries: List[Dict],
    ) -> Tuple[int, List[ValidationIssue], Set[int]]:
        """Validate numbered citation style"""
        issues = []
        matched = 0
        matched_indices = set()

        bib_by_num = {e.get('number'): e for e in bib_entries if e.get('number')}
        max_bib = max(bib_by_num.keys()) if bib_by_num else 0

        for cit in citations:
            num = cit.get('number')
            if num is None:
                continue

            if num in bib_by_num:
                matched += 1
                matched_indices.add(bib_by_num[num].get('index', 0))
            else:
                issues.append(ValidationIssue(
                    issue_type='missing_ref',
                    severity='error',
                    description=f"Citation [{num}] has no matching bibliography entry"
                                + (f" (max entry is [{max_bib}])" if num > max_bib else ""),
                    citation_text=cit.get('raw', ''),
                    suggestion=f"Add bibliography entry [{num}]",
                ))

        return matched, issues, matched_indices

    def _validate_apa(
        self,
        citations: List[Dict],
        bib_entries: List[Dict],
    ) -> Tuple[int, List[ValidationIssue], Set[int]]:
        """Validate APA-style citations"""
        issues = []
        matched = 0
        matched_indices = set()

        for cit in citations:
            author = cit.get('author', '')
            year = cit.get('year', '')

            if not author:
                continue

            result = self.matcher.best_match(author, bib_entries)

            if result:
                entry, confidence = result
                matched += 1
                matched_indices.add(entry.get('index', 0))

                # Check year mismatch
                bib_year = entry.get('year', '')
                if year and bib_year and year != bib_year:
                    issues.append(ValidationIssue(
                        issue_type='year_mismatch',
                        severity='warning',
                        description=f"Year mismatch: citation says {year}, "
                                    f"bibliography says {bib_year}",
                        citation_text=cit.get('raw', ''),
                        suggestion=f"Verify correct year: {year} vs {bib_year}",
                    ))
            else:
                issues.append(ValidationIssue(
                    issue_type='missing_ref',
                    severity='error',
                    description=f"No bibliography entry found for \"{author}\"",
                    citation_text=cit.get('raw', ''),
                    suggestion=f"Add bibliography entry for {author} ({year})",
                ))

        return matched, issues, matched_indices

    @staticmethod
    def _check_format_consistency(citations: List[Dict]) -> List[ValidationIssue]:
        """Check for mixed citation styles"""
        styles = Counter(c['style'] for c in citations)
        issues = []

        if len(styles) > 1:
            style_desc = ", ".join(f"{s}: {n}" for s, n in styles.most_common())
            issues.append(ValidationIssue(
                issue_type='format_issue',
                severity='warning',
                description=f"Mixed citation styles detected: {style_desc}",
                suggestion="Use a consistent citation style throughout",
            ))

        return issues

    @staticmethod
    def _check_duplicates(bib_entries: List[Dict]) -> List[ValidationIssue]:
        """Check for duplicate bibliography entries"""
        issues = []
        seen = {}

        for entry in bib_entries:
            # Create a normalized key
            author = entry.get('author', '').lower().strip()
            year = entry.get('year', '')
            key = f"{author}_{year}"

            if key in seen and author:
                issues.append(ValidationIssue(
                    issue_type='duplicate',
                    severity='warning',
                    description=f"Possible duplicate: entries #{seen[key]} and #{entry.get('index', '?')}",
                    citation_text=entry.get('raw', '')[:80],
                    suggestion="Remove duplicate bibliography entry",
                ))
            else:
                seen[key] = entry.get('index', '?')

        return issues

    def _verify_dois(self, bib_entries: List[Dict]) -> List[ValidationIssue]:
        """Verify DOIs via CrossRef"""
        issues = []

        for entry in bib_entries:
            doi = entry.get('doi')
            if not doi:
                continue

            try:
                papers = self.crossref.search(f"doi:{doi}", rows=1)
                if not papers:
                    issues.append(ValidationIssue(
                        issue_type='doi_mismatch',
                        severity='error',
                        description=f"DOI {doi} could not be verified",
                        location=f"bib entry #{entry.get('index', '?')}",
                        suggestion="Check if DOI is correct",
                    ))
            except Exception:
                pass

        return issues

    @staticmethod
    def _split_paper(text: str) -> Tuple[str, str]:
        """
        Split paper text into body and bibliography sections.
        """
        # Look for common bibliography headers
        patterns = [
            r'\n\s*References?\s*\n',
            r'\n\s*Bibliography\s*\n',
            r'\n\s*Works?\s+Cited\s*\n',
            r'\n\s*Literature\s+Cited\s*\n',
            r'\n\s*REFERENCES?\s*\n',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return text[:match.start()], text[match.end():]

        # Fallback: last 30% of text is bibliography
        split_point = int(len(text) * 0.7)
        return text[:split_point], text[split_point:]

    @staticmethod
    def print_report(report: ValidationReport):
        """Print formatted validation report"""
        print(f"\n{'='*65}")
        print(f"  🔍 Cross-Reference Validation Report")
        print(f"{'='*65}")
        print(f"  Citations found:     {report.total_citations}")
        print(f"  Bibliography entries: {report.total_bib_entries}")
        print(f"  Matched:             {report.matched}")

        # Score bar
        bar_len = int(report.accuracy_score * 30)
        bar = '█' * bar_len + '░' * (30 - bar_len)
        pct = report.accuracy_score * 100
        print(f"\n  Accuracy: {pct:.1f}%")
        print(f"  [{bar}]")

        # Issue summary
        if report.issues:
            print(f"\n  ⚠️ Issues Found ({len(report.issues)}):")
            print(f"  {'─'*55}")

            icons = {
                'missing_ref': '❌',
                'orphan_entry': '👻',
                'format_issue': '📋',
                'year_mismatch': '📅',
                'duplicate': '♊',
                'doi_mismatch': '🔗',
            }

            if report.missing_refs:
                print(f"    ❌ Missing references: {report.missing_refs}")
            if report.orphan_entries:
                print(f"    👻 Orphan entries:     {report.orphan_entries}")
            if report.format_issues:
                print(f"    📋 Format issues:      {report.format_issues}")
            if report.year_mismatches:
                print(f"    📅 Year mismatches:    {report.year_mismatches}")
            if report.duplicates:
                print(f"    ♊ Duplicates:          {report.duplicates}")

            print(f"\n  Details:")
            for i, issue in enumerate(report.issues[:15], 1):
                icon = icons.get(issue.issue_type, '·')
                sev = issue.severity.upper()
                print(f"    {i}. [{sev}] {icon} {issue.description}")
                if issue.suggestion:
                    print(f"       💡 {issue.suggestion}")
        else:
            print(f"\n  ✅ No issues found — all references valid!")

        print(f"\n{'='*65}")
