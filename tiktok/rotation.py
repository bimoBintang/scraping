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
