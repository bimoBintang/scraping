"""
Graph Traversal Algorithms
BFS, DFS, dan Priority Queue untuk crawling social network
"""

import asyncio
import random
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


# ==================== A* SEARCH ====================

class AStarCrawler:
    """
    A* Search untuk menemukan path optimal ke high-value users
    
    Menggunakan heuristic berdasarkan follower count untuk prioritas.
    
    Usage:
        crawler = AStarCrawler(max_depth=3, max_users=50)
        users = await crawler.search(
            start_user="tiktok",
            get_connections=scraper.get_followers,
            get_profile=scraper.get_profile
        )
    """
    
    def __init__(
        self,
        max_depth: int = 3,
        max_users: int = 50,
        delay_between: float = 2.0,
        depth_penalty: float = 0.1
    ):
        self.max_depth = max_depth
        self.max_users = max_users
        self.delay_between = delay_between
        self.depth_penalty = depth_penalty
        self.visited: Set[str] = set()
        self.results: List[Dict] = []
    
    def reset(self):
        self.visited.clear()
        self.results.clear()
    
    async def search(
        self,
        start_user: str,
        get_connections: Callable,
        get_profile: Optional[Callable] = None
    ) -> List[Dict]:
        """
        A* search dengan heuristic = follower_count - (depth * penalty * 1M)
        Higher value = lebih diprioritaskan
        """
        self.reset()
        
        # Priority queue: (negative_score, depth, username)
        # Negative karena heapq adalah min-heap
        heap: List[tuple] = []
        heappush(heap, (0, 0, start_user))
        
        print(f"[A*] Starting from @{start_user}, max_depth={self.max_depth}")
        
        while heap and len(self.results) < self.max_users:
            neg_score, depth, username = heappop(heap)
            
            if username in self.visited:
                continue
            
            self.visited.add(username)
            
            # Get profile untuk heuristic jika tersedia
            follower_count = 0
            profile_data = {}
            
            if get_profile and depth > 0:
                try:
                    profile = await get_profile(username)
                    if profile:
                        follower_count = profile.followers
                        profile_data = {
                            'followers': profile.followers,
                            'nickname': profile.nickname
                        }
                except:
                    pass
            
            if depth > 0:
                self.results.append({
                    'username': username,
                    'depth': depth,
                    'score': -neg_score,
                    'follower_count': follower_count,
                    'profile_url': f"https://www.tiktok.com/@{username}",
                    **profile_data
                })
            
            if depth >= self.max_depth:
                continue
            
            # Get connections
            print(f"[A*] Depth {depth}: Exploring @{username} (score: {-neg_score:.0f})")
            try:
                connections = await get_connections(username)
                
                for conn in connections:
                    conn_username = conn.get('username')
                    if conn_username and conn_username not in self.visited:
                        # Heuristic: estimate based on connection position + depth penalty
                        estimated_score = 1000000 - (depth + 1) * self.depth_penalty * 1000000
                        heappush(heap, (-estimated_score, depth + 1, conn_username))
                
                await asyncio.sleep(self.delay_between)
            except Exception as e:
                print(f"[A*] Error: {e}")
        
        # Sort by score descending
        self.results.sort(key=lambda x: x.get('score', 0), reverse=True)
        print(f"[A*] Complete: {len(self.results)} users found")
        return self.results


# ==================== BIDIRECTIONAL SEARCH ====================

class BidirectionalSearch:
    """
    Bidirectional BFS untuk menemukan shortest path antara dua user
    
    Usage:
        searcher = BidirectionalSearch()
        path = await searcher.find_path(
            user_a="user1",
            user_b="user2", 
            get_connections=scraper.get_followers
        )
    """
    
    def __init__(self, max_depth: int = 3, delay_between: float = 2.0):
        self.max_depth = max_depth
        self.delay_between = delay_between
    
    async def find_path(
        self,
        user_a: str,
        user_b: str,
        get_connections: Callable
    ) -> Optional[List[str]]:
        """
        Find shortest path between two users using bidirectional BFS
        
        Returns:
            List of usernames from user_a to user_b, or None if not found
        """
        print(f"[Bidirectional] Finding path: @{user_a} <-> @{user_b}")
        
        # Forward search from user_a
        forward_visited: Dict[str, str] = {user_a: None}  # user -> parent
        forward_queue = deque([user_a])
        
        # Backward search from user_b
        backward_visited: Dict[str, str] = {user_b: None}
        backward_queue = deque([user_b])
        
        forward_depth = 0
        backward_depth = 0
        meeting_point = None
        
        while forward_queue or backward_queue:
            # Expand forward
            if forward_queue and forward_depth <= self.max_depth:
                meeting_point = await self._expand_level(
                    forward_queue, forward_visited, backward_visited,
                    get_connections, "forward"
                )
                if meeting_point:
                    break
                forward_depth += 1
            
            # Expand backward
            if backward_queue and backward_depth <= self.max_depth:
                meeting_point = await self._expand_level(
                    backward_queue, backward_visited, forward_visited,
                    get_connections, "backward"
                )
                if meeting_point:
                    break
                backward_depth += 1
            
            # Check depth limit
            if forward_depth > self.max_depth and backward_depth > self.max_depth:
                break
        
        if meeting_point:
            path = self._reconstruct_path(meeting_point, forward_visited, backward_visited)
            print(f"[Bidirectional] Path found! Length: {len(path)}")
            return path
        
        print(f"[Bidirectional] No path found within depth {self.max_depth}")
        return None
    
    async def _expand_level(
        self,
        queue: deque,
        visited: Dict[str, str],
        other_visited: Dict[str, str],
        get_connections: Callable,
        direction: str
    ) -> Optional[str]:
        """Expand one level of BFS"""
        level_size = len(queue)
        
        for _ in range(level_size):
            if not queue:
                break
            
            current = queue.popleft()
            
            try:
                connections = await get_connections(current)
                await asyncio.sleep(self.delay_between)
                
                for conn in connections:
                    neighbor = conn.get('username')
                    if not neighbor:
                        continue
                    
                    if neighbor in other_visited:
                        # Found meeting point!
                        visited[neighbor] = current
                        return neighbor
                    
                    if neighbor not in visited:
                        visited[neighbor] = current
                        queue.append(neighbor)
                        
            except Exception as e:
                print(f"[Bidirectional] Error expanding {current}: {e}")
        
        return None
    
    def _reconstruct_path(
        self,
        meeting: str,
        forward_visited: Dict[str, str],
        backward_visited: Dict[str, str]
    ) -> List[str]:
        """Reconstruct path from meeting point"""
        # Build forward path
        forward_path = []
        current = meeting
        while current is not None:
            forward_path.append(current)
            current = forward_visited.get(current)
        forward_path.reverse()
        
        # Build backward path
        backward_path = []
        current = backward_visited.get(meeting)
        while current is not None:
            backward_path.append(current)
            current = backward_visited.get(current)
        
        return forward_path + backward_path


# ==================== RANDOM WALK ====================

class RandomWalkSampler:
    """
    Random Walk untuk sampling representatif dari social network
    
    Usage:
        sampler = RandomWalkSampler(num_walks=10, walk_length=20)
        samples = await sampler.sample(
            start_user="tiktok",
            get_connections=scraper.get_followers
        )
    """
    
    def __init__(
        self,
        num_walks: int = 10,
        walk_length: int = 20,
        delay_between: float = 1.5
    ):
        self.num_walks = num_walks
        self.walk_length = walk_length
        self.delay_between = delay_between
    
    async def sample(
        self,
        start_user: str,
        get_connections: Callable
    ) -> List[Dict]:
        """
        Perform random walks and return sampled users
        
        Returns:
            List of sampled users with visit frequency
        """
        print(f"[RandomWalk] Starting {self.num_walks} walks of length {self.walk_length}")
        
        visit_count: Dict[str, int] = {}
        all_walks: List[List[str]] = []
        
        for walk_num in range(self.num_walks):
            walk = await self._single_walk(start_user, get_connections)
            all_walks.append(walk)
            
            for user in walk:
                visit_count[user] = visit_count.get(user, 0) + 1
            
            print(f"[RandomWalk] Walk {walk_num + 1}/{self.num_walks}: {len(walk)} steps")
        
        # Build results sorted by visit frequency
        results = []
        for username, count in sorted(visit_count.items(), key=lambda x: -x[1]):
            results.append({
                'username': username,
                'visit_count': count,
                'visit_frequency': count / (self.num_walks * self.walk_length),
                'profile_url': f"https://www.tiktok.com/@{username}"
            })
        
        print(f"[RandomWalk] Complete: {len(results)} unique users sampled")
        return results
    
    async def _single_walk(self, start: str, get_connections: Callable) -> List[str]:
        """Perform single random walk"""
        walk = [start]
        current = start
        
        for _ in range(self.walk_length):
            try:
                connections = await get_connections(current)
                await asyncio.sleep(self.delay_between)
                
                if not connections:
                    break
                
                # Random selection
                next_user = random.choice(connections).get('username')
                if next_user:
                    walk.append(next_user)
                    current = next_user
                else:
                    break
                    
            except Exception:
                break
        
        return walk


# ==================== INFLUENCE SCORE ====================

class InfluenceScorer:
    """
    PageRank-style influence scoring untuk social network
    
    Usage:
        scorer = InfluenceScorer()
        scores = await scorer.calculate(
            seed_users=["user1", "user2"],
            get_connections=scraper.get_followers,
            iterations=10
        )
    """
    
    def __init__(
        self,
        damping: float = 0.85,
        max_iterations: int = 10,
        delay_between: float = 2.0
    ):
        self.damping = damping
        self.max_iterations = max_iterations
        self.delay_between = delay_between
    
    async def calculate(
        self,
        seed_users: List[str],
        get_connections: Callable,
        max_users: int = 100
    ) -> List[Dict]:
        """
        Calculate influence scores for users in network
        """
        print(f"[Influence] Building graph from {len(seed_users)} seed users")
        
        # Build graph: user -> list of followers
        graph: Dict[str, List[str]] = {}
        all_users: Set[str] = set(seed_users)
        
        # BFS to collect graph
        queue = deque(seed_users)
        visited = set(seed_users)
        
        while queue and len(all_users) < max_users:
            current = queue.popleft()
            
            try:
                connections = await get_connections(current)
                await asyncio.sleep(self.delay_between)
                
                graph[current] = []
                for conn in connections[:20]:  # Limit connections
                    follower = conn.get('username')
                    if follower:
                        graph[current].append(follower)
                        all_users.add(follower)
                        
                        if follower not in visited and len(all_users) < max_users:
                            visited.add(follower)
                            queue.append(follower)
                            
            except Exception as e:
                print(f"[Influence] Error: {e}")
        
        print(f"[Influence] Graph built: {len(all_users)} users")
        
        # Calculate PageRank-style scores
        scores = await self._pagerank(graph, all_users)
        
        # Build results
        results = []
        for username, score in sorted(scores.items(), key=lambda x: -x[1]):
            results.append({
                'username': username,
                'influence_score': round(score, 6),
                'follower_count': len(graph.get(username, [])),
                'profile_url': f"https://www.tiktok.com/@{username}"
            })
        
        print(f"[Influence] Complete: Top score = {results[0]['influence_score'] if results else 0}")
        return results
    
    async def _pagerank(
        self,
        graph: Dict[str, List[str]],
        all_users: Set[str]
    ) -> Dict[str, float]:
        """Simple PageRank implementation"""
        n = len(all_users)
        if n == 0:
            return {}
        
        # Initialize scores
        scores = {user: 1.0 / n for user in all_users}
        
        # Build reverse graph (who follows whom)
        reverse_graph: Dict[str, List[str]] = {user: [] for user in all_users}
        out_degree: Dict[str, int] = {user: 0 for user in all_users}
        
        for user, followers in graph.items():
            out_degree[user] = len(followers) if followers else 1
            for follower in followers:
                if follower in reverse_graph:
                    reverse_graph[follower].append(user)
        
        # Iterate
        for iteration in range(self.max_iterations):
            new_scores = {}
            
            for user in all_users:
                # Sum contributions from users who follow this user
                rank_sum = 0
                for follower in reverse_graph[user]:
                    rank_sum += scores[follower] / out_degree[follower]
                
                new_scores[user] = (1 - self.damping) / n + self.damping * rank_sum
            
            scores = new_scores
        
        return scores


# ==================== COMMUNITY DETECTION ====================

class CommunityDetector:
    """
    Label Propagation untuk community detection
    
    Usage:
        detector = CommunityDetector()
        communities = await detector.detect(
            seed_users=["user1", "user2"],
            get_connections=scraper.get_followers
        )
    """
    
    def __init__(
        self,
        max_iterations: int = 10,
        delay_between: float = 2.0
    ):
        self.max_iterations = max_iterations
        self.delay_between = delay_between
    
    async def detect(
        self,
        seed_users: List[str],
        get_connections: Callable,
        max_users: int = 100
    ) -> Dict[str, List[Dict]]:
        """
        Detect communities using Label Propagation
        
        Returns:
            Dict mapping community_id -> list of users
        """
        print(f"[Community] Building graph from {len(seed_users)} seed users")
        
        # Build adjacency list
        graph: Dict[str, Set[str]] = {}
        all_users: Set[str] = set(seed_users)
        
        queue = deque(seed_users)
        visited = set(seed_users)
        
        while queue and len(all_users) < max_users:
            current = queue.popleft()
            
            try:
                connections = await get_connections(current)
                await asyncio.sleep(self.delay_between)
                
                graph[current] = set()
                for conn in connections[:15]:
                    neighbor = conn.get('username')
                    if neighbor:
                        graph[current].add(neighbor)
                        all_users.add(neighbor)
                        
                        if neighbor not in visited and len(all_users) < max_users:
                            visited.add(neighbor)
                            queue.append(neighbor)
                            
            except Exception as e:
                print(f"[Community] Error: {e}")
        
        # Make graph symmetric (undirected)
        for user in list(graph.keys()):
            for neighbor in list(graph.get(user, [])):
                if neighbor not in graph:
                    graph[neighbor] = set()
                graph[neighbor].add(user)
        
        print(f"[Community] Graph built: {len(all_users)} users")
        
        # Label Propagation
        labels = self._label_propagation(graph, all_users)
        
        # Group by community
        communities: Dict[str, List[Dict]] = {}
        for user, label in labels.items():
            community_id = f"community_{label}"
            if community_id not in communities:
                communities[community_id] = []
            communities[community_id].append({
                'username': user,
                'community': community_id,
                'profile_url': f"https://www.tiktok.com/@{user}"
            })
        
        print(f"[Community] Detected {len(communities)} communities")
        return communities
    
    def _label_propagation(
        self,
        graph: Dict[str, Set[str]],
        all_users: Set[str]
    ) -> Dict[str, int]:
        """Label Propagation algorithm"""
        # Initialize each node with unique label
        labels = {user: i for i, user in enumerate(all_users)}
        
        users_list = list(all_users)
        
        for iteration in range(self.max_iterations):
            changed = False
            random.shuffle(users_list)
            
            for user in users_list:
                neighbors = graph.get(user, set())
                if not neighbors:
                    continue
                
                # Count neighbor labels
                label_counts: Dict[int, int] = {}
                for neighbor in neighbors:
                    if neighbor in labels:
                        lbl = labels[neighbor]
                        label_counts[lbl] = label_counts.get(lbl, 0) + 1
                
                if label_counts:
                    # Adopt most common label
                    max_label = max(label_counts, key=label_counts.get)
                    if labels[user] != max_label:
                        labels[user] = max_label
                        changed = True
            
            if not changed:
                print(f"[Community] Converged at iteration {iteration + 1}")
                break
        
        return labels


# ==================== HELPER FUNCTIONS ====================

async def crawl_network(
    start_user: str,
    get_connections: Callable,
    algorithm: str = "bfs",
    max_depth: int = 2,
    max_users: int = 100,
    delay: float = 2.0,
    **kwargs
) -> List[Dict]:
    """
    Helper function untuk crawling dengan pilihan algoritma
    
    Args:
        start_user: Username awal
        get_connections: Async function untuk get followers/following
        algorithm: "bfs", "dfs", "priority", "astar", "random_walk"
        max_depth: Kedalaman maksimal
        max_users: Jumlah user maksimal
        delay: Delay antar request
        **kwargs: Additional arguments for specific algorithms
    """
    if algorithm == "astar":
        crawler = AStarCrawler(
            max_depth=max_depth,
            max_users=max_users,
            delay_between=delay
        )
        return await crawler.search(start_user, get_connections, kwargs.get('get_profile'))
    
    elif algorithm == "random_walk":
        sampler = RandomWalkSampler(
            num_walks=kwargs.get('num_walks', 10),
            walk_length=kwargs.get('walk_length', 20),
            delay_between=delay
        )
        return await sampler.sample(start_user, get_connections)
    
    else:
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
