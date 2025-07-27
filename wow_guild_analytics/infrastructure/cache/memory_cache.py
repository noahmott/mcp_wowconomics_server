"""
Memory Cache Implementation

In-memory cache implementation for testing and development.
"""

import json
import logging
import time
from typing import Optional, Any, Dict
from collections import OrderedDict
from datetime import datetime

from ...core.protocols import CacheProtocol

logger = logging.getLogger(__name__)


class MemoryCache(CacheProtocol):
    """In-memory cache implementation."""

    def __init__(self, max_size: int = 1000):
        """
        Initialize memory cache.

        Args:
            max_size: Maximum number of items to store
        """
        self.max_size = max_size
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._initialized = False
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0
        }

    async def initialize(self) -> None:
        """Initialize the cache."""
        self._initialized = True
        logger.info("Memory cache initialized")

    async def shutdown(self) -> None:
        """Shutdown the cache."""
        self._cache.clear()
        self._initialized = False
        logger.info("Memory cache shutdown")

    async def health_check(self) -> bool:
        """Check if cache is healthy."""
        return self._initialized

    async def get(
        self,
        key: str,
        namespace: Optional[str] = None
    ) -> Optional[Any]:
        """Retrieve a value from cache."""
        if not self._initialized:
            return None

        full_key = self._make_key(key, namespace)

        if full_key in self._cache:
            entry = self._cache[full_key]

            # Check expiration
            if entry["expires_at"] and time.time() > entry["expires_at"]:
                # Expired, remove it
                del self._cache[full_key]
                self._stats["misses"] += 1
                return None

            # Move to end (LRU)
            self._cache.move_to_end(full_key)
            self._stats["hits"] += 1

            value = entry["value"]

            # Try to deserialize JSON if it's a string
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value

            return value

        self._stats["misses"] += 1
        return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        namespace: Optional[str] = None
    ) -> bool:
        """Store a value in cache."""
        if not self._initialized:
            return False

        full_key = self._make_key(key, namespace)

        # Serialize value if needed
        if not isinstance(value, (str, bytes, int, float)):
            value = json.dumps(value, default=str)

        expires_at = None
        if ttl:
            expires_at = time.time() + ttl

        self._cache[full_key] = {
            "value": value,
            "expires_at": expires_at,
            "created_at": time.time()
        }

        # Move to end (LRU)
        self._cache.move_to_end(full_key)

        # Evict oldest if over max size
        if len(self._cache) > self.max_size:
            self._cache.popitem(last=False)

        self._stats["sets"] += 1
        return True

    async def delete(
        self,
        key: str,
        namespace: Optional[str] = None
    ) -> bool:
        """Delete a value from cache."""
        if not self._initialized:
            return False

        full_key = self._make_key(key, namespace)

        if full_key in self._cache:
            del self._cache[full_key]
            self._stats["deletes"] += 1
            return True

        return False

    async def exists(
        self,
        key: str,
        namespace: Optional[str] = None
    ) -> bool:
        """Check if a key exists in cache."""
        if not self._initialized:
            return False

        full_key = self._make_key(key, namespace)

        if full_key in self._cache:
            entry = self._cache[full_key]

            # Check expiration
            if entry["expires_at"] and time.time() > entry["expires_at"]:
                # Expired, remove it
                del self._cache[full_key]
                return False

            return True

        return False

    async def clear(
        self,
        namespace: Optional[str] = None
    ) -> int:
        """Clear cache entries."""
        if not self._initialized:
            return 0

        if namespace:
            # Clear by namespace
            prefix = f"{namespace}:"
            keys_to_delete = [
                k for k in self._cache.keys()
                if k.startswith(prefix)
            ]

            for key in keys_to_delete:
                del self._cache[key]

            return len(keys_to_delete)
        else:
            # Clear all
            count = len(self._cache)
            self._cache.clear()
            return count

    async def get_ttl(
        self,
        key: str,
        namespace: Optional[str] = None
    ) -> Optional[int]:
        """Get TTL for a key."""
        if not self._initialized:
            return None

        full_key = self._make_key(key, namespace)

        if full_key in self._cache:
            entry = self._cache[full_key]

            if entry["expires_at"]:
                ttl = int(entry["expires_at"] - time.time())
                return ttl if ttl > 0 else None

            return None  # No expiration

        return None

    async def get_stats(self) -> dict:
        """Get cache statistics."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = (
            (self._stats["hits"] / total * 100) if total > 0 else 0.0
        )

        # Clean up expired entries
        expired_count = 0
        current_time = time.time()
        keys_to_delete = []

        for key, entry in self._cache.items():
            if entry["expires_at"] and current_time > entry["expires_at"]:
                keys_to_delete.append(key)

        for key in keys_to_delete:
            del self._cache[key]
            expired_count += 1

        return {
            "status": "active" if self._initialized else "inactive",
            "type": "memory",
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "sets": self._stats["sets"],
            "deletes": self._stats["deletes"],
            "hit_rate": hit_rate,
            "expired_cleaned": expired_count
        }

    def _make_key(self, key: str, namespace: Optional[str] = None) -> str:
        """Create full key with namespace."""
        if namespace:
            return f"{namespace}:{key}"
        return key
