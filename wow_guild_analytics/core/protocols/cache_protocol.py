"""
Cache Protocol Definition

Defines the interface for all cache implementations.
"""

from typing import Protocol, Optional, Any, runtime_checkable


@runtime_checkable
class CacheProtocol(Protocol):
    """Protocol for cache implementations."""

    async def get(
        self,
        key: str,
        namespace: Optional[str] = None
    ) -> Optional[Any]:
        """
        Retrieve a value from cache.

        Args:
            key: Cache key
            namespace: Optional namespace for key isolation

        Returns:
            Cached value or None if not found
        """
        ...

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        namespace: Optional[str] = None
    ) -> bool:
        """
        Store a value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            namespace: Optional namespace for key isolation

        Returns:
            True if successful, False otherwise
        """
        ...

    async def delete(
        self,
        key: str,
        namespace: Optional[str] = None
    ) -> bool:
        """
        Delete a value from cache.

        Args:
            key: Cache key
            namespace: Optional namespace for key isolation

        Returns:
            True if deleted, False otherwise
        """
        ...

    async def exists(
        self,
        key: str,
        namespace: Optional[str] = None
    ) -> bool:
        """
        Check if a key exists in cache.

        Args:
            key: Cache key
            namespace: Optional namespace for key isolation

        Returns:
            True if exists, False otherwise
        """
        ...

    async def clear(
        self,
        namespace: Optional[str] = None
    ) -> int:
        """
        Clear cache entries.

        Args:
            namespace: If provided, only clear this namespace

        Returns:
            Number of entries cleared
        """
        ...
