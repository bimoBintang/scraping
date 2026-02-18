"""
Algorithm J16: Bibliometric Mapping & Visualization

Generate bibliometric network data:
  - Co-citation: papers frequently cited together
  - Bibliographic coupling: papers sharing references
  - Keyword co-occurrence: term co-occurrence matrix

Export formats: VOSviewer CSV, Gephi GEXF, JSON graph

Usage:
    from journal.bibliometric_map import BibliometricMapper

    mapper = BibliometricMapper()
    bibmap = mapper.map("deep learning", map_type="cocitation", n_papers=50)
"""

import re
import math
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Set, Tuple
from itertools import combinations

from .models import Paper, BibNode, BibEdge, BibliometricMap
from .api_client import OpenAlexClient


# ==================== STOPWORDS ====================

STOPWORDS = {
    'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
    'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
    'could', 'should', 'may', 'might', 'can', 'shall', 'this', 'that',
    'these', 'those', 'it', 'its', 'we', 'our', 'they', 'their', 'he',
    'she', 'his', 'her', 'not', 'no', 'nor', 'as', 'if', 'than', 'so',
    'up', 'out', 'about', 'into', 'over', 'after', 'between', 'under',
    'during', 'each', 'all', 'both', 'such', 'more', 'most', 'other',
    'some', 'any', 'many', 'also', 'how', 'which', 'what', 'when',
    'where', 'who', 'whom', 'why', 'very', 'only', 'just', 'well',
    'based', 'using', 'used', 'use', 'new', 'two', 'one', 'first',
    'study', 'results', 'however', 'paper', 'approach', 'method',
    'proposed', 'show', 'shown', 'different', 'among', 'through',
}


# ==================== CO-CITATION BUILDER ====================

class CoCitationBuilder:
    """
    Build co-citation network.
    Two papers are co-cited when they appear in the same reference list.
    Edge weight = number of papers citing both.
    """

    @classmethod
    def build(cls, papers: List[Paper]) -> Tuple[List[BibNode], List[BibEdge]]:
        """
        Build co-citation network from papers.

        Args:
            papers: List of papers with references

        Returns:
            (nodes, edges) for the co-citation network
        """
        # Collect all references and count how often each is cited
        ref_papers = defaultdict(int)  # ref_id -> cite count
        ref_labels = {}  # ref_id -> label

        # Track which papers cite which references
        paper_refs = {}  # paper_id -> set of ref_ids
        for paper in papers:
            pid = cls._paper_id(paper)
            refs = set()
            if hasattr(paper, 'referenced_works') and paper.referenced_works:
                for ref in paper.referenced_works:
                    ref_id = str(ref)
                    refs.add(ref_id)
                    ref_papers[ref_id] += 1
                    if ref_id not in ref_labels:
                        ref_labels[ref_id] = ref_id[-12:]
            paper_refs[pid] = refs

        # Filter to most-cited references (top 100)
        top_refs = sorted(ref_papers.items(), key=lambda x: -x[1])[:100]
        top_ref_ids = {r[0] for r in top_refs}

        # Build co-citation matrix
        cocite_count = Counter()
        for pid, refs in paper_refs.items():
            filtered = refs & top_ref_ids
            for pair in combinations(sorted(filtered), 2):
                cocite_count[pair] += 1

        # Filter edges (min weight 2)
        edges = []
        connected = set()
        for (src, tgt), weight in cocite_count.items():
            if weight >= 2:
                edges.append(BibEdge(
                    source=src, target=tgt,
                    weight=float(weight),
                    edge_type='cocitation',
                ))
                connected.add(src)
                connected.add(tgt)

        # Build nodes
        nodes = []
        for ref_id in connected:
            nodes.append(BibNode(
                id=ref_id,
                label=ref_labels.get(ref_id, ref_id[-12:]),
                size=float(ref_papers.get(ref_id, 1)),
                node_type='paper',
                attributes={'cited_by': ref_papers.get(ref_id, 0)},
            ))

        return nodes, edges

    @staticmethod
    def _paper_id(paper: Paper) -> str:
        """Get unique paper identifier"""
        if hasattr(paper, 'doi') and paper.doi:
            return paper.doi
        if hasattr(paper, 'openalex_id') and paper.openalex_id:
            return paper.openalex_id
        return paper.title[:50] if paper.title else str(id(paper))


# ==================== BIBLIOGRAPHIC COUPLING BUILDER ====================

class BibCouplingBuilder:
    """
    Build bibliographic coupling network.
    Two papers are coupled if they share one or more references.
    Edge weight = number of shared references.
    """

    @classmethod
    def build(cls, papers: List[Paper]) -> Tuple[List[BibNode], List[BibEdge]]:
        """
        Build bibliographic coupling network.

        Args:
            papers: List of papers with references

        Returns:
            (nodes, edges) for coupling network
        """
        # Get reference sets for each paper
        paper_data = []
        for paper in papers:
            pid = CoCitationBuilder._paper_id(paper)
            refs = set()
            if hasattr(paper, 'referenced_works') and paper.referenced_works:
                refs = {str(r) for r in paper.referenced_works}
            paper_data.append((pid, paper, refs))

        # Compute coupling strength between all pairs
        edges = []
        connected = set()
        for i in range(len(paper_data)):
            for j in range(i + 1, len(paper_data)):
                pid_i, paper_i, refs_i = paper_data[i]
                pid_j, paper_j, refs_j = paper_data[j]

                shared = refs_i & refs_j
                if len(shared) >= 2:
                    edges.append(BibEdge(
                        source=pid_i, target=pid_j,
                        weight=float(len(shared)),
                        edge_type='coupling',
                    ))
                    connected.add(pid_i)
                    connected.add(pid_j)

        # Build nodes
        nodes = []
        for pid, paper, refs in paper_data:
            if pid in connected:
                title = paper.title[:40] if paper.title else pid
                nodes.append(BibNode(
                    id=pid,
                    label=title,
                    size=float(paper.citation_count or 1),
                    node_type='paper',
                    attributes={
                        'year': paper.year or 0,
                        'citations': paper.citation_count or 0,
                        'ref_count': len(refs),
                    },
                ))

        return nodes, edges


# ==================== KEYWORD CO-OCCURRENCE ====================

class KeywordCoOccurrence:
    """
    Build keyword co-occurrence network from paper keywords and abstracts.
    """

    @classmethod
    def build(
        cls,
        papers: List[Paper],
        min_freq: int = 2,
        max_terms: int = 100,
    ) -> Tuple[List[BibNode], List[BibEdge]]:
        """
        Build keyword co-occurrence network.

        Args:
            papers: List of papers
            min_freq: Minimum term frequency
            max_terms: Maximum number of terms

        Returns:
            (nodes, edges) for keyword network
        """
        # Extract terms from each paper
        paper_terms = []
        term_freq = Counter()

        for paper in papers:
            terms = cls._extract_terms(paper)
            paper_terms.append(terms)
            term_freq.update(terms)

        # Filter by frequency and take top terms
        valid_terms = {
            t for t, f in term_freq.items()
            if f >= min_freq
        }
        top_terms = sorted(valid_terms, key=lambda t: -term_freq[t])[:max_terms]
        top_set = set(top_terms)

        # Build co-occurrence matrix
        cooccur = Counter()
        for terms in paper_terms:
            filtered = terms & top_set
            for pair in combinations(sorted(filtered), 2):
                cooccur[pair] += 1

        # Build edges
        edges = []
        connected = set()
        for (t1, t2), count in cooccur.items():
            if count >= min_freq:
                edges.append(BibEdge(
                    source=t1, target=t2,
                    weight=float(count),
                    edge_type='cooccurrence',
                ))
                connected.add(t1)
                connected.add(t2)

        # Build nodes
        nodes = []
        for term in connected:
            nodes.append(BibNode(
                id=term,
                label=term,
                size=float(term_freq[term]),
                node_type='keyword',
                attributes={'frequency': term_freq[term]},
            ))

        # Simple clustering (connected component-ish via highest co-occurring neighbor)
        cls._assign_clusters(nodes, edges)

        return nodes, edges

    @classmethod
    def _extract_terms(cls, paper: Paper) -> Set[str]:
        """Extract meaningful terms from paper"""
        terms = set()

        # From explicit keywords
        if paper.keywords:
            for kw in paper.keywords:
                kw_clean = kw.strip().lower()
                if kw_clean and kw_clean not in STOPWORDS and len(kw_clean) > 2:
                    terms.add(kw_clean)

        # From title — extract bigrams and significant unigrams
        if paper.title:
            words = re.findall(r'\b[a-zA-Z]{3,}\b', paper.title.lower())
            content = [w for w in words if w not in STOPWORDS]

            # Unigrams
            for w in content:
                if len(w) > 4:
                    terms.add(w)

            # Bigrams
            for i in range(len(content) - 1):
                bigram = f"{content[i]} {content[i+1]}"
                terms.add(bigram)

        return terms

    @classmethod
    def _assign_clusters(cls, nodes: List[BibNode], edges: List[BibEdge]):
        """Simple clustering based on strongest connections"""
        if not nodes:
            return

        # Build adjacency with weights
        adj = defaultdict(list)
        for e in edges:
            adj[e.source].append((e.target, e.weight))
            adj[e.target].append((e.source, e.weight))

        # Assign clusters via greedy label propagation
        node_map = {n.id: n for n in nodes}
        cluster_id = 0

        visited = set()
        for node in sorted(nodes, key=lambda n: -n.size):
            if node.id in visited:
                continue
            # BFS from this node
            queue = [node.id]
            cluster_id += 1
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                if current in node_map:
                    node_map[current].cluster = cluster_id
                # Add strongest neighbors
                neighbors = sorted(adj.get(current, []), key=lambda x: -x[1])
                for nid, w in neighbors[:5]:
                    if nid not in visited:
                        queue.append(nid)


# ==================== NETWORK EXPORTER ====================

class NetworkExporter:
    """
    Export bibliometric networks to various formats.
    """

    @classmethod
    def to_gexf(cls, bmap: BibliometricMap) -> str:
        """Export to Gephi GEXF format (XML)"""
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<gexf xmlns="http://gexf.net/1.3" version="1.3">',
            f'  <meta><creator>JournalScraper</creator><description>{bmap.query}</description></meta>',
            '  <graph defaultedgetype="undirected">',
            '    <nodes>',
        ]

        for node in bmap.nodes:
            label = node.label.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;')
            lines.append(
                f'      <node id="{node.id}" label="{label}">'
            )
            lines.append(f'        <attvalues>')
            lines.append(f'          <attvalue for="cluster" value="{node.cluster}"/>')
            lines.append(f'          <attvalue for="size" value="{node.size}"/>')
            lines.append(f'          <attvalue for="type" value="{node.node_type}"/>')
            lines.append(f'        </attvalues>')
            lines.append(f'        <viz:size value="{max(node.size, 1.0)}"/>')
            lines.append(f'      </node>')

        lines.append('    </nodes>')
        lines.append('    <edges>')

        for i, edge in enumerate(bmap.edges):
            lines.append(
                f'      <edge id="{i}" source="{edge.source}" '
                f'target="{edge.target}" weight="{edge.weight}"/>'
            )

        lines.append('    </edges>')
        lines.append('  </graph>')
        lines.append('</gexf>')

        return '\n'.join(lines)

    @classmethod
    def to_vosviewer(cls, bmap: BibliometricMap) -> Tuple[str, str]:
        """
        Export to VOSviewer format (two CSVs).

        Returns:
            (nodes_csv, edges_csv)
        """
        # Nodes CSV
        node_lines = ['id\tlabel\tcluster\tweight']
        for node in bmap.nodes:
            node_lines.append(
                f'{node.id}\t{node.label}\t{node.cluster}\t{node.size}'
            )

        # Edges CSV
        edge_lines = ['source\ttarget\tweight']
        for edge in bmap.edges:
            edge_lines.append(
                f'{edge.source}\t{edge.target}\t{edge.weight}'
            )

        return '\n'.join(node_lines), '\n'.join(edge_lines)

    @classmethod
    def to_json_graph(cls, bmap: BibliometricMap) -> Dict:
        """Export to JSON graph format (D3-compatible)"""
        return {
            'nodes': [
                {
                    'id': n.id,
                    'label': n.label,
                    'group': n.cluster,
                    'size': n.size,
                    'type': n.node_type,
                }
                for n in bmap.nodes
            ],
            'links': [
                {
                    'source': e.source,
                    'target': e.target,
                    'value': e.weight,
                    'type': e.edge_type,
                }
                for e in bmap.edges
            ],
        }


# ==================== BIBLIOMETRIC MAPPER ====================

class BibliometricMapper:
    """
    Full bibliometric mapping pipeline.
    """

    def __init__(self, openalex: Optional[OpenAlexClient] = None):
        self.oa = openalex or OpenAlexClient()

    def map(
        self,
        query: str,
        map_type: str = 'keyword',
        n_papers: int = 50,
    ) -> BibliometricMap:
        """
        Generate bibliometric map.

        Args:
            query: Search query
            map_type: 'cocitation', 'coupling', or 'keyword'
            n_papers: Number of papers to analyze

        Returns:
            BibliometricMap with nodes and edges
        """
        print(f"\n  [🗺️] Bibliometric Mapper")
        print(f"  [·] Query: \"{query}\"")
        print(f"  [·] Type: {map_type}")

        # Fetch papers
        print(f"  [·] Fetching papers...")
        papers = self._fetch_papers(query, n_papers)
        print(f"  [✓] {len(papers)} papers fetched")

        if not papers:
            return BibliometricMap(query=query, map_type=map_type)

        # Build network
        print(f"  [·] Building {map_type} network...")
        if map_type == 'cocitation':
            nodes, edges = CoCitationBuilder.build(papers)
        elif map_type == 'coupling':
            nodes, edges = BibCouplingBuilder.build(papers)
        else:  # keyword
            nodes, edges = KeywordCoOccurrence.build(papers)

        # Compute density
        n = len(nodes)
        max_edges = n * (n - 1) / 2 if n > 1 else 1
        density = len(edges) / max_edges if max_edges > 0 else 0

        # Count clusters
        clusters = len(set(node.cluster for node in nodes)) if nodes else 0

        bmap = BibliometricMap(
            query=query,
            map_type=map_type,
            total_papers=len(papers),
            nodes=nodes,
            edges=edges,
            clusters=clusters,
            density=round(density, 4),
        )

        self.print_map(bmap)
        return bmap

    def _fetch_papers(self, query: str, n: int) -> List[Paper]:
        """Fetch papers"""
        try:
            return self.oa.search(query, per_page=min(n, 200))
        except Exception as e:
            print(f"  [!] Fetch failed: {e}")
            return []

    @staticmethod
    def print_map(bmap: BibliometricMap):
        """Print formatted map summary"""
        print(f"\n{'='*65}")
        print(f"  🗺️ Bibliometric Map")
        print(f"{'='*65}")
        print(f"  Query: \"{bmap.query}\"")
        print(f"  Type:  {bmap.map_type}")

        print(f"\n  📊 Network Statistics:")
        print(f"    Papers analyzed: {bmap.total_papers}")
        print(f"    Nodes:           {len(bmap.nodes)}")
        print(f"    Edges:           {len(bmap.edges)}")
        print(f"    Clusters:        {bmap.clusters}")
        print(f"    Density:         {bmap.density:.4f}")

        # Top nodes by size
        if bmap.nodes:
            print(f"\n  🔝 Top Nodes:")
            sorted_nodes = sorted(bmap.nodes, key=lambda n: -n.size)[:10]
            for node in sorted_nodes:
                label = node.label[:35] + "..." if len(node.label) > 35 else node.label
                print(f"    [{node.cluster}] {label:<40} (size: {node.size:.0f})")

        # Cluster distribution
        if bmap.clusters > 0:
            cluster_sizes = Counter(n.cluster for n in bmap.nodes)
            print(f"\n  🎨 Clusters:")
            for cid, count in sorted(cluster_sizes.items()):
                bar = '█' * min(count, 30)
                print(f"    Cluster {cid}: {bar} {count}")

        # Strongest edges
        if bmap.edges:
            print(f"\n  🔗 Strongest Connections:")
            top_edges = sorted(bmap.edges, key=lambda e: -e.weight)[:5]
            for edge in top_edges:
                src = edge.source[:20]
                tgt = edge.target[:20]
                print(f"    {src} ↔ {tgt} (weight: {edge.weight:.0f})")

        print(f"\n{'='*65}")
