"""
Journal Article Exporter

Export papers to multiple formats:
  - BibTeX (.bib)
  - RIS format (.ris)
  - CSV
  - JSON
  - Markdown literature review report
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .models import Paper, SearchResult, ResearchReport


class JournalExporter:
    """Export journal papers to various formats"""

    def __init__(self, output_dir: str = "."):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(
        self,
        papers: List[Paper],
        fmt: str = "json",
        filename: Optional[str] = None,
        query: str = "",
    ) -> str:
        """
        Export papers to the specified format.

        Args:
            papers: List of Paper objects
            fmt: Export format (bibtex, ris, csv, json, markdown)
            filename: Output filename (auto-generated if None)
            query: Original search query (for report title)

        Returns:
            Path to exported file
        """
        if filename is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_query = query.replace(' ', '_')[:30] if query else 'papers'
            ext_map = {
                'bibtex': 'bib', 'ris': 'ris', 'csv': 'csv',
                'json': 'json', 'markdown': 'md',
            }
            ext = ext_map.get(fmt, fmt)
            filename = f"journal_{safe_query}_{ts}.{ext}"

        filepath = self.output_dir / filename

        if fmt == 'bibtex':
            content = self._to_bibtex(papers)
        elif fmt == 'ris':
            content = self._to_ris(papers)
        elif fmt == 'csv':
            self._to_csv(papers, filepath)
            print(f"  [✓] Exported {len(papers)} papers → {filepath}")
            return str(filepath)
        elif fmt == 'json':
            content = json.dumps(
                [p.to_dict() for p in papers],
                indent=2, ensure_ascii=False,
            )
        elif fmt == 'markdown':
            content = self._to_markdown_report(papers, query)
        else:
            content = json.dumps([p.to_dict() for p in papers], indent=2)

        filepath.write_text(content, encoding='utf-8')
        print(f"  [✓] Exported {len(papers)} papers → {filepath}")
        return str(filepath)

    @staticmethod
    def _to_bibtex(papers: List[Paper]) -> str:
        """Convert papers to BibTeX format"""
        entries = []
        used_keys = set()

        for p in papers:
            # Generate unique key
            key = p.to_bibtex_key()
            counter = 1
            original_key = key
            while key in used_keys:
                key = f"{original_key}{chr(96 + counter)}"
                counter += 1
            used_keys.add(key)

            lines = [f"@article{{{key},"]
            lines.append(f"  title = {{{p.title}}},")

            if p.author_names:
                authors = " and ".join(p.author_names)
                lines.append(f"  author = {{{authors}}},")

            if p.year:
                lines.append(f"  year = {{{p.year}}},")
            if p.journal:
                lines.append(f"  journal = {{{p.journal}}},")
            if p.volume:
                lines.append(f"  volume = {{{p.volume}}},")
            if p.issue:
                lines.append(f"  number = {{{p.issue}}},")
            if p.pages:
                lines.append(f"  pages = {{{p.pages}}},")
            if p.doi:
                lines.append(f"  doi = {{{p.doi}}},")
            if p.url:
                lines.append(f"  url = {{{p.url}}},")
            if p.abstract:
                # Escape special chars
                abstract = p.abstract.replace('{', '\\{').replace('}', '\\}')
                lines.append(f"  abstract = {{{abstract[:500]}}},")

            lines.append("}")
            entries.append("\n".join(lines))

        return "\n\n".join(entries) + "\n"

    @staticmethod
    def _to_ris(papers: List[Paper]) -> str:
        """Convert papers to RIS format"""
        entries = []

        for p in papers:
            lines = ["TY  - JOUR"]
            lines.append(f"TI  - {p.title}")

            for author in p.author_names:
                lines.append(f"AU  - {author}")

            if p.year:
                lines.append(f"PY  - {p.year}")
            if p.journal:
                lines.append(f"JO  - {p.journal}")
            if p.volume:
                lines.append(f"VL  - {p.volume}")
            if p.issue:
                lines.append(f"IS  - {p.issue}")
            if p.pages:
                if '-' in p.pages:
                    sp, ep = p.pages.split('-', 1)
                    lines.append(f"SP  - {sp.strip()}")
                    lines.append(f"EP  - {ep.strip()}")
                else:
                    lines.append(f"SP  - {p.pages}")
            if p.doi:
                lines.append(f"DO  - {p.doi}")
            if p.url:
                lines.append(f"UR  - {p.url}")
            if p.abstract:
                lines.append(f"AB  - {p.abstract[:1000]}")
            if p.keywords:
                for kw in p.keywords:
                    lines.append(f"KW  - {kw}")

            lines.append("ER  - ")
            entries.append("\n".join(lines))

        return "\n\n".join(entries) + "\n"

    @staticmethod
    def _to_csv(papers: List[Paper], filepath: Path):
        """Export papers to CSV"""
        fieldnames = [
            'title', 'authors', 'year', 'journal', 'doi',
            'citation_count', 'abstract', 'url', 'is_open_access',
            'topics', 'keywords',
        ]

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for p in papers:
                writer.writerow({
                    'title': p.title,
                    'authors': '; '.join(p.author_names),
                    'year': p.year,
                    'journal': p.journal,
                    'doi': p.doi,
                    'citation_count': p.citation_count,
                    'abstract': p.abstract[:500],
                    'url': p.url,
                    'is_open_access': p.is_open_access,
                    'topics': '; '.join(p.topics),
                    'keywords': '; '.join(p.keywords),
                })

    @staticmethod
    def _to_markdown_report(papers: List[Paper], query: str = "") -> str:
        """Generate a markdown literature review report"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        lines = [
            f"# Literature Review: {query or 'Research Papers'}",
            f"\n*Generated: {now} | Papers: {len(papers)}*\n",
            "---\n",
        ]

        # Summary statistics
        years = [p.year for p in papers if p.year]
        citations = [p.citation_count for p in papers]
        oa_count = sum(1 for p in papers if p.is_open_access)

        if years:
            lines.append("## Summary\n")
            lines.append(f"- **Total Papers:** {len(papers)}")
            lines.append(f"- **Year Range:** {min(years)}–{max(years)}")
            lines.append(f"- **Total Citations:** {sum(citations):,}")
            lines.append(f"- **Avg Citations:** {sum(citations) / len(citations):.0f}")
            lines.append(f"- **Open Access:** {oa_count} ({oa_count / len(papers) * 100:.0f}%)")
            lines.append("")

        # Paper list
        lines.append("## Papers\n")
        for i, p in enumerate(papers, 1):
            authors = ", ".join(p.author_names[:3])
            if len(p.author_names) > 3:
                authors += " et al."
            oa = " 🔓" if p.is_open_access else ""

            lines.append(f"### {i}. {p.title}{oa}\n")
            lines.append(f"**{authors}** ({p.year})")
            lines.append(f"*{p.journal}* | Citations: {p.citation_count}")
            if p.doi:
                lines.append(f"DOI: [{p.doi}](https://doi.org/{p.doi})")
            if p.abstract:
                lines.append(f"\n> {p.abstract[:300]}{'...' if len(p.abstract) > 300 else ''}")
            lines.append("")

        return "\n".join(lines)

