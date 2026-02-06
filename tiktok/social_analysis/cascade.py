"""
Influence Cascade Tracking
Track how influence spreads through social network

Features:
- Cascade tree construction
- Propagation speed measurement
- Structural virality index
- Super-spreader identification
- Branching factor distribution
"""

import asyncio
import math
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


@dataclass
class CascadeEvent:
    """Single event in influence cascade"""
    cascade_id: str
    source_user: str
    target_user: str
    timestamp: datetime
    depth: int
    
    def to_dict(self) -> Dict:
        return {
            "cascade_id": self.cascade_id,
            "source": self.source_user,
            "target": self.target_user,
            "timestamp": self.timestamp.isoformat(),
            "depth": self.depth,
        }


@dataclass
class CascadeNode:
    """Node in cascade tree"""
    username: str
    depth: int
    children: List["CascadeNode"] = field(default_factory=list)
    timestamp: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        return {
            "username": self.username,
            "depth": self.depth,
            "children_count": len(self.children),
            "children": [c.to_dict() for c in self.children],
        }


@dataclass
class CascadeStats:
    """Statistics for a cascade"""
    cascade_id: str
    origin_user: str
    total_nodes: int
    max_depth: int
    
    # Speed metrics
    propagation_speed: float  # Nodes per hour
    time_to_peak: float       # Hours to max spread rate
    cascade_duration: float   # Total hours
    
    # Virality metrics
    structural_virality: float   # Wiener index based
    viral_coefficient: float     # Avg children per node
    branching_factor_avg: float
    branching_factor_max: int
    
    # Distribution
    depth_distribution: Dict[int, int] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "cascade_id": self.cascade_id,
            "origin": self.origin_user,
            "total_nodes": self.total_nodes,
            "max_depth": self.max_depth,
            "propagation_speed": round(self.propagation_speed, 4),
            "time_to_peak_hours": round(self.time_to_peak, 2),
            "cascade_duration_hours": round(self.cascade_duration, 2),
            "structural_virality": round(self.structural_virality, 4),
            "viral_coefficient": round(self.viral_coefficient, 4),
            "branching_factor_avg": round(self.branching_factor_avg, 4),
            "branching_factor_max": self.branching_factor_max,
            "depth_distribution": self.depth_distribution,
        }


class InfluenceCascadeTracker:
    """
    Track influence propagation patterns
    
    Usage:
        tracker = InfluenceCascadeTracker(max_depth=5)
        
        # Track cascade from origin
        cascade = await tracker.track_cascade("influencer", get_connections)
        
        # Get statistics
        stats = tracker.get_cascade_statistics(cascade.cascade_id)
        spreaders = tracker.identify_super_spreaders()
    """
    
    def __init__(
        self,
        max_depth: int = 5,
        max_nodes: int = 1000,
        delay_between: float = 1.5
    ):
        self.max_depth = max_depth
        self.max_nodes = max_nodes
        self.delay_between = delay_between
        
        self.cascades: Dict[str, CascadeNode] = {}  # cascade_id -> root node
        self.events: Dict[str, List[CascadeEvent]] = {}  # cascade_id -> events
        self._node_children: Dict[str, int] = {}  # Track children count per node
    
    async def track_cascade(
        self,
        origin_user: str,
        get_connections: Callable,
        cascade_id: Optional[str] = None
    ) -> CascadeNode:
        """
        Track influence cascade from origin
        
        Args:
            origin_user: Starting point of cascade
            get_connections: Async function to get connections
            cascade_id: Optional custom ID
            
        Returns:
            Root node of cascade tree
        """
        cascade_id = cascade_id or str(uuid.uuid4())[:8]
        start_time = datetime.now()
        
        print(f"[Cascade] Tracking from @{origin_user}, max_depth={self.max_depth}")
        
        # Build cascade tree using BFS
        root = CascadeNode(
            username=origin_user,
            depth=0,
            timestamp=start_time
        )
        
        events: List[CascadeEvent] = []
        visited: Set[str] = {origin_user}
        queue: deque = deque([(root, 0)])
        
        nodes_at_depth: Dict[int, List[datetime]] = {0: [start_time]}
        
        while queue and len(visited) < self.max_nodes:
            node, depth = queue.popleft()
            
            if depth >= self.max_depth:
                continue
            
            try:
                connections = await get_connections(node.username)
                await asyncio.sleep(self.delay_between)
                
                timestamp = datetime.now()
                children_count = 0
                
                for conn in connections[:30]:  # Limit per user
                    conn_user = conn.get('username')
                    if not conn_user or conn_user in visited:
                        continue
                    
                    visited.add(conn_user)
                    children_count += 1
                    
                    # Create child node
                    child = CascadeNode(
                        username=conn_user,
                        depth=depth + 1,
                        timestamp=timestamp
                    )
                    node.children.append(child)
                    
                    # Record event
                    events.append(CascadeEvent(
                        cascade_id=cascade_id,
                        source_user=node.username,
                        target_user=conn_user,
                        timestamp=timestamp,
                        depth=depth + 1
                    ))
                    
                    # Track for depth distribution
                    if depth + 1 not in nodes_at_depth:
                        nodes_at_depth[depth + 1] = []
                    nodes_at_depth[depth + 1].append(timestamp)
                    
                    queue.append((child, depth + 1))
                
                # Track children count for branching factor
                self._node_children[node.username] = children_count
                
            except Exception as e:
                print(f"[Cascade] Error at {node.username}: {e}")
        
        self.cascades[cascade_id] = root
        self.events[cascade_id] = events
        
        print(f"[Cascade] Complete: {len(visited)} nodes, cascade_id={cascade_id}")
        return root
    
    def get_cascade_tree(self, cascade_id: str) -> Optional[Dict]:
        """Get cascade as tree structure"""
        if cascade_id not in self.cascades:
            return None
        return self.cascades[cascade_id].to_dict()
    
    def get_propagation_speed(self, cascade_id: str) -> float:
        """
        Calculate propagation speed (nodes per hour)
        """
        events = self.events.get(cascade_id, [])
        if len(events) < 2:
            return 0.0
        
        first_event = min(e.timestamp for e in events)
        last_event = max(e.timestamp for e in events)
        duration_hours = (last_event - first_event).total_seconds() / 3600
        
        if duration_hours == 0:
            return float(len(events))
        
        return len(events) / duration_hours
    
    def get_reach(self, cascade_id: str) -> int:
        """Get total nodes reached in cascade"""
        return len(self.events.get(cascade_id, [])) + 1  # +1 for origin
    
    def get_structural_virality(self, cascade_id: str) -> float:
        """
        Calculate structural virality index (Goel et al.)
        
        Based on average distance between all pairs of nodes.
        Higher = more viral (broad spreading)
        Lower = more broadcast (star structure)
        """
        root = self.cascades.get(cascade_id)
        if not root:
            return 0.0
        
        # Collect all nodes with depths
        nodes_depths: List[Tuple[str, int]] = []
        
        def traverse(node: CascadeNode):
            nodes_depths.append((node.username, node.depth))
            for child in node.children:
                traverse(child)
        
        traverse(root)
        n = len(nodes_depths)
        
        if n <= 1:
            return 0.0
        
        # Calculate Wiener index (sum of all pairwise distances)
        # Approximation using depth differences
        total_distance = 0
        for i in range(n):
            for j in range(i + 1, n):
                # Distance in tree ≈ |depth_i - depth_j| + 2*min(depth_i, depth_j)
                d1, d2 = nodes_depths[i][1], nodes_depths[j][1]
                distance = abs(d1 - d2) + 2 * min(d1, d2)
                total_distance += distance
        
        # Normalize by n(n-1)
        return total_distance / (n * (n - 1))
    
    def get_cascade_statistics(self, cascade_id: str) -> Optional[CascadeStats]:
        """
        Get comprehensive cascade statistics
        """
        root = self.cascades.get(cascade_id)
        events = self.events.get(cascade_id, [])
        
        if not root:
            return None
        
        # Count nodes and find max depth
        total_nodes = 0
        max_depth = 0
        depth_distribution: Dict[int, int] = {}
        branching_factors: List[int] = []
        
        def traverse(node: CascadeNode):
            nonlocal total_nodes, max_depth
            total_nodes += 1
            max_depth = max(max_depth, node.depth)
            
            depth_distribution[node.depth] = depth_distribution.get(node.depth, 0) + 1
            branching_factors.append(len(node.children))
            
            for child in node.children:
                traverse(child)
        
        traverse(root)
        
        # Calculate timing metrics
        propagation_speed = self.get_propagation_speed(cascade_id)
        
        cascade_duration = 0.0
        time_to_peak = 0.0
        
        if events:
            timestamps = [e.timestamp for e in events]
            first = min(timestamps)
            last = max(timestamps)
            cascade_duration = (last - first).total_seconds() / 3600
            
            # Time to peak: when spread rate was highest
            if len(events) > 2:
                hourly_counts = {}
                for e in events:
                    hour = int((e.timestamp - first).total_seconds() / 3600)
                    hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
                
                if hourly_counts:
                    peak_hour = max(hourly_counts, key=hourly_counts.get)
                    time_to_peak = float(peak_hour)
        
        # Branching metrics
        avg_branching = sum(branching_factors) / len(branching_factors) if branching_factors else 0
        max_branching = max(branching_factors) if branching_factors else 0
        
        # Viral coefficient: avg children for non-leaf nodes
        non_leaf_branching = [b for b in branching_factors if b > 0]
        viral_coefficient = sum(non_leaf_branching) / len(non_leaf_branching) if non_leaf_branching else 0
        
        return CascadeStats(
            cascade_id=cascade_id,
            origin_user=root.username,
            total_nodes=total_nodes,
            max_depth=max_depth,
            propagation_speed=propagation_speed,
            time_to_peak=time_to_peak,
            cascade_duration=cascade_duration,
            structural_virality=self.get_structural_virality(cascade_id),
            viral_coefficient=viral_coefficient,
            branching_factor_avg=avg_branching,
            branching_factor_max=max_branching,
            depth_distribution=depth_distribution,
        )
    
    def identify_super_spreaders(self, top_n: int = 10) -> List[Dict]:
        """
        Identify users with highest cascade impact
        
        Returns users sorted by number of downstream nodes
        """
        # Aggregate children counts
        spreader_scores: Dict[str, int] = {}
        
        for cascade_id, root in self.cascades.items():
            def count_descendants(node: CascadeNode) -> int:
                count = len(node.children)
                for child in node.children:
                    count += count_descendants(child)
                return count
            
            def traverse(node: CascadeNode):
                descendants = count_descendants(node)
                spreader_scores[node.username] = spreader_scores.get(node.username, 0) + descendants
                for child in node.children:
                    traverse(child)
            
            traverse(root)
        
        # Sort by score
        sorted_spreaders = sorted(spreader_scores.items(), key=lambda x: -x[1])[:top_n]
        
        return [
            {
                "username": username,
                "downstream_reach": score,
                "profile_url": f"https://www.tiktok.com/@{username}"
            }
            for username, score in sorted_spreaders
        ]
    
    def get_branching_distribution(self, cascade_id: str) -> Dict[int, int]:
        """
        Get distribution of branching factors
        
        Returns dict: branching_factor -> count
        """
        root = self.cascades.get(cascade_id)
        if not root:
            return {}
        
        distribution: Dict[int, int] = {}
        
        def traverse(node: CascadeNode):
            bf = len(node.children)
            distribution[bf] = distribution.get(bf, 0) + 1
            for child in node.children:
                traverse(child)
        
        traverse(root)
        return distribution
    
    def export_events(self, cascade_id: str) -> List[Dict]:
        """Export all events for a cascade"""
        events = self.events.get(cascade_id, [])
        return [e.to_dict() for e in events]
