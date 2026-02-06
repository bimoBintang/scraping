"""
Base Notification Classes with Circuit Breaker Pattern
Fault tolerance for notification delivery
"""

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from ..events import ScrapingEvent, Severity


class CircuitState(str, Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation, requests pass through
    OPEN = "open"          # Failure threshold exceeded, requests blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5        # Failures before opening
    success_threshold: int = 2        # Successes needed to close
    timeout_seconds: float = 60.0     # Time before trying again
    half_open_max_calls: int = 3      # Max calls in half-open state


class CircuitBreaker:
    """
    Circuit Breaker Pattern Implementation
    
    Prevents cascading failures by:
    1. CLOSED: Normal operation, track failures
    2. OPEN: Block all calls when failure threshold exceeded
    3. HALF_OPEN: After timeout, allow limited calls to test recovery
    
    Use for:
    - External API calls (Telegram, Discord, webhooks)
    - Database connections
    - Any unreliable external service
    """
    
    def __init__(self, config: Optional[CircuitBreakerConfig] = None, name: str = "default"):
        self.config = config or CircuitBreakerConfig()
        self.name = name
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()
    
    @property
    def state(self) -> CircuitState:
        """Current circuit state"""
        return self._state
    
    @property
    def is_allowed(self) -> bool:
        """Check if requests are allowed"""
        if self._state == CircuitState.CLOSED:
            return True
        
        if self._state == CircuitState.OPEN:
            # Check if timeout has passed
            if self._last_failure_time:
                elapsed = (datetime.now() - self._last_failure_time).total_seconds()
                if elapsed >= self.config.timeout_seconds:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    return True
            return False
        
        if self._state == CircuitState.HALF_OPEN:
            return self._half_open_calls < self.config.half_open_max_calls
        
        return False
    
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection
        
        Args:
            func: Async function to execute
            *args, **kwargs: Function arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitOpenError: If circuit is open
        """
        async with self._lock:
            if not self.is_allowed:
                raise CircuitOpenError(f"Circuit {self.name} is OPEN")
            
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1
        
        try:
            result = await func(*args, **kwargs)
            await self.record_success()
            return result
        except Exception as e:
            await self.record_failure()
            raise
    
    async def record_success(self) -> None:
        """Record successful call"""
        async with self._lock:
            self._failure_count = 0
            
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._success_count = 0
                    print(f"[CircuitBreaker:{self.name}] Circuit CLOSED - service recovered")
    
    async def record_failure(self) -> None:
        """Record failed call"""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now()
            self._success_count = 0
            
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                print(f"[CircuitBreaker:{self.name}] Circuit OPEN - failure in half-open state")
            elif self._failure_count >= self.config.failure_threshold:
                self._state = CircuitState.OPEN
                print(f"[CircuitBreaker:{self.name}] Circuit OPEN - threshold exceeded")
    
    def reset(self) -> None:
        """Reset circuit to closed state"""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        self._half_open_calls = 0
    
    def get_stats(self) -> Dict:
        """Get circuit breaker statistics"""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure": self._last_failure_time.isoformat() if self._last_failure_time else None,
        }


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


@dataclass
class AlertRule:
    """
    Rule for triggering alerts
    
    Defines conditions for when to send notifications
    """
    name: str
    event_types: List[str]           # Event types to match
    severity_threshold: Severity = Severity.WARNING  # Minimum severity
    cooldown_seconds: int = 60       # Seconds between alerts
    max_alerts_per_hour: int = 10    # Rate limit
    enabled: bool = True
    
    _last_alert_time: Optional[datetime] = field(default=None, repr=False)
    _alert_count_hour: int = field(default=0, repr=False)
    _hour_start: Optional[datetime] = field(default=None, repr=False)
    
    def matches(self, event: ScrapingEvent) -> bool:
        """Check if event matches this rule"""
        if not self.enabled:
            return False
        
        # Check event type
        event_type_str = event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type)
        if event_type_str not in self.event_types and "*" not in self.event_types:
            return False
        
        # Check severity
        severity_order = list(Severity)
        event_idx = severity_order.index(event.severity)
        threshold_idx = severity_order.index(self.severity_threshold)
        if event_idx < threshold_idx:
            return False
        
        return True
    
    def should_alert(self) -> bool:
        """Check if alert should be sent (respecting cooldown/rate limit)"""
        now = datetime.now()
        
        # Reset hourly counter if needed
        if self._hour_start is None or (now - self._hour_start).total_seconds() >= 3600:
            self._hour_start = now
            self._alert_count_hour = 0
        
        # Check rate limit
        if self._alert_count_hour >= self.max_alerts_per_hour:
            return False
        
        # Check cooldown
        if self._last_alert_time:
            elapsed = (now - self._last_alert_time).total_seconds()
            if elapsed < self.cooldown_seconds:
                return False
        
        return True
    
    def record_alert(self) -> None:
        """Record that an alert was sent"""
        self._last_alert_time = datetime.now()
        self._alert_count_hour += 1


class BaseNotifier(ABC):
    """Abstract base class for notifiers"""
    
    def __init__(self, name: str = "notifier"):
        self.name = name
        self.circuit_breaker = CircuitBreaker(name=name)
        self._enabled = True
        self._sent_count = 0
        self._error_count = 0
    
    @abstractmethod
    async def send_alert(self, event: ScrapingEvent) -> bool:
        """
        Send alert notification
        
        Args:
            event: Event to send
            
        Returns:
            True if sent successfully
        """
        pass
    
    @abstractmethod
    async def send_report(self, stats: Dict[str, Any]) -> bool:
        """
        Send periodic report
        
        Args:
            stats: Statistics to report
            
        Returns:
            True if sent successfully
        """
        pass
    
    async def send_with_circuit_breaker(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> bool:
        """Send with circuit breaker protection"""
        try:
            await self.circuit_breaker.execute(func, *args, **kwargs)
            self._sent_count += 1
            return True
        except CircuitOpenError:
            print(f"[{self.name}] Circuit open, skipping notification")
            return False
        except Exception as e:
            self._error_count += 1
            print(f"[{self.name}] Error sending notification: {e}")
            return False
    
    @property
    def is_enabled(self) -> bool:
        return self._enabled and self.circuit_breaker.is_allowed
    
    def enable(self) -> None:
        self._enabled = True
    
    def disable(self) -> None:
        self._enabled = False
    
    def get_stats(self) -> Dict:
        return {
            "name": self.name,
            "enabled": self._enabled,
            "sent_count": self._sent_count,
            "error_count": self._error_count,
            "circuit_breaker": self.circuit_breaker.get_stats(),
        }


class NotificationManager:
    """
    Unified notification dispatcher
    
    Manages multiple notifiers with:
    - Alert rules for filtering
    - Circuit breakers for fault tolerance
    - Rate limiting to prevent spam
    """
    
    def __init__(self):
        self.notifiers: List[BaseNotifier] = []
        self.alert_rules: List[AlertRule] = []
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._processing = False
        self._processor_task: Optional[asyncio.Task] = None
    
    def add_notifier(self, notifier: BaseNotifier) -> None:
        """Register a notification channel"""
        self.notifiers.append(notifier)
        print(f"[NotificationManager] Added notifier: {notifier.name}")
    
    def remove_notifier(self, name: str) -> bool:
        """Remove notifier by name"""
        for i, n in enumerate(self.notifiers):
            if n.name == name:
                self.notifiers.pop(i)
                return True
        return False
    
    def add_rule(self, rule: AlertRule) -> None:
        """Add alert trigger rule"""
        self.alert_rules.append(rule)
    
    def add_default_rules(self) -> None:
        """Add commonly used default rules"""
        self.add_rule(AlertRule(
            name="errors",
            event_types=["error", "browser_crash"],
            severity_threshold=Severity.ERROR,
            cooldown_seconds=30
        ))
        self.add_rule(AlertRule(
            name="rate_limits",
            event_types=["rate_limit", "captcha"],
            severity_threshold=Severity.WARNING,
            cooldown_seconds=60
        ))
        self.add_rule(AlertRule(
            name="anomalies",
            event_types=["anomaly_detected", "threshold_exceeded"],
            severity_threshold=Severity.WARNING,
            cooldown_seconds=120
        ))
    
    async def process_event(self, event: ScrapingEvent) -> int:
        """
        Process event and dispatch notifications
        
        Args:
            event: Event to process
            
        Returns:
            Number of notifications sent
        """
        sent_count = 0
        
        for rule in self.alert_rules:
            if rule.matches(event) and rule.should_alert():
                # Send to all enabled notifiers
                for notifier in self.notifiers:
                    if notifier.is_enabled:
                        success = await notifier.send_with_circuit_breaker(
                            notifier.send_alert,
                            event
                        )
                        if success:
                            sent_count += 1
                
                if sent_count > 0:
                    rule.record_alert()
        
        return sent_count
    
    async def send_to_all(self, event: ScrapingEvent) -> int:
        """Send to all notifiers regardless of rules"""
        sent_count = 0
        for notifier in self.notifiers:
            if notifier.is_enabled:
                success = await notifier.send_with_circuit_breaker(
                    notifier.send_alert,
                    event
                )
                if success:
                    sent_count += 1
        return sent_count
    
    async def broadcast_report(self, stats: Dict[str, Any]) -> int:
        """Send periodic report to all notifiers"""
        sent_count = 0
        for notifier in self.notifiers:
            if notifier.is_enabled:
                success = await notifier.send_with_circuit_breaker(
                    notifier.send_report,
                    stats
                )
                if success:
                    sent_count += 1
        return sent_count
    
    def get_stats(self) -> Dict:
        """Get notification system statistics"""
        return {
            "notifiers": [n.get_stats() for n in self.notifiers],
            "rules": [
                {
                    "name": r.name,
                    "event_types": r.event_types,
                    "enabled": r.enabled,
                    "alerts_this_hour": r._alert_count_hour,
                }
                for r in self.alert_rules
            ]
        }
