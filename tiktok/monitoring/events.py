"""
Event System for TikTok Monitoring
Pub/sub event emitter with LRU cache for recent events
"""

import asyncio
from collections import OrderedDict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
import json


class EventType(str, Enum):
    """Event types for monitoring"""
    # Scraping events
    PROFILE_SCRAPED = "profile_scraped"
    FOLLOWERS_SCRAPED = "followers_scraped"
    FOLLOWING_SCRAPED = "following_scraped"
    
    # Error events
    ERROR = "error"
    RATE_LIMIT = "rate_limit"
    CAPTCHA = "captcha"
    TIMEOUT = "timeout"
    
    # System events
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    BROWSER_CRASH = "browser_crash"
    
    # Monitoring events
    ANOMALY_DETECTED = "anomaly_detected"
    THRESHOLD_EXCEEDED = "threshold_exceeded"
    HEARTBEAT = "heartbeat"


class Severity(str, Enum):
    """Event severity levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ScrapingEvent:
    """Data class for scraping events"""
    event_type: EventType
    timestamp: datetime = field(default_factory=datetime.now)
    username: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    severity: Severity = Severity.INFO
    source: str = "scraper"
    event_id: str = field(default_factory=lambda: f"{datetime.now().timestamp():.6f}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value if isinstance(self.event_type, Enum) else self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "username": self.username,
            "data": self.data,
            "severity": self.severity.value if isinstance(self.severity, Enum) else self.severity,
            "source": self.source,
        }
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScrapingEvent":
        """Create from dictionary"""
        return cls(
            event_type=EventType(data["event_type"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            username=data.get("username"),
            data=data.get("data", {}),
            severity=Severity(data.get("severity", "info")),
            source=data.get("source", "scraper"),
            event_id=data.get("event_id", ""),
        )


class LRUCache:
    """
    LRU Cache for storing recent events
    Algorithm: OrderedDict with move_to_end on access
    """
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._cache: OrderedDict[str, ScrapingEvent] = OrderedDict()
    
    def put(self, event: ScrapingEvent) -> None:
        """Add event to cache"""
        key = event.event_id
        
        if key in self._cache:
            # Move to end (most recent)
            self._cache.move_to_end(key)
        else:
            # Add new
            self._cache[key] = event
            
            # Evict oldest if over capacity
            while len(self._cache) > self.max_size:
                self._cache.popitem(last=False)
    
    def get(self, event_id: str) -> Optional[ScrapingEvent]:
        """Get event by ID, moves to end (most recently accessed)"""
        if event_id in self._cache:
            self._cache.move_to_end(event_id)
            return self._cache[event_id]
        return None
    
    def get_recent(self, count: int = 10) -> List[ScrapingEvent]:
        """Get most recent events"""
        items = list(self._cache.values())
        return items[-count:] if count < len(items) else items
    
    def get_by_type(self, event_type: EventType, limit: int = 50) -> List[ScrapingEvent]:
        """Get events by type"""
        matching = [e for e in self._cache.values() if e.event_type == event_type]
        return matching[-limit:]
    
    def get_by_severity(self, min_severity: Severity) -> List[ScrapingEvent]:
        """Get events at or above severity level"""
        severity_order = list(Severity)
        min_idx = severity_order.index(min_severity)
        return [e for e in self._cache.values() 
                if severity_order.index(e.severity) >= min_idx]
    
    def clear(self) -> None:
        """Clear all cached events"""
        self._cache.clear()
    
    def __len__(self) -> int:
        return len(self._cache)


class EventEmitter:
    """
    Pub/sub event system with async support
    Subscribers can register callbacks for specific event types
    """
    
    def __init__(self, cache_size: int = 1000):
        self._subscribers: Dict[EventType, List[Callable]] = {}
        self._async_subscribers: Dict[EventType, List[Callable]] = {}
        self._global_subscribers: List[Callable] = []
        self._async_global_subscribers: List[Callable] = []
        self._cache = LRUCache(max_size=cache_size)
        self._lock = asyncio.Lock()
    
    def subscribe(self, event_type: EventType, callback: Callable[[ScrapingEvent], None]) -> None:
        """Subscribe to specific event type with sync callback"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)
    
    def subscribe_async(self, event_type: EventType, callback: Callable[[ScrapingEvent], Any]) -> None:
        """Subscribe to specific event type with async callback"""
        if event_type not in self._async_subscribers:
            self._async_subscribers[event_type] = []
        self._async_subscribers[event_type].append(callback)
    
    def subscribe_all(self, callback: Callable[[ScrapingEvent], None]) -> None:
        """Subscribe to all events with sync callback"""
        self._global_subscribers.append(callback)
    
    def subscribe_all_async(self, callback: Callable[[ScrapingEvent], Any]) -> None:
        """Subscribe to all events with async callback"""
        self._async_global_subscribers.append(callback)
    
    def unsubscribe(self, event_type: EventType, callback: Callable) -> bool:
        """Unsubscribe callback from event type"""
        if event_type in self._subscribers and callback in self._subscribers[event_type]:
            self._subscribers[event_type].remove(callback)
            return True
        if event_type in self._async_subscribers and callback in self._async_subscribers[event_type]:
            self._async_subscribers[event_type].remove(callback)
            return True
        return False
    
    def emit(self, event: ScrapingEvent) -> None:
        """Emit event synchronously"""
        # Cache the event
        self._cache.put(event)
        
        # Call type-specific callbacks
        if event.event_type in self._subscribers:
            for callback in self._subscribers[event.event_type]:
                try:
                    callback(event)
                except Exception as e:
                    print(f"[EventEmitter] Error in callback: {e}")
        
        # Call global callbacks
        for callback in self._global_subscribers:
            try:
                callback(event)
            except Exception as e:
                print(f"[EventEmitter] Error in global callback: {e}")
    
    async def emit_async(self, event: ScrapingEvent) -> None:
        """Emit event asynchronously"""
        async with self._lock:
            # Cache the event
            self._cache.put(event)
        
        tasks = []
        
        # Type-specific async callbacks
        if event.event_type in self._async_subscribers:
            for callback in self._async_subscribers[event.event_type]:
                tasks.append(self._safe_call_async(callback, event))
        
        # Global async callbacks
        for callback in self._async_global_subscribers:
            tasks.append(self._safe_call_async(callback, event))
        
        # Also call sync callbacks
        self.emit(event)
        
        # Wait for all async callbacks
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _safe_call_async(self, callback: Callable, event: ScrapingEvent) -> None:
        """Safely call async callback with error handling"""
        try:
            await callback(event)
        except Exception as e:
            print(f"[EventEmitter] Error in async callback: {e}")
    
    def get_recent_events(self, count: int = 10) -> List[ScrapingEvent]:
        """Get recent events from cache"""
        return self._cache.get_recent(count)
    
    def get_events_by_type(self, event_type: EventType, limit: int = 50) -> List[ScrapingEvent]:
        """Get events by type from cache"""
        return self._cache.get_by_type(event_type, limit)
    
    def get_errors(self, limit: int = 50) -> List[ScrapingEvent]:
        """Get recent error events"""
        return self._cache.get_by_severity(Severity.ERROR)[-limit:]
    
    @property
    def cache(self) -> LRUCache:
        """Access to event cache"""
        return self._cache


# Convenience functions for creating events
def create_scrape_event(
    username: str,
    data: Dict[str, Any],
    event_type: EventType = EventType.PROFILE_SCRAPED
) -> ScrapingEvent:
    """Create a scraping event"""
    return ScrapingEvent(
        event_type=event_type,
        username=username,
        data=data,
        severity=Severity.INFO
    )


def create_error_event(
    error_type: str,
    message: str,
    username: Optional[str] = None,
    severity: Severity = Severity.ERROR
) -> ScrapingEvent:
    """Create an error event"""
    return ScrapingEvent(
        event_type=EventType.ERROR,
        username=username,
        data={"error_type": error_type, "message": message},
        severity=severity
    )


def create_rate_limit_event(
    wait_seconds: float,
    username: Optional[str] = None
) -> ScrapingEvent:
    """Create a rate limit event"""
    return ScrapingEvent(
        event_type=EventType.RATE_LIMIT,
        username=username,
        data={"wait_seconds": wait_seconds},
        severity=Severity.WARNING
    )
