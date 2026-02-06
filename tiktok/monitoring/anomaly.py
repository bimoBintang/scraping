"""
Anomaly Detection for TikTok Monitoring
Z-score based anomaly detection with adaptive thresholds
"""

import math
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Deque, Dict, List, Optional, Tuple
from enum import Enum


class AnomalyType(str, Enum):
    """Types of anomalies"""
    SPIKE = "spike"                  # Sudden increase
    DROP = "drop"                    # Sudden decrease
    OUTLIER = "outlier"             # Value far from mean
    TREND_CHANGE = "trend_change"   # Change in trend direction
    RATE_LIMIT = "rate_limit"       # Possible rate limiting detected


@dataclass
class Anomaly:
    """Detected anomaly"""
    anomaly_type: AnomalyType
    value: float
    expected: float
    z_score: float
    timestamp: datetime
    metric_name: str
    severity: str  # low, medium, high, critical
    message: str
    
    def to_dict(self) -> Dict:
        return {
            "type": self.anomaly_type.value,
            "value": self.value,
            "expected": self.expected,
            "z_score": self.z_score,
            "timestamp": self.timestamp.isoformat(),
            "metric": self.metric_name,
            "severity": self.severity,
            "message": self.message,
        }


class ZScoreDetector:
    """
    Z-score based anomaly detector
    
    Z-score measures how many standard deviations a value is from the mean.
    Z = (x - μ) / σ
    
    Typically:
    - |Z| < 2: Normal
    - 2 ≤ |Z| < 3: Possibly anomalous
    - |Z| ≥ 3: Highly likely anomaly
    """
    
    def __init__(
        self,
        window_size: int = 100,
        z_threshold: float = 2.5,
        min_samples: int = 10
    ):
        """
        Args:
            window_size: Number of recent values to consider
            z_threshold: Z-score threshold for anomaly detection
            min_samples: Minimum samples before detection starts
        """
        self.window_size = window_size
        self.z_threshold = z_threshold
        self.min_samples = min_samples
        
        self._values: Deque[float] = deque(maxlen=window_size)
        self._sum = 0.0
        self._sum_sq = 0.0
    
    def add(self, value: float) -> Optional[Tuple[float, bool]]:
        """
        Add value and check for anomaly
        
        Args:
            value: New data point
            
        Returns:
            Tuple of (z_score, is_anomaly) or None if not enough samples
        """
        # Remove oldest value from running sums if at capacity
        if len(self._values) == self.window_size:
            old_value = self._values[0]
            self._sum -= old_value
            self._sum_sq -= old_value ** 2
        
        # Add new value
        self._values.append(value)
        self._sum += value
        self._sum_sq += value ** 2
        
        # Check for anomaly
        if len(self._values) < self.min_samples:
            return None
        
        z_score = self.get_z_score(value)
        is_anomaly = abs(z_score) >= self.z_threshold
        
        return (z_score, is_anomaly)
    
    def get_z_score(self, value: float) -> float:
        """
        Calculate Z-score for a value
        
        Args:
            value: Value to calculate Z-score for
            
        Returns:
            Z-score (number of standard deviations from mean)
        """
        n = len(self._values)
        if n < 2:
            return 0.0
        
        mean = self._sum / n
        variance = (self._sum_sq / n) - (mean ** 2)
        
        # Handle edge case where variance is 0 or negative (floating point error)
        if variance <= 0:
            return 0.0
        
        std_dev = math.sqrt(variance)
        if std_dev == 0:
            return 0.0
        
        return (value - mean) / std_dev
    
    @property
    def mean(self) -> float:
        """Current mean of window"""
        n = len(self._values)
        return self._sum / n if n > 0 else 0.0
    
    @property
    def std_dev(self) -> float:
        """Current standard deviation of window"""
        n = len(self._values)
        if n < 2:
            return 0.0
        
        mean = self._sum / n
        variance = (self._sum_sq / n) - (mean ** 2)
        return math.sqrt(max(0, variance))
    
    def reset(self) -> None:
        """Reset detector state"""
        self._values.clear()
        self._sum = 0.0
        self._sum_sq = 0.0


class AnomalyDetector:
    """
    Multi-metric anomaly detector with severity classification
    """
    
    def __init__(
        self,
        window_size: int = 100,
        z_threshold_low: float = 2.0,
        z_threshold_medium: float = 2.5,
        z_threshold_high: float = 3.0,
        z_threshold_critical: float = 4.0
    ):
        """
        Args:
            window_size: Window size for each metric detector
            z_threshold_*: Thresholds for severity levels
        """
        self.window_size = window_size
        self.thresholds = {
            "low": z_threshold_low,
            "medium": z_threshold_medium,
            "high": z_threshold_high,
            "critical": z_threshold_critical,
        }
        
        self._detectors: Dict[str, ZScoreDetector] = {}
        self._anomaly_history: List[Anomaly] = []
        self._max_history = 1000
    
    def add_value(
        self,
        metric_name: str,
        value: float
    ) -> Optional[Anomaly]:
        """
        Add value for a metric and check for anomaly
        
        Args:
            metric_name: Name of the metric
            value: New value
            
        Returns:
            Anomaly if detected, None otherwise
        """
        # Create detector if new metric
        if metric_name not in self._detectors:
            self._detectors[metric_name] = ZScoreDetector(
                window_size=self.window_size,
                z_threshold=self.thresholds["medium"]
            )
        
        detector = self._detectors[metric_name]
        result = detector.add(value)
        
        if result is None:
            return None
        
        z_score, is_anomaly = result
        
        if not is_anomaly:
            return None
        
        # Determine severity
        abs_z = abs(z_score)
        if abs_z >= self.thresholds["critical"]:
            severity = "critical"
        elif abs_z >= self.thresholds["high"]:
            severity = "high"
        elif abs_z >= self.thresholds["medium"]:
            severity = "medium"
        else:
            severity = "low"
        
        # Determine anomaly type
        if z_score > 0:
            anomaly_type = AnomalyType.SPIKE
            message = f"Spike detected: {value:.2f} is {abs_z:.1f}σ above mean ({detector.mean:.2f})"
        else:
            anomaly_type = AnomalyType.DROP
            message = f"Drop detected: {value:.2f} is {abs_z:.1f}σ below mean ({detector.mean:.2f})"
        
        anomaly = Anomaly(
            anomaly_type=anomaly_type,
            value=value,
            expected=detector.mean,
            z_score=z_score,
            timestamp=datetime.now(),
            metric_name=metric_name,
            severity=severity,
            message=message
        )
        
        # Store in history
        self._anomaly_history.append(anomaly)
        if len(self._anomaly_history) > self._max_history:
            self._anomaly_history = self._anomaly_history[-self._max_history // 2:]
        
        return anomaly
    
    def check_rate_limit(
        self,
        response_time_ms: float,
        error_count: int,
        window_minutes: int = 5
    ) -> Optional[Anomaly]:
        """
        Check for possible rate limiting based on response patterns
        
        Args:
            response_time_ms: Current response time
            error_count: Number of recent errors
            window_minutes: Time window to consider
            
        Returns:
            Anomaly if rate limiting suspected
        """
        # Check response time anomaly
        rt_anomaly = self.add_value("response_time", response_time_ms)
        
        # Check error rate anomaly
        error_anomaly = self.add_value("error_count", float(error_count))
        
        # If both spiking, likely rate limited
        if rt_anomaly and error_anomaly:
            if rt_anomaly.z_score > 2 and error_anomaly.z_score > 2:
                return Anomaly(
                    anomaly_type=AnomalyType.RATE_LIMIT,
                    value=response_time_ms,
                    expected=self._detectors["response_time"].mean,
                    z_score=max(rt_anomaly.z_score, error_anomaly.z_score),
                    timestamp=datetime.now(),
                    metric_name="rate_limit_detection",
                    severity="high",
                    message=f"Possible rate limiting: response time and errors both elevated"
                )
        
        return rt_anomaly or error_anomaly
    
    def get_recent_anomalies(self, limit: int = 50) -> List[Anomaly]:
        """Get recent anomalies"""
        return self._anomaly_history[-limit:]
    
    def get_anomalies_by_severity(self, severity: str) -> List[Anomaly]:
        """Get anomalies filtered by severity"""
        return [a for a in self._anomaly_history if a.severity == severity]
    
    def get_metric_stats(self, metric_name: str) -> Dict:
        """Get statistics for a metric"""
        if metric_name not in self._detectors:
            return {"error": "Metric not found"}
        
        detector = self._detectors[metric_name]
        return {
            "metric": metric_name,
            "mean": detector.mean,
            "std_dev": detector.std_dev,
            "sample_count": len(detector._values),
            "z_threshold": detector.z_threshold,
        }
    
    def reset_metric(self, metric_name: str) -> bool:
        """Reset a specific metric detector"""
        if metric_name in self._detectors:
            self._detectors[metric_name].reset()
            return True
        return False
    
    def reset_all(self) -> None:
        """Reset all detectors"""
        self._detectors.clear()
        self._anomaly_history.clear()
