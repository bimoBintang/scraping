"""
API Sniffer Module
Intercept dan capture internal TikTok API calls
"""

import json
import re
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, field


@dataclass
class CapturedRequest:
    """Captured API request data"""
    url: str
    method: str
    headers: Dict = field(default_factory=dict)
    post_data: Optional[str] = None
    response_status: Optional[int] = None
    response_body: Optional[str] = None
    
    @property
    def is_api(self) -> bool:
        """Check if this looks like an API call"""
        return any(pattern in self.url for pattern in [
            '/api/', '/v1/', '/v2/', 
            'webcast', 'user/detail',
            'follower', 'following'
        ])
    
    def to_dict(self) -> Dict:
        return {
            'url': self.url,
            'method': self.method,
            'is_api': self.is_api,
            'status': self.response_status,
        }


class APISniffer:
    """
    Intercept network requests untuk capture TikTok internal API
    
    Usage:
        sniffer = APISniffer()
        
        # Attach to page
        await sniffer.attach(page)
        
        # ... do scraping actions ...
        
        # Get captured API calls
        apis = sniffer.get_api_calls()
    """
    
    # Patterns untuk API endpoints yang menarik
    API_PATTERNS = [
        r'/api/user/detail',
        r'/api/post/item_list',
        r'/api/user/list',
        r'/api/follow',
        r'/api/comment',
        r'/webcast/user/following',
        r'/webcast/user/follower',
        r'/web/api/v2',
        r'/node/share/user/',
    ]
    
    def __init__(self):
        self.captured: List[CapturedRequest] = []
        self._attached = False
    
    async def attach(self, page) -> None:
        """Attach sniffer ke Playwright page"""
        if self._attached:
            return
        
        # Listen to all requests
        page.on("request", self._on_request)
        page.on("response", self._on_response)
        
        self._attached = True
        print("[Sniffer] Attached to page")
    
    def _on_request(self, request) -> None:
        """Handle request event"""
        url = request.url
        
        # Only capture interesting requests
        if self._is_interesting(url):
            self.captured.append(CapturedRequest(
                url=url,
                method=request.method,
                headers=dict(request.headers),
                post_data=request.post_data,
            ))
    
    async def _on_response(self, response) -> None:
        """Handle response event"""
        url = response.url
        
        # Find matching request and update with response
        for req in reversed(self.captured):
            if req.url == url and req.response_status is None:
                req.response_status = response.status
                
                # Try to get response body for API calls
                if req.is_api:
                    try:
                        req.response_body = await response.text()
                    except:
                        pass
                break
    
    def _is_interesting(self, url: str) -> bool:
        """Check if URL is worth capturing"""
        # Skip static resources
        skip_extensions = ['.js', '.css', '.png', '.jpg', '.gif', '.svg', '.woff', '.ttf']
        if any(url.lower().endswith(ext) for ext in skip_extensions):
            return False
        
        # Check for API patterns
        return any(re.search(pattern, url) for pattern in self.API_PATTERNS)
    
    def get_api_calls(self) -> List[CapturedRequest]:
        """Get all captured API calls"""
        return [req for req in self.captured if req.is_api]
    
    def get_endpoints(self) -> List[str]:
        """Get unique API endpoints"""
        endpoints = set()
        for req in self.get_api_calls():
            # Extract base endpoint
            url = req.url.split('?')[0]
            endpoints.add(url)
        return sorted(endpoints)
    
    def find_by_pattern(self, pattern: str) -> List[CapturedRequest]:
        """Find requests matching pattern"""
        return [req for req in self.captured if re.search(pattern, req.url)]
    
    def get_user_data_apis(self) -> List[CapturedRequest]:
        """Get API calls that likely contain user data"""
        patterns = ['user/detail', 'user/list', 'follower', 'following']
        results = []
        for req in self.captured:
            if any(p in req.url for p in patterns):
                results.append(req)
        return results
    
    def extract_json_responses(self) -> List[Dict]:
        """Extract JSON from API responses"""
        results = []
        for req in self.get_api_calls():
            if req.response_body:
                try:
                    data = json.loads(req.response_body)
                    results.append({
                        'url': req.url,
                        'data': data
                    })
                except json.JSONDecodeError:
                    pass
        return results
    
    def clear(self) -> None:
        """Clear captured requests"""
        self.captured.clear()
    
    def to_har(self) -> Dict:
        """Export captures ke HAR-like format"""
        entries = []
        for req in self.captured:
            entries.append({
                'request': {
                    'method': req.method,
                    'url': req.url,
                    'headers': req.headers,
                    'postData': req.post_data,
                },
                'response': {
                    'status': req.response_status,
                    'body': req.response_body[:500] if req.response_body else None,
                }
            })
        return {'log': {'entries': entries}}
