"""
Monitoring and Analytics Module for TikTok AI
Model performance metrics, resource utilization, alerting
"""

import asyncio
import time
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
import json


# ==================== DATA CLASSES ====================

@dataclass
class MetricPoint:
    """Single metric data point"""
    name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class ModelMetrics:
    """Model performance metrics"""
    model_name: str
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    inference_count: int = 0
    avg_latency_ms: float = 0.0
    error_rate: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class ResourceMetrics:
    """System resource metrics"""
    timestamp: datetime = field(default_factory=datetime.now)
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    gpu_memory_mb: float = 0.0
    gpu_utilization: float = 0.0
    active_tasks: int = 0


@dataclass
class AlertConfig:
    """Alert configuration"""
    name: str
    metric: str
    threshold: float
    operator: str  # 'gt', 'lt', 'eq'
    severity: str = "warning"  # warning, error, critical
    cooldown_seconds: float = 300.0  # Min time between alerts


@dataclass
class Alert:
    """Triggered alert"""
    config: AlertConfig
    value: float
    message: str
    triggered_at: datetime = field(default_factory=datetime.now)


# ==================== METRICS COLLECTOR ====================

class MetricsCollector:
    """
    Collect and store metrics
    """
    
    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self._metrics: Dict[str, deque] = {}
        self._counters: Dict[str, int] = {}
        self._gauges: Dict[str, float] = {}
    
    def record(self, name: str, value: float, labels: Dict[str, str] = None):
        """Record a metric value"""
        if name not in self._metrics:
            self._metrics[name] = deque(maxlen=self.max_history)
        
        self._metrics[name].append(MetricPoint(
            name=name,
            value=value,
            labels=labels or {}
        ))
        
        # Update gauge
        self._gauges[name] = value
    
    def increment(self, name: str, value: int = 1):
        """Increment counter"""
        self._counters[name] = self._counters.get(name, 0) + value
    
    def get_gauge(self, name: str) -> float:
        """Get current gauge value"""
        return self._gauges.get(name, 0.0)
    
    def get_counter(self, name: str) -> int:
        """Get counter value"""
        return self._counters.get(name, 0)
    
    def get_history(
        self, 
        name: str, 
        since: Optional[datetime] = None
    ) -> List[MetricPoint]:
        """Get metric history"""
        if name not in self._metrics:
            return []
        
        points = list(self._metrics[name])
        
        if since:
            points = [p for p in points if p.timestamp >= since]
        
        return points
    
    def get_statistics(self, name: str) -> Dict[str, float]:
        """Get metric statistics"""
        history = self.get_history(name)
        
        if not history:
            return {"min": 0, "max": 0, "avg": 0, "count": 0}
        
        values = [p.value for p in history]
        
        return {
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "count": len(values)
        }
    
    def export(self) -> Dict[str, Any]:
        """Export all metrics"""
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "statistics": {
                name: self.get_statistics(name)
                for name in self._metrics
            }
        }


# ==================== MODEL MONITOR ====================

class ModelMonitor:
    """
    Monitor AI model performance
    """
    
    def __init__(self):
        self.metrics: Dict[str, ModelMetrics] = {}
        self._latencies: Dict[str, deque] = {}
        self._predictions: Dict[str, List] = {}
    
    def record_prediction(
        self,
        model_name: str,
        prediction: Any,
        actual: Optional[Any] = None,
        latency_ms: float = 0.0
    ):
        """Record a model prediction"""
        if model_name not in self.metrics:
            self.metrics[model_name] = ModelMetrics(model_name=model_name)
            self._latencies[model_name] = deque(maxlen=1000)
            self._predictions[model_name] = []
        
        m = self.metrics[model_name]
        m.inference_count += 1
        m.last_updated = datetime.now()
        
        # Track latency
        self._latencies[model_name].append(latency_ms)
        m.avg_latency_ms = sum(self._latencies[model_name]) / len(self._latencies[model_name])
        
        # Track accuracy if actual value provided
        if actual is not None:
            self._predictions[model_name].append({
                "predicted": prediction,
                "actual": actual,
                "correct": prediction == actual
            })
            
            correct = sum(1 for p in self._predictions[model_name] if p["correct"])
            total = len(self._predictions[model_name])
            m.accuracy = correct / total
    
    def record_error(self, model_name: str):
        """Record model error"""
        if model_name not in self.metrics:
            self.metrics[model_name] = ModelMetrics(model_name=model_name)
        
        m = self.metrics[model_name]
        errors = int(m.error_rate * m.inference_count) + 1
        m.inference_count += 1
        m.error_rate = errors / m.inference_count
    
    def get_metrics(self, model_name: str) -> Optional[ModelMetrics]:
        """Get model metrics"""
        return self.metrics.get(model_name)
    
    def get_all_metrics(self) -> Dict[str, ModelMetrics]:
        """Get all model metrics"""
        return self.metrics.copy()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all models"""
        return {
            name: {
                "accuracy": m.accuracy,
                "avg_latency_ms": m.avg_latency_ms,
                "inference_count": m.inference_count,
                "error_rate": m.error_rate
            }
            for name, m in self.metrics.items()
        }


# ==================== RESOURCE MONITOR ====================

class ResourceMonitor:
    """
    Monitor system resources
    """
    
    def __init__(self, history_size: int = 100):
        self._history: deque = deque(maxlen=history_size)
        self._running = False
        self._task = None
    
    def collect(self) -> ResourceMetrics:
        """Collect current resource metrics"""
        metrics = ResourceMetrics()
        
        try:
            import psutil
            metrics.cpu_percent = psutil.cpu_percent()
            metrics.memory_percent = psutil.virtual_memory().percent
        except ImportError:
            pass
        
        try:
            import torch
            if torch.cuda.is_available():
                metrics.gpu_memory_mb = torch.cuda.memory_allocated() / (1024 * 1024)
                # Note: GPU utilization requires nvidia-smi
        except ImportError:
            pass
        
        self._history.append(metrics)
        return metrics
    
    async def start_monitoring(self, interval: float = 5.0):
        """Start continuous monitoring"""
        self._running = True
        
        while self._running:
            self.collect()
            await asyncio.sleep(interval)
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self._running = False
    
    def get_current(self) -> Optional[ResourceMetrics]:
        """Get current metrics"""
        return self._history[-1] if self._history else None
    
    def get_history(self) -> List[ResourceMetrics]:
        """Get metrics history"""
        return list(self._history)
    
    def get_average(self) -> ResourceMetrics:
        """Get average metrics"""
        if not self._history:
            return ResourceMetrics()
        
        return ResourceMetrics(
            cpu_percent=sum(m.cpu_percent for m in self._history) / len(self._history),
            memory_percent=sum(m.memory_percent for m in self._history) / len(self._history),
            gpu_memory_mb=sum(m.gpu_memory_mb for m in self._history) / len(self._history)
        )


# ==================== ALERT MANAGER ====================

class AlertManager:
    """
    Manage alerts and notifications
    """
    
    def __init__(self):
        self.configs: List[AlertConfig] = []
        self._active_alerts: List[Alert] = []
        self._alert_history: deque = deque(maxlen=100)
        self._last_triggered: Dict[str, datetime] = {}
        self._handlers: List[Callable[[Alert], None]] = []
    
    def add_alert(self, config: AlertConfig):
        """Add alert configuration"""
        self.configs.append(config)
    
    def add_handler(self, handler: Callable[[Alert], None]):
        """Add alert handler"""
        self._handlers.append(handler)
    
    def check(self, metrics: Dict[str, float]):
        """Check metrics against alert configs"""
        now = datetime.now()
        
        for config in self.configs:
            if config.metric not in metrics:
                continue
            
            value = metrics[config.metric]
            triggered = False
            
            if config.operator == 'gt' and value > config.threshold:
                triggered = True
            elif config.operator == 'lt' and value < config.threshold:
                triggered = True
            elif config.operator == 'eq' and value == config.threshold:
                triggered = True
            
            if triggered:
                # Check cooldown
                last = self._last_triggered.get(config.name)
                if last and (now - last).total_seconds() < config.cooldown_seconds:
                    continue
                
                alert = Alert(
                    config=config,
                    value=value,
                    message=f"{config.name}: {config.metric}={value:.2f} {config.operator} {config.threshold}"
                )
                
                self._active_alerts.append(alert)
                self._alert_history.append(alert)
                self._last_triggered[config.name] = now
                
                # Call handlers
                for handler in self._handlers:
                    try:
                        handler(alert)
                    except Exception as e:
                        print(f"[ALERT] Handler error: {e}")
    
    def get_active_alerts(self) -> List[Alert]:
        """Get active alerts"""
        return self._active_alerts.copy()
    
    def acknowledge(self, alert_name: str):
        """Acknowledge and clear alert"""
        self._active_alerts = [
            a for a in self._active_alerts
            if a.config.name != alert_name
        ]
    
    def get_history(self) -> List[Alert]:
        """Get alert history"""
        return list(self._alert_history)


# ==================== DASHBOARD DATA ====================

class DashboardData:
    """
    Aggregate data for dashboard display
    """
    
    def __init__(
        self,
        metrics_collector: MetricsCollector,
        model_monitor: ModelMonitor,
        resource_monitor: ResourceMonitor,
        alert_manager: AlertManager
    ):
        self.metrics = metrics_collector
        self.models = model_monitor
        self.resources = resource_monitor
        self.alerts = alert_manager
    
    def get_overview(self) -> Dict[str, Any]:
        """Get dashboard overview data"""
        return {
            "timestamp": datetime.now().isoformat(),
            
            # Model summary
            "models": self.models.get_summary(),
            
            # Resource current
            "resources": {
                "current": self._metrics_to_dict(self.resources.get_current()),
                "average": self._metrics_to_dict(self.resources.get_average())
            },
            
            # Alerts
            "alerts": {
                "active": len(self.alerts.get_active_alerts()),
                "recent": [
                    {
                        "name": a.config.name,
                        "message": a.message,
                        "severity": a.config.severity,
                        "time": a.triggered_at.isoformat()
                    }
                    for a in self.alerts.get_active_alerts()
                ]
            },
            
            # Metrics summary
            "metrics": self.metrics.export()
        }
    
    def _metrics_to_dict(self, m: Optional[ResourceMetrics]) -> Dict[str, Any]:
        """Convert resource metrics to dict"""
        if not m:
            return {}
        
        return {
            "cpu_percent": m.cpu_percent,
            "memory_percent": m.memory_percent,
            "gpu_memory_mb": m.gpu_memory_mb
        }
    
    def get_model_details(self, model_name: str) -> Dict[str, Any]:
        """Get detailed model metrics"""
        m = self.models.get_metrics(model_name)
        if not m:
            return {}
        
        return {
            "name": m.model_name,
            "accuracy": m.accuracy,
            "precision": m.precision,
            "recall": m.recall,
            "f1_score": m.f1_score,
            "inference_count": m.inference_count,
            "avg_latency_ms": m.avg_latency_ms,
            "error_rate": m.error_rate,
            "last_updated": m.last_updated.isoformat()
        }
    
    def export_json(self) -> str:
        """Export dashboard data as JSON"""
        return json.dumps(self.get_overview(), indent=2, default=str)


# ==================== CONVENIENCE FUNCTIONS ====================

def create_default_alerts() -> List[AlertConfig]:
    """Create default alert configurations"""
    return [
        AlertConfig(
            name="high_cpu",
            metric="cpu_percent",
            threshold=90.0,
            operator="gt",
            severity="warning"
        ),
        AlertConfig(
            name="high_memory",
            metric="memory_percent",
            threshold=85.0,
            operator="gt",
            severity="warning"
        ),
        AlertConfig(
            name="high_gpu_memory",
            metric="gpu_memory_mb",
            threshold=7000,  # ~85% of 8GB
            operator="gt",
            severity="warning"
        ),
        AlertConfig(
            name="model_error_rate",
            metric="error_rate",
            threshold=0.1,  # 10% errors
            operator="gt",
            severity="error"
        ),
        AlertConfig(
            name="high_latency",
            metric="avg_latency_ms",
            threshold=5000,  # 5 seconds
            operator="gt",
            severity="warning"
        ),
    ]


class MonitoringSystem:
    """
    Complete monitoring system
    """
    
    def __init__(self):
        self.metrics = MetricsCollector()
        self.models = ModelMonitor()
        self.resources = ResourceMonitor()
        self.alerts = AlertManager()
        
        # Add default alerts
        for config in create_default_alerts():
            self.alerts.add_alert(config)
        
        # Create dashboard
        self.dashboard = DashboardData(
            self.metrics,
            self.models,
            self.resources,
            self.alerts
        )
    
    async def start(self, interval: float = 5.0):
        """Start monitoring"""
        print("[MONITOR] Starting monitoring system...")
        await self.resources.start_monitoring(interval)
    
    def stop(self):
        """Stop monitoring"""
        self.resources.stop_monitoring()
        print("[MONITOR] Monitoring stopped")
    
    def record_inference(
        self,
        model_name: str,
        prediction: Any,
        actual: Any = None,
        latency_ms: float = 0.0
    ):
        """Record model inference"""
        self.models.record_prediction(model_name, prediction, actual, latency_ms)
        self.metrics.increment(f"{model_name}_inferences")
        self.metrics.record(f"{model_name}_latency", latency_ms)
    
    def check_alerts(self):
        """Check all alerts"""
        current = self.resources.get_current()
        if current:
            self.alerts.check({
                "cpu_percent": current.cpu_percent,
                "memory_percent": current.memory_percent,
                "gpu_memory_mb": current.gpu_memory_mb
            })
        
        # Check model metrics
        for name, m in self.models.metrics.items():
            self.alerts.check({
                "error_rate": m.error_rate,
                "avg_latency_ms": m.avg_latency_ms
            })
    
    def get_status(self) -> Dict[str, Any]:
        """Get system status"""
        return self.dashboard.get_overview()
