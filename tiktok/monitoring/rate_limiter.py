"""
Rate Limiter for TikTok Monitoring
Token Bucket algorithm for controlling request rates
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting"""
    requests_per_second: float = 1.0
    burst_size: int = 5
    cooldown_multiplier: float = 2.0
    max_cooldown_seconds: float = 300.0


class TokenBucket:
    """
    Token Bucket Rate Limiter
    
    Algorithm:
    - Bucket has maximum capacity (burst_size)
    - Tokens are added at a constant rate (rate)
    - Each request consumes one token
    - If no tokens available, request must wait
    
    Advantages:
    - Allows bursting up to bucket capacity
    - Smooths out request rate over time
    - Simple and efficient
    """
    
    def __init__(
        self,
        rate: float = 1.0,
        capacity: int = 5,
        initial_tokens: Optional[int] = None
    ):
        """
        Args:
            rate: Tokens per second (request rate limit)
            capacity: Maximum tokens (burst capacity)
            initial_tokens: Starting tokens (defaults to capacity)
        """
        self.rate = rate
        self.capacity = capacity
        self._tokens = initial_tokens if initial_tokens is not None else capacity
        self._last_update = time.monotonic()
        self._lock = asyncio.Lock()
        
        # Statistics
        self._total_requests = 0
        self._throttled_requests = 0
        self._total_wait_time = 0.0
    
    def _refill(self) -> None:
        """Refill tokens based on elapsed time"""
        now = time.monotonic()
        elapsed = now - self._last_update
        
        # Add tokens based on time passed
        tokens_to_add = elapsed * self.rate
        self._tokens = min(self.capacity, self._tokens + tokens_to_add)
        self._last_update = now
    
    def try_acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens without waiting
        
        Args:
            tokens: Number of tokens to acquire
            
        Returns:
            True if tokens acquired, False if not enough tokens
        """
        self._refill()
        self._total_requests += 1
        
        if self._tokens >= tokens:
            self._tokens -= tokens
            return True
        
        self._throttled_requests += 1
        return False
    
    def wait_time(self, tokens: int = 1) -> float:
        """
        Calculate wait time for tokens to be available
        
        Args:
            tokens: Number of tokens needed
            
        Returns:
            Seconds to wait (0 if tokens available now)
        """
        self._refill()
        
        if self._tokens >= tokens:
            return 0.0
        
        tokens_needed = tokens - self._tokens
        return tokens_needed / self.rate
    
    async def acquire(self, tokens: int = 1) -> float:
        """
        Acquire tokens, waiting if necessary
        
        Args:
            tokens: Number of tokens to acquire
            
        Returns:
            Time waited in seconds
        """
        async with self._lock:
            self._total_requests += 1
            wait_time = self.wait_time(tokens)
            
            if wait_time > 0:
                self._throttled_requests += 1
                self._total_wait_time += wait_time
                await asyncio.sleep(wait_time)
                self._refill()
            
            self._tokens -= tokens
            return wait_time
    
    @property
    def available_tokens(self) -> float:
        """Get current available tokens"""
        self._refill()
        return self._tokens
    
    @property
    def stats(self) -> Dict:
        """Get rate limiter statistics"""
        return {
            "total_requests": self._total_requests,
            "throttled_requests": self._throttled_requests,
            "throttle_rate": self._throttled_requests / self._total_requests if self._total_requests > 0 else 0,
            "total_wait_time": self._total_wait_time,
            "avg_wait_time": self._total_wait_time / self._throttled_requests if self._throttled_requests > 0 else 0,
            "current_tokens": self.available_tokens,
            "capacity": self.capacity,
            "rate": self.rate,
        }
    
    def reset(self) -> None:
        """Reset bucket to full capacity"""
        self._tokens = self.capacity
        self._last_update = time.monotonic()


class AdaptiveRateLimiter:
    """
    Adaptive rate limiter that adjusts based on response patterns
    
    - Slows down on errors/rate limit responses
    - Speeds up when things go smoothly
    """
    
    def __init__(
        self,
        base_rate: float = 1.0,
        min_rate: float = 0.1,
        max_rate: float = 5.0,
        capacity: int = 5,
        backoff_factor: float = 0.5,
        recovery_factor: float = 1.1,
        recovery_threshold: int = 10
    ):
        """
        Args:
            base_rate: Starting rate (requests/second)
            min_rate: Minimum rate when backing off
            max_rate: Maximum rate when speeding up
            capacity: Burst capacity
            backoff_factor: Multiply rate by this on error
            recovery_factor: Multiply rate by this on success
            recovery_threshold: Consecutive successes before speeding up
        """
        self.base_rate = base_rate
        self.min_rate = min_rate
        self.max_rate = max_rate
        self.backoff_factor = backoff_factor
        self.recovery_factor = recovery_factor
        self.recovery_threshold = recovery_threshold
        
        self._current_rate = base_rate
        self._bucket = TokenBucket(rate=base_rate, capacity=capacity)
        self._consecutive_success = 0
        self._consecutive_errors = 0
        self._in_cooldown = False
        self._cooldown_until: Optional[datetime] = None
    
    def record_success(self) -> None:
        """Record successful request"""
        self._consecutive_success += 1
        self._consecutive_errors = 0
        
        # Speed up after consecutive successes
        if self._consecutive_success >= self.recovery_threshold:
            self._adjust_rate(self.recovery_factor)
            self._consecutive_success = 0
    
    def record_error(self, is_rate_limit: bool = False) -> None:
        """
        Record failed request
        
        Args:
            is_rate_limit: True if error was due to rate limiting
        """
        self._consecutive_errors += 1
        self._consecutive_success = 0
        
        # Back off on any error
        factor = self.backoff_factor
        if is_rate_limit:
            # More aggressive backoff for rate limits
            factor = self.backoff_factor ** 2
        
        self._adjust_rate(factor)
    
    def _adjust_rate(self, factor: float) -> None:
        """Adjust rate by factor"""
        new_rate = self._current_rate * factor
        self._current_rate = max(self.min_rate, min(self.max_rate, new_rate))
        self._bucket.rate = self._current_rate
    
    async def acquire(self) -> float:
        """Acquire permission to make request"""
        return await self._bucket.acquire()
    
    def try_acquire(self) -> bool:
        """Try to acquire without waiting"""
        return self._bucket.try_acquire()
    
    @property
    def current_rate(self) -> float:
        """Current rate limit"""
        return self._current_rate
    
    @property
    def stats(self) -> Dict:
        """Get statistics"""
        bucket_stats = self._bucket.stats
        return {
            **bucket_stats,
            "current_rate": self._current_rate,
            "base_rate": self.base_rate,
            "consecutive_success": self._consecutive_success,
            "consecutive_errors": self._consecutive_errors,
        }
    
    def reset(self) -> None:
        """Reset to base rate"""
        self._current_rate = self.base_rate
        self._bucket = TokenBucket(rate=self.base_rate, capacity=self._bucket.capacity)
        self._consecutive_success = 0
        self._consecutive_errors = 0


class RateLimiter:
    """
    Multi-endpoint rate limiter
    Manages rate limits for different API endpoints
    """
    
    def __init__(self, default_config: Optional[RateLimitConfig] = None):
        self.default_config = default_config or RateLimitConfig()
        self._limiters: Dict[str, AdaptiveRateLimiter] = {}
        self._global_limiter = AdaptiveRateLimiter(
            base_rate=self.default_config.requests_per_second,
            capacity=self.default_config.burst_size
        )
    
    def get_limiter(self, endpoint: str) -> AdaptiveRateLimiter:
        """Get or create limiter for endpoint"""
        if endpoint not in self._limiters:
            self._limiters[endpoint] = AdaptiveRateLimiter(
                base_rate=self.default_config.requests_per_second,
                capacity=self.default_config.burst_size
            )
        return self._limiters[endpoint]
    
    async def acquire(self, endpoint: str = "default") -> float:
        """Acquire rate limit token for endpoint"""
        limiter = self.get_limiter(endpoint)
        
        # Check both endpoint and global limits
        endpoint_wait = await limiter.acquire()
        global_wait = await self._global_limiter.acquire()
        
        return max(endpoint_wait, global_wait)
    
    def record_success(self, endpoint: str = "default") -> None:
        """Record successful request"""
        self.get_limiter(endpoint).record_success()
        self._global_limiter.record_success()
    
    def record_error(self, endpoint: str = "default", is_rate_limit: bool = False) -> None:
        """Record failed request"""
        self.get_limiter(endpoint).record_error(is_rate_limit)
        self._global_limiter.record_error(is_rate_limit)
    
    def get_stats(self) -> Dict:
        """Get all rate limiter stats"""
        return {
            "global": self._global_limiter.stats,
            "endpoints": {
                endpoint: limiter.stats
                for endpoint, limiter in self._limiters.items()
            }
        }
    
    def reset_all(self) -> None:
        """Reset all rate limiters"""
        self._global_limiter.reset()
        for limiter in self._limiters.values():
            limiter.reset()
