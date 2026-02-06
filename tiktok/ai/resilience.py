"""
Resilience Module for TikTok AI
Circuit breaker, fallback chains, resource management, partial results
"""

import asyncio
import time
from typing import Any, Callable, List, Dict, Optional, TypeVar, Generic
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
import traceback

T = TypeVar('T')


# ==================== CIRCUIT BREAKER ====================

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitStats:
    """Circuit breaker statistics"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None


class CircuitBreaker:
    """
    Circuit breaker pattern for fault tolerance
    Prevents cascade failures by stopping calls to failing services
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        reset_timeout: float = 60.0,
        half_open_max_calls: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.half_open_max_calls = half_open_max_calls
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.stats = CircuitStats()
        
        self._lock = asyncio.Lock()
    
    async def call(
        self, 
        func: Callable, 
        *args, 
        fallback: Optional[Callable] = None,
        **kwargs
    ) -> Any:
        """
        Execute function with circuit breaker protection
        
        Args:
            func: Async function to call
            fallback: Optional fallback function if circuit is open
        """
        async with self._lock:
            self._check_state_transition()
            
            if self.state == CircuitState.OPEN:
                self.stats.rejected_calls += 1
                if fallback:
                    return await self._execute_fallback(fallback, *args, **kwargs)
                raise CircuitOpenError("Circuit is open, request rejected")
        
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
            
        except Exception as e:
            await self._on_failure(e)
            
            if fallback:
                return await self._execute_fallback(fallback, *args, **kwargs)
            raise
    
    def _check_state_transition(self):
        """Check and update circuit state"""
        if self.state == CircuitState.OPEN:
            if self.last_failure_time:
                elapsed = (datetime.now() - self.last_failure_time).total_seconds()
                if elapsed >= self.reset_timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                    print(f"[CIRCUIT] Transitioning to HALF_OPEN after {elapsed:.1f}s")
    
    async def _on_success(self):
        """Handle successful call"""
        async with self._lock:
            self.stats.total_calls += 1
            self.stats.successful_calls += 1
            self.stats.last_success_time = datetime.now()
            
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.half_open_max_calls:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    print("[CIRCUIT] Circuit CLOSED - service recovered")
            
            elif self.state == CircuitState.CLOSED:
                self.failure_count = max(0, self.failure_count - 1)
    
    async def _on_failure(self, error: Exception):
        """Handle failed call"""
        async with self._lock:
            self.stats.total_calls += 1
            self.stats.failed_calls += 1
            self.stats.last_failure_time = datetime.now()
            self.last_failure_time = datetime.now()
            self.failure_count += 1
            
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                print(f"[CIRCUIT] Circuit OPEN - failure in half-open state: {error}")
            
            elif self.state == CircuitState.CLOSED:
                if self.failure_count >= self.failure_threshold:
                    self.state = CircuitState.OPEN
                    print(f"[CIRCUIT] Circuit OPEN - threshold reached ({self.failure_count} failures)")
    
    async def _execute_fallback(self, fallback: Callable, *args, **kwargs) -> Any:
        """Execute fallback function"""
        try:
            if asyncio.iscoroutinefunction(fallback):
                return await fallback(*args, **kwargs)
            return fallback(*args, **kwargs)
        except Exception as e:
            print(f"[CIRCUIT] Fallback also failed: {e}")
            raise
    
    def get_stats(self) -> CircuitStats:
        """Get circuit statistics"""
        return self.stats
    
    def reset(self):
        """Manually reset circuit"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None


class CircuitOpenError(Exception):
    """Raised when circuit is open"""
    pass


# ==================== FALLBACK CHAIN ====================

@dataclass
class FallbackStrategy:
    """Single fallback strategy"""
    name: str
    handler: Callable
    is_async: bool = True
    timeout: float = 30.0


class FallbackChain:
    """
    Chain of fallback strategies
    Tries strategies in order until one succeeds
    """
    
    def __init__(self):
        self.strategies: List[FallbackStrategy] = []
        self.last_successful_strategy: Optional[str] = None
    
    def add_strategy(
        self, 
        name: str, 
        handler: Callable, 
        timeout: float = 30.0
    ) -> 'FallbackChain':
        """Add fallback strategy"""
        self.strategies.append(FallbackStrategy(
            name=name,
            handler=handler,
            is_async=asyncio.iscoroutinefunction(handler),
            timeout=timeout
        ))
        return self
    
    async def execute(self, *args, **kwargs) -> Any:
        """Execute strategies until one succeeds"""
        errors = []
        
        for strategy in self.strategies:
            try:
                print(f"[FALLBACK] Trying strategy: {strategy.name}")
                
                if strategy.is_async:
                    result = await asyncio.wait_for(
                        strategy.handler(*args, **kwargs),
                        timeout=strategy.timeout
                    )
                else:
                    result = strategy.handler(*args, **kwargs)
                
                self.last_successful_strategy = strategy.name
                print(f"[FALLBACK] Success with: {strategy.name}")
                return result
                
            except asyncio.TimeoutError:
                errors.append((strategy.name, "Timeout"))
                print(f"[FALLBACK] Timeout: {strategy.name}")
                
            except Exception as e:
                errors.append((strategy.name, str(e)))
                print(f"[FALLBACK] Failed {strategy.name}: {e}")
        
        # All strategies failed
        raise FallbackExhaustedError(
            f"All {len(self.strategies)} strategies failed",
            errors=errors
        )


class FallbackExhaustedError(Exception):
    """Raised when all fallback strategies fail"""
    def __init__(self, message: str, errors: List[tuple]):
        super().__init__(message)
        self.errors = errors


# ==================== RESOURCE MANAGER ====================

@dataclass
class ResourceLimits:
    """Resource usage limits"""
    max_gpu_memory_mb: int = 4096
    max_cpu_percent: float = 80.0
    max_memory_mb: int = 8192
    max_concurrent_tasks: int = 10


class ResourceManager:
    """
    Manage system resources for AI processing
    Prevents OOM and resource exhaustion
    """
    
    def __init__(self, limits: Optional[ResourceLimits] = None):
        self.limits = limits or ResourceLimits()
        self._semaphore = asyncio.Semaphore(self.limits.max_concurrent_tasks)
        self._active_tasks = 0
    
    async def acquire(self) -> bool:
        """Acquire resources for a task"""
        await self._semaphore.acquire()
        self._active_tasks += 1
        return True
    
    def release(self):
        """Release resources after task"""
        self._active_tasks -= 1
        self._semaphore.release()
    
    async def with_resources(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with resource management"""
        await self.acquire()
        try:
            return await func(*args, **kwargs)
        finally:
            self.release()
    
    def check_gpu_memory(self) -> int:
        """Check available GPU memory in MB"""
        try:
            import torch
            if torch.cuda.is_available():
                free_memory = torch.cuda.get_device_properties(0).total_memory
                allocated = torch.cuda.memory_allocated(0)
                return (free_memory - allocated) // (1024 * 1024)
        except ImportError:
            pass
        return 0
    
    def check_system_memory(self) -> Dict[str, int]:
        """Check system memory usage"""
        try:
            import psutil
            mem = psutil.virtual_memory()
            return {
                "total_mb": mem.total // (1024 * 1024),
                "available_mb": mem.available // (1024 * 1024),
                "percent_used": mem.percent
            }
        except ImportError:
            return {"total_mb": 0, "available_mb": 0, "percent_used": 0}
    
    def can_proceed(self) -> tuple[bool, str]:
        """Check if resources allow proceeding"""
        # Check concurrent tasks
        if self._active_tasks >= self.limits.max_concurrent_tasks:
            return False, "Max concurrent tasks reached"
        
        # Check GPU memory
        gpu_mem = self.check_gpu_memory()
        if gpu_mem > 0 and gpu_mem < 512:  # Less than 512MB free
            return False, f"Low GPU memory: {gpu_mem}MB"
        
        # Check system memory
        sys_mem = self.check_system_memory()
        if sys_mem["available_mb"] < 1024:  # Less than 1GB free
            return False, f"Low system memory: {sys_mem['available_mb']}MB"
        
        return True, "OK"
    
    @property
    def active_tasks(self) -> int:
        return self._active_tasks


def with_timeout(timeout: float = 30.0):
    """Decorator to add timeout to async functions"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=timeout
            )
        return wrapper
    return decorator


# ==================== PARTIAL RESULT HANDLER ====================

@dataclass
class PartialResult(Generic[T]):
    """Result that may be partial"""
    data: Optional[T] = None
    is_complete: bool = True
    completed_components: List[str] = field(default_factory=list)
    failed_components: List[str] = field(default_factory=list)
    errors: Dict[str, str] = field(default_factory=dict)
    
    @property
    def success_rate(self) -> float:
        total = len(self.completed_components) + len(self.failed_components)
        if total == 0:
            return 1.0
        return len(self.completed_components) / total


class PartialResultHandler:
    """
    Handle partial results when some components fail
    Returns whatever data was successfully obtained
    """
    
    def __init__(self, required_components: Optional[List[str]] = None):
        self.required_components = required_components or []
    
    async def execute_components(
        self,
        components: Dict[str, Callable],
        *args,
        **kwargs
    ) -> PartialResult:
        """
        Execute multiple components, collecting whatever succeeds
        
        Args:
            components: Dict of component_name -> async function
        """
        results = {}
        completed = []
        failed = []
        errors = {}
        
        for name, func in components.items():
            try:
                result = await func(*args, **kwargs)
                results[name] = result
                completed.append(name)
                
            except Exception as e:
                failed.append(name)
                errors[name] = str(e)
                print(f"[PARTIAL] Component '{name}' failed: {e}")
        
        # Check if required components succeeded
        missing_required = [
            comp for comp in self.required_components 
            if comp in failed
        ]
        
        is_complete = len(failed) == 0
        
        return PartialResult(
            data=results,
            is_complete=is_complete,
            completed_components=completed,
            failed_components=failed,
            errors=errors
        )
    
    def aggregate_results(
        self, 
        partial_results: List[PartialResult]
    ) -> PartialResult:
        """Aggregate multiple partial results"""
        all_data = {}
        all_completed = []
        all_failed = []
        all_errors = {}
        
        for result in partial_results:
            if result.data:
                all_data.update(result.data)
            all_completed.extend(result.completed_components)
            all_failed.extend(result.failed_components)
            all_errors.update(result.errors)
        
        return PartialResult(
            data=all_data,
            is_complete=len(all_failed) == 0,
            completed_components=list(set(all_completed)),
            failed_components=list(set(all_failed)),
            errors=all_errors
        )


# ==================== RETRY UTILITIES ====================

def async_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for async retry with exponential backoff
    
    Args:
        max_attempts: Maximum retry attempts
        delay: Initial delay between retries
        backoff: Backoff multiplier
        exceptions: Tuple of exceptions to retry on
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                    
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_attempts - 1:
                        print(f"[RETRY] Attempt {attempt + 1} failed: {e}. Retrying in {current_delay:.1f}s")
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        print(f"[RETRY] All {max_attempts} attempts failed")
            
            raise last_exception
        
        return wrapper
    return decorator


# ==================== GRACEFUL DEGRADATION ====================

class GracefulDegradation:
    """
    System for graceful degradation under load or failures
    """
    
    def __init__(self):
        self.degradation_level = 0  # 0 = full, 1 = reduced, 2 = minimal
        self.feature_status: Dict[str, bool] = {}
    
    def set_degradation_level(self, level: int):
        """Set degradation level (0=full, 1=reduced, 2=minimal)"""
        self.degradation_level = max(0, min(2, level))
        print(f"[DEGRADATION] Level set to {self.degradation_level}")
    
    def is_feature_enabled(self, feature: str) -> bool:
        """Check if feature is enabled at current degradation level"""
        feature_levels = {
            # Feature: max level it's available at
            "vision_analysis": 0,     # Only at full
            "audio_analysis": 0,      # Only at full
            "sentiment_analysis": 1,  # Full and reduced
            "basic_stats": 2,         # Always available
        }
        
        max_level = feature_levels.get(feature, 2)
        return self.degradation_level <= max_level
    
    def get_enabled_features(self) -> List[str]:
        """Get list of currently enabled features"""
        return [
            feature for feature in [
                "vision_analysis", "audio_analysis", 
                "sentiment_analysis", "basic_stats"
            ]
            if self.is_feature_enabled(feature)
        ]
