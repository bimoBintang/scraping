"""
Temporal Network Analysis
Analyze network structure changes over time with configurable intervals

Features:
- Network snapshots at configurable intervals
- Growth/churn metrics
- Temporal centrality measures
- Burstiness coefficient
- Persistence metrics
"""

import asyncio
import math
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


@dataclass
class NetworkSnapshot:
    """Snapshot of network at specific timestamp"""
    timestamp: datetime
    nodes: Set[str]
    edges: Dict[str, Set[str]]  # user -> set of connections
    
    # Basic metrics
    node_count: int = 0
    edge_count: int = 0
    density: float = 0.0
    avg_degree: float = 0.0
    
    # Advanced metrics
    centrality_scores: Dict[str, float] = field(default_factory=dict)
    
    def __post_init__(self):
        self.node_count = len(self.nodes)
        self.edge_count = sum(len(e) for e in self.edges.values())
        
        if self.node_count > 1:
            max_edges = self.node_count * (self.node_count - 1)
            self.density = self.edge_count / max_edges if max_edges > 0 else 0
            self.avg_degree = self.edge_count / self.node_count
    
    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "density": round(self.density, 6),
            "avg_degree": round(self.avg_degree, 2),
        }


@dataclass
class NetworkDiff:
    """Difference between two network snapshots"""
    timestamp_from: datetime
    timestamp_to: datetime
    
    # Node changes
    nodes_added: Set[str] = field(default_factory=set)
    nodes_removed: Set[str] = field(default_factory=set)
    
    # Edge changes
    edges_added: int = 0
    edges_removed: int = 0
    
    # Metrics
    node_growth_rate: float = 0.0
    edge_growth_rate: float = 0.0
    churn_rate: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "period": {
                "from": self.timestamp_from.isoformat(),
                "to": self.timestamp_to.isoformat(),
            },
            "nodes_added": len(self.nodes_added),
            "nodes_removed": len(self.nodes_removed),
            "edges_added": self.edges_added,
            "edges_removed": self.edges_removed,
            "node_growth_rate": round(self.node_growth_rate, 4),
            "edge_growth_rate": round(self.edge_growth_rate, 4),
            "churn_rate": round(self.churn_rate, 4),
        }


@dataclass
class GrowthAnalysis:
    """Comprehensive growth analysis over time"""
    total_snapshots: int
    time_span: timedelta
    
    # Growth rates
    avg_node_growth: float
    avg_edge_growth: float
    
    # Stability
    avg_churn_rate: float
    persistence_rate: float  # Nodes present in all snapshots
    
    # Burstiness
    burstiness_coefficient: float  # σ/μ - 1 for inter-event times
    
    def to_dict(self) -> Dict:
        return {
            "total_snapshots": self.total_snapshots,
            "time_span_hours": self.time_span.total_seconds() / 3600,
            "avg_node_growth": round(self.avg_node_growth, 4),
            "avg_edge_growth": round(self.avg_edge_growth, 4),
            "avg_churn_rate": round(self.avg_churn_rate, 4),
            "persistence_rate": round(self.persistence_rate, 4),
            "burstiness_coefficient": round(self.burstiness_coefficient, 4),
        }


class TemporalNetworkAnalyzer:
    """
    Analyze network evolution with configurable intervals
    
    Usage:
        analyzer = TemporalNetworkAnalyzer(interval_hours=24)
        
        # Capture multiple snapshots
        await analyzer.capture_snapshot(seed_users, get_connections)
        await asyncio.sleep(3600)  # Wait 1 hour
        await analyzer.capture_snapshot(seed_users, get_connections)
        
        # Analyze changes
        diff = analyzer.compare_snapshots(0, 1)
        growth = analyzer.get_growth_metrics()
    """
    
    def __init__(
        self,
        interval_hours: int = 24,
        max_users_per_snapshot: int = 500,
        delay_between: float = 1.5
    ):
        self.interval = timedelta(hours=interval_hours)
        self.max_users = max_users_per_snapshot
        self.delay_between = delay_between
        self.snapshots: List[NetworkSnapshot] = []
        self._node_history: Dict[str, List[datetime]] = {}  # Track when nodes appear
    
    async def capture_snapshot(
        self,
        seed_users: List[str],
        get_connections: Callable,
        connection_type: str = "followers"
    ) -> NetworkSnapshot:
        """
        Capture current network state
        
        Args:
            seed_users: Starting points for network discovery
            get_connections: Async function to get user connections
            connection_type: Type of connections to fetch
            
        Returns:
            NetworkSnapshot of current state
        """
        timestamp = datetime.now()
        nodes: Set[str] = set()
        edges: Dict[str, Set[str]] = {}
        
        # BFS to discover network
        queue = deque(seed_users)
        visited = set(seed_users)
        
        print(f"[Temporal] Capturing snapshot at {timestamp.isoformat()}")
        
        while queue and len(nodes) < self.max_users:
            current = queue.popleft()
            nodes.add(current)
            
            try:
                connections = await get_connections(current)
                await asyncio.sleep(self.delay_between)
                
                edges[current] = set()
                for conn in connections[:50]:  # Limit per user
                    conn_user = conn.get('username')
                    if conn_user:
                        edges[current].add(conn_user)
                        nodes.add(conn_user)
                        
                        if conn_user not in visited and len(nodes) < self.max_users:
                            visited.add(conn_user)
                            queue.append(conn_user)
                            
            except Exception as e:
                print(f"[Temporal] Error getting connections for {current}: {e}")
        
        # Update node history for persistence tracking
        for node in nodes:
            if node not in self._node_history:
                self._node_history[node] = []
            self._node_history[node].append(timestamp)
        
        # Calculate centrality scores
        centrality = self._calculate_degree_centrality(nodes, edges)
        
        snapshot = NetworkSnapshot(
            timestamp=timestamp,
            nodes=nodes,
            edges=edges,
            centrality_scores=centrality
        )
        
        self.snapshots.append(snapshot)
        print(f"[Temporal] Snapshot captured: {snapshot.node_count} nodes, {snapshot.edge_count} edges")
        
        return snapshot
    
    def compare_snapshots(
        self,
        index1: int = -2,
        index2: int = -1
    ) -> Optional[NetworkDiff]:
        """
        Compare two snapshots
        
        Args:
            index1: Index of first snapshot (default: second-to-last)
            index2: Index of second snapshot (default: last)
            
        Returns:
            NetworkDiff with changes, or None if insufficient snapshots
        """
        if len(self.snapshots) < 2:
            return None
        
        snap1 = self.snapshots[index1]
        snap2 = self.snapshots[index2]
        
        nodes_added = snap2.nodes - snap1.nodes
        nodes_removed = snap1.nodes - snap2.nodes
        
        # Count edge changes
        edges_added = 0
        edges_removed = 0
        
        all_users = snap1.nodes | snap2.nodes
        for user in all_users:
            old_edges = snap1.edges.get(user, set())
            new_edges = snap2.edges.get(user, set())
            edges_added += len(new_edges - old_edges)
            edges_removed += len(old_edges - new_edges)
        
        # Calculate rates
        time_delta = (snap2.timestamp - snap1.timestamp).total_seconds() / 3600  # hours
        
        node_growth = (snap2.node_count - snap1.node_count) / max(snap1.node_count, 1)
        edge_growth = (snap2.edge_count - snap1.edge_count) / max(snap1.edge_count, 1)
        churn = len(nodes_removed) / max(snap1.node_count, 1)
        
        return NetworkDiff(
            timestamp_from=snap1.timestamp,
            timestamp_to=snap2.timestamp,
            nodes_added=nodes_added,
            nodes_removed=nodes_removed,
            edges_added=edges_added,
            edges_removed=edges_removed,
            node_growth_rate=node_growth / max(time_delta, 1),
            edge_growth_rate=edge_growth / max(time_delta, 1),
            churn_rate=churn,
        )
    
    def get_growth_metrics(self) -> Optional[GrowthAnalysis]:
        """
        Calculate comprehensive growth analysis
        
        Returns:
            GrowthAnalysis with all temporal metrics
        """
        if len(self.snapshots) < 2:
            return None
        
        # Calculate average growth rates
        node_growths = []
        edge_growths = []
        churns = []
        
        for i in range(1, len(self.snapshots)):
            diff = self.compare_snapshots(i - 1, i)
            if diff:
                node_growths.append(diff.node_growth_rate)
                edge_growths.append(diff.edge_growth_rate)
                churns.append(diff.churn_rate)
        
        # Persistence: nodes that appear in ALL snapshots
        persistent_nodes = set.intersection(*[s.nodes for s in self.snapshots])
        all_nodes = set.union(*[s.nodes for s in self.snapshots])
        persistence_rate = len(persistent_nodes) / max(len(all_nodes), 1)
        
        # Burstiness coefficient
        burstiness = self._calculate_burstiness()
        
        time_span = self.snapshots[-1].timestamp - self.snapshots[0].timestamp
        
        return GrowthAnalysis(
            total_snapshots=len(self.snapshots),
            time_span=time_span,
            avg_node_growth=sum(node_growths) / len(node_growths) if node_growths else 0,
            avg_edge_growth=sum(edge_growths) / len(edge_growths) if edge_growths else 0,
            avg_churn_rate=sum(churns) / len(churns) if churns else 0,
            persistence_rate=persistence_rate,
            burstiness_coefficient=burstiness,
        )
    
    def get_temporal_centrality(self, username: str) -> Dict[str, float]:
        """
        Calculate temporal centrality measures for a user
        
        Args:
            username: User to analyze
            
        Returns:
            Dict with temporal centrality metrics
        """
        if not self.snapshots:
            return {}
        
        centralities = []
        presence_count = 0
        
        for snap in self.snapshots:
            if username in snap.nodes:
                presence_count += 1
                centralities.append(snap.centrality_scores.get(username, 0))
        
        if not centralities:
            return {"presence_rate": 0, "avg_centrality": 0, "centrality_stability": 0}
        
        avg_centrality = sum(centralities) / len(centralities)
        
        # Stability: inverse of coefficient of variation
        if len(centralities) > 1 and avg_centrality > 0:
            variance = sum((c - avg_centrality) ** 2 for c in centralities) / len(centralities)
            cv = math.sqrt(variance) / avg_centrality
            stability = 1 / (1 + cv)  # Normalize to 0-1
        else:
            stability = 1.0
        
        return {
            "presence_rate": presence_count / len(self.snapshots),
            "avg_centrality": round(avg_centrality, 6),
            "centrality_stability": round(stability, 4),
            "centrality_trend": self._get_trend(centralities),
        }
    
    def get_churn_rate(self, index1: int = -2, index2: int = -1) -> float:
        """Get churn rate between two snapshots"""
        diff = self.compare_snapshots(index1, index2)
        return diff.churn_rate if diff else 0.0
    
    def export_timeline(self) -> List[Dict]:
        """Export all snapshots as timeline"""
        timeline = []
        
        for i, snap in enumerate(self.snapshots):
            entry = snap.to_dict()
            entry["index"] = i
            
            if i > 0:
                diff = self.compare_snapshots(i - 1, i)
                if diff:
                    entry["changes"] = diff.to_dict()
            
            timeline.append(entry)
        
        return timeline
    
    def _calculate_degree_centrality(
        self,
        nodes: Set[str],
        edges: Dict[str, Set[str]]
    ) -> Dict[str, float]:
        """Calculate normalized degree centrality"""
        n = len(nodes)
        if n <= 1:
            return {node: 0.0 for node in nodes}
        
        centrality = {}
        for node in nodes:
            degree = len(edges.get(node, set()))
            centrality[node] = degree / (n - 1)
        
        return centrality
    
    def _calculate_burstiness(self) -> float:
        """
        Calculate burstiness coefficient: (σ - μ) / (σ + μ)
        
        Range: -1 (periodic) to 1 (bursty), 0 = random
        """
        if len(self.snapshots) < 3:
            return 0.0
        
        # Calculate inter-snapshot intervals
        intervals = []
        for i in range(1, len(self.snapshots)):
            delta = (self.snapshots[i].timestamp - self.snapshots[i-1].timestamp).total_seconds()
            intervals.append(delta)
        
        if not intervals:
            return 0.0
        
        mean = sum(intervals) / len(intervals)
        if mean == 0:
            return 0.0
        
        variance = sum((x - mean) ** 2 for x in intervals) / len(intervals)
        std = math.sqrt(variance)
        
        # Burstiness: (σ - μ) / (σ + μ)
        return (std - mean) / (std + mean) if (std + mean) > 0 else 0.0
    
    def _get_trend(self, values: List[float]) -> str:
        """Determine trend direction from a series of values"""
        if len(values) < 2:
            return "stable"
        
        first_half = sum(values[:len(values)//2]) / max(len(values)//2, 1)
        second_half = sum(values[len(values)//2:]) / max(len(values) - len(values)//2, 1)
        
        diff = second_half - first_half
        threshold = 0.1 * max(abs(first_half), abs(second_half), 0.01)
        
        if diff > threshold:
            return "increasing"
        elif diff < -threshold:
            return "decreasing"
        return "stable"
