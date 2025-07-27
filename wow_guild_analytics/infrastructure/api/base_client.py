"""
Base API Client

Base implementation for API clients with common functionality.
"""

import logging
import asyncio
from typing import Optional, Dict, Any, TypeVar, Generic, AsyncIterator
from abc import ABC, abstractmethod

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

from ...core.protocols import APIClientProtocol
from ...core.config import Settings

logger = logging.getLogger(__name__)

T = TypeVar('T')


class BaseAPIClient(APIClientProtocol, ABC):
    """Base API client with common functionality."""

    def __init__(
        self,
        base_url: str,
        timeout: int = 30,
        max_retries: int = 3,
        rate_limit: Optional[int] = None
    ):
        """
        Initialize base API client.

        Args:
            base_url: Base URL for API
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries
            rate_limit: Rate limit (requests per second)
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate_limit = rate_limit

        self._client: Optional[httpx.AsyncClient] = None
        self._rate_limiter: Optional[asyncio.Semaphore] = None

        if rate_limit:
            self._rate_limiter = asyncio.Semaphore(rate_limit)

    async def __aenter__(self):
        """Enter async context."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        await self.close()

    async def initialize(self) -> None:
        """Initialize HTTP client."""
        if not self._client:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
                headers=self._get_default_headers()
            )
            logger.info(f"API client initialized for {self.base_url}")

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("API client closed")

    @abstractmethod
    def _get_default_headers(self) -> Dict[str, str]:
        """Get default headers for requests."""
        pass

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError))
    )
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> httpx.Response:
        """
        Make HTTP request with retries.

        Args:
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Additional request arguments

        Returns:
            HTTP response
        """
        if not self._client:
            await self.initialize()

        # Apply rate limiting
        if self._rate_limiter:
            async with self._rate_limiter:
                return await self._execute_request(method, endpoint, **kwargs)
        else:
            return await self._execute_request(method, endpoint, **kwargs)

    async def _execute_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> httpx.Response:
        """Execute the actual HTTP request."""
        url = endpoint if endpoint.startswith('http') else f"{self.base_url}/{endpoint.lstrip('/')}"

        logger.debug(f"{method} {url}")

        response = await self._client.request(
            method=method,
            url=url,
            **kwargs
        )

        response.raise_for_status()
        return response

    async def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Make GET request."""
        response = await self._make_request(
            "GET",
            endpoint,
            params=params,
            headers=headers
        )
        return response.json()

    async def post(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Make POST request."""
        response = await self._make_request(
            "POST",
            endpoint,
            data=data,
            json=json,
            headers=headers
        )
        return response.json()

    async def put(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Make PUT request."""
        response = await self._make_request(
            "PUT",
            endpoint,
            data=data,
            json=json,
            headers=headers
        )
        return response.json()

    async def delete(
        self,
        endpoint: str,
        headers: Optional[Dict[str, str]] = None
    ) -> bool:
        """Make DELETE request."""
        response = await self._make_request(
            "DELETE",
            endpoint,
            headers=headers
        )
        return response.status_code in (200, 204)

    async def health_check(self) -> bool:
        """Check if API is accessible."""
        try:
            # Try to access base URL
            response = await self._make_request("GET", "/")
            return response.status_code < 500
        except Exception:
            return False


class PaginatedAPIClient(BaseAPIClient):
    """API client with pagination support."""

    async def get_paginated(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        page_param: str = "page",
        per_page_param: str = "per_page",
        per_page: int = 100,
        max_pages: Optional[int] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Get paginated results.

        Args:
            endpoint: API endpoint
            params: Query parameters
            page_param: Page parameter name
            per_page_param: Per page parameter name
            per_page: Items per page
            max_pages: Maximum pages to fetch

        Yields:
            Page results
        """
        params = params or {}
        params[per_page_param] = per_page

        page = 1
        while True:
            if max_pages and page > max_pages:
                break

            params[page_param] = page

            try:
                result = await self.get(endpoint, params=params)

                # Handle different pagination formats
                if isinstance(result, dict):
                    # Check for common pagination keys
                    if 'data' in result:
                        items = result['data']
                    elif 'items' in result:
                        items = result['items']
                    elif 'results' in result:
                        items = result['results']
                    else:
                        items = [result]
                else:
                    items = result

                if not items:
                    break

                for item in items:
                    yield item

                # Check if more pages
                if isinstance(result, dict):
                    if 'has_next' in result and not result['has_next']:
                        break
                    if 'next' in result and not result['next']:
                        break

                page += 1

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    # No more pages
                    break
                raise
