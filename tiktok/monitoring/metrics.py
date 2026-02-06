"""
Metrics Collector for TikTok Monitoring
Real-time metrics tracking with Exponential Moving Average (EMA)
"""

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Deque, Dict, List, Optional, Tuple
import statistics


@dataclass
class MetricPoint:
    """Single metric data point"""
    name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    tags: Dict[str, str] = field(default_factory=dict)


class ExponentialMovingAverage:
    """
    Exponential Moving Average (EMA) Calculator
    
    EMA gives more weight to recent data points, useful for:
    - Smoothing noisy metrics
    - Trend detection
    - Anomaly baseline calculation
    
    Formula: EMA_t = α * value_t + (1 - α) * EMA_(t-1)
    where α (alpha) = 2 / (span + 1)
    """
    
    def __init__(self, span: int = 10, alpha: Optional[float] = None):
        """
        Args:
            span: Number of periods for EMA calculation (default 10)
            alpha: Smoothing factor (0-1). If None, calculated from span.
                   Higher alpha = more weight on recent values
        """
        self.span = span
        self.alpha = alpha if alpha is not None else 2.0 / (span + 1)
        self._ema: Optional[float] = None
        self._count = 0
    
    def update(self, value: float) -> float:
        """
        Update EMA with new value
        
        Args:
            value: New data point
            
        Returns:
            Current EMA value
        """
        self._count += 1
        
        if self._ema is None:
            # First value becomes the initial EMA
            self._ema = value
        else:
            # EMA formula: α * current + (1 - α) * previous
            self._ema = self.alpha * value + (1 - self.alpha) * self._ema
        
        return self._ema
    
    @property
    def value(self) -> Optional[float]:
        """Current EMA value"""
        return self._ema
    
    @property
    def count(self) -> int:
        """Number of values processed"""
        return self._count
    
    def reset(self) -> None:
        """Reset EMA to initial state"""
        self._ema = None
        self._count = 0


class TimeWindowBuffer:
    """
    Time-windowed buffer for metrics
    Keeps only metrics within a specified time window
    """
    
    def __init__(self, window_seconds: int = 300):
        """
        Args:
            window_seconds: Time window in seconds (default 5 minutes)
        """
        self.window_seconds = window_seconds
        self._buffer: Deque[Tuple[datetime, float]] = deque()
    
    def add(self, value: float, timestamp: Optional[datetime] = None) -> None:
        """Add value to buffer"""
        ts = timestamp or datetime.now()
        self._buffer.append((ts, value))
        self._cleanup()
    
    def _cleanup(self) -> None:
        """Remove expired entries"""
        cutoff = datetime.now() - timedelta(seconds=self.window_seconds)
        while self._buffer and self._buffer[0][0] < cutoff:
            self._buffer.popleft()
    
    def get_values(self) -> List[float]:
        """Get all values in current window"""
        self._cleanup()
        return [v for _, v in self._buffer]
    
    def get_stats(self) -> Dict[str, float]:
        """Get statistics for current window"""
        values = self.get_values()
        if not values:
            return {"count": 0, "sum": 0, "mean": 0, "min": 0, "max": 0}
        
        return {
            "count": len(values),
            "sum": sum(values),
            "mean": statistics.mean(values),
            "min": min(values),
            "max": max(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0,
        }
    
    def rate_per_minute(self) -> float:
        """Calculate rate per minute"""
        self._cleanup()
        if not self._buffer:
            return 0.0
        
        count = len(self._buffer)
        if count < 2:
            return count * (60.0 / self.window_seconds)
        
        time_span = (self._buffer[-1][0] - self._buffer[0][0]).total_seconds()
        if time_span <= 0:
            return 0.0
        
        return (count / time_span) * 60.0
    
    def __len__(self) -> int:
        self._cleanup()
        return len(self._buffer)


class MetricsCollector:
    """
    Real-time metrics collector with EMA smoothing
    
    Collects and aggregates:
    - Scrape counts (success/failure)
    - Response times
    - Error rates
    - Rate per minute
    """
    
    def __init__(self, window_seconds: int = 300, ema_span: int = 20):
        """
        Args:
            window_seconds: Time window for metrics (default 5 minutes)
            ema_span: Span for EMA calculation (default 20)
        """
        self.window_seconds = window_seconds
        self.ema_span = ema_span
        
        # Counters
        self._total_scrapes = 0
        self._successful_scrapes = 0
        self._failed_scrapes = 0
        
        # Time buffers
        self._scrape_times = TimeWindowBuffer(window_seconds)
        self._response_times = TimeWindowBuffer(window_seconds)
        self._error_times = TimeWindowBuffer(window_seconds)
        
        # EMA trackers
        self._response_time_ema = ExponentialMovingAverage(span=ema_span)
        self._success_rate_ema = ExponentialMovingAverage(span=ema_span)
        
        # Error tracking by type
        self._error_counts: Dict[str, int] = {}
        
        # Start time
        self._start_time = datetime.now()
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
    
    def record_scrape(
        self,
        username: str,
        duration_ms: float,
        success: bool,
        data_size: int = 0
    ) -> None:
        """
        Record a scraping operation
        
        Args:
            username: Username that was scraped
            duration_ms: Response time in milliseconds
            success: Whether scrape was successful
            data_size: Size of scraped data in bytes
        """
        self._total_scrapes += 1
        self._scrape_times.add(1.0)
        
        if success:
            self._successful_scrapes += 1
            self._response_times.add(duration_ms)
            self._response_time_ema.update(duration_ms)
        else:
            self._failed_scrapes += 1
            self._error_times.add(1.0)
        
        # Update success rate EMA
        success_rate = self._successful_scrapes / self._total_scrapes if self._total_scrapes > 0 else 1.0
        self._success_rate_ema.update(success_rate)
    
    def record_error(self, error_type: str, message: str = "") -> None:
        """
        Record an error
        
        Args:
            error_type: Type/category of error
            message: Error message (optional)
        """
        self._error_counts[error_type] = self._error_counts.get(error_type, 0) + 1
        self._error_times.add(1.0)
        self._failed_scrapes += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get current statistics
        
        Returns:
            Dictionary with all current metrics
        """
        uptime = (datetime.now() - self._start_time).total_seconds()
        
        return {
            # Counts
            "total_scrapes": self._total_scrapes,
            "successful_scrapes": self._successful_scrapes,
            "failed_scrapes": self._failed_scrapes,
            
            # Rates
            "success_rate": self._successful_scrapes / self._total_scrapes if self._total_scrapes > 0 else 1.0,
            "success_rate_ema": self._success_rate_ema.value or 1.0,
            "scrapes_per_minute": self._scrape_times.rate_per_minute(),
            "errors_per_minute": self._error_times.rate_per_minute(),
            
            # Response times
            "response_time_stats": self._response_times.get_stats(),
            "response_time_ema": self._response_time_ema.value or 0,
            
            # Errors by type
            "error_counts": dict(self._error_counts),
            
            # System
            "uptime_seconds": uptime,
            "start_time": self._start_time.isoformat(),
            "window_seconds": self.window_seconds,
        }
    
    def get_rate_per_minute(self) -> float:
        """Get current scraping rate per minute"""
        return self._scrape_times.rate_per_minute()
    
    def get_error_rate(self) -> float:
        """Get current error rate (0-1)"""
        if self._total_scrapes == 0:
            return 0.0
        return self._failed_scrapes / self._total_scrapes
    
    def get_response_time_ema(self) -> float:
        """Get EMA of response times"""
        return self._response_time_ema.value or 0.0
    
    def reset(self) -> None:
        """Reset all metrics"""
        self._total_scrapes = 0
        self._successful_scrapes = 0
        self._failed_scrapes = 0
        self._scrape_times = TimeWindowBuffer(self.window_seconds)
        self._response_times = TimeWindowBuffer(self.window_seconds)
        self._error_times = TimeWindowBuffer(self.window_seconds)
        self._response_time_ema.reset()
        self._success_rate_ema.reset()
        self._error_counts.clear()
        self._start_time = datetime.now()


class MetricsAggregator:
    """
    Aggregates metrics from multiple collectors
    Supports time-windowed aggregation
    """
    
    def __init__(self):
        self._metrics: Dict[str, List[MetricPoint]] = {}
        self._emas: Dict[str, ExponentialMovingAverage] = {}
    
    def add_metric(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Add a metric data point
        
        Args:
            name: Metric name
            value: Metric value
            tags: Optional tags for filtering
        """
        point = MetricPoint(name=name, value=value, tags=tags or {})
        
        if name not in self._metrics:
            self._metrics[name] = []
            self._emas[name] = ExponentialMovingAverage(span=20)
        
        self._metrics[name].append(point)
        self._emas[name].update(value)
        
        # Keep only last 10000 points per metric
        if len(self._metrics[name]) > 10000:
            self._metrics[name] = self._metrics[name][-5000:]
    
    def get_aggregated(
        self,
        name: str,
        window_minutes: int = 5
    ) -> Dict[str, Any]:
        """
        Get aggregated metrics for time window
        
        Args:
            name: Metric name
            window_minutes: Time window in minutes
            
        Returns:
            Aggregated statistics
        """
        if name not in self._metrics:
            return {"error": f"Metric '{name}' not found"}
        
        cutoff = datetime.now() - timedelta(minutes=window_minutes)
        points = [p for p in self._metrics[name] if p.timestamp >= cutoff]
        
        if not points:
            return {"count": 0, "values": []}
        
        values = [p.value for p in points]
        
        return {
            "name": name,
            "count": len(values),
            "sum": sum(values),
            "mean": statistics.mean(values),
            "min": min(values),
            "max": max(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0,
            "ema": self._emas[name].value,
            "window_minutes": window_minutes,
        }
    
    def get_all_metrics(self) -> List[str]:
        """Get list of all metric names"""
        return list(self._metrics.keys())
    
    def get_ema(self, name: str) -> Optional[float]:
        """Get EMA for specific metric"""
        if name in self._emas:
            return self._emas[name].value
        return None
