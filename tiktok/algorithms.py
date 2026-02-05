"""
Graph Traversal Algorithms
BFS, DFS, dan Priority Queue untuk crawling social network
"""

import asyncio
from collections import deque
from dataclasses import dataclass, field
from typing import List, Set, Dict, Optional, Callable, Any
from heapq import heappush, heappop


@dataclass(order=True)
class PriorityUser:
    """User dengan priority score untuk heap"""
    priority: int
    username: str = field(compare=False)
    depth: int = field(compare=False)
    metadata: Dict = field(default_factory=dict, compare=False)


class GraphCrawler:
    """
    Crawler untuk social network graph menggunakan BFS/DFS/Priority
    
    Usage:
        crawler = GraphCrawler(max_depth=2, max_users=100)
        
        # BFS - crawl level by level
        users = await crawler.bfs(
            start_user="tiktok",
            get_connections=scraper.get_followers
        )
        
        # DFS - crawl deep first
        users = await crawler.dfs(
            start_user="tiktok", 
            get_connections=scraper.get_followers
        )
        
        # Priority - crawl high-follower users first
        users = await crawler.priority_crawl(
            start_user="tiktok",
            get_connections=scraper.get_followers,
            get_priority=lambda u: u.get('follower_count', 0)
        )
    """
    
    def __init__(
        self,
        max_depth: int = 2,
        max_users: int = 100,
        delay_between: float = 2.0
    ):
        self.max_depth = max_depth
        self.max_users = max_users
        self.delay_between = delay_between
        self.visited: Set[str] = set()
        self.results: List[Dict] = []
    
    def reset(self):
        """Reset crawler state"""
        self.visited.clear()
        self.results.clear()
    
    # ==================== BFS ====================
    
    async def bfs(
        self,
        start_user: str,
        get_connections: Callable,
        connection_type: str = "followers"
    ) -> List[Dict]:
        """
        Breadth-First Search - crawl level by level
        
        Level 0: start_user
        Level 1: semua connections start_user
        Level 2: semua connections dari level 1
        ...
        """
        self.reset()
        queue = deque([(start_user, 0)])  # (username, depth)
        
        print(f"[BFS] Starting from @{start_user}, max_depth={self.max_depth}")
        
        while queue and len(self.results) < self.max_users:
            username, depth = queue.popleft()
            
            if username in self.visited:
                continue
            
            self.visited.add(username)
            
            if depth > 0:  # Don't add start user to results
                self.results.append({
                    'username': username,
                    'depth': depth,
                    'profile_url': f"https://www.tiktok.com/@{username}"
                })
            
            if depth >= self.max_depth:
                continue
            
            # Get connections
            print(f"[BFS] Depth {depth}: Getting {connection_type} of @{username}")
            try:
                connections = await get_connections(username)
                
                for conn in connections:
                    conn_username = conn.get('username')
                    if conn_username and conn_username not in self.visited:
                        queue.append((conn_username, depth + 1))
                
                await asyncio.sleep(self.delay_between)
            except Exception as e:
                print(f"[BFS] Error getting connections for @{username}: {e}")
        
        print(f"[BFS] Complete: {len(self.results)} users found")
        return self.results
    
    # ==================== DFS ====================
    
    async def dfs(
        self,
        start_user: str,
        get_connections: Callable,
        connection_type: str = "followers"
    ) -> List[Dict]:
        """
        Depth-First Search - crawl one branch deep before backtracking
        
        Follows: start -> conn1 -> conn1_conn1 -> conn1_conn1_conn1...
        Then backtracks to explore other branches
        """
        self.reset()
        stack = [(start_user, 0)]  # (username, depth)
        
        print(f"[DFS] Starting from @{start_user}, max_depth={self.max_depth}")
        
        while stack and len(self.results) < self.max_users:
            username, depth = stack.pop()
            
            if username in self.visited:
                continue
            
            self.visited.add(username)
            
            if depth > 0:
                self.results.append({
                    'username': username,
                    'depth': depth,
                    'profile_url': f"https://www.tiktok.com/@{username}"
                })
            
            if depth >= self.max_depth:
                continue
            
            # Get connections
            print(f"[DFS] Depth {depth}: Getting {connection_type} of @{username}")
            try:
                connections = await get_connections(username)
                
                # Reverse untuk maintain order (stack is LIFO)
                for conn in reversed(connections):
                    conn_username = conn.get('username')
                    if conn_username and conn_username not in self.visited:
                        stack.append((conn_username, depth + 1))
                
                await asyncio.sleep(self.delay_between)
            except Exception as e:
                print(f"[DFS] Error getting connections for @{username}: {e}")
        
        print(f"[DFS] Complete: {len(self.results)} users found")
        return self.results
    
    # ==================== PRIORITY QUEUE ====================
    
    async def priority_crawl(
        self,
        start_user: str,
        get_connections: Callable,
        get_priority: Optional[Callable] = None,
        connection_type: str = "followers"
    ) -> List[Dict]:
        """
        Priority-based crawling - process high-priority users first
        
        Default priority: follower count (higher = processed first)
        Custom priority function can be provided
        """
        self.reset()
        
        # Default priority: negative follower count (heapq is min-heap)
        if get_priority is None:
            get_priority = lambda u: -u.get('follower_count', 0)
        
        # Initialize heap with start user
        heap: List[PriorityUser] = []
        heappush(heap, PriorityUser(priority=0, username=start_user, depth=0))
        
        print(f"[Priority] Starting from @{start_user}, max_depth={self.max_depth}")
        
        while heap and len(self.results) < self.max_users:
            item = heappop(heap)
            username = item.username
            depth = item.depth
            
            if username in self.visited:
                continue
            
            self.visited.add(username)
            
            if depth > 0:
                self.results.append({
                    'username': username,
                    'depth': depth,
                    'priority': -item.priority,  # Restore original priority
                    'profile_url': f"https://www.tiktok.com/@{username}"
                })
            
            if depth >= self.max_depth:
                continue
            
            # Get connections
            print(f"[Priority] Depth {depth}: Getting {connection_type} of @{username}")
            try:
                connections = await get_connections(username)
                
                for conn in connections:
                    conn_username = conn.get('username')
                    if conn_username and conn_username not in self.visited:
                        priority = get_priority(conn)
                        heappush(heap, PriorityUser(
                            priority=priority,
                            username=conn_username,
                            depth=depth + 1,
                            metadata=conn
                        ))
                
                await asyncio.sleep(self.delay_between)
            except Exception as e:
                print(f"[Priority] Error getting connections for @{username}: {e}")
        
        print(f"[Priority] Complete: {len(self.results)} users found")
        return self.results


# ==================== HELPER FUNCTIONS ====================

async def crawl_network(
    start_user: str,
    get_connections: Callable,
    algorithm: str = "bfs",
    max_depth: int = 2,
    max_users: int = 100,
    delay: float = 2.0
) -> List[Dict]:
    """
    Helper function untuk crawling dengan pilihan algoritma
    
    Args:
        start_user: Username awal
        get_connections: Async function untuk get followers/following
        algorithm: "bfs", "dfs", atau "priority"
        max_depth: Kedalaman maksimal
        max_users: Jumlah user maksimal
        delay: Delay antar request
    """
    crawler = GraphCrawler(
        max_depth=max_depth,
        max_users=max_users,
        delay_between=delay
    )
    
    if algorithm == "bfs":
        return await crawler.bfs(start_user, get_connections)
    elif algorithm == "dfs":
        return await crawler.dfs(start_user, get_connections)
    elif algorithm == "priority":
        return await crawler.priority_crawl(start_user, get_connections)
    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")
