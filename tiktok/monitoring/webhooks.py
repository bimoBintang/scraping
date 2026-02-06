"""
Webhook Dispatcher for TikTok Monitoring
Send events to external endpoints with enhanced security

Security Features:
- HMAC-SHA256 signature with timestamp (replay protection)
- URL validation (SSRF protection)
- Request ID for idempotency
- Per-webhook rate limiting
- Secret strength enforcement
- Payload sanitization
"""

import asyncio
import hashlib
import hmac
import ipaddress
import json
import re
import secrets
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from enum import Enum
from urllib.parse import urlparse

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

from .events import ScrapingEvent


class WebhookStatus(str, Enum):
    """Webhook delivery status"""
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"
    BLOCKED = "blocked"  # Security blocked


class WebhookSecurityError(Exception):
    """Raised for security-related webhook errors"""
    pass


# ============================================================================
# SECURITY: URL Validation (SSRF Protection)
# ============================================================================

class URLValidator:
    """
    Validates webhook URLs to prevent SSRF attacks
    Blocks private IPs, localhost, and dangerous schemes
    """
    
    # Private IP ranges (RFC 1918, RFC 4193, etc.)
    PRIVATE_RANGES = [
        ipaddress.ip_network('10.0.0.0/8'),
        ipaddress.ip_network('172.16.0.0/12'),
        ipaddress.ip_network('192.168.0.0/16'),
        ipaddress.ip_network('127.0.0.0/8'),       # Loopback
        ipaddress.ip_network('169.254.0.0/16'),    # Link-local
        ipaddress.ip_network('::1/128'),           # IPv6 loopback
        ipaddress.ip_network('fc00::/7'),          # IPv6 private
        ipaddress.ip_network('fe80::/10'),         # IPv6 link-local
    ]
    
    BLOCKED_HOSTS = {
        'localhost', 'localhost.localdomain',
        '0.0.0.0', '[::]', '[::1]',
        'metadata.google.internal',  # GCP metadata
        '169.254.169.254',           # AWS/Azure metadata
    }
    
    ALLOWED_SCHEMES = {'https'}  # Only HTTPS by default
    
    @classmethod
    def validate(cls, url: str, allow_http: bool = False) -> bool:
        """
        Validate URL is safe for webhook delivery
        
        Args:
            url: URL to validate
            allow_http: Allow HTTP (insecure) - default False
            
        Returns:
            True if URL is safe
            
        Raises:
            WebhookSecurityError: If URL is blocked
        """
        try:
            parsed = urlparse(url)
            
            # Check scheme
            allowed = cls.ALLOWED_SCHEMES.copy()
            if allow_http:
                allowed.add('http')
            
            if parsed.scheme not in allowed:
                raise WebhookSecurityError(
                    f"Blocked scheme: {parsed.scheme}. Only {allowed} allowed."
                )
            
            # Check host
            host = parsed.hostname or ''
            host_lower = host.lower()
            
            if host_lower in cls.BLOCKED_HOSTS:
                raise WebhookSecurityError(f"Blocked host: {host}")
            
            # Check if IP address
            try:
                ip = ipaddress.ip_address(host)
                for network in cls.PRIVATE_RANGES:
                    if ip in network:
                        raise WebhookSecurityError(
                            f"Blocked private IP: {ip} (in {network})"
                        )
            except ValueError:
                # Not an IP, it's a hostname - check for suspicious patterns
                if re.match(r'^[\d.]+$', host):
                    raise WebhookSecurityError(f"Invalid IP format: {host}")
                
                # Block internal-looking hostnames
                suspicious = ['internal', 'private', 'local', 'intranet', 'corp']
                if any(s in host_lower for s in suspicious):
                    raise WebhookSecurityError(
                        f"Suspicious internal hostname: {host}"
                    )
            
            return True
            
        except WebhookSecurityError:
            raise
        except Exception as e:
            raise WebhookSecurityError(f"URL validation error: {e}")


# ============================================================================
# SECURITY: Rate Limiting
# ============================================================================

class WebhookRateLimiter:
    """Per-webhook rate limiting using sliding window"""
    
    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, List[float]] = {}
    
    def is_allowed(self, webhook_name: str) -> bool:
        """Check if request is allowed"""
        now = time.time()
        cutoff = now - self.window_seconds
        
        if webhook_name not in self._requests:
            self._requests[webhook_name] = []
        
        # Remove old requests
        self._requests[webhook_name] = [
            t for t in self._requests[webhook_name] if t > cutoff
        ]
        
        if len(self._requests[webhook_name]) >= self.max_requests:
            return False
        
        self._requests[webhook_name].append(now)
        return True
    
    def get_wait_time(self, webhook_name: str) -> float:
        """Get seconds to wait before next allowed request"""
        if webhook_name not in self._requests or not self._requests[webhook_name]:
            return 0.0
        
        oldest = min(self._requests[webhook_name])
        wait = (oldest + self.window_seconds) - time.time()
        return max(0.0, wait)


# ============================================================================
# SECURITY: Payload Sanitization
# ============================================================================

class PayloadSanitizer:
    """Sanitize payloads to prevent sensitive data leakage"""
    
    SENSITIVE_KEYS = {
        'password', 'secret', 'token', 'api_key', 'apikey', 'auth',
        'authorization', 'credential', 'private_key', 'session',
        'cookie', 'csrf', 'jwt', 'bearer', 'access_token', 'refresh_token',
    }
    
    REDACT_VALUE = "[REDACTED]"
    
    @classmethod
    def sanitize(cls, data: Dict[str, Any], max_depth: int = 10) -> Dict[str, Any]:
        """
        Recursively sanitize sensitive data
        
        Args:
            data: Dictionary to sanitize
            max_depth: Maximum recursion depth
            
        Returns:
            Sanitized dictionary
        """
        if max_depth <= 0:
            return {"_truncated": True}
        
        result = {}
        for key, value in data.items():
            key_lower = key.lower()
            
            # Check if key is sensitive
            if any(s in key_lower for s in cls.SENSITIVE_KEYS):
                result[key] = cls.REDACT_VALUE
            elif isinstance(value, dict):
                result[key] = cls.sanitize(value, max_depth - 1)
            elif isinstance(value, list):
                result[key] = [
                    cls.sanitize(v, max_depth - 1) if isinstance(v, dict) else v
                    for v in value[:100]  # Limit list size
                ]
            elif isinstance(value, str) and len(value) > 10000:
                result[key] = value[:10000] + "...[TRUNCATED]"
            else:
                result[key] = value
        
        return result


# ============================================================================
# Enhanced WebhookConfig
# ============================================================================

@dataclass
class WebhookConfig:
    """Configuration for a webhook endpoint with security options"""
    url: str
    secret: str = ""
    events: List[str] = field(default_factory=lambda: ["*"])
    retry_count: int = 3
    timeout: int = 10
    headers: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    name: str = ""
    
    # Security options
    allow_http: bool = False           # Allow insecure HTTP
    validate_url: bool = True          # Enable SSRF protection
    sanitize_payload: bool = True      # Enable payload sanitization  
    max_requests_per_minute: int = 60  # Rate limit
    replay_window_seconds: int = 300   # Timestamp validation window (5 min)
    
    MIN_SECRET_LENGTH = 32  # Minimum secret length for security
    
    def __post_init__(self):
        if not self.name:
            self.name = hashlib.sha256(self.url.encode()).hexdigest()[:12]
        
        # Validate secret strength
        if self.secret and len(self.secret) < self.MIN_SECRET_LENGTH:
            raise WebhookSecurityError(
                f"Secret too short. Minimum {self.MIN_SECRET_LENGTH} characters required."
            )
    
    @staticmethod
    def generate_secret() -> str:
        """Generate a cryptographically secure secret"""
        return secrets.token_urlsafe(48)  # 64 chars, 384 bits


@dataclass
class WebhookDelivery:
    """Record of a webhook delivery attempt"""
    webhook_name: str
    event_id: str
    request_id: str  # Unique request ID for idempotency
    status: WebhookStatus
    attempts: int = 0
    last_attempt: Optional[datetime] = None
    response_code: Optional[int] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "webhook": self.webhook_name,
            "event_id": self.event_id,
            "request_id": self.request_id,
            "status": self.status.value,
            "attempts": self.attempts,
            "last_attempt": self.last_attempt.isoformat() if self.last_attempt else None,
            "response_code": self.response_code,
            "error": self.error_message,
        }


# ============================================================================
# Enhanced WebhookDispatcher
# ============================================================================

class WebhookDispatcher:
    """
    Secure webhook delivery system
    
    Security Features:
    - HMAC-SHA256 signature with timestamp (replay protection)
    - URL validation (SSRF protection) 
    - Request ID for idempotency
    - Per-webhook rate limiting
    - Payload sanitization
    """
    
    def __init__(
        self,
        max_requests_per_minute: int = 60,
        global_rate_limit: int = 300
    ):
        if not AIOHTTP_AVAILABLE:
            raise ImportError("aiohttp required. Install with: pip install aiohttp")
        
        self.webhooks: List[WebhookConfig] = []
        self._queue: asyncio.Queue = asyncio.Queue()
        self._deliveries: List[WebhookDelivery] = []
        self._max_deliveries = 1000
        self._processing = False
        self._processor_task: Optional[asyncio.Task] = None
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Security components
        self._rate_limiter = WebhookRateLimiter(
            max_requests=max_requests_per_minute,
            window_seconds=60
        )
        self._global_rate_limiter = WebhookRateLimiter(
            max_requests=global_rate_limit,
            window_seconds=60
        )
        self._processed_request_ids: Set[str] = set()
        self._max_processed_ids = 10000
    
    def register(self, config: WebhookConfig) -> str:
        """
        Register a webhook endpoint with security validation
        
        Args:
            config: Webhook configuration
            
        Returns:
            Webhook name/ID
            
        Raises:
            WebhookSecurityError: If URL validation fails
        """
        # Validate URL if enabled
        if config.validate_url:
            URLValidator.validate(config.url, allow_http=config.allow_http)
        
        self.webhooks.append(config)
        print(f"[Webhook] Registered: {config.name} -> {config.url[:50]}...")
        return config.name
    
    def unregister(self, name: str) -> bool:
        """Remove a webhook by name"""
        for i, wh in enumerate(self.webhooks):
            if wh.name == name:
                self.webhooks.pop(i)
                return True
        return False
    
    async def start(self) -> None:
        """Start webhook processor"""
        self._session = aiohttp.ClientSession()
        self._processing = True
        self._processor_task = asyncio.create_task(self._process_queue())
        print("[Webhook] Secure dispatcher started")
    
    async def stop(self) -> None:
        """Stop webhook processor"""
        self._processing = False
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        if self._session:
            await self._session.close()
        print("[Webhook] Dispatcher stopped")
    
    async def dispatch(self, event: ScrapingEvent) -> int:
        """Dispatch event to matching webhooks"""
        event_type = event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type)
        queued = 0
        
        # Check global rate limit
        if not self._global_rate_limiter.is_allowed("_global"):
            print("[Webhook] Global rate limit exceeded")
            return 0
        
        for webhook in self.webhooks:
            if not webhook.enabled:
                continue
            
            if "*" not in webhook.events and event_type not in webhook.events:
                continue
            
            # Check per-webhook rate limit
            if not self._rate_limiter.is_allowed(webhook.name):
                print(f"[Webhook] Rate limited: {webhook.name}")
                continue
            
            await self._queue.put((webhook, event))
            queued += 1
        
        return queued
    
    async def _process_queue(self) -> None:
        """Process webhook queue"""
        while self._processing:
            try:
                webhook, event = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0
                )
                await self._send_webhook(webhook, event)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"[Webhook] Queue error: {e}")
    
    async def _send_webhook(self, webhook: WebhookConfig, event: ScrapingEvent) -> bool:
        """Send webhook with full security measures"""
        
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        
        # Check for replay (idempotency)
        if request_id in self._processed_request_ids:
            return False
        
        # Build payload
        payload = self._build_payload(event, request_id)
        
        # Sanitize if enabled
        if webhook.sanitize_payload:
            payload = PayloadSanitizer.sanitize(payload)
        
        payload_str = json.dumps(payload, default=str)
        
        # Current timestamp for signature
        timestamp = int(time.time())
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "TikTokScraper-Webhook/2.0",
            "X-Webhook-Event": event.event_type.value,
            "X-Webhook-Timestamp": str(timestamp),
            "X-Webhook-Request-Id": request_id,
            "X-Webhook-Delivery": event.event_id,
        }
        headers.update(webhook.headers)
        
        # Generate signature with timestamp (replay protection)
        if webhook.secret:
            signature = self._generate_signature(payload_str, webhook.secret, timestamp)
            headers["X-Webhook-Signature"] = f"sha256={signature}"
            headers["X-Webhook-Signature-Timestamp"] = str(timestamp)
        
        # Create delivery record
        delivery = WebhookDelivery(
            webhook_name=webhook.name,
            event_id=event.event_id,
            request_id=request_id,
            status=WebhookStatus.PENDING
        )
        
        # Retry loop with exponential backoff
        for attempt in range(webhook.retry_count + 1):
            delivery.attempts = attempt + 1
            delivery.last_attempt = datetime.now()
            
            try:
                async with self._session.post(
                    webhook.url,
                    data=payload_str,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=webhook.timeout)
                ) as response:
                    delivery.response_code = response.status
                    
                    if response.status < 300:
                        delivery.status = WebhookStatus.DELIVERED
                        self._record_delivery(delivery)
                        self._record_processed(request_id)
                        return True
                    
                    if response.status >= 500:
                        delivery.status = WebhookStatus.RETRYING
                        delivery.error_message = f"Server error: {response.status}"
                    else:
                        delivery.status = WebhookStatus.FAILED
                        delivery.error_message = f"Client error: {response.status}"
                        self._record_delivery(delivery)
                        return False
                        
            except asyncio.TimeoutError:
                delivery.status = WebhookStatus.RETRYING
                delivery.error_message = "Request timeout"
            except Exception as e:
                delivery.status = WebhookStatus.RETRYING
                delivery.error_message = str(e)
            
            # Exponential backoff with jitter
            if attempt < webhook.retry_count:
                base_wait = 2 ** attempt
                jitter = secrets.randbelow(1000) / 1000  # 0-1 second jitter
                await asyncio.sleep(base_wait + jitter)
        
        delivery.status = WebhookStatus.FAILED
        self._record_delivery(delivery)
        return False
    
    def _build_payload(self, event: ScrapingEvent, request_id: str) -> Dict[str, Any]:
        """Build webhook payload with security metadata"""
        return {
            "event": event.to_dict(),
            "timestamp": datetime.now().isoformat(),
            "source": "tiktok-scraper",
            "request_id": request_id,
            "api_version": "2.0",
        }
    
    def _generate_signature(self, payload: str, secret: str, timestamp: int) -> str:
        """
        Generate HMAC-SHA256 signature with timestamp
        
        Signing format: "{timestamp}.{payload}"
        This prevents replay attacks as signature is time-bound
        """
        signing_string = f"{timestamp}.{payload}"
        return hmac.new(
            secret.encode('utf-8'),
            signing_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    @staticmethod
    def verify_signature(
        payload: str,
        secret: str,
        signature: str,
        timestamp: int,
        max_age_seconds: int = 300
    ) -> bool:
        """
        Verify webhook signature with replay protection
        
        Args:
            payload: JSON payload string
            secret: Webhook secret
            signature: Signature to verify
            timestamp: Request timestamp
            max_age_seconds: Maximum age of request (default 5 min)
            
        Returns:
            True if signature is valid and not expired
        """
        # Check timestamp freshness (replay protection)
        now = int(time.time())
        if abs(now - timestamp) > max_age_seconds:
            return False  # Request too old or from future
        
        if signature.startswith("sha256="):
            signature = signature[7:]
        
        signing_string = f"{timestamp}.{payload}"
        expected = hmac.new(
            secret.encode('utf-8'),
            signing_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected, signature)
    
    def _record_delivery(self, delivery: WebhookDelivery) -> None:
        """Record delivery for history"""
        self._deliveries.append(delivery)
        if len(self._deliveries) > self._max_deliveries:
            self._deliveries = self._deliveries[-self._max_deliveries // 2:]
    
    def _record_processed(self, request_id: str) -> None:
        """Record processed request ID for idempotency"""
        self._processed_request_ids.add(request_id)
        if len(self._processed_request_ids) > self._max_processed_ids:
            # Remove oldest half
            to_remove = list(self._processed_request_ids)[:self._max_processed_ids // 2]
            for rid in to_remove:
                self._processed_request_ids.discard(rid)
    
    def get_stats(self) -> Dict:
        """Get webhook statistics"""
        delivered = sum(1 for d in self._deliveries if d.status == WebhookStatus.DELIVERED)
        failed = sum(1 for d in self._deliveries if d.status == WebhookStatus.FAILED)
        blocked = sum(1 for d in self._deliveries if d.status == WebhookStatus.BLOCKED)
        
        return {
            "webhooks_registered": len(self.webhooks),
            "queue_size": self._queue.qsize(),
            "total_deliveries": len(self._deliveries),
            "delivered": delivered,
            "failed": failed,
            "blocked": blocked,
            "success_rate": delivered / len(self._deliveries) if self._deliveries else 1.0,
            "processed_request_ids": len(self._processed_request_ids),
        }
    
    def get_recent_deliveries(self, limit: int = 50) -> List[Dict]:
        """Get recent delivery records"""
        return [d.to_dict() for d in self._deliveries[-limit:]]
    
    def get_webhooks(self) -> List[Dict]:
        """Get registered webhooks info (secrets redacted)"""
        return [
            {
                "name": wh.name,
                "url": wh.url[:30] + "..." if len(wh.url) > 30 else wh.url,
                "events": wh.events,
                "enabled": wh.enabled,
                "has_secret": bool(wh.secret),
                "security": {
                    "url_validation": wh.validate_url,
                    "payload_sanitization": wh.sanitize_payload,
                    "https_only": not wh.allow_http,
                }
            }
            for wh in self.webhooks
        ]
