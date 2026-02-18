"""
Algorithm J6: Author Disambiguation & Network Analysis

Two-phase algorithm:
  1. AuthorDisambiguator — resolve homonym authors using multiple signals
     (ORCID, affiliation, co-authors, topics, temporal patterns)
  2. CollaborationNetwork — build co-authorship graph, compute centrality,
     detect communities, and analyze collaboration patterns

Usage:
    from journal.author_network import AuthorDisambiguator, CollaborationNetwork

    papers = openalex.search("deep learning", count=100)

    dis = AuthorDisambiguator()
    authors = dis.disambiguate(papers)

    net = CollaborationNetwork()
    report = net.build_and_analyze(papers, authors)
    net.print_report(report)
"""

import re
from collections import Counter, defaultdict
from itertools import combinations
from typing import Any, Dict, List, Optional, Set, Tuple

from .models import (
    Author, Paper,
    DisambiguatedAuthor, CollaborationEdge, NetworkReport,
)


# ==================== AUTHOR DISAMBIGUATOR ====================

class AuthorDisambiguator:
    """
    Resolve author name ambiguity using multiple signals.

    Signals (weighted):
      - ORCID / API author ID  → exact match (1.0)
      - Affiliation overlap    → Jaccard similarity (0.30)
      - Co-author overlap      → shared collaborators (0.25)
      - Topic consistency      → shared fields/topics (0.25)
      - Temporal continuity    → publishing year overlap (0.20)

    Threshold: score ≥ 0.6 → same author
    """

    WEIGHTS = {
        'affiliation': 0.30,
        'coauthor': 0.25,
        'topic': 0.25,
        'temporal': 0.20,
    }
    MERGE_THRESHOLD = 0.6

    def disambiguate(self, papers: List[Paper]) -> Dict[str, DisambiguatedAuthor]:
        """
        Disambiguate authors across a list of papers.

        Args:
            papers: List of Paper objects with author info

        Returns:
            Dict mapping canonical_name → DisambiguatedAuthor
        """
        print(f"\n  [🔍] Disambiguating authors from {len(papers)} papers...")

        # Phase 1: Group raw author records by normalized name
        name_groups = self._cluster_by_name(papers)
        print(f"  [·] Found {len(name_groups)} unique author names")

        # Phase 2: Within each name group, check if multiple people
        # share the same name. Use signals to split or merge.
        disambiguated = {}

        for norm_name, records in name_groups.items():
            if len(records) == 1:
                # Only one record — no ambiguity
                r = records[0]
                disambiguated[norm_name] = self._make_author(norm_name, records)
            else:
                # Multiple records with same name — check signals
                clusters = self._resolve_ambiguity(norm_name, records)
                for i, cluster in enumerate(clusters):
                    key = norm_name if i == 0 else f"{norm_name}_{i+1}"
                    disambiguated[key] = self._make_author(key, cluster)

        # Fill co-author lists
        for name, author in disambiguated.items():
            coauth_set = set()
            for title in author.paper_titles:
                # Find other authors who co-authored same paper
                for other_name, other_author in disambiguated.items():
                    if other_name != name and title in other_author.paper_titles:
                        coauth_set.add(other_author.canonical_name)
            author.coauthors = sorted(coauth_set)

        print(f"  [✓] Disambiguated to {len(disambiguated)} unique authors")
        return disambiguated

    def _cluster_by_name(self, papers: List[Paper]) -> Dict[str, List[Dict]]:
        """Group author records by normalized name"""
        groups = defaultdict(list)

        for paper in papers:
            for i, author in enumerate(paper.authors):
                name = author.name.strip()
                if not name:
                    continue

                norm = self._normalize_name(name)
                record = {
                    'name': name,
                    'author_id': author.author_id,
                    'orcid': author.orcid,
                    'affiliation': author.affiliation,
                    'paper_title': paper.title,
                    'paper_year': paper.year,
                    'topics': paper.topics + paper.fields_of_study,
                    'keywords': paper.keywords,
                    'citations': paper.citation_count,
                    'coauthors': [
                        a.name for j, a in enumerate(paper.authors) if j != i
                    ],
                }
                groups[norm].append(record)

        return dict(groups)

    def _resolve_ambiguity(
        self, name: str, records: List[Dict]
    ) -> List[List[Dict]]:
        """
        Given multiple records with the same name, decide if they
        are the same person or different people (homonyms).

        Uses union-find to cluster records with high similarity.
        """
        n = len(records)

        # Quick check: if all have same ORCID or author_id → same person
        orcids = {r['orcid'] for r in records if r['orcid']}
        author_ids = {r['author_id'] for r in records if r['author_id']}

        if len(orcids) == 1 or len(author_ids) == 1:
            return [records]

        # Union-Find
        parent = list(range(n))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        # Compare all pairs
        for i in range(n):
            for j in range(i + 1, n):
                # Exact ID match
                if (records[i]['orcid'] and records[i]['orcid'] == records[j]['orcid']):
                    union(i, j)
                    continue
                if (records[i]['author_id'] and records[i]['author_id'] == records[j]['author_id']):
                    union(i, j)
                    continue

                # Compute similarity score
                score = self._compute_similarity(records[i], records[j])
                if score >= self.MERGE_THRESHOLD:
                    union(i, j)

        # Build clusters
        clusters = defaultdict(list)
        for i in range(n):
            clusters[find(i)].append(records[i])

        return list(clusters.values())

    def _compute_similarity(self, a: Dict, b: Dict) -> float:
        """
        Compute similarity between two author records.

        Returns float 0.0–1.0.
        """
        score = 0.0

        # 1. Affiliation overlap
        aff_sim = self._jaccard(
            self._tokenize(a.get('affiliation', '')),
            self._tokenize(b.get('affiliation', '')),
        )
        score += aff_sim * self.WEIGHTS['affiliation']

        # 2. Co-author overlap
        coauth_sim = self._jaccard(
            set(a.get('coauthors', [])),
            set(b.get('coauthors', [])),
        )
        score += coauth_sim * self.WEIGHTS['coauthor']

        # 3. Topic consistency
        topics_a = set(a.get('topics', []) + a.get('keywords', []))
        topics_b = set(b.get('topics', []) + b.get('keywords', []))
        topic_sim = self._jaccard(topics_a, topics_b)
        score += topic_sim * self.WEIGHTS['topic']

        # 4. Temporal continuity
        year_a = a.get('paper_year', 0)
        year_b = b.get('paper_year', 0)
        if year_a and year_b:
            gap = abs(year_a - year_b)
            # Same decade → high score, >20 years → low
            temporal_sim = max(0, 1 - gap / 20)
        else:
            temporal_sim = 0.5  # unknown → neutral
        score += temporal_sim * self.WEIGHTS['temporal']

        return score

    @staticmethod
    def _jaccard(set_a: set, set_b: set) -> float:
        """Jaccard similarity between two sets"""
        if not set_a and not set_b:
            return 0.0
        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / len(union) if union else 0.0

    @staticmethod
    def _tokenize(text: str) -> set:
        """Tokenize text into a set of lowercase words"""
        if not text:
            return set()
        return set(re.findall(r'[a-z]+', text.lower()))

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normalize author name for grouping"""
        name = name.strip().lower()
        name = re.sub(r'[^a-z\s\-]', '', name)
        name = re.sub(r'\s+', ' ', name)
        return name

    @staticmethod
    def _make_author(key: str, records: List[Dict]) -> DisambiguatedAuthor:
        """Build DisambiguatedAuthor from a list of records"""
        # Pick the most common name form
        names = Counter(r['name'] for r in records)
        canonical = names.most_common(1)[0][0]

        author_ids = list({r['author_id'] for r in records if r['author_id']})
        orcids = list({r['orcid'] for r in records if r['orcid']})
        affiliations = list({r['affiliation'] for r in records if r['affiliation']})

        all_topics = []
        for r in records:
            all_topics.extend(r.get('topics', []))
        top_topics = [t for t, _ in Counter(all_topics).most_common(10)]

        years = [r['paper_year'] for r in records if r.get('paper_year')]
        titles = [r['paper_title'] for r in records if r.get('paper_title')]
        total_cites = sum(r.get('citations', 0) for r in records)

        return DisambiguatedAuthor(
            canonical_name=canonical,
            author_ids=author_ids,
            orcids=orcids,
            affiliations=affiliations,
            paper_count=len(records),
            paper_titles=titles,
            paper_years=sorted(set(years)),
            topics=top_topics,
            total_citations=total_cites,
        )


# ==================== COLLABORATION NETWORK ====================

class CollaborationNetwork:
    """
    Build and analyze a co-authorship network graph.

    Nodes = authors (DisambiguatedAuthor)
    Edges = co-authorship with weight (number of shared papers)

    Computes:
      - Degree centrality (most connections)
      - Betweenness centrality (bridge authors)
      - Closeness centrality (closest to all others)
      - Community detection (label propagation)
    """

    def build_and_analyze(
        self,
        papers: List[Paper],
        disambiguated: Dict[str, DisambiguatedAuthor],
        top_n: int = 15,
    ) -> NetworkReport:
        """
        Build collaboration graph and run analysis.

        Args:
            papers: Source papers
            disambiguated: Disambiguated author map
            top_n: Number of top authors to highlight

        Returns:
            NetworkReport with full analysis
        """
        print(f"\n  [🕸️] Building collaboration network...")

        # Build adjacency list + edge data
        adj, edges = self._build_graph(papers, disambiguated)

        total_nodes = len(adj)
        total_edges = len(edges)
        print(f"  [·] Graph: {total_nodes} nodes, {total_edges} edges")

        # Compute centrality scores
        degree = self._degree_centrality(adj)
        betweenness = self._betweenness_centrality(adj)
        closeness = self._closeness_centrality(adj)

        # Apply scores to disambiguated authors
        for name, author in disambiguated.items():
            cname = author.canonical_name
            author.degree_centrality = degree.get(cname, 0.0)
            author.betweenness_centrality = betweenness.get(cname, 0.0)
            author.closeness_centrality = closeness.get(cname, 0.0)

        # Top authors
        top_degree = sorted(
            degree.items(), key=lambda x: x[1], reverse=True
        )[:top_n]
        top_between = sorted(
            betweenness.items(), key=lambda x: x[1], reverse=True
        )[:top_n]

        # Top collaboration pairs
        top_pairs = sorted(edges, key=lambda e: e.weight, reverse=True)[:top_n]

        # Community detection
        communities = self._detect_communities(adj)

        report = NetworkReport(
            total_authors=total_nodes,
            total_edges=total_edges,
            total_papers_analyzed=len(papers),
            disambiguated_authors=list(disambiguated.values()),
            collaboration_edges=edges,
            top_authors_by_degree=[f"{n} ({s:.3f})" for n, s in top_degree],
            top_authors_by_betweenness=[f"{n} ({s:.3f})" for n, s in top_between],
            top_collaboration_pairs=[
                {'a': e.author_a, 'b': e.author_b, 'weight': e.weight}
                for e in top_pairs
            ],
            communities=[sorted(c) for c in communities if len(c) >= 2],
        )

        return report

    def _build_graph(
        self, papers: List[Paper], disambiguated: Dict[str, DisambiguatedAuthor]
    ) -> Tuple[Dict[str, Set[str]], List[CollaborationEdge]]:
        """Build adjacency list and edge list from papers"""
        # Create name → canonical_name lookup
        norm_to_canonical = {}
        normalizer = AuthorDisambiguator()
        for key, author in disambiguated.items():
            norm = normalizer._normalize_name(author.canonical_name)
            norm_to_canonical[norm] = author.canonical_name

        adj: Dict[str, Set[str]] = defaultdict(set)
        edge_map: Dict[Tuple[str, str], CollaborationEdge] = {}

        for paper in papers:
            # Get canonical names for this paper's authors
            canonical_authors = []
            for author in paper.authors:
                norm = normalizer._normalize_name(author.name)
                cname = norm_to_canonical.get(norm, author.name)
                canonical_authors.append(cname)

            # Every pair of authors in the same paper = collaboration
            for a, b in combinations(set(canonical_authors), 2):
                key = tuple(sorted([a, b]))

                adj[a].add(b)
                adj[b].add(a)

                if key in edge_map:
                    edge_map[key].weight += 1
                    edge_map[key].shared_papers.append(paper.title)
                    if paper.year:
                        edge_map[key].years.append(paper.year)
                else:
                    edge_map[key] = CollaborationEdge(
                        author_a=key[0],
                        author_b=key[1],
                        weight=1,
                        shared_papers=[paper.title],
                        years=[paper.year] if paper.year else [],
                    )

        # Ensure all disambiguated authors appear in graph
        for author in disambiguated.values():
            if author.canonical_name not in adj:
                adj[author.canonical_name] = set()

        return dict(adj), list(edge_map.values())

    @staticmethod
    def _degree_centrality(adj: Dict[str, Set[str]]) -> Dict[str, float]:
        """
        Degree centrality: fraction of nodes each node is connected to.
        C_D(v) = deg(v) / (n - 1)
        """
        n = len(adj)
        if n <= 1:
            return {name: 0.0 for name in adj}

        return {
            name: len(neighbors) / (n - 1)
            for name, neighbors in adj.items()
        }

    @staticmethod
    def _betweenness_centrality(adj: Dict[str, Set[str]]) -> Dict[str, float]:
        """
        Betweenness centrality using Brandes' algorithm.
        C_B(v) = sum_{s≠v≠t} σ_st(v) / σ_st

        Identifies "bridge" authors connecting different communities.
        """
        nodes = list(adj.keys())
        n = len(nodes)
        betweenness = {v: 0.0 for v in nodes}

        for s in nodes:
            # BFS from s
            stack = []
            predecessors = {v: [] for v in nodes}
            sigma = {v: 0 for v in nodes}
            sigma[s] = 1
            dist = {v: -1 for v in nodes}
            dist[s] = 0
            queue = [s]

            while queue:
                v = queue.pop(0)
                stack.append(v)
                for w in adj.get(v, set()):
                    # First visit
                    if dist[w] < 0:
                        dist[w] = dist[v] + 1
                        queue.append(w)
                    # Shortest path via v
                    if dist[w] == dist[v] + 1:
                        sigma[w] += sigma[v]
                        predecessors[w].append(v)

            # Back-propagation
            delta = {v: 0.0 for v in nodes}
            while stack:
                w = stack.pop()
                for v in predecessors[w]:
                    if sigma[w] > 0:
                        delta[v] += (sigma[v] / sigma[w]) * (1 + delta[w])
                if w != s:
                    betweenness[w] += delta[w]

        # Normalize
        if n > 2:
            norm = 2.0 / ((n - 1) * (n - 2))
            betweenness = {v: c * norm for v, c in betweenness.items()}

        return betweenness

    @staticmethod
    def _closeness_centrality(adj: Dict[str, Set[str]]) -> Dict[str, float]:
        """
        Closeness centrality: inverse of average shortest path.
        C_C(v) = (n-1) / sum_t d(v,t)
        """
        nodes = list(adj.keys())
        n = len(nodes)
        closeness = {}

        for source in nodes:
            # BFS
            dist = {source: 0}
            queue = [source]
            while queue:
                v = queue.pop(0)
                for w in adj.get(v, set()):
                    if w not in dist:
                        dist[w] = dist[v] + 1
                        queue.append(w)

            total_dist = sum(dist.values())
            reachable = len(dist) - 1

            if reachable > 0 and total_dist > 0:
                closeness[source] = reachable / total_dist
            else:
                closeness[source] = 0.0

        return closeness

    @staticmethod
    def _detect_communities(adj: Dict[str, Set[str]]) -> List[List[str]]:
        """
        Simple community detection using label propagation.

        Each node starts with its own label. Iteratively, each node
        adopts the most frequent label among its neighbors.
        """
        nodes = list(adj.keys())
        labels = {node: i for i, node in enumerate(nodes)}

        # Iterate until convergence (max 50 iters)
        for _ in range(50):
            changed = False
            for node in nodes:
                neighbors = adj.get(node, set())
                if not neighbors:
                    continue

                # Count neighbor labels
                label_counts = Counter(labels[n] for n in neighbors)
                most_common = label_counts.most_common(1)[0][0]

                if labels[node] != most_common:
                    labels[node] = most_common
                    changed = True

            if not changed:
                break

        # Group by label
        communities = defaultdict(list)
        for node, label in labels.items():
            communities[label].append(node)

        return [members for members in communities.values() if len(members) >= 2]

    @staticmethod
    def print_report(report: NetworkReport):
        """Print formatted network analysis report"""
        print(f"\n{'='*65}")
        print(f"  🕸️  Author Collaboration Network Analysis")
        print(f"{'='*65}")
        print(f"  Papers analyzed: {report.total_papers_analyzed}")
        print(f"  Unique authors:  {report.total_authors}")
        print(f"  Collaborations:  {report.total_edges}")

        if report.communities:
            print(f"  Communities:     {len(report.communities)}")

        # Top by degree centrality
        if report.top_authors_by_degree:
            print(f"\n  📊 Top Authors by Connections (Degree Centrality)")
            print(f"  {'─'*55}")
            for i, entry in enumerate(report.top_authors_by_degree[:10], 1):
                print(f"  {i:2d}. {entry}")

        # Top by betweenness
        if report.top_authors_by_betweenness:
            print(f"\n  🌉 Bridge Authors (Betweenness Centrality)")
            print(f"  {'─'*55}")
            for i, entry in enumerate(report.top_authors_by_betweenness[:10], 1):
                print(f"  {i:2d}. {entry}")

        # Top collaboration pairs
        if report.top_collaboration_pairs:
            print(f"\n  🤝 Strongest Collaborations")
            print(f"  {'─'*55}")
            for i, pair in enumerate(report.top_collaboration_pairs[:10], 1):
                print(f"  {i:2d}. {pair['a']} ↔ {pair['b']} ({pair['weight']} papers)")

        # Communities
        if report.communities:
            print(f"\n  👥 Research Communities ({len(report.communities)} detected)")
            print(f"  {'─'*55}")
            for i, comm in enumerate(report.communities[:5], 1):
                members = ", ".join(comm[:5])
                if len(comm) > 5:
                    members += f" +{len(comm)-5} more"
                print(f"  {i}. [{len(comm)} members] {members}")

        print(f"\n{'='*65}")
