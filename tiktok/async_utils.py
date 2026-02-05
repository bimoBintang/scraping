"""
Async Utilities for TikTok Scraper
Timeout wrappers, retry logic, and async helpers
"""

import asyncio
from typing import TypeVar, Callable, Optional, Any
from functools import wraps

T = TypeVar('T')

# ==================== TIMEOUT WRAPPER ====================

async def with_timeout(
    coro,
    timeout: float = 10.0,
    default: Any = None,
    error_msg: str = "Operation timed out"
) -> Any:
    """
    Wrap coroutine with timeout
    
    Args:
        coro: Coroutine to execute
        timeout: Timeout in seconds
        default: Value to return on timeout
        error_msg: Message to print on timeout
    
    Returns:
        Result of coroutine or default value
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        print(f"[!] {error_msg}")
        return default
    except Exception as e:
        print(f"[!] Error: {e}")
        return default


# ==================== RETRY DECORATOR ====================

def async_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for retrying async functions with exponential backoff
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries
        backoff: Multiplier for delay after each retry
        exceptions: Tuple of exceptions to catch
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        print(f"[~] Retry {attempt + 1}/{max_attempts} after {current_delay}s...")
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
            
            raise last_exception
        
        return wrapper
    return decorator


# ==================== SAFE EVALUATE ====================

async def safe_evaluate(
    page,
    script: str,
    timeout: float = 10.0,
    default: Any = None
) -> Any:
    """
    Safely evaluate JavaScript with timeout and error handling
    
    Args:
        page: Playwright page object
        script: JavaScript to evaluate
        timeout: Timeout in seconds
        default: Default value on failure
    
    Returns:
        Evaluation result or default
    """
    try:
        return await asyncio.wait_for(
            page.evaluate(script),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        print("[!] Script evaluation timed out")
        return default
    except Exception as e:
        print(f"[!] Script evaluation error: {e}")
        return default


# ==================== BATCH EXECUTOR ====================

async def execute_batch(
    tasks: list,
    max_concurrent: int = 5,
    delay_between: float = 0.5
) -> list:
    """
    Execute tasks in batches with concurrency limit
    
    Args:
        tasks: List of coroutines
        max_concurrent: Maximum concurrent tasks
        delay_between: Delay between batches
    
    Returns:
        List of results
    """
    results = []
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def limited_task(task):
        async with semaphore:
            result = await task
            await asyncio.sleep(delay_between)
            return result
    
    results = await asyncio.gather(
        *[limited_task(task) for task in tasks],
        return_exceptions=True
    )
    
    return results


# ==================== GRACEFUL TASK MANAGER ====================

class TaskManager:
    """Manage async tasks with graceful shutdown"""
    
    def __init__(self):
        self.tasks: list = []
        self.running = False
    
    def add_task(self, coro) -> asyncio.Task:
        """Add and track a task"""
        task = asyncio.create_task(coro)
        self.tasks.append(task)
        return task
    
    async def cancel_all(self, timeout: float = 5.0):
        """Cancel all tasks gracefully"""
        for task in self.tasks:
            if not task.done():
                task.cancel()
        
        if self.tasks:
            await asyncio.wait(self.tasks, timeout=timeout)
        
        self.tasks = []
    
    async def wait_all(self, timeout: Optional[float] = None):
        """Wait for all tasks to complete"""
        if self.tasks:
            await asyncio.wait(self.tasks, timeout=timeout)


# ==================== INTERVAL RUNNER ====================

class IntervalRunner:
    """Run a function at regular intervals"""
    
    def __init__(self, interval: float = 5.0):
        self.interval = interval
        self.running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self, func: Callable):
        """Start running function at intervals"""
        self.running = True
        
        async def loop():
            while self.running:
                try:
                    await func()
                except Exception as e:
                    print(f"[!] Interval error: {e}")
                await asyncio.sleep(self.interval)
        
        self._task = asyncio.create_task(loop())
    
    async def stop(self):
        """Stop the interval runner"""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
