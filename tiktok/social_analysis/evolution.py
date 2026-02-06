"""
Community Evolution Analysis
Study how communities form, merge, split, and dissolve over time

Features:
- Community state snapshots
- Merge/split detection
- Modularity trajectory
- Community loyalty index
- Boundary spanner analysis
"""

import asyncio
import math
import random
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from enum import Enum


class CommunityEventType(str, Enum):
    """Types of community evolution events"""
    BIRTH = "birth"
    DEATH = "death"
    MERGE = "merge"
    SPLIT = "split"
    GROWTH = "growth"
    SHRINK = "shrink"
    STABLE = "stable"


@dataclass
class CommunityState:
    """Community at a point in time"""
    community_id: str
    members: Set[str]
    timestamp: datetime
    
    # Structure metrics
    size: int = 0
    internal_edges: int = 0
    external_edges: int = 0
    
    # Key members
    centroid_user: str = ""  # Most connected member
    boundary_spanners: List[str] = field(default_factory=list)  # Bridge nodes
    
    def __post_init__(self):
        self.size = len(self.members)
    
    def to_dict(self) -> Dict:
        return {
            "community_id": self.community_id,
            "size": self.size,
            "timestamp": self.timestamp.isoformat(),
            "centroid": self.centroid_user,
            "boundary_spanners": self.boundary_spanners[:5],
        }


@dataclass
class CommunityEvent:
    """Event in community evolution"""
    event_type: CommunityEventType
    timestamp: datetime
    communities_involved: List[str]
    details: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "communities": self.communities_involved,
            "details": self.details,
        }


@dataclass
class CommunityLifecycle:
    """Lifecycle of a single community"""
    community_id: str
    birth_time: datetime
    death_time: Optional[datetime]
    
    # History
    size_history: List[Tuple[datetime, int]] = field(default_factory=list)
    events: List[CommunityEvent] = field(default_factory=list)
    
    # Metrics
    lifespan_hours: float = 0.0
    avg_size: float = 0.0
    stability: float = 0.0  # Jaccard similarity between consecutive snapshots
    loyalty_index: float = 0.0  # Members that stayed throughout
    
    def to_dict(self) -> Dict:
        return {
            "community_id": self.community_id,
            "birth": self.birth_time.isoformat(),
            "death": self.death_time.isoformat() if self.death_time else None,
            "lifespan_hours": round(self.lifespan_hours, 2),
            "avg_size": round(self.avg_size, 2),
            "stability": round(self.stability, 4),
            "loyalty_index": round(self.loyalty_index, 4),
            "event_count": len(self.events),
        }


class CommunityEvolutionAnalyzer:
    """
    Analyze community lifecycle
    
    Usage:
        analyzer = CommunityEvolutionAnalyzer(similarity_threshold=0.5)
        
        # Take multiple snapshots
        await analyzer.snapshot_communities(seed_users, get_connections)
        await asyncio.sleep(3600)
        await analyzer.snapshot_communities(seed_users, get_connections)
        
        # Analyze evolution
        events = analyzer.track_evolution()
        lifecycle = analyzer.get_lifecycle("community_0")
    """
    
    def __init__(
        self,
        similarity_threshold: float = 0.5,
        max_users: int = 500,
        max_iterations: int = 15,
        delay_between: float = 1.5
    ):
        self.similarity_threshold = similarity_threshold
        self.max_users = max_users
        self.max_iterations = max_iterations
        self.delay_between = delay_between
        
        self.history: List[Dict[str, CommunityState]] = []  # Snapshots of all communities
        self.evolution_events: List[CommunityEvent] = []
        self._modularity_history: List[Tuple[datetime, float]] = []
    
    async def snapshot_communities(
        self,
        seed_users: List[str],
        get_connections: Callable
    ) -> Dict[str, CommunityState]:
        """
        Capture current community structure
        
        Args:
            seed_users: Starting points
            get_connections: Async function for connections
            
        Returns:
            Dict of community_id -> CommunityState
        """
        timestamp = datetime.now()
        print(f"[Evolution] Capturing community snapshot at {timestamp.isoformat()}")
        
        # Build graph first
        graph, all_nodes = await self._build_graph(seed_users, get_connections)
        
        # Detect communities using Label Propagation
        communities = self._label_propagation(graph, all_nodes)
        
        # Calculate modularity
        modularity = self._calculate_modularity(graph, communities)
        self._modularity_history.append((timestamp, modularity))
        
        # Build community states
        states: Dict[str, CommunityState] = {}
        
        for i, (comm_id, members) in enumerate(communities.items()):
            # Find centroid (highest internal degree)
            centroid = self._find_centroid(members, graph)
            
            # Find boundary spanners
            spanners = self._find_boundary_spanners(members, graph, communities)
            
            # Count edges
            internal, external = self._count_edges(members, graph)
            
            state = CommunityState(
                community_id=comm_id,
                members=members,
                timestamp=timestamp,
                internal_edges=internal,
                external_edges=external,
                centroid_user=centroid,
                boundary_spanners=spanners,
            )
            states[comm_id] = state
        
        self.history.append(states)
        print(f"[Evolution] Detected {len(states)} communities, modularity={modularity:.4f}")
        
        return states
    
    def track_evolution(self) -> List[CommunityEvent]:
        """
        Analyze evolution between all snapshots
        
        Returns:
            List of CommunityEvent
        """
        if len(self.history) < 2:
            return []
        
        all_events = []
        
        for i in range(1, len(self.history)):
            old_snapshot = self.history[i - 1]
            new_snapshot = self.history[i]
            
            timestamp = next(iter(new_snapshot.values())).timestamp if new_snapshot else datetime.now()
            
            # Detect births
            births = self._detect_births(old_snapshot, new_snapshot)
            all_events.extend(births)
            
            # Detect deaths
            deaths = self._detect_deaths(old_snapshot, new_snapshot)
            all_events.extend(deaths)
            
            # Detect merges
            merges = self.detect_merge(old_snapshot, new_snapshot)
            all_events.extend(merges)
            
            # Detect splits
            splits = self.detect_split(old_snapshot, new_snapshot)
            all_events.extend(splits)
            
            # Detect growth/shrink
            changes = self._detect_size_changes(old_snapshot, new_snapshot)
            all_events.extend(changes)
        
        self.evolution_events = all_events
        return all_events
    
    def detect_merge(
        self,
        old_communities: Dict[str, CommunityState],
        new_communities: Dict[str, CommunityState]
    ) -> List[CommunityEvent]:
        """Detect communities that merged"""
        merges = []
        
        for new_id, new_state in new_communities.items():
            # Find old communities that contribute most members
            contributors = []
            
            for old_id, old_state in old_communities.items():
                overlap = len(new_state.members & old_state.members)
                if overlap > 0:
                    contribution = overlap / len(old_state.members)
                    if contribution > 0.3:  # Significant contribution
                        contributors.append((old_id, contribution))
            
            # If multiple old communities contribute significantly
            if len(contributors) >= 2:
                merges.append(CommunityEvent(
                    event_type=CommunityEventType.MERGE,
                    timestamp=new_state.timestamp,
                    communities_involved=[c[0] for c in contributors] + [new_id],
                    details={
                        "result": new_id,
                        "contributors": {c[0]: round(c[1], 3) for c in contributors}
                    }
                ))
        
        return merges
    
    def detect_split(
        self,
        old_communities: Dict[str, CommunityState],
        new_communities: Dict[str, CommunityState]
    ) -> List[CommunityEvent]:
        """Detect communities that split"""
        splits = []
        
        for old_id, old_state in old_communities.items():
            # Find new communities that contain old members
            fragments = []
            
            for new_id, new_state in new_communities.items():
                overlap = len(old_state.members & new_state.members)
                if overlap > 0:
                    fragment_ratio = overlap / len(old_state.members)
                    if fragment_ratio > 0.2:  # Significant fragment
                        fragments.append((new_id, fragment_ratio))
            
            # If old community split into multiple
            if len(fragments) >= 2:
                splits.append(CommunityEvent(
                    event_type=CommunityEventType.SPLIT,
                    timestamp=next(iter(new_communities.values())).timestamp,
                    communities_involved=[old_id] + [f[0] for f in fragments],
                    details={
                        "source": old_id,
                        "fragments": {f[0]: round(f[1], 3) for f in fragments}
                    }
                ))
        
        return splits
    
    def get_community_stability(self, community_id: str) -> float:
        """
        Calculate stability: average Jaccard similarity over time
        """
        member_sets = []
        
        for snapshot in self.history:
            if community_id in snapshot:
                member_sets.append(snapshot[community_id].members)
        
        if len(member_sets) < 2:
            return 1.0
        
        similarities = []
        for i in range(1, len(member_sets)):
            intersection = len(member_sets[i] & member_sets[i-1])
            union = len(member_sets[i] | member_sets[i-1])
            if union > 0:
                similarities.append(intersection / union)
        
        return sum(similarities) / len(similarities) if similarities else 1.0
    
    def get_lifecycle(self, community_id: str) -> Optional[CommunityLifecycle]:
        """Get complete lifecycle for a community"""
        appearances = []
        
        for snapshot in self.history:
            if community_id in snapshot:
                state = snapshot[community_id]
                appearances.append(state)
        
        if not appearances:
            return None
        
        first = appearances[0]
        last = appearances[-1]
        
        # Check if community is still alive
        is_alive = community_id in self.history[-1] if self.history else False
        
        # Calculate metrics
        sizes = [(a.timestamp, a.size) for a in appearances]
        stability = self.get_community_stability(community_id)
        
        # Loyalty: members present in first and last snapshot
        loyalty = 0.0
        if len(appearances) >= 2:
            intersection = len(first.members & last.members)
            loyalty = intersection / len(first.members) if first.members else 0
        
        lifespan = (last.timestamp - first.timestamp).total_seconds() / 3600
        
        # Get relevant events
        relevant_events = [
            e for e in self.evolution_events
            if community_id in e.communities_involved
        ]
        
        return CommunityLifecycle(
            community_id=community_id,
            birth_time=first.timestamp,
            death_time=None if is_alive else last.timestamp,
            size_history=sizes,
            events=relevant_events,
            lifespan_hours=lifespan,
            avg_size=sum(s[1] for s in sizes) / len(sizes) if sizes else 0,
            stability=stability,
            loyalty_index=loyalty,
        )
    
    def get_modularity_trajectory(self) -> List[Dict]:
        """Get modularity scores over time"""
        return [
            {"timestamp": ts.isoformat(), "modularity": round(m, 4)}
            for ts, m in self._modularity_history
        ]
    
    def get_boundary_spanners(self, snapshot_index: int = -1) -> List[Dict]:
        """
        Get all boundary spanners from a snapshot
        
        Boundary spanners: nodes connected to multiple communities
        """
        if not self.history:
            return []
        
        snapshot = self.history[snapshot_index]
        all_spanners: Dict[str, List[str]] = {}  # user -> communities
        
        for comm_id, state in snapshot.items():
            for spanner in state.boundary_spanners:
                if spanner not in all_spanners:
                    all_spanners[spanner] = []
                all_spanners[spanner].append(comm_id)
        
        # Filter to those in multiple communities
        results = [
            {
                "username": user,
                "communities": comms,
                "span_count": len(comms),
                "profile_url": f"https://www.tiktok.com/@{user}"
            }
            for user, comms in all_spanners.items()
            if len(comms) > 1
        ]
        
        return sorted(results, key=lambda x: -x["span_count"])
    
    # ============ Private Methods ============
    
    async def _build_graph(
        self,
        seed_users: List[str],
        get_connections: Callable
    ) -> Tuple[Dict[str, Set[str]], Set[str]]:
        """Build adjacency graph"""
        graph: Dict[str, Set[str]] = {}
        all_nodes: Set[str] = set(seed_users)
        
        queue = deque(seed_users)
        visited = set(seed_users)
        
        while queue and len(all_nodes) < self.max_users:
            current = queue.popleft()
            
            try:
                connections = await get_connections(current)
                await asyncio.sleep(self.delay_between)
                
                graph[current] = set()
                for conn in connections[:30]:
                    neighbor = conn.get('username')
                    if neighbor:
                        graph[current].add(neighbor)
                        all_nodes.add(neighbor)
                        
                        if neighbor not in visited and len(all_nodes) < self.max_users:
                            visited.add(neighbor)
                            queue.append(neighbor)
                            
            except Exception as e:
                print(f"[Evolution] Error: {e}")
        
        # Make symmetric
        for user, neighbors in list(graph.items()):
            for neighbor in neighbors:
                if neighbor not in graph:
                    graph[neighbor] = set()
                graph[neighbor].add(user)
        
        return graph, all_nodes
    
    def _label_propagation(
        self,
        graph: Dict[str, Set[str]],
        all_nodes: Set[str]
    ) -> Dict[str, Set[str]]:
        """Label propagation for community detection"""
        labels = {user: i for i, user in enumerate(all_nodes)}
        users_list = list(all_nodes)
        
        for _ in range(self.max_iterations):
            changed = False
            random.shuffle(users_list)
            
            for user in users_list:
                neighbors = graph.get(user, set())
                if not neighbors:
                    continue
                
                label_counts: Dict[int, int] = {}
                for neighbor in neighbors:
                    if neighbor in labels:
                        lbl = labels[neighbor]
                        label_counts[lbl] = label_counts.get(lbl, 0) + 1
                
                if label_counts:
                    max_label = max(label_counts, key=label_counts.get)
                    if labels[user] != max_label:
                        labels[user] = max_label
                        changed = True
            
            if not changed:
                break
        
        # Group by label
        communities: Dict[str, Set[str]] = {}
        for user, label in labels.items():
            comm_id = f"community_{label}"
            if comm_id not in communities:
                communities[comm_id] = set()
            communities[comm_id].add(user)
        
        return communities
    
    def _calculate_modularity(
        self,
        graph: Dict[str, Set[str]],
        communities: Dict[str, Set[str]]
    ) -> float:
        """Calculate Newman modularity Q"""
        m = sum(len(edges) for edges in graph.values()) / 2  # Total edges
        if m == 0:
            return 0.0
        
        q = 0.0
        
        for comm_id, members in communities.items():
            for u in members:
                for v in members:
                    if u == v:
                        continue
                    
                    a_uv = 1 if v in graph.get(u, set()) else 0
                    k_u = len(graph.get(u, set()))
                    k_v = len(graph.get(v, set()))
                    
                    q += a_uv - (k_u * k_v) / (2 * m)
        
        return q / (2 * m)
    
    def _find_centroid(self, members: Set[str], graph: Dict[str, Set[str]]) -> str:
        """Find node with highest internal degree"""
        max_internal = -1
        centroid = ""
        
        for member in members:
            internal_degree = len(graph.get(member, set()) & members)
            if internal_degree > max_internal:
                max_internal = internal_degree
                centroid = member
        
        return centroid
    
    def _find_boundary_spanners(
        self,
        members: Set[str],
        graph: Dict[str, Set[str]],
        all_communities: Dict[str, Set[str]]
    ) -> List[str]:
        """Find nodes connected to other communities"""
        spanners = []
        
        other_members = set()
        for comm_id, comm_members in all_communities.items():
            if comm_members != members:
                other_members |= comm_members
        
        for member in members:
            external = graph.get(member, set()) & other_members
            if external:
                spanners.append(member)
        
        return spanners
    
    def _count_edges(
        self,
        members: Set[str],
        graph: Dict[str, Set[str]]
    ) -> Tuple[int, int]:
        """Count internal and external edges"""
        internal = 0
        external = 0
        
        for member in members:
            neighbors = graph.get(member, set())
            internal += len(neighbors & members)
            external += len(neighbors - members)
        
        return internal // 2, external  # Internal counted twice
    
    def _detect_births(
        self,
        old: Dict[str, CommunityState],
        new: Dict[str, CommunityState]
    ) -> List[CommunityEvent]:
        """Detect newly formed communities"""
        events = []
        
        for new_id, new_state in new.items():
            # Check if this community has significant overlap with any old one
            has_predecessor = False
            
            for old_id, old_state in old.items():
                jaccard = len(new_state.members & old_state.members) / len(new_state.members | old_state.members)
                if jaccard > self.similarity_threshold:
                    has_predecessor = True
                    break
            
            if not has_predecessor:
                events.append(CommunityEvent(
                    event_type=CommunityEventType.BIRTH,
                    timestamp=new_state.timestamp,
                    communities_involved=[new_id],
                    details={"initial_size": new_state.size}
                ))
        
        return events
    
    def _detect_deaths(
        self,
        old: Dict[str, CommunityState],
        new: Dict[str, CommunityState]
    ) -> List[CommunityEvent]:
        """Detect dissolved communities"""
        events = []
        timestamp = next(iter(new.values())).timestamp if new else datetime.now()
        
        for old_id, old_state in old.items():
            has_successor = False
            
            for new_id, new_state in new.items():
                jaccard = len(old_state.members & new_state.members) / len(old_state.members | new_state.members)
                if jaccard > self.similarity_threshold:
                    has_successor = True
                    break
            
            if not has_successor:
                events.append(CommunityEvent(
                    event_type=CommunityEventType.DEATH,
                    timestamp=timestamp,
                    communities_involved=[old_id],
                    details={"final_size": old_state.size}
                ))
        
        return events
    
    def _detect_size_changes(
        self,
        old: Dict[str, CommunityState],
        new: Dict[str, CommunityState]
    ) -> List[CommunityEvent]:
        """Detect significant size changes"""
        events = []
        
        for new_id, new_state in new.items():
            # Find matching old community
            best_match = None
            best_jaccard = 0
            
            for old_id, old_state in old.items():
                jaccard = len(new_state.members & old_state.members) / len(new_state.members | old_state.members)
                if jaccard > best_jaccard:
                    best_jaccard = jaccard
                    best_match = old_state
            
            if best_match and best_jaccard > self.similarity_threshold:
                change = (new_state.size - best_match.size) / max(best_match.size, 1)
                
                if change > 0.2:
                    events.append(CommunityEvent(
                        event_type=CommunityEventType.GROWTH,
                        timestamp=new_state.timestamp,
                        communities_involved=[new_id],
                        details={"change_percent": round(change * 100, 1)}
                    ))
                elif change < -0.2:
                    events.append(CommunityEvent(
                        event_type=CommunityEventType.SHRINK,
                        timestamp=new_state.timestamp,
                        communities_involved=[new_id],
                        details={"change_percent": round(change * 100, 1)}
                    ))
        
        return events
