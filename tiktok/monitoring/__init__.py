"""
TikTok Monitoring Package
Real-time monitoring, metrics, notifications, and webhooks for TikTok Scraper

Features:
- Event System: Pub/sub with LRU cache
- Metrics: EMA, time-windowed aggregation
- Anomaly Detection: Z-score based
- Rate Limiting: Token Bucket algorithm
- WebSocket: Real-time streaming with Delta Encoding
- Notifications: Telegram with Circuit Breaker
- Webhooks: HMAC signatures + retry logic
- Dashboard: FastAPI with Chart.js
"""

# Events
from .events import (
    EventEmitter,
    ScrapingEvent,
    EventType,
    Severity,
    LRUCache,
    create_scrape_event,
    create_error_event,
    create_rate_limit_event,
)

# Metrics
from .metrics import (
    MetricsCollector,
    MetricsAggregator,
    ExponentialMovingAverage,
    TimeWindowBuffer,
    MetricPoint,
)

# Anomaly Detection
from .anomaly import (
    AnomalyDetector,
    ZScoreDetector,
    Anomaly,
    AnomalyType,
)

# Rate Limiting
from .rate_limiter import (
    RateLimiter,
    TokenBucket,
    AdaptiveRateLimiter,
    RateLimitConfig,
)

# WebSocket
from .websocket_server import (
    MonitoringWebSocket,
    DeltaEncoder,
    MessageType,
    ClientConnection,
)

# Notifications
from .notifications import (
    NotificationManager,
    CircuitBreaker,
    AlertRule,
    BaseNotifier,
    TelegramNotifier,
)

# Webhooks
from .webhooks import (
    WebhookDispatcher,
    WebhookConfig,
    WebhookDelivery,
    WebhookStatus,
)

# Dashboard
from .dashboard import (
    DashboardServer,
    create_app,
)


__all__ = [
    # Events
    'EventEmitter',
    'ScrapingEvent',
    'EventType',
    'Severity',
    'LRUCache',
    'create_scrape_event',
    'create_error_event',
    'create_rate_limit_event',
    
    # Metrics
    'MetricsCollector',
    'MetricsAggregator',
    'ExponentialMovingAverage',
    'TimeWindowBuffer',
    'MetricPoint',
    
    # Anomaly Detection
    'AnomalyDetector',
    'ZScoreDetector',
    'Anomaly',
    'AnomalyType',
    
    # Rate Limiting
    'RateLimiter',
    'TokenBucket',
    'AdaptiveRateLimiter',
    'RateLimitConfig',
    
    # WebSocket
    'MonitoringWebSocket',
    'DeltaEncoder',
    'MessageType',
    'ClientConnection',
    
    # Notifications
    'NotificationManager',
    'CircuitBreaker',
    'AlertRule',
    'BaseNotifier',
    'TelegramNotifier',
    
    # Webhooks
    'WebhookDispatcher',
    'WebhookConfig',
    'WebhookDelivery',
    'WebhookStatus',
    
    # Dashboard
    'DashboardServer',
    'create_app',
]

__version__ = '1.0.0'
