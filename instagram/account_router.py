"""
Distributed Account Rotation dengan Consistent Hashing — Algorithm 6

Mendistribusikan request ke multiple akun Instagram via consistent hashing.
- Target username selalu di-route ke akun yang sama (sticky routing)
- Virtual nodes untuk distribusi merata
- Health scoring dengan auto-removal dan recovery

Usage:
    # Setup: letakkan cookie files di satu folder
    # accounts/
    #   ├── akun_utama.json
    #   ├── akun_backup.json
    #   └── akun_cadangan.json
    
    router = AccountRouter("accounts/")
    
    # Route target ke akun (selalu konsisten)
    account = router.get_account("cristiano")
    # → AccountInfo(name="akun_backup", cookies=[...], health=0.95)
    
    # Report result
    router.report_success("akun_backup")
    router.report_failure("akun_backup", rate_limited=True)
"""

import hashlib
import json
import time
from bisect import bisect_right
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .utils import load_cookies


# ==================== CONSTANTS ====================

DEFAULT_VIRTUAL_NODES = 150    # Virtual nodes per akun
HEALTH_INITIAL = 1.0
HEALTH_SUCCESS_BONUS = 0.05   # Per successful request
HEALTH_RATE_LIMIT_PENALTY = -0.3  # 429 error
HEALTH_ERROR_PENALTY = -0.1   # Other errors
HEALTH_THRESHOLD = 0.3        # Remove from ring if below
COOLDOWN_SECONDS = 900        # 15 minutes recovery


# ==================== ACCOUNT DATA ====================

@dataclass
class AccountInfo:
    """Represents a single Instagram account in the rotation pool"""
    name: str
    cookies: List[Dict]
    cookie_file: str = ""
    health_score: float = HEALTH_INITIAL
    total_requests: int = 0
    total_success: int = 0
    total_failures: int = 0
    total_rate_limited: int = 0
    last_request_time: float = 0.0
    last_failure_time: float = 0.0
    cooldown_until: float = 0.0
    is_active: bool = True
    
    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return self.total_success / self.total_requests
    
    @property
    def is_healthy(self) -> bool:
        return self.health_score >= HEALTH_THRESHOLD
    
    @property
    def is_in_cooldown(self) -> bool:
        return time.time() < self.cooldown_until
    
    def record_success(self):
        """Record a successful request"""
        self.total_requests += 1
        self.total_success += 1
        self.last_request_time = time.time()
        self.health_score = min(HEALTH_INITIAL, self.health_score + HEALTH_SUCCESS_BONUS)
    
    def record_failure(self, rate_limited: bool = False):
        """Record a failed request"""
        self.total_requests += 1
        self.total_failures += 1
        self.last_failure_time = time.time()
        self.last_request_time = time.time()
        
        if rate_limited:
            self.total_rate_limited += 1
            self.health_score = max(0.0, self.health_score + HEALTH_RATE_LIMIT_PENALTY)
        else:
            self.health_score = max(0.0, self.health_score + HEALTH_ERROR_PENALTY)
    
    def enter_cooldown(self):
        """Put account in cooldown"""
        self.is_active = False
        self.cooldown_until = time.time() + COOLDOWN_SECONDS
        print(f"  [⏸] Account '{self.name}' entering cooldown "
              f"(health={self.health_score:.2f}, resume in {COOLDOWN_SECONDS//60}min)")
    
    def try_recover(self) -> bool:
        """Check if account can recover from cooldown"""
        if self.is_active:
            return False
        if time.time() >= self.cooldown_until:
            self.is_active = True
            self.health_score = HEALTH_THRESHOLD + 0.1  # Start slightly above threshold
            print(f"  [▶] Account '{self.name}' recovered from cooldown (health={self.health_score:.2f})")
            return True
        return False
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'cookie_file': self.cookie_file,
            'health_score': round(self.health_score, 3),
            'total_requests': self.total_requests,
            'success_rate': f"{self.success_rate:.0%}",
            'total_rate_limited': self.total_rate_limited,
            'is_active': self.is_active,
            'is_healthy': self.is_healthy,
        }


# ==================== CONSISTENT HASH RING ====================

class ConsistentHashRing:
    """
    Consistent Hash Ring with virtual nodes.
    
    Each physical node (account) is mapped to multiple positions on the ring
    via virtual nodes, ensuring even distribution of keys across accounts.
    
    Properties:
    - O(log N) lookup via binary search
    - Adding/removing a node only rehashes ~1/N keys
    - Virtual nodes prevent hotspots
    """
    
    def __init__(self, num_virtual_nodes: int = DEFAULT_VIRTUAL_NODES):
        self.num_virtual_nodes = num_virtual_nodes
        self._ring: List[Tuple[int, str]] = []  # (hash_position, node_name)
        self._sorted_keys: List[int] = []
        self._nodes: set = set()
    
    @staticmethod
    def _hash(key: str) -> int:
        """MD5 hash → 32-bit integer position on the ring"""
        digest = hashlib.md5(key.encode('utf-8')).hexdigest()
        return int(digest[:8], 16)  # First 8 hex chars → 32-bit
    
    def add_node(self, node_name: str):
        """Add a physical node with virtual nodes to the ring"""
        if node_name in self._nodes:
            return
        
        self._nodes.add(node_name)
        
        for i in range(self.num_virtual_nodes):
            virtual_key = f"{node_name}:v{i}"
            position = self._hash(virtual_key)
            self._ring.append((position, node_name))
        
        # Sort ring by position
        self._ring.sort(key=lambda x: x[0])
        self._sorted_keys = [pos for pos, _ in self._ring]
    
    def remove_node(self, node_name: str):
        """Remove a physical node and all its virtual nodes from the ring"""
        if node_name not in self._nodes:
            return
        
        self._nodes.discard(node_name)
        self._ring = [(pos, name) for pos, name in self._ring if name != node_name]
        self._sorted_keys = [pos for pos, _ in self._ring]
    
    def get_node(self, key: str) -> Optional[str]:
        """
        Find the account responsible for a given key (e.g., target username).
        Uses clockwise lookup: find the first node position >= key hash.
        
        Returns:
            Account name, or None if ring is empty
        """
        if not self._ring:
            return None
        
        position = self._hash(key)
        
        # Binary search for first position >= hash
        idx = bisect_right(self._sorted_keys, position)
        
        # Wrap around to start of ring if past the end
        if idx >= len(self._ring):
            idx = 0
        
        return self._ring[idx][1]
    
    def get_distribution(self) -> Dict[str, int]:
        """Show how many virtual nodes each account has on the ring"""
        dist = {}
        for _, name in self._ring:
            dist[name] = dist.get(name, 0) + 1
        return dist
    
    @property
    def size(self) -> int:
        return len(self._ring)
    
    @property
    def node_count(self) -> int:
        return len(self._nodes)
    
    @property
    def nodes(self) -> set:
        return self._nodes.copy()


# ==================== ACCOUNT ROUTER ====================

class AccountRouter:
    """
    Orchestrates multi-account rotation via consistent hashing.
    
    Usage:
        router = AccountRouter("accounts/")
        
        # Get account for a target username (always consistent)
        account = router.get_account("cristiano")
        
        # Report results
        router.report_success(account.name)
        router.report_failure(account.name, rate_limited=True)
        
        # View status
        router.print_ring_status()
    """
    
    def __init__(
        self,
        accounts_dir: str,
        virtual_nodes: int = DEFAULT_VIRTUAL_NODES,
        health_threshold: float = HEALTH_THRESHOLD,
    ):
        self.accounts_dir = Path(accounts_dir)
        self.health_threshold = health_threshold
        
        # All accounts (including inactive)
        self.accounts: Dict[str, AccountInfo] = {}
        
        # Hash ring (only active accounts)
        self.ring = ConsistentHashRing(num_virtual_nodes=virtual_nodes)
        
        # Routing log for debugging
        self._routing_log: List[Dict] = []
        
        # Stats
        self._total_routed = 0
        self._total_rerouted = 0
        self._ring_rebuilds = 0
        
        # Load accounts
        self._load_accounts()
    
    def _load_accounts(self):
        """Load all cookie files from the accounts directory"""
        if not self.accounts_dir.exists():
            print(f"  [!] Accounts directory not found: {self.accounts_dir}")
            print(f"  [!] Creating directory: {self.accounts_dir}")
            self.accounts_dir.mkdir(parents=True, exist_ok=True)
            return
        
        cookie_files = list(self.accounts_dir.glob("*.json"))
        
        if not cookie_files:
            print(f"  [!] No cookie files found in {self.accounts_dir}")
            return
        
        for cookie_file in sorted(cookie_files):
            name = cookie_file.stem  # filename without extension
            cookies = load_cookies(str(cookie_file))
            
            if cookies:
                account = AccountInfo(
                    name=name,
                    cookies=cookies,
                    cookie_file=str(cookie_file),
                )
                self.accounts[name] = account
                self.ring.add_node(name)
        
        print(f"  [🔄] Account Router: {len(self.accounts)} accounts loaded, "
              f"{self.ring.size} virtual nodes on ring")
    
    # ==================== PUBLIC API ====================
    
    def get_account(self, target_username: str) -> Optional[AccountInfo]:
        """
        Route a target username to an account via consistent hashing.
        
        The same target always maps to the same account (sticky routing).
        If the primary account is unhealthy, falls back to next on ring.
        
        Args:
            target_username: Instagram username to scrape
            
        Returns:
            AccountInfo or None if no accounts available
        """
        if not self.accounts:
            return None
        
        # Check for recovered accounts first
        self._check_recovery()
        
        if self.ring.node_count == 0:
            print("  [!] No active accounts on the ring")
            return None
        
        # Primary routing
        primary_name = self.ring.get_node(target_username)
        
        if primary_name and primary_name in self.accounts:
            account = self.accounts[primary_name]
            if account.is_healthy and account.is_active:
                self._total_routed += 1
                self._log_route(target_username, primary_name, "primary")
                return account
        
        # Primary unhealthy — find fallback (walk clockwise)
        self._total_rerouted += 1
        return self._get_fallback(target_username, exclude=primary_name)
    
    def report_success(self, account_name: str):
        """Record a successful request for an account"""
        if account_name in self.accounts:
            self.accounts[account_name].record_success()
    
    def report_failure(self, account_name: str, rate_limited: bool = False):
        """Record a failed request and check health"""
        if account_name not in self.accounts:
            return
        
        account = self.accounts[account_name]
        account.record_failure(rate_limited=rate_limited)
        
        # Check if account should be removed from ring
        if not account.is_healthy and account.is_active:
            account.enter_cooldown()
            self.ring.remove_node(account_name)
            self._ring_rebuilds += 1
            print(f"  [🔄] Ring rebuilt: {self.ring.node_count} active accounts remaining")
    
    def get_stats(self) -> Dict:
        """Get comprehensive routing statistics"""
        active = sum(1 for a in self.accounts.values() if a.is_active)
        in_cooldown = sum(1 for a in self.accounts.values() if a.is_in_cooldown)
        
        return {
            'total_accounts': len(self.accounts),
            'active_accounts': active,
            'in_cooldown': in_cooldown,
            'ring_nodes': self.ring.size,
            'total_routed': self._total_routed,
            'total_rerouted': self._total_rerouted,
            'ring_rebuilds': self._ring_rebuilds,
            'accounts': {
                name: acc.to_dict()
                for name, acc in self.accounts.items()
            },
        }
    
    def print_ring_status(self):
        """Print visual ring status"""
        stats = self.get_stats()
        
        print(f"""
╔══════════════════════════════════════════════════╗
║   🔄 Account Router — Ring Status               ║
╠══════════════════════════════════════════════════╣
║  Accounts:    {stats['active_accounts']}/{stats['total_accounts']} active""", end="")
        
        if stats['in_cooldown'] > 0:
            print(f" ({stats['in_cooldown']} cooldown)", end="")
        
        print(f"""
║  Ring Nodes:  {stats['ring_nodes']:>5}                            ║
║  Routed:      {stats['total_routed']:>5}  (rerouted: {stats['total_rerouted']})               ║
║  Rebuilds:    {stats['ring_rebuilds']:>5}                            ║
╠══════════════════════════════════════════════════╣""")
        
        for name, acc in sorted(self.accounts.items()):
            health_bar = self._health_bar(acc.health_score)
            status = "✓" if acc.is_active else "⏸"
            print(f"║  {status} {name:<16} {health_bar} "
                  f"({acc.total_requests:>4} req, {acc.success_rate:.0%} ok)  ║")
        
        print("╚══════════════════════════════════════════════════╝")
    
    def test_distribution(self, num_keys: int = 1000) -> Dict[str, int]:
        """Test how evenly keys are distributed across accounts"""
        dist = {}
        for i in range(num_keys):
            key = f"test_user_{i}"
            node = self.ring.get_node(key)
            if node:
                dist[node] = dist.get(node, 0) + 1
        return dist
    
    # ==================== INTERNAL ====================
    
    def _get_fallback(self, target: str, exclude: Optional[str] = None) -> Optional[AccountInfo]:
        """Find a healthy fallback account by walking the ring clockwise"""
        # Try all active accounts
        for name, account in self.accounts.items():
            if name == exclude:
                continue
            if account.is_active and account.is_healthy:
                self._log_route(target, name, "fallback")
                return account
        
        return None
    
    def _check_recovery(self):
        """Check if any accounts in cooldown can recover"""
        for name, account in self.accounts.items():
            if account.try_recover():
                self.ring.add_node(name)
                self._ring_rebuilds += 1
                print(f"  [🔄] Ring rebuilt: {self.ring.node_count} active accounts")
    
    def _log_route(self, target: str, account: str, route_type: str):
        """Log a routing decision (keep last 100)"""
        self._routing_log.append({
            'target': target,
            'account': account,
            'type': route_type,
            'time': time.time(),
        })
        if len(self._routing_log) > 100:
            self._routing_log = self._routing_log[-100:]
    
    @staticmethod
    def _health_bar(score: float) -> str:
        """Visual health bar"""
        filled = int(score * 10)
        empty = 10 - filled
        
        if score >= 0.7:
            color = "🟢"
        elif score >= 0.4:
            color = "🟡"
        else:
            color = "🔴"
        
        return f"{color} {'█' * filled}{'░' * empty} {score:.0%}"
