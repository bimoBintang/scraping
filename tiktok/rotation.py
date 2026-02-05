"""
User-Agent & Proxy Rotation Module
Rotasi fingerprint dan proxy untuk anti-detection
"""

import random
from typing import List, Optional, Dict
from dataclasses import dataclass


# ==================== USER-AGENT ROTATION ====================

USER_AGENTS = [
    # Chrome Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    
    # Chrome Mac
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    
    # Firefox Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
    
    # Firefox Mac
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',
    
    # Edge Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0',
    
    # Safari Mac
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15',
    
    # Chrome Linux
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0',
    
    # Mobile - untuk variasi
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
]


class UserAgentRotator:
    """Rotasi User-Agent untuk menghindari fingerprinting"""
    
    def __init__(self, user_agents: Optional[List[str]] = None):
        self.user_agents = user_agents or USER_AGENTS.copy()
        self._index = 0
        self._used = set()
    
    def get_random(self) -> str:
        """Ambil user-agent random"""
        return random.choice(self.user_agents)
    
    def get_next(self) -> str:
        """Ambil user-agent secara berurutan"""
        ua = self.user_agents[self._index]
        self._index = (self._index + 1) % len(self.user_agents)
        return ua
    
    def get_unique(self) -> str:
        """Ambil user-agent yang belum pernah digunakan"""
        available = [ua for ua in self.user_agents if ua not in self._used]
        if not available:
            self._used.clear()
            available = self.user_agents
        
        ua = random.choice(available)
        self._used.add(ua)
        return ua
    
    def add(self, user_agent: str):
        """Tambah user-agent baru"""
        if user_agent not in self.user_agents:
            self.user_agents.append(user_agent)


# ==================== PROXY ROTATION ====================

@dataclass
class Proxy:
    """Proxy configuration"""
    host: str
    port: int
    protocol: str = "http"  # http, https, socks5
    username: Optional[str] = None
    password: Optional[str] = None
    is_healthy: bool = True
    fail_count: int = 0
    
    @property
    def url(self) -> str:
        """Get full proxy URL"""
        auth = ""
        if self.username and self.password:
            auth = f"{self.username}:{self.password}@"
        return f"{self.protocol}://{auth}{self.host}:{self.port}"
    
    def mark_failed(self):
        self.fail_count += 1
        if self.fail_count >= 3:
            self.is_healthy = False
    
    def mark_success(self):
        self.fail_count = 0
        self.is_healthy = True


class ProxyRotator:
    """Rotasi proxy dengan health checking"""
    
    def __init__(self, proxies: Optional[List[Proxy]] = None):
        self.proxies: List[Proxy] = proxies or []
        self._index = 0
    
    def add(self, proxy: Proxy):
        """Tambah proxy baru"""
        self.proxies.append(proxy)
    
    def add_from_string(self, proxy_str: str):
        """
        Parse proxy dari string format:
        - host:port
        - protocol://host:port
        - protocol://user:pass@host:port
        """
        try:
            if "://" in proxy_str:
                protocol, rest = proxy_str.split("://", 1)
            else:
                protocol = "http"
                rest = proxy_str
            
            if "@" in rest:
                auth, host_port = rest.rsplit("@", 1)
                username, password = auth.split(":", 1)
            else:
                host_port = rest
                username, password = None, None
            
            host, port = host_port.split(":")
            self.add(Proxy(
                host=host,
                port=int(port),
                protocol=protocol,
                username=username,
                password=password
            ))
        except Exception as e:
            print(f"[!] Invalid proxy format: {proxy_str} - {e}")
    
    def load_from_file(self, filepath: str):
        """Load proxies dari file (satu per baris)"""
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        self.add_from_string(line)
            print(f"[+] Loaded {len(self.proxies)} proxies from {filepath}")
        except FileNotFoundError:
            print(f"[!] Proxy file not found: {filepath}")
    
    def get_healthy(self) -> List[Proxy]:
        """Ambil semua proxy yang healthy"""
        return [p for p in self.proxies if p.is_healthy]
    
    def get_random(self) -> Optional[Proxy]:
        """Ambil proxy random yang healthy"""
        healthy = self.get_healthy()
        if not healthy:
            return None
        return random.choice(healthy)
    
    def get_next(self) -> Optional[Proxy]:
        """Ambil proxy berikutnya yang healthy"""
        healthy = self.get_healthy()
        if not healthy:
            return None
        
        proxy = healthy[self._index % len(healthy)]
        self._index += 1
        return proxy
    
    def to_playwright_format(self, proxy: Proxy) -> Dict:
        """Convert ke format yang diterima Playwright"""
        config = {
            'server': f"{proxy.protocol}://{proxy.host}:{proxy.port}"
        }
        if proxy.username and proxy.password:
            config['username'] = proxy.username
            config['password'] = proxy.password
        return config
    
    @property
    def count(self) -> int:
        return len(self.proxies)
    
    @property
    def healthy_count(self) -> int:
        return len(self.get_healthy())


# ==================== PROXY CHAIN (MULTI-HOP) ====================

@dataclass
class ProxyChainConfig:
    """Configuration for proxy chaining"""
    chain_length: int = 2  # Number of hops
    residential_only: bool = False
    country_lock: Optional[str] = None  # ISO country code
    rotate_every: int = 10  # Requests before rotation


class ProxyChain:
    """
    Multi-hop proxy chain for enhanced anonymity
    Routes traffic through multiple proxies sequentially
    """
    
    def __init__(self, rotator: ProxyRotator, config: Optional[ProxyChainConfig] = None):
        self.rotator = rotator
        self.config = config or ProxyChainConfig()
        self.current_chain: List[Proxy] = []
        self.request_count = 0
    
    def build_chain(self) -> List[Proxy]:
        """Build a new proxy chain"""
        healthy = self.rotator.get_healthy()
        
        if len(healthy) < self.config.chain_length:
            print(f"[!] Not enough proxies for chain of {self.config.chain_length}")
            return healthy
        
        # Select proxies for chain
        chain = random.sample(healthy, self.config.chain_length)
        self.current_chain = chain
        
        print(f"[CHAIN] Built chain with {len(chain)} hops")
        return chain
    
    def get_entry_proxy(self) -> Optional[Proxy]:
        """Get the entry point proxy (first in chain)"""
        if not self.current_chain:
            self.build_chain()
        
        self.request_count += 1
        
        # Rotate chain if needed
        if self.request_count >= self.config.rotate_every:
            self.build_chain()
            self.request_count = 0
        
        return self.current_chain[0] if self.current_chain else None
    
    def get_chain_string(self) -> str:
        """Get human-readable chain description"""
        return " -> ".join([f"{p.host}:{p.port}" for p in self.current_chain])


class ResidentialProxyManager:
    """
    Manager for residential proxies
    Residential IPs are harder to detect than datacenter IPs
    """
    
    # Known residential proxy providers patterns
    RESIDENTIAL_PATTERNS = [
        'residential', 'mobile', 'isp', 'home',
        'smartproxy', 'luminati', 'oxylabs', 'brightdata'
    ]
    
    def __init__(self, rotator: ProxyRotator):
        self.rotator = rotator
        self.residential_proxies: List[Proxy] = []
        self.datacenter_proxies: List[Proxy] = []
        self._categorize_proxies()
    
    def _categorize_proxies(self):
        """Categorize proxies as residential or datacenter"""
        for proxy in self.rotator.proxies:
            is_residential = any(
                pattern in proxy.host.lower() 
                for pattern in self.RESIDENTIAL_PATTERNS
            )
            
            if is_residential:
                self.residential_proxies.append(proxy)
            else:
                self.datacenter_proxies.append(proxy)
    
    def get_residential(self) -> Optional[Proxy]:
        """Get a residential proxy"""
        healthy = [p for p in self.residential_proxies if p.is_healthy]
        return random.choice(healthy) if healthy else None
    
    def get_datacenter(self) -> Optional[Proxy]:
        """Get a datacenter proxy"""
        healthy = [p for p in self.datacenter_proxies if p.is_healthy]
        return random.choice(healthy) if healthy else None
    
    def mark_as_residential(self, proxy: Proxy):
        """Manually mark a proxy as residential"""
        if proxy not in self.residential_proxies:
            self.residential_proxies.append(proxy)
            if proxy in self.datacenter_proxies:
                self.datacenter_proxies.remove(proxy)


class AutoRotatingProxy:
    """
    Automatically rotating proxy based on various triggers
    """
    
    def __init__(
        self,
        rotator: ProxyRotator,
        requests_per_proxy: int = 20,
        rotate_on_error: bool = True,
        rotate_on_captcha: bool = True
    ):
        self.rotator = rotator
        self.requests_per_proxy = requests_per_proxy
        self.rotate_on_error = rotate_on_error
        self.rotate_on_captcha = rotate_on_captcha
        
        self.current_proxy: Optional[Proxy] = None
        self.request_count = 0
    
    def get_proxy(self) -> Optional[Proxy]:
        """Get current or rotated proxy"""
        if self._should_rotate():
            self.current_proxy = self.rotator.get_random()
            self.request_count = 0
            if self.current_proxy:
                print(f"[PROXY] Rotated to: {self.current_proxy.host}:{self.current_proxy.port}")
        
        self.request_count += 1
        return self.current_proxy
    
    def _should_rotate(self) -> bool:
        """Check if rotation is needed"""
        if self.current_proxy is None:
            return True
        if self.request_count >= self.requests_per_proxy:
            return True
        if not self.current_proxy.is_healthy:
            return True
        return False
    
    def trigger_rotation(self, reason: str = "manual"):
        """Force rotation"""
        print(f"[PROXY] Forced rotation: {reason}")
        self.current_proxy = self.rotator.get_random()
        self.request_count = 0
    
    def on_error(self):
        """Handle error event"""
        if self.rotate_on_error and self.current_proxy:
            self.current_proxy.mark_failed()
            self.trigger_rotation("error")
    
    def on_captcha(self):
        """Handle CAPTCHA detection"""
        if self.rotate_on_captcha:
            self.trigger_rotation("captcha_detected")

