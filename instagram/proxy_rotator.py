"""
Multi-Proxy Rotation dengan Latency-Based Selection — Algorithm 8

Mengelola pool proxy, memilih proxy optimal berdasarkan composite score
dari latency dan success rate. Proxy gagal otomatis di-ban sementara.
Mendukung geolocation-aware routing untuk meminimalkan latency.

Usage:
    from instagram.proxy_rotator import ProxyManager
    
    # Load proxy pool
    manager = ProxyManager("proxies.json")
    
    # Get best proxy for request
    proxy = manager.get_best_proxy(target_region="US")
    proxies_dict = proxy.to_requests_dict()
    
    # Record result
    manager.record_result(proxy, success=True, latency_ms=150)
    
Proxy file format (JSON):
    {
        "proxies": [
            {"url": "http://host:port", "region": "US"},
            {"url": "socks5://host:port", "region": "EU"},
            {"url": "http://user:pass@host:port", "region": "ASIA"}
        ]
    }
"""

import json
import time
import requests
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse


# ==================== CONSTANTS ====================

# Scoring weights
W_SUCCESS = 0.6           # Weight for success rate
W_LATENCY = 0.4           # Weight for latency score

# EMA (Exponential Moving Average) for latency
EMA_ALPHA = 0.3           # Smoothing factor (higher = more recent data)

# Ban settings
MAX_CONSECUTIVE_FAILURES = 3
BAN_DURATION_SECONDS = 300     # 5 minutes
MAX_BAN_DURATION_SECONDS = 3600  # 1 hour (exponential backoff)

# Latency
MAX_LATENCY_MS = 10000    # 10 seconds — anything above this gets score 0
DEFAULT_LATENCY_MS = 1000  # Default for untested proxies
TEST_TIMEOUT_SECONDS = 10

# Instagram CDN regions for geo-routing
INSTAGRAM_REGIONS = {
    "US": ["US", "NA"],
    "EU": ["EU", "DE", "FR", "NL", "GB"],
    "ASIA": ["ASIA", "SG", "JP", "KR", "IN", "ID"],
}


# ==================== PROXY INFO ====================

@dataclass
class ProxyInfo:
    """Information and statistics for a single proxy"""
    url: str
    region: str = "auto"
    
    # Performance metrics
    latency_ms: float = DEFAULT_LATENCY_MS  # EMA latency
    success_count: int = 0
    fail_count: int = 0
    total_requests: int = 0
    
    # Consecutive failure tracking
    consecutive_failures: int = 0
    
    # Ban state
    is_banned: bool = False
    banned_until: float = 0.0
    ban_count: int = 0  # For exponential backoff
    
    # Timing
    last_used: float = 0.0
    last_success: float = 0.0
    last_failure: float = 0.0
    
    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.5  # Neutral for untested proxies
        return self.success_count / self.total_requests
    
    @property
    def score(self) -> float:
        """Composite score: weighted success_rate + normalized latency"""
        latency_score = max(0.0, 1.0 - (self.latency_ms / MAX_LATENCY_MS))
        return W_SUCCESS * self.success_rate + W_LATENCY * latency_score
    
    @property
    def name(self) -> str:
        """Short display name (host:port)"""
        parsed = urlparse(self.url)
        return f"{parsed.hostname}:{parsed.port}"
    
    @property
    def protocol(self) -> str:
        """Proxy protocol (http, https, socks5)"""
        return urlparse(self.url).scheme.lower()
    
    def to_requests_dict(self) -> Dict[str, str]:
        """Convert to requests library proxies dict"""
        return {
            "http": self.url,
            "https": self.url,
        }
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d['success_rate'] = round(self.success_rate, 3)
        d['score'] = round(self.score, 3)
        d['name'] = self.name
        return d


# ==================== PROXY MANAGER ====================

class ProxyManager:
    """
    Manages a pool of proxies with latency-based selection.
    
    Features:
    - Composite scoring (success_rate + latency)
    - EMA latency smoothing
    - Auto-ban with exponential backoff
    - Geolocation-aware routing
    - Direct connection fallback
    """
    
    def __init__(
        self,
        proxy_file: str,
        ban_duration: int = BAN_DURATION_SECONDS,
        max_failures: int = MAX_CONSECUTIVE_FAILURES,
    ):
        self.proxy_file = Path(proxy_file)
        self.ban_duration = ban_duration
        self.max_failures = max_failures
        self.proxies: List[ProxyInfo] = []
        
        self._load_proxies()
        
        if self.proxies:
            print(f"  [🌐] Proxy pool: {len(self.proxies)} proxies loaded")
            regions = set(p.region for p in self.proxies)
            print(f"  [🌐] Regions: {', '.join(sorted(regions))}")
    
    def get_best_proxy(self, target_region: Optional[str] = None) -> Optional[ProxyInfo]:
        """
        Get the best available proxy based on score.
        
        Args:
            target_region: Optional region filter (US, EU, ASIA)
            
        Returns:
            Best ProxyInfo or None if all banned
        """
        self._check_bans()
        
        # Filter available proxies
        available = [p for p in self.proxies if not p.is_banned]
        
        if not available:
            return None  # All banned — caller should use direct
        
        # Apply geo-filter if requested
        if target_region:
            geo_proxies = self._filter_by_region(available, target_region)
            if geo_proxies:
                available = geo_proxies
            # If no geo match, use all available (fallback)
        
        # Sort by score (highest first), break ties by latency
        available.sort(key=lambda p: (p.score, -p.latency_ms), reverse=True)
        
        best = available[0]
        best.last_used = time.time()
        return best
    
    def record_result(
        self,
        proxy: ProxyInfo,
        success: bool,
        latency_ms: float = 0,
    ):
        """
        Record the result of a request through a proxy.
        
        Args:
            proxy: The proxy that was used
            success: Whether the request succeeded
            latency_ms: Response time in milliseconds
        """
        proxy.total_requests += 1
        
        if success:
            proxy.success_count += 1
            proxy.consecutive_failures = 0
            proxy.last_success = time.time()
            
            # Update EMA latency
            if latency_ms > 0:
                if proxy.latency_ms == DEFAULT_LATENCY_MS:
                    proxy.latency_ms = latency_ms  # First real measurement
                else:
                    proxy.latency_ms = (
                        EMA_ALPHA * latency_ms +
                        (1 - EMA_ALPHA) * proxy.latency_ms
                    )
        else:
            proxy.fail_count += 1
            proxy.consecutive_failures += 1
            proxy.last_failure = time.time()
            
            # Check if should ban
            if proxy.consecutive_failures >= self.max_failures:
                self._ban_proxy(proxy)
    
    def _ban_proxy(self, proxy: ProxyInfo):
        """Ban a proxy with exponential backoff"""
        proxy.is_banned = True
        proxy.ban_count += 1
        
        # Exponential backoff: 5min, 10min, 20min, 40min, ... capped at 1h
        duration = min(
            self.ban_duration * (2 ** (proxy.ban_count - 1)),
            MAX_BAN_DURATION_SECONDS,
        )
        proxy.banned_until = time.time() + duration
        
        print(f"  [⛔] Proxy {proxy.name} banned for {duration}s "
              f"({proxy.consecutive_failures} consecutive failures)")
    
    def _check_bans(self):
        """Unban proxies whose ban duration has expired"""
        now = time.time()
        for proxy in self.proxies:
            if proxy.is_banned and now >= proxy.banned_until:
                proxy.is_banned = False
                proxy.consecutive_failures = 0
                print(f"  [✓] Proxy {proxy.name} unbanned (recovered)")
    
    def _filter_by_region(
        self,
        proxies: List[ProxyInfo],
        target_region: str,
    ) -> List[ProxyInfo]:
        """Filter proxies by geographic region"""
        target_upper = target_region.upper()
        
        # Build list of acceptable region codes
        acceptable = set()
        acceptable.add(target_upper)
        for region, codes in INSTAGRAM_REGIONS.items():
            if target_upper in codes or target_upper == region:
                acceptable.update(codes)
                acceptable.add(region)
        
        return [p for p in proxies if p.region.upper() in acceptable]
    
    def test_all_proxies(self) -> List[Dict]:
        """
        Test all proxies by making HEAD requests to Instagram.
        
        Returns:
            List of test results [{proxy, latency_ms, status}]
        """
        print(f"\n  [🔍] Testing {len(self.proxies)} proxies...")
        results = []
        
        test_url = "https://www.instagram.com/favicon.ico"
        
        for proxy in self.proxies:
            try:
                start = time.time()
                resp = requests.head(
                    test_url,
                    proxies=proxy.to_requests_dict(),
                    timeout=TEST_TIMEOUT_SECONDS,
                    allow_redirects=True,
                )
                latency = (time.time() - start) * 1000
                
                success = resp.status_code < 400
                self.record_result(proxy, success=success, latency_ms=latency)
                
                status = "✓" if success else f"✗ ({resp.status_code})"
                results.append({
                    'proxy': proxy.name,
                    'region': proxy.region,
                    'latency_ms': round(latency, 1),
                    'status': status,
                })
                print(f"    {proxy.name:<30} {latency:>8.1f}ms  {status}")
                
            except Exception as e:
                self.record_result(proxy, success=False)
                results.append({
                    'proxy': proxy.name,
                    'region': proxy.region,
                    'latency_ms': -1,
                    'status': f"✗ ({str(e)[:40]})",
                })
                print(f"    {proxy.name:<30} {'timeout':>8}    ✗ {str(e)[:40]}")
        
        active = sum(1 for r in results if r['latency_ms'] > 0)
        print(f"\n  [✓] {active}/{len(results)} proxies active")
        
        return results
    
    def get_stats(self) -> Dict:
        """Get proxy pool statistics"""
        active = [p for p in self.proxies if not p.is_banned]
        banned = [p for p in self.proxies if p.is_banned]
        
        avg_latency = (
            sum(p.latency_ms for p in active) / len(active)
            if active else 0
        )
        avg_score = (
            sum(p.score for p in active) / len(active)
            if active else 0
        )
        
        return {
            'total_proxies': len(self.proxies),
            'active_proxies': len(active),
            'banned_proxies': len(banned),
            'avg_latency_ms': round(avg_latency, 1),
            'avg_score': round(avg_score, 3),
            'regions': list(set(p.region for p in self.proxies)),
            'total_requests': sum(p.total_requests for p in self.proxies),
            'total_failures': sum(p.fail_count for p in self.proxies),
        }
    
    def print_pool_status(self):
        """Print formatted proxy pool table"""
        self._check_bans()
        
        print(f"""
╔══════════════════════════════════════════════════════════════════╗
║   🌐 Proxy Pool Status                                         ║
╠══════════════════════════════════════════════════════════════════╣""")
        
        print(f"║  {'Proxy':<28} {'Region':<7} {'Latency':>8} {'Rate':>6} {'Score':>6} {'Status':<8}║")
        print(f"║  {'─'*28} {'─'*6} {'─'*8} {'─'*6} {'─'*6} {'─'*7}║")
        
        # Sort by score
        sorted_proxies = sorted(self.proxies, key=lambda p: p.score, reverse=True)
        
        for p in sorted_proxies:
            status = "⛔ BAN" if p.is_banned else "✓ OK"
            latency_str = f"{p.latency_ms:.0f}ms"
            rate_str = f"{p.success_rate:.0%}"
            score_str = f"{p.score:.3f}"
            
            print(f"║  {p.name:<28} {p.region:<7} {latency_str:>8} {rate_str:>6} {score_str:>6} {status:<8}║")
        
        stats = self.get_stats()
        print(f"╠══════════════════════════════════════════════════════════════════╣")
        print(f"║  Active: {stats['active_proxies']}/{stats['total_proxies']}  "
              f"Avg latency: {stats['avg_latency_ms']:.0f}ms  "
              f"Avg score: {stats['avg_score']:.3f}           ║")
        print(f"╚══════════════════════════════════════════════════════════════════╝")
    
    # ==================== PERSISTENCE ====================
    
    def _load_proxies(self):
        """Load proxies from JSON file"""
        if not self.proxy_file.exists():
            print(f"  [!] Proxy file not found: {self.proxy_file}")
            return
        
        try:
            with open(self.proxy_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            proxy_list = data.get('proxies', [])
            if isinstance(data, list):
                proxy_list = data  # Allow flat list format too
            
            for item in proxy_list:
                if isinstance(item, str):
                    # Simple format: just URL
                    self.proxies.append(ProxyInfo(url=item))
                elif isinstance(item, dict):
                    self.proxies.append(ProxyInfo(
                        url=item['url'],
                        region=item.get('region', 'auto'),
                    ))
        except Exception as e:
            print(f"  [!] Error loading proxy file: {e}")
    
    def save_stats(self, output_file: Optional[str] = None):
        """Save proxy stats to JSON"""
        path = Path(output_file) if output_file else self.proxy_file.with_suffix('.stats.json')
        try:
            data = {
                'updated_at': time.time(),
                'pool_stats': self.get_stats(),
                'proxies': [p.to_dict() for p in self.proxies],
            }
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
