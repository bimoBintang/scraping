"""
Algorithm J18: Reviewer Matching System

Recommend reviewers via:
  1. Expertise Matching   — TF-IDF cosine similarity
  2. Conflict Detection   — co-authorship, affiliation overlap
  3. Reviewer Ranking     — weighted scoring with justification

Usage:
    from journal.reviewer_matcher import ReviewerMatcher

    matcher = ReviewerMatcher()
    report = matcher.match("deep learning medical imaging", n_candidates=10)
"""

import re
import math
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Set, Tuple

from .models import Paper, Author, ReviewerCandidate, ReviewerMatchReport
from .api_client import OpenAlexClient


# ==================== TF-IDF ENGINE ====================

class TfIdfEngine:
    """
    Lightweight TF-IDF implementation (no external dependencies).
    """

    @classmethod
    def vectorize(cls, documents: List[str]) -> Tuple[List[Dict[str, float]], Dict[str, float]]:
        """
        Compute TF-IDF vectors for documents.

        Args:
            documents: List of text documents

        Returns:
            (tfidf_vectors, idf_scores)
        """
        # Tokenize
        tokenized = [cls._tokenize(doc) for doc in documents]
        n_docs = len(documents)

        # Compute document frequency
        df = Counter()
        for tokens in tokenized:
            unique = set(tokens)
            for token in unique:
                df[token] += 1

        # IDF
        idf = {}
        for term, freq in df.items():
            idf[term] = math.log(n_docs / (1 + freq)) + 1

        # TF-IDF vectors
        vectors = []
        for tokens in tokenized:
            tf = Counter(tokens)
            total = len(tokens) if tokens else 1
            vec = {}
            for term, count in tf.items():
                vec[term] = (count / total) * idf.get(term, 1.0)
            vectors.append(vec)

        return vectors, idf

    @classmethod
    def cosine_similarity(cls, vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
        """Compute cosine similarity between two sparse vectors"""
        # Common terms
        common = set(vec_a.keys()) & set(vec_b.keys())
        if not common:
            return 0.0

        dot = sum(vec_a[t] * vec_b[t] for t in common)
        mag_a = math.sqrt(sum(v ** 2 for v in vec_a.values()))
        mag_b = math.sqrt(sum(v ** 2 for v in vec_b.values()))

        if mag_a == 0 or mag_b == 0:
            return 0.0

        return dot / (mag_a * mag_b)

    @classmethod
    def _tokenize(cls, text: str) -> List[str]:
        """Tokenize text into meaningful terms"""
        text = text.lower()
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text)

        stopwords = {
            'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all',
            'can', 'had', 'her', 'was', 'one', 'our', 'out', 'has',
            'have', 'been', 'from', 'this', 'that', 'with', 'they',
            'will', 'each', 'make', 'than', 'them', 'its', 'also',
            'into', 'very', 'more', 'some', 'what', 'when', 'who',
            'how', 'which', 'their', 'other', 'about', 'many', 'then',
            'these', 'would', 'first', 'where', 'after', 'those',
            'being', 'does', 'using', 'used', 'based', 'such', 'only',
            'paper', 'study', 'results', 'method', 'approach', 'show',
            'propose', 'proposed', 'present', 'presented', 'develop',
        }

        return [w for w in words if w not in stopwords]


# ==================== EXPERTISE MATCHER ====================

class ExpertiseMatcher:
    """
    Match reviewer expertise to manuscript topic.
    """

    @classmethod
    def compute_match(
        cls,
        manuscript_text: str,
        candidate_texts: List[str],
    ) -> List[float]:
        """
        Compute expertise match scores.

        Args:
            manuscript_text: Manuscript abstract/title
            candidate_texts: Candidate publication texts

        Returns:
            List of similarity scores (0-1)
        """
        if not candidate_texts:
            return []

        # Build corpus: manuscript + all candidate texts
        all_docs = [manuscript_text] + candidate_texts
        vectors, _ = TfIdfEngine.vectorize(all_docs)

        manuscript_vec = vectors[0]
        scores = []
        for i in range(1, len(vectors)):
            sim = TfIdfEngine.cosine_similarity(manuscript_vec, vectors[i])
            scores.append(sim)

        return scores

    @classmethod
    def keyword_overlap(
        cls,
        manuscript_keywords: List[str],
        candidate_keywords: List[str],
    ) -> Tuple[float, List[str]]:
        """
        Compute keyword overlap.

        Returns:
            (overlap_ratio, matching_keywords)
        """
        ms_kw = {k.lower().strip() for k in manuscript_keywords}
        cd_kw = {k.lower().strip() for k in candidate_keywords}

        matching = ms_kw & cd_kw
        total = ms_kw | cd_kw

        ratio = len(matching) / len(total) if total else 0
        return ratio, sorted(matching)


# ==================== CONFLICT DETECTOR ====================

class ConflictDetector:
    """
    Detect conflicts of interest between manuscript authors and reviewer candidates.
    """

    @classmethod
    def detect_conflicts(
        cls,
        manuscript_authors: List[str],
        candidate_name: str,
        candidate_coauthors: Optional[List[str]] = None,
        candidate_affiliation: str = "",
        manuscript_affiliations: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Detect conflicts of interest.

        Args:
            manuscript_authors: Authors of the manuscript
            candidate_name: Reviewer candidate name
            candidate_coauthors: Candidate's recent co-authors
            candidate_affiliation: Candidate's institution
            manuscript_affiliations: Manuscript authors' institutions

        Returns:
            List of conflict descriptions
        """
        conflicts = []

        # 1. Direct authorship conflict
        ms_name_parts = set()
        for name in manuscript_authors:
            for part in name.lower().split():
                if len(part) > 2:
                    ms_name_parts.add(part)

        cand_parts = {p.lower() for p in candidate_name.split() if len(p) > 2}
        if cand_parts & ms_name_parts:
            conflicts.append(f"Direct: candidate name matches manuscript author")

        # 2. Co-authorship conflict
        if candidate_coauthors:
            coauth_parts = set()
            for ca in candidate_coauthors:
                for part in ca.lower().split():
                    if len(part) > 2:
                        coauth_parts.add(part)

            overlap = coauth_parts & ms_name_parts
            if overlap:
                conflicts.append(f"Co-authorship: shared collaborators ({', '.join(list(overlap)[:3])})")

        # 3. Institutional conflict
        if candidate_affiliation and manuscript_affiliations:
            cand_inst = candidate_affiliation.lower()
            for ms_inst in manuscript_affiliations:
                if cls._institution_match(cand_inst, ms_inst.lower()):
                    conflicts.append(f"Institutional: same institution ({candidate_affiliation[:30]})")
                    break

        return conflicts

    @classmethod
    def _institution_match(cls, inst_a: str, inst_b: str) -> bool:
        """Check if two institution strings likely refer to the same place"""
        # Direct substring match
        if inst_a in inst_b or inst_b in inst_a:
            return True

        # Extract key words
        words_a = set(re.findall(r'\b[a-z]{4,}\b', inst_a))
        words_b = set(re.findall(r'\b[a-z]{4,}\b', inst_b))

        # Remove common words
        common_words = {'university', 'institute', 'department', 'school', 'college', 'center', 'centre', 'national', 'research'}
        key_a = words_a - common_words
        key_b = words_b - common_words

        if key_a and key_b:
            overlap = key_a & key_b
            return len(overlap) >= 1

        return False


# ==================== REVIEWER RANKER ====================

class ReviewerRanker:
    """
    Rank reviewer candidates using weighted scoring.
    """

    WEIGHTS = {
        'expertise': 0.50,
        'productivity': 0.20,
        'diversity': 0.15,
        'recency': 0.15,
    }

    @classmethod
    def rank(
        cls,
        candidates: List[ReviewerCandidate],
    ) -> List[ReviewerCandidate]:
        """
        Rank candidates by weighted score.

        Args:
            candidates: List of reviewer candidates

        Returns:
            Sorted list by total_score descending
        """
        if not candidates:
            return []

        # Normalize metrics
        max_h = max(c.h_index for c in candidates) or 1
        max_papers = max(c.paper_count for c in candidates) or 1
        max_recent = max(c.recent_papers for c in candidates) or 1

        for cand in candidates:
            # Expertise score (already computed)
            expertise = cand.expertise_score

            # Productivity (h-index normalized)
            productivity = cand.h_index / max_h

            # Diversity (keyword breadth)
            diversity = min(len(cand.matching_keywords) / 5, 1.0)

            # Recency (recent papers normalized)
            recency = cand.recent_papers / max_recent

            # Weighted total
            total = (
                cls.WEIGHTS['expertise'] * expertise +
                cls.WEIGHTS['productivity'] * productivity +
                cls.WEIGHTS['diversity'] * diversity +
                cls.WEIGHTS['recency'] * recency
            )

            # Penalty for conflicts
            if cand.has_conflict:
                total *= 0.1  # Severe penalty

            cand.total_score = round(total, 4)

            # Generate justification
            cand.justification = cls._justify(cand, expertise, productivity, recency)

        # Sort by total score descending
        candidates.sort(key=lambda c: -c.total_score)

        return candidates

    @classmethod
    def _justify(
        cls,
        cand: ReviewerCandidate,
        expertise: float,
        productivity: float,
        recency: float,
    ) -> str:
        """Generate justification string"""
        parts = []

        if expertise > 0.7:
            parts.append("strong expertise match")
        elif expertise > 0.4:
            parts.append("moderate expertise match")

        if cand.matching_keywords:
            parts.append(f"keywords: {', '.join(cand.matching_keywords[:3])}")

        if productivity > 0.7:
            parts.append(f"high productivity (h={cand.h_index})")

        if recency > 0.5:
            parts.append(f"{cand.recent_papers} recent papers")

        if cand.has_conflict:
            parts.append(f"⚠️ COI: {'; '.join(cand.conflicts[:2])}")

        return "; ".join(parts) if parts else "general match"


# ==================== REVIEWER MATCHER ====================

class ReviewerMatcher:
    """
    Full reviewer matching pipeline.
    """

    def __init__(self, openalex: Optional[OpenAlexClient] = None):
        self.oa = openalex or OpenAlexClient()

    def match(
        self,
        manuscript_text: str,
        manuscript_authors: Optional[List[str]] = None,
        manuscript_affiliations: Optional[List[str]] = None,
        n_candidates: int = 10,
        n_search: int = 50,
    ) -> ReviewerMatchReport:
        """
        Find matching reviewers for a manuscript.

        Args:
            manuscript_text: Manuscript abstract or title
            manuscript_authors: Manuscript author names (for COI)
            manuscript_affiliations: Author affiliations (for COI)
            n_candidates: Number of candidates to return
            n_search: Number of papers to search

        Returns:
            ReviewerMatchReport
        """
        print(f"\n  [👥] Reviewer Matcher")
        print(f"  [·] Manuscript: \"{manuscript_text[:50]}...\"")

        manuscript_authors = manuscript_authors or []
        manuscript_affiliations = manuscript_affiliations or []

        # Extract keywords from manuscript
        keywords = self._extract_keywords(manuscript_text)
        print(f"  [·] Keywords: {keywords[:5]}")

        # Fetch related papers to find candidate reviewers
        print(f"  [·] Searching for related papers...")
        papers = self._fetch_papers(manuscript_text, n_search)
        print(f"  [✓] Found {len(papers)} papers")

        if not papers:
            return ReviewerMatchReport(
                manuscript_title=manuscript_text[:60],
                manuscript_keywords=keywords,
            )

        # Build candidate profiles from paper authors
        print(f"  [·] Building candidate profiles...")
        author_profiles = self._build_profiles(papers)
        print(f"  [✓] {len(author_profiles)} unique authors found")

        # Compute expertise match
        print(f"  [·] Computing expertise match...")
        candidates = []
        candidate_texts = []
        candidate_keys = []

        for author_name, profile in author_profiles.items():
            combined = ' '.join(profile['titles'])
            candidate_texts.append(combined)
            candidate_keys.append(author_name)

        if candidate_texts:
            scores = ExpertiseMatcher.compute_match(manuscript_text, candidate_texts)

            for i, author_name in enumerate(candidate_keys):
                profile = author_profiles[author_name]

                # Keyword overlap
                kw_ratio, matching_kws = ExpertiseMatcher.keyword_overlap(
                    keywords, profile.get('keywords', [])
                )

                # Conflict detection
                conflicts = ConflictDetector.detect_conflicts(
                    manuscript_authors,
                    author_name,
                    candidate_coauthors=profile.get('coauthors', []),
                    candidate_affiliation=profile.get('affiliation', ''),
                    manuscript_affiliations=manuscript_affiliations,
                )

                # Blend TF-IDF score with keyword overlap
                tfidf_score = scores[i] if i < len(scores) else 0
                expertise = 0.7 * tfidf_score + 0.3 * kw_ratio

                cand = ReviewerCandidate(
                    name=author_name,
                    affiliation=profile.get('affiliation', ''),
                    expertise_score=round(expertise, 4),
                    h_index=profile.get('h_index', 0),
                    paper_count=profile.get('paper_count', 0),
                    recent_papers=profile.get('recent', 0),
                    matching_keywords=matching_kws,
                    conflicts=conflicts,
                    has_conflict=len(conflicts) > 0,
                )
                candidates.append(cand)

        # Rank candidates
        print(f"  [·] Ranking candidates...")
        ranked = ReviewerRanker.rank(candidates)

        # Filter and take top N (exclude conflicted from top)
        clean = [c for c in ranked if not c.has_conflict][:n_candidates]
        conflicted = [c for c in ranked if c.has_conflict]

        conflicts_found = len(conflicted)
        final = clean if clean else ranked[:n_candidates]

        report = ReviewerMatchReport(
            manuscript_title=manuscript_text[:60],
            manuscript_keywords=keywords,
            candidates=final,
            total_candidates_screened=len(candidates),
            conflicts_found=conflicts_found,
        )

        self.print_report(report)
        return report

    def _fetch_papers(self, query: str, n: int) -> List[Paper]:
        """Fetch papers"""
        try:
            return self.oa.search(query, per_page=min(n, 200))
        except Exception as e:
            print(f"  [!] Fetch failed: {e}")
            return []

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text"""
        tokens = TfIdfEngine._tokenize(text)
        freq = Counter(tokens)
        # Return top keywords by frequency
        return [t for t, _ in freq.most_common(10)]

    def _build_profiles(self, papers: List[Paper]) -> Dict[str, Dict]:
        """Build author profiles from paper data"""
        profiles = defaultdict(lambda: {
            'titles': [],
            'keywords': [],
            'coauthors': [],
            'paper_count': 0,
            'recent': 0,
            'h_index': 0,
            'affiliation': '',
            'citations': [],
        })

        for paper in papers:
            names = paper.author_names or []
            if not names and paper.authors:
                names = [a.name for a in paper.authors if a.name]

            for name in names:
                if not name or len(name) < 3:
                    continue

                p = profiles[name]
                p['titles'].append(paper.title or '')
                p['paper_count'] += 1

                if paper.year and paper.year >= 2022:
                    p['recent'] += 1

                if paper.keywords:
                    p['keywords'].extend(paper.keywords)

                if paper.citation_count:
                    p['citations'].append(paper.citation_count)

                # Track co-authors
                for other in names:
                    if other != name:
                        p['coauthors'].append(other)

                # Affiliation from author objects
                if paper.authors:
                    for a in paper.authors:
                        if a.name == name and hasattr(a, 'affiliation') and a.affiliation:
                            p['affiliation'] = a.affiliation

        # Compute h-index for each author
        for name, p in profiles.items():
            cites = sorted(p['citations'], reverse=True)
            h = 0
            for i, c in enumerate(cites):
                if c >= i + 1:
                    h = i + 1
                else:
                    break
            p['h_index'] = h
            p['keywords'] = list(set(p['keywords']))

        return dict(profiles)

    @staticmethod
    def print_report(report: ReviewerMatchReport):
        """Print formatted report"""
        print(f"\n{'='*65}")
        print(f"  👥 Reviewer Match Report")
        print(f"{'='*65}")
        print(f"  Manuscript: \"{report.manuscript_title}\"")
        print(f"  Keywords: {', '.join(report.manuscript_keywords[:5])}")
        print(f"  Screened: {report.total_candidates_screened} candidates")
        print(f"  Conflicts: {report.conflicts_found}")

        if report.candidates:
            print(f"\n  🏆 Top {len(report.candidates)} Reviewers:")
            for i, c in enumerate(report.candidates, 1):
                conflict_mark = " ⚠️" if c.has_conflict else ""
                print(f"\n    {i}. {c.name}{conflict_mark}")
                print(f"       Score: {c.total_score:.3f} (expertise: {c.expertise_score:.3f})")
                if c.affiliation:
                    print(f"       Affiliation: {c.affiliation[:40]}")
                print(f"       h-index: {c.h_index}, papers: {c.paper_count}, recent: {c.recent_papers}")
                if c.matching_keywords:
                    print(f"       Keywords: {', '.join(c.matching_keywords[:5])}")
                print(f"       Justification: {c.justification}")

        print(f"\n{'='*65}")
