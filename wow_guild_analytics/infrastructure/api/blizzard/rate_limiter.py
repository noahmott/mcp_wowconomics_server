"""
Blizzard API Rate Limiter

Advanced rate limiting for Blizzard API requests.
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class RateLimitBucket:
    """Rate limit bucket for tracking requests."""
    capacity: int
    refill_rate: float  # tokens per second
    tokens: float = field(init=False)
    last_refill: float = field(init=False)

    def __post_init__(self):
        self.tokens = float(self.capacity)
        self.last_refill = time.time()

    def refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill

        # Add tokens based on refill rate
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now

    async def acquire(self, tokens: int = 1) -> float:
        """
        Acquire tokens from bucket.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            Wait time in seconds (0 if tokens available)
        """
        self.refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return 0.0

        # Calculate wait time
        tokens_needed = tokens - self.tokens
        wait_time = tokens_needed / self.refill_rate

        return wait_time


class BlizzardRateLimiter:
    """
    Advanced rate limiter for Blizzard API.

    Implements:
    - Token bucket algorithm
    - Per-realm rate limiting
    - Global rate limiting
    - Burst handling
    - Request queuing
    """

    # Blizzard API limits (approximate)
    DEFAULT_REQUESTS_PER_SECOND = 100
    DEFAULT_REQUESTS_PER_HOUR = 36000
    BURST_CAPACITY = 200

    def __init__(
        self,
        requests_per_second: int = DEFAULT_REQUESTS_PER_SECOND,
        requests_per_hour: int = DEFAULT_REQUESTS_PER_HOUR,
        burst_capacity: int = BURST_CAPACITY
    ):
        """
        Initialize rate limiter.

        Args:
            requests_per_second: Max requests per second
            requests_per_hour: Max requests per hour
            burst_capacity: Burst capacity
        """
        # Global buckets
        self.second_bucket = RateLimitBucket(
            capacity=burst_capacity,
            refill_rate=requests_per_second
        )

        self.hour_bucket = RateLimitBucket(
            capacity=requests_per_hour,
            refill_rate=requests_per_hour / 3600
        )

        # Per-realm buckets
        self.realm_buckets: Dict[str, RateLimitBucket] = {}
        self.realm_limit = 20  # Per realm per second

        # Request queue
        self.request_queue: deque = deque()
        self.processing = False

        # Statistics
        self.total_requests = 0
        self.total_wait_time = 0.0
        self.request_times: deque = deque(maxlen=1000)

    def _get_realm_bucket(self, realm: str) -> RateLimitBucket:
        """Get or create realm bucket."""
        if realm not in self.realm_buckets:
            self.realm_buckets[realm] = RateLimitBucket(
                capacity=self.realm_limit * 2,  # Allow burst
                refill_rate=self.realm_limit
            )
        return self.realm_buckets[realm]

    async def acquire(
        self,
        realm: Optional[str] = None,
        priority: int = 0
    ) -> None:
        """
        Acquire permission to make request.

        Args:
            realm: Realm for per-realm limiting
            priority: Request priority (higher = more important)
        """
        start_time = time.time()

        # Check all buckets
        wait_times = []

        # Global second bucket
        second_wait = await self.second_bucket.acquire()
        wait_times.append(second_wait)

        # Global hour bucket
        hour_wait = await self.hour_bucket.acquire()
        wait_times.append(hour_wait)

        # Realm bucket if specified
        if realm:
            realm_bucket = self._get_realm_bucket(realm)
            realm_wait = await realm_bucket.acquire()
            wait_times.append(realm_wait)

        # Wait for the longest time
        max_wait = max(wait_times)

        if max_wait > 0:
            logger.debug(f"Rate limit wait: {max_wait:.2f}s")
            await asyncio.sleep(max_wait)

        # Update statistics
        self.total_requests += 1
        wait_time = time.time() - start_time
        self.total_wait_time += wait_time
        self.request_times.append(time.time())

    def get_current_rate(self) -> float:
        """Get current request rate (requests per second)."""
        if len(self.request_times) < 2:
            return 0.0

        # Calculate rate over recent requests
        now = time.time()
        recent_times = [t for t in self.request_times if now - t < 60]

        if len(recent_times) < 2:
            return 0.0

        duration = recent_times[-1] - recent_times[0]
        if duration == 0:
            return 0.0

        return len(recent_times) / duration

    def get_statistics(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        current_rate = self.get_current_rate()
        avg_wait = self.total_wait_time / self.total_requests if self.total_requests > 0 else 0

        return {
            "total_requests": self.total_requests,
            "current_rate": current_rate,
            "average_wait_time": avg_wait,
            "second_bucket_tokens": self.second_bucket.tokens,
            "hour_bucket_tokens": self.hour_bucket.tokens,
            "active_realm_buckets": len(self.realm_buckets)
        }

    async def __aenter__(self):
        """Context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        pass

    def reset(self) -> None:
        """Reset rate limiter state."""
        self.second_bucket = RateLimitBucket(
            capacity=self.second_bucket.capacity,
            refill_rate=self.second_bucket.refill_rate
        )

        self.hour_bucket = RateLimitBucket(
            capacity=self.hour_bucket.capacity,
            refill_rate=self.hour_bucket.refill_rate
        )

        self.realm_buckets.clear()
        self.request_queue.clear()

        logger.info("Rate limiter reset")
