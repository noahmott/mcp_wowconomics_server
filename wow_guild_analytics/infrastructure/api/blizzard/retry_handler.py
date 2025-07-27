"""
Blizzard API Retry Handler

Handles retries with exponential backoff for Blizzard API.
"""

import asyncio
import logging
import random
from typing import TypeVar, Callable, Optional, Type, Tuple
from functools import wraps

import httpx

logger = logging.getLogger(__name__)

T = TypeVar('T')


class BlizzardAPIError(Exception):
    """Base exception for Blizzard API errors."""
    pass


class RateLimitError(BlizzardAPIError):
    """Rate limit exceeded error."""
    def __init__(self, retry_after: Optional[int] = None):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after: {retry_after}s")


class MaintenanceError(BlizzardAPIError):
    """API maintenance error."""
    pass


class RetryHandler:
    """
    Retry handler for Blizzard API requests.

    Implements exponential backoff with jitter.
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        """
        Initialize retry handler.

        Args:
            max_retries: Maximum number of retries
            base_delay: Base delay between retries
            max_delay: Maximum delay between retries
            exponential_base: Base for exponential backoff
            jitter: Whether to add jitter to delays
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for retry attempt.

        Args:
            attempt: Retry attempt number (0-based)

        Returns:
            Delay in seconds
        """
        # Exponential backoff
        delay = min(
            self.base_delay * (self.exponential_base ** attempt),
            self.max_delay
        )

        # Add jitter
        if self.jitter:
            delay = delay * (0.5 + random.random() * 0.5)

        return delay

    def should_retry(
        self,
        exception: Exception,
        attempt: int
    ) -> Tuple[bool, Optional[float]]:
        """
        Determine if request should be retried.

        Args:
            exception: Exception that occurred
            attempt: Current attempt number

        Returns:
            Tuple of (should_retry, delay_override)
        """
        if attempt >= self.max_retries:
            return False, None

        # Rate limit errors
        if isinstance(exception, RateLimitError):
            # Use retry_after if available
            if exception.retry_after:
                return True, float(exception.retry_after)
            return True, None

        # HTTP errors
        if isinstance(exception, httpx.HTTPStatusError):
            status_code = exception.response.status_code

            # Rate limit
            if status_code == 429:
                retry_after = exception.response.headers.get('Retry-After')
                if retry_after:
                    return True, float(retry_after)
                return True, None

            # Server errors (5xx)
            if 500 <= status_code < 600:
                return True, None

            # Maintenance (503)
            if status_code == 503:
                return True, None

            # Request timeout (408)
            if status_code == 408:
                return True, None

        # Network errors
        if isinstance(exception, (
            httpx.NetworkError,
            httpx.TimeoutException,
            asyncio.TimeoutError
        )):
            return True, None

        # Don't retry other errors
        return False, None

    async def execute_with_retry(
        self,
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> T:
        """
        Execute function with retry logic.

        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            Last exception if all retries failed
        """
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)

            except Exception as e:
                last_exception = e

                # Check if we should retry
                should_retry, delay_override = self.should_retry(e, attempt)

                if not should_retry:
                    raise

                # Calculate delay
                if delay_override is not None:
                    delay = delay_override
                else:
                    delay = self.calculate_delay(attempt)

                logger.warning(
                    f"Request failed (attempt {attempt + 1}/{self.max_retries + 1}): "
                    f"{type(e).__name__}: {e}. Retrying in {delay:.2f}s..."
                )

                # Wait before retry
                await asyncio.sleep(delay)

        # All retries failed
        raise last_exception


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Decorator for adding retry logic to async functions.

    Args:
        max_retries: Maximum number of retries
        base_delay: Base delay between retries
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff
        jitter: Whether to add jitter
        exceptions: Exceptions to catch
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            handler = RetryHandler(
                max_retries=max_retries,
                base_delay=base_delay,
                max_delay=max_delay,
                exponential_base=exponential_base,
                jitter=jitter
            )

            return await handler.execute_with_retry(func, *args, **kwargs)

        return wrapper

    return decorator
