"""
Rate Limiter

Implements rate limiting for API requests.
"""

import asyncio
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from collections import deque

logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str,
        retry_after: Optional[float] = None
    ):
        self.message = message
        self.retry_after = retry_after
        super().__init__(self.message)


class RateLimiter:
    """
    Token bucket rate limiter for API requests.

    Implements a sliding window algorithm for rate limiting.
    """

    def __init__(
        self,
        max_requests: int = 100,
        time_window: int = 1,
        burst_size: Optional[int] = None
    ):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum requests allowed in time window
            time_window: Time window in seconds
            burst_size: Maximum burst size (defaults to max_requests)
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.burst_size = burst_size or max_requests

        # Use deque for efficient removal of old timestamps
        self.requests: deque = deque()
        self._lock = asyncio.Lock()

        # Track rate limit status
        self._is_limited = False
        self._limit_until: Optional[datetime] = None

    async def acquire(self, weight: int = 1) -> None:
        """
        Acquire permission to make a request.

        Args:
            weight: Weight of the request (default 1)

        Raises:
            RateLimitExceeded: If rate limit is exceeded
        """
        async with self._lock:
            now = time.time()

            # Remove old requests outside the time window
            cutoff = now - self.time_window
            while self.requests and self.requests[0] < cutoff:
                self.requests.popleft()

            # Check if we're currently rate limited
            if self._is_limited and self._limit_until:
                if datetime.now() < self._limit_until:
                    retry_after = (
                        self._limit_until - datetime.now()
                    ).total_seconds()
                    raise RateLimitExceeded(
                        "Rate limit exceeded",
                        retry_after=retry_after
                    )
                else:
                    # Reset rate limit
                    self._is_limited = False
                    self._limit_until = None

            # Check if adding this request would exceed limit
            current_count = len(self.requests)
            if current_count + weight > self.max_requests:
                # Calculate when we can retry
                if self.requests:
                    oldest_request = self.requests[0]
                    retry_after = (
                        oldest_request + self.time_window - now
                    )
                else:
                    retry_after = 0

                self._is_limited = True
                self._limit_until = datetime.now() + timedelta(
                    seconds=retry_after
                )

                raise RateLimitExceeded(
                    f"Rate limit exceeded: {current_count + weight}/"
                    f"{self.max_requests} requests in "
                    f"{self.time_window}s",
                    retry_after=retry_after
                )

            # Add the request timestamp(s)
            for _ in range(weight):
                self.requests.append(now)

    async def wait_if_needed(self, weight: int = 1) -> None:
        """
        Wait if necessary before making a request.

        Args:
            weight: Weight of the request
        """
        while True:
            try:
                await self.acquire(weight)
                break
            except RateLimitExceeded as e:
                if e.retry_after:
                    logger.warning(
                        f"Rate limited. Waiting {e.retry_after:.1f}s"
                    )
                    await asyncio.sleep(e.retry_after)
                else:
                    raise

    def get_status(self) -> Dict[str, any]:
        """
        Get current rate limiter status.

        Returns:
            Status information
        """
        now = time.time()
        cutoff = now - self.time_window

        # Count current requests
        current_requests = sum(
            1 for req in self.requests if req >= cutoff
        )

        return {
            "current_requests": current_requests,
            "max_requests": self.max_requests,
            "time_window": self.time_window,
            "is_limited": self._is_limited,
            "available_requests": max(
                0, self.max_requests - current_requests
            ),
            "reset_time": self._limit_until.isoformat()
            if self._limit_until else None
        }

    def reset(self) -> None:
        """Reset the rate limiter."""
        self.requests.clear()
        self._is_limited = False
        self._limit_until = None


class MultiKeyRateLimiter:
    """Rate limiter that supports multiple keys/endpoints."""

    def __init__(self, default_config: Dict[str, int]):
        """
        Initialize multi-key rate limiter.

        Args:
            default_config: Default rate limit configuration
                           {max_requests, time_window}
        """
        self.default_config = default_config
        self.limiters: Dict[str, RateLimiter] = {}
        self._lock = asyncio.Lock()

    async def acquire(
        self,
        key: str,
        weight: int = 1,
        config: Optional[Dict[str, int]] = None
    ) -> None:
        """
        Acquire permission for a specific key.

        Args:
            key: Rate limit key (e.g., endpoint name)
            weight: Request weight
            config: Optional custom config for this key
        """
        async with self._lock:
            if key not in self.limiters:
                cfg = config or self.default_config
                self.limiters[key] = RateLimiter(**cfg)

        await self.limiters[key].acquire(weight)

    async def wait_if_needed(
        self,
        key: str,
        weight: int = 1,
        config: Optional[Dict[str, int]] = None
    ) -> None:
        """
        Wait if necessary for a specific key.

        Args:
            key: Rate limit key
            weight: Request weight
            config: Optional custom config
        """
        async with self._lock:
            if key not in self.limiters:
                cfg = config or self.default_config
                self.limiters[key] = RateLimiter(**cfg)

        await self.limiters[key].wait_if_needed(weight)
