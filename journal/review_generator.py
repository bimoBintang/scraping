"""
Algorithm J10: Literature Review Generator

Auto-generate structured literature review drafts from collections of papers.

Pipeline:
  1. Fetch relevant papers (OpenAlex + Semantic Scholar)
  2. Extract key sentences using TF-IDF scoring
  3. Cluster papers by thematic similarity (keyword Jaccard)
  4. Detect research gaps (under-explored subtopics)
  5. Generate structured markdown review with APA citations

Usage:
    from journal.review_generator import LiteratureReviewGenerator

    generator = LiteratureReviewGenerator()
    review = generator.generate("transformer attention mechanisms", n_papers=30)
    generator.export_markdown(review, "review.md")
"""

import math
import re
import time
from collections import Counter, defaultdict
from itertools import combinations
from typing import Dict, List, Optional, Set, Tuple

from .models import Paper, ReviewSection, LiteratureReview
from .api_client import OpenAlexClient, SemanticScholarClient


# ==================== SENTENCE EXTRACTOR ====================

class SentenceExtractor:
    """
    Extract key sentences from text using TF-IDF scoring.

    Identifies the most informative sentences from abstracts
    and other textual content.
    """

    @staticmethod
    def split_sentences(text: str) -> List[str]:
        """Split text into sentences"""
        if not text:
            return []
        # Split on period, exclamation, question mark followed by space/end
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        return [s.strip() for s in sentences if len(s.strip()) > 20]

    @staticmethod
    def extract_key_sentences(text: str, n: int = 3, corpus: Optional[List[str]] = None) -> List[str]:
        """
        Extract top-n key sentences from text using TF-IDF-like scoring.

        Args:
            text: The text to extract from
            n: Number of sentences to extract
            corpus: Optional background corpus for IDF calculation

        Returns:
            List of top-n sentences
        """
        sentences = SentenceExtractor.split_sentences(text)
        if not sentences:
            return []

        if len(sentences) <= n:
            return sentences

        # Build term frequencies
        scores = []
        for sent in sentences:
            score = SentenceExtractor._score_sentence(sent, sentences, corpus)
            scores.append((score, sent))

        # Sort by score descending, pick top-n
        scores.sort(reverse=True)
        top = [sent for _, sent in scores[:n]]

        # Return in original order
        ordered = [s for s in sentences if s in top]
        return ordered[:n]

    @staticmethod
    def _score_sentence(
        sentence: str,
        all_sentences: List[str],
        corpus: Optional[List[str]] = None,
    ) -> float:
        """
        Score a sentence using TF-IDF-like features.

        Features:
          - Term frequency uniqueness
          - Sentence position (early = important)
          - Length preference (not too short, not too long)
          - Presence of key academic phrases
        """
        words = re.findall(r'\b[a-z]{3,}\b', sentence.lower())
        if not words:
            return 0.0

        # 1. Term uniqueness (IDF-like)
        word_set = set(words)
        doc_freq = Counter()
        docs = corpus if corpus else [' '.join(all_sentences)]
        for doc in docs:
            doc_words = set(re.findall(r'\b[a-z]{3,}\b', doc.lower()))
            for w in word_set:
                if w in doc_words:
                    doc_freq[w] += 1

        n_docs = max(len(docs), 1)
        idf_score = sum(
            math.log(n_docs / max(doc_freq.get(w, 1), 1))
            for w in word_set
        ) / max(len(word_set), 1)

        # 2. Position bonus (first and last sentences are important)
        pos = all_sentences.index(sentence) if sentence in all_sentences else len(all_sentences)
        n_sent = len(all_sentences)
        if pos == 0:
            pos_score = 1.5
        elif pos == n_sent - 1:
            pos_score = 1.2
        elif pos < n_sent * 0.3:
            pos_score = 1.1
        else:
            pos_score = 1.0

        # 3. Length preference (15-40 words is ideal)
        n_words = len(words)
        if 15 <= n_words <= 40:
            len_score = 1.0
        elif n_words < 10:
            len_score = 0.5
        else:
            len_score = 0.7

        # 4. Academic phrase bonus
        academic_patterns = [
            r'\b(we (propose|present|introduce|demonstrate|show))',
            r'\b(results? (show|indicate|suggest|demonstrate))',
            r'\b(significant|novel|state.of.the.art|outperform)',
            r'\b(contribution|finding|conclusion|implication)',
            r'\b(improve|enhance|advance|achieve)',
        ]
        phrase_bonus = 1.0
        for pattern in academic_patterns:
            if re.search(pattern, sentence.lower()):
                phrase_bonus += 0.15

        return idf_score * pos_score * len_score * phrase_bonus


# ==================== THEMATIC CLUSTERER ====================

class ThematicClusterer:
    """
    Cluster papers by thematic similarity using keyword overlap.
    """

    @staticmethod
    def cluster_papers(
        papers: List[Paper],
        min_similarity: float = 0.15,
        max_clusters: int = 8,
    ) -> List[Tuple[str, List[Paper]]]:
        """
        Group papers into thematic clusters.

        Args:
            papers: Papers to cluster
            min_similarity: Minimum Jaccard similarity to link papers
            max_clusters: Maximum number of clusters

        Returns:
            List of (theme_label, papers) tuples
        """
        if not papers:
            return []

        # Build keyword sets for each paper
        paper_kws = []
        for p in papers:
            kws = set()
            for k in (p.keywords + p.topics):
                kws.add(k.lower().strip())
            # Add title words as fallback
            title_words = set(re.findall(r'\b[a-z]{4,}\b', p.title.lower()))
            stop = {'this', 'that', 'with', 'from', 'have', 'been', 'their',
                    'which', 'would', 'could', 'about', 'into', 'than', 'each',
                    'more', 'also', 'were', 'using', 'based', 'paper', 'study'}
            title_words -= stop
            kws.update(title_words)
            paper_kws.append(kws)

        # Build adjacency graph via Jaccard similarity
        n = len(papers)
        adj: Dict[int, Set[int]] = defaultdict(set)

        for i, j in combinations(range(n), 2):
            sim = ThematicClusterer._jaccard(paper_kws[i], paper_kws[j])
            if sim >= min_similarity:
                adj[i].add(j)
                adj[j].add(i)

        # Connected components
        visited = set()
        raw_clusters = []

        for node in range(n):
            if node in visited:
                continue
            cluster = []
            queue = [node]
            while queue:
                v = queue.pop(0)
                if v in visited:
                    continue
                visited.add(v)
                cluster.append(v)
                for neighbor in adj.get(v, set()):
                    if neighbor not in visited:
                        queue.append(neighbor)
            raw_clusters.append(cluster)

        # Sort clusters by size (largest first)
        raw_clusters.sort(key=len, reverse=True)

        # Merge tiny clusters (size 1) into "Other"
        main_clusters = [c for c in raw_clusters if len(c) >= 2]
        orphans = [idx for c in raw_clusters if len(c) < 2 for idx in c]

        if orphans and len(main_clusters) < max_clusters:
            main_clusters.append(orphans)

        # Label each cluster by most common keywords
        result = []
        for cluster_idxs in main_clusters[:max_clusters]:
            cluster_papers = [papers[i] for i in cluster_idxs]
            label = ThematicClusterer._label_cluster(cluster_papers)
            result.append((label, cluster_papers))

        return result

    @staticmethod
    def _jaccard(set_a: Set[str], set_b: Set[str]) -> float:
        """Jaccard similarity between two sets"""
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0

    @staticmethod
    def _label_cluster(papers: List[Paper]) -> str:
        """Generate label for a cluster from common keywords"""
        kw_freq = Counter()
        for p in papers:
            for k in (p.keywords + p.topics):
                kw_freq[k.lower().strip()] += 1

        top = kw_freq.most_common(3)
        if top:
            return " & ".join(kw for kw, _ in top)
        return "General"


# ==================== GAP DETECTOR ====================

class GapDetector:
    """
    Identify research gaps from a collection of papers.
    """

    @staticmethod
    def find_gaps(
        papers: List[Paper],
        query: str,
        clusters: List[Tuple[str, List[Paper]]],
    ) -> List[str]:
        """
        Detect potential research gaps.

        Strategies:
          1. Under-represented temporal periods
          2. Small clusters (niche areas with few papers)
          3. High-cited papers with no recent follow-up
          4. Missing methodology combinations

        Returns:
            List of gap descriptions
        """
        gaps = []

        # 1. Temporal gaps
        year_counts = Counter(p.year for p in papers if p.year)
        if year_counts:
            years = sorted(year_counts.keys())
            for i in range(len(years) - 1):
                if years[i + 1] - years[i] > 2:
                    gaps.append(
                        f"Limited research during {years[i]+1}–{years[i+1]-1} "
                        f"(publication gap)"
                    )

        # 2. Small clusters = niche opportunities
        for label, cluster_papers in clusters:
            if 1 <= len(cluster_papers) <= 2:
                gaps.append(
                    f"Under-explored area: \"{label}\" "
                    f"(only {len(cluster_papers)} paper(s))"
                )

        # 3. Highly cited but no recent work
        old_high = [
            p for p in papers
            if p.citation_count > 50 and p.year and p.year < 2022
        ]
        for p in old_high[:3]:
            recent_related = [
                r for r in papers
                if r.year and r.year >= 2023
                and set(r.keywords) & set(p.keywords)
            ]
            if not recent_related:
                gaps.append(
                    f"Foundational work \"{p.title[:50]}...\" ({p.year}, "
                    f"{p.citation_count} cites) lacks recent follow-up"
                )

        # 4. Methodology gaps
        all_methods = set()
        for p in papers:
            for kw in p.keywords:
                kw_lower = kw.lower()
                if any(m in kw_lower for m in [
                    'method', 'algorithm', 'framework', 'model',
                    'approach', 'technique', 'architecture',
                ]):
                    all_methods.add(kw_lower)

        if len(all_methods) < 3 and len(papers) > 10:
            gaps.append(
                "Limited methodological diversity — most papers use similar approaches"
            )

        return gaps[:8]


# ==================== REVIEW GENERATOR ====================

class LiteratureReviewGenerator:
    """
    Generate structured literature review from paper collections.
    """

    def __init__(
        self,
        openalex: Optional[OpenAlexClient] = None,
        semantic_scholar: Optional[SemanticScholarClient] = None,
    ):
        self.oa = openalex or OpenAlexClient()
        self.s2 = semantic_scholar or SemanticScholarClient()
        self.extractor = SentenceExtractor()
        self.clusterer = ThematicClusterer()
        self.gap_detector = GapDetector()

    def generate(
        self,
        query: str,
        n_papers: int = 30,
        style: str = "thematic",
    ) -> LiteratureReview:
        """
        Generate a literature review.

        Args:
            query: Research topic
            n_papers: Number of papers to include
            style: "thematic" or "chronological"

        Returns:
            LiteratureReview with full markdown text
        """
        print(f"\n  [📝] Literature Review Generator")
        print(f"  [·] Topic: \"{query}\"")
        print(f"  [·] Papers: {n_papers}, Style: {style}")

        # Step 1: Fetch papers
        print(f"  [·] Fetching papers...")
        papers = self.oa.search(
            query,
            per_page=min(n_papers, 200),
            sort="cited_by_count:desc",
        )

        if not papers:
            print("  [!] No papers found")
            return LiteratureReview(query=query, title=f"Literature Review: {query}")

        # Deduplicate by title
        seen = set()
        unique = []
        for p in papers:
            key = p.title.lower().strip()
            if key not in seen:
                seen.add(key)
                unique.append(p)
        papers = unique[:n_papers]

        print(f"  [✓] {len(papers)} papers collected")

        # Step 2: Cluster by theme
        print(f"  [·] Clustering by theme...")
        clusters = self.clusterer.cluster_papers(papers)
        print(f"  [✓] {len(clusters)} thematic clusters")

        # Step 3: Detect gaps
        print(f"  [·] Detecting research gaps...")
        gaps = self.gap_detector.find_gaps(papers, query, clusters)
        print(f"  [✓] {len(gaps)} gaps identified")

        # Step 4: Build review
        print(f"  [·] Generating review...")

        # Year range
        years = [p.year for p in papers if p.year]
        year_range = f"{min(years)}–{max(years)}" if years else "N/A"

        # Title
        title = f"Literature Review: {query.title()}"

        # Introduction
        intro = self._build_introduction(query, papers, year_range)

        # Sections
        if style == "chronological":
            sections = self._build_chronological_sections(papers)
        else:
            sections = self._build_thematic_sections(clusters)

        # Conclusion
        conclusion = self._build_conclusion(query, papers, gaps)

        # Bibliography
        bibliography = self._build_bibliography(papers)

        # Assemble full markdown
        full_text = self._assemble_markdown(
            title, intro, sections, gaps, conclusion, bibliography
        )

        review = LiteratureReview(
            query=query,
            title=title,
            total_papers=len(papers),
            year_range=year_range,
            introduction=intro,
            sections=sections,
            research_gaps=gaps,
            conclusion=conclusion,
            bibliography=bibliography,
            full_text=full_text,
        )

        print(f"  [✓] Review generated ({len(full_text):,} characters)")
        self._print_summary(review)
        return review

    def _build_introduction(
        self, query: str, papers: List[Paper], year_range: str
    ) -> str:
        """Build introduction paragraph"""
        n = len(papers)
        top_cited = sorted(papers, key=lambda p: p.citation_count, reverse=True)
        most_cited = top_cited[0] if top_cited else None

        intro = (
            f"This literature review examines {n} publications on the topic of "
            f"\"{query}\" spanning {year_range}. "
        )

        if most_cited:
            intro += (
                f"The most cited work in this collection is "
                f"\"{most_cited.title}\" "
                f"({most_cited.year}) with {most_cited.citation_count:,} citations. "
            )

        # Year distribution summary
        year_counts = Counter(p.year for p in papers if p.year)
        if year_counts:
            peak_year = max(year_counts, key=year_counts.get)
            intro += (
                f"Publication activity peaked in {peak_year} with "
                f"{year_counts[peak_year]} papers. "
            )

        return intro

    def _build_thematic_sections(
        self, clusters: List[Tuple[str, List[Paper]]]
    ) -> List[ReviewSection]:
        """Build review sections organized by theme"""
        sections = []
        corpus = []

        # Build corpus for TF-IDF
        for _, cluster_papers in clusters:
            for p in cluster_papers:
                if p.abstract:
                    corpus.append(p.abstract)

        for theme_label, cluster_papers in clusters:
            # Sort within cluster by year
            cluster_papers.sort(key=lambda p: p.year or 0)

            content_parts = []
            paper_titles = []

            for p in cluster_papers:
                paper_titles.append(p.title)
                # Citation tag
                authors = p.authors[0].name if p.authors else "Unknown"
                if len(p.authors) > 1:
                    authors += " et al."
                cite = f"({authors}, {p.year})"

                if p.abstract:
                    # Extract key sentences
                    key_sents = self.extractor.extract_key_sentences(
                        p.abstract, n=2, corpus=corpus
                    )
                    if key_sents:
                        content_parts.append(
                            f"{key_sents[0]} {cite}."
                        )
                else:
                    content_parts.append(
                        f"\"{p.title}\" {cite} contributes to this area "
                        f"with {p.citation_count} citations."
                    )

            content = " ".join(content_parts)

            # Extract keywords for the cluster
            kw_freq = Counter()
            for p in cluster_papers:
                for k in (p.keywords + p.topics):
                    kw_freq[k.lower()] += 1

            sections.append(ReviewSection(
                title=theme_label.title(),
                content=content,
                papers=paper_titles,
                paper_count=len(cluster_papers),
                theme_keywords=[k for k, _ in kw_freq.most_common(5)],
            ))

        return sections

    def _build_chronological_sections(
        self, papers: List[Paper]
    ) -> List[ReviewSection]:
        """Build review sections organized by time period"""
        papers_by_year = defaultdict(list)
        for p in papers:
            if p.year:
                papers_by_year[p.year].append(p)

        sections = []
        years = sorted(papers_by_year.keys())

        # Group into periods
        periods = []
        if len(years) <= 4:
            for y in years:
                periods.append((str(y), [y]))
        else:
            chunk_size = max(len(years) // 4, 1)
            for i in range(0, len(years), chunk_size):
                chunk = years[i:i + chunk_size]
                label = f"{chunk[0]}–{chunk[-1]}" if len(chunk) > 1 else str(chunk[0])
                periods.append((label, chunk))

        for label, period_years in periods:
            period_papers = []
            for y in period_years:
                period_papers.extend(papers_by_year.get(y, []))

            if not period_papers:
                continue

            content_parts = []
            paper_titles = []

            for p in sorted(period_papers, key=lambda x: x.citation_count, reverse=True):
                paper_titles.append(p.title)
                authors = p.authors[0].name if p.authors else "Unknown"
                if len(p.authors) > 1:
                    authors += " et al."
                cite = f"({authors}, {p.year})"

                if p.abstract:
                    key_sents = self.extractor.extract_key_sentences(p.abstract, n=1)
                    if key_sents:
                        content_parts.append(f"{key_sents[0]} {cite}.")
                else:
                    content_parts.append(f"\"{p.title}\" {cite}.")

            sections.append(ReviewSection(
                title=f"Period: {label}",
                content=" ".join(content_parts),
                papers=paper_titles,
                paper_count=len(period_papers),
            ))

        return sections

    def _build_conclusion(
        self, query: str, papers: List[Paper], gaps: List[str]
    ) -> str:
        """Build conclusion paragraph"""
        conclusion = (
            f"This review analyzed {len(papers)} publications on \"{query}\". "
        )

        if gaps:
            conclusion += (
                f"The analysis identified {len(gaps)} potential research gaps, "
                f"including: {gaps[0].lower()}. "
            )

        recent = [p for p in papers if p.year and p.year >= 2024]
        if recent:
            conclusion += (
                f"{len(recent)} recent publications ({2024}–present) indicate "
                f"continued active research in this area. "
            )

        conclusion += (
            "Future work should address the identified gaps and build upon "
            "the foundations established by the most influential works in this field."
        )

        return conclusion

    @staticmethod
    def _build_bibliography(papers: List[Paper]) -> List[str]:
        """Build APA-style bibliography"""
        bib = []
        for p in sorted(papers, key=lambda x: (x.authors[0].name if x.authors else "Z", x.year or 0)):
            authors = ", ".join(a.name for a in p.authors[:3])
            if len(p.authors) > 3:
                authors += ", et al."
            elif not authors:
                authors = "Unknown"

            entry = f"{authors} ({p.year or 'n.d.'}). {p.title}."
            if p.journal:
                entry += f" *{p.journal}*."
            if p.doi:
                entry += f" https://doi.org/{p.doi}"
            bib.append(entry)

        return bib

    @staticmethod
    def _assemble_markdown(
        title: str,
        intro: str,
        sections: List[ReviewSection],
        gaps: List[str],
        conclusion: str,
        bibliography: List[str],
    ) -> str:
        """Assemble full markdown document"""
        parts = [f"# {title}\n"]
        parts.append(f"## Introduction\n\n{intro}\n")

        # Thematic/Chronological sections
        for i, section in enumerate(sections, 1):
            parts.append(f"## {i}. {section.title}\n")
            parts.append(f"*{section.paper_count} papers*\n")
            if section.theme_keywords:
                parts.append(f"**Keywords:** {', '.join(section.theme_keywords)}\n")
            parts.append(f"\n{section.content}\n")

        # Research gaps
        if gaps:
            parts.append("## Research Gaps\n")
            for gap in gaps:
                parts.append(f"- {gap}")
            parts.append("")

        # Conclusion
        parts.append(f"## Conclusion\n\n{conclusion}\n")

        # Bibliography
        parts.append("## References\n")
        for i, ref in enumerate(bibliography, 1):
            parts.append(f"{i}. {ref}")

        return "\n".join(parts)

    @staticmethod
    def _print_summary(review: LiteratureReview):
        """Print review summary"""
        print(f"\n{'='*65}")
        print(f"  📝 Literature Review Generated")
        print(f"{'='*65}")
        print(f"  Title:   {review.title}")
        print(f"  Papers:  {review.total_papers}")
        print(f"  Period:  {review.year_range}")
        print(f"  Sections: {len(review.sections)}")

        for i, sec in enumerate(review.sections, 1):
            print(f"    {i}. {sec.title} ({sec.paper_count} papers)")

        if review.research_gaps:
            print(f"\n  🔍 Research Gaps ({len(review.research_gaps)}):")
            for gap in review.research_gaps[:5]:
                print(f"    • {gap[:70]}{'...' if len(gap) > 70 else ''}")

        print(f"\n  📚 Bibliography: {len(review.bibliography)} entries")
        print(f"  📄 Total length: {len(review.full_text):,} characters")
        print(f"{'='*65}")

    @staticmethod
    def export_markdown(review: LiteratureReview, filepath: str):
        """Export review to markdown file"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(review.full_text)
        print(f"  [✓] Exported → {filepath}")
