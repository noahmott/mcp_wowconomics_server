"""
Redis Cache Implementation

Concrete implementation of CacheProtocol using Redis.
"""

import json
import logging
from typing import Optional, Any
from datetime import timedelta

import redis.asyncio as aioredis
from redis.asyncio import Redis

from ...core.protocols import CacheProtocol
from ...core.exceptions import ServiceError

logger = logging.getLogger(__name__)


class RedisCache(CacheProtocol):
    """Redis-based cache implementation."""

    def __init__(self, redis_url: str, decode_responses: bool = True):
        """
        Initialize Redis cache.

        Args:
            redis_url: Redis connection URL
            decode_responses: Whether to decode responses as strings
        """
        self.redis_url = redis_url
        self.decode_responses = decode_responses
        self.redis: Optional[Redis] = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the Redis connection."""
        try:
            self.redis = aioredis.from_url(
                self.redis_url,
                decode_responses=self.decode_responses,
                retry_on_timeout=True,
                health_check_interval=30
            )

            # Test connection
            await self.redis.ping()
            self._initialized = True
            logger.info("Redis cache initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Redis cache: {e}")
            raise ServiceError(
                f"Redis initialization failed: {str(e)}",
                service_name="RedisCache",
                operation="initialize"
            )

    async def shutdown(self) -> None:
        """Shutdown the Redis connection."""
        if self.redis:
            await self.redis.close()
            self._initialized = False
            logger.info("Redis cache shutdown")

    async def health_check(self) -> bool:
        """Check if Redis is healthy."""
        if not self._initialized or not self.redis:
            return False

        try:
            await self.redis.ping()
            return True
        except Exception:
            return False

    async def get(
        self,
        key: str,
        namespace: Optional[str] = None
    ) -> Optional[Any]:
        """Retrieve a value from cache."""
        if not self._initialized:
            return None

        try:
            full_key = self._make_key(key, namespace)
            value = await self.redis.get(full_key)

            if value is None:
                return None

            # Try to deserialize JSON
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value

            return value

        except Exception as e:
            logger.error(f"Error getting from Redis: {e}")
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

        try:
            full_key = self._make_key(key, namespace)

            # Serialize value if needed
            if not isinstance(value, (str, bytes, int, float)):
                value = json.dumps(value, default=str)

            if ttl:
                await self.redis.setex(full_key, ttl, value)
            else:
                await self.redis.set(full_key, value)

            return True

        except Exception as e:
            logger.error(f"Error setting in Redis: {e}")
            return False

    async def delete(
        self,
        key: str,
        namespace: Optional[str] = None
    ) -> bool:
        """Delete a value from cache."""
        if not self._initialized:
            return False

        try:
            full_key = self._make_key(key, namespace)
            result = await self.redis.delete(full_key)
            return result > 0

        except Exception as e:
            logger.error(f"Error deleting from Redis: {e}")
            return False

    async def exists(
        self,
        key: str,
        namespace: Optional[str] = None
    ) -> bool:
        """Check if a key exists in cache."""
        if not self._initialized:
            return False

        try:
            full_key = self._make_key(key, namespace)
            result = await self.redis.exists(full_key)
            return result > 0

        except Exception as e:
            logger.error(f"Error checking existence in Redis: {e}")
            return False

    async def clear(
        self,
        namespace: Optional[str] = None
    ) -> int:
        """Clear cache entries."""
        if not self._initialized:
            return 0

        try:
            if namespace:
                # Clear by namespace pattern
                pattern = f"{namespace}:*"
                keys = []

                # Use scan to avoid blocking
                async for key in self.redis.scan_iter(match=pattern):
                    keys.append(key)

                if keys:
                    result = await self.redis.delete(*keys)
                    return result
                return 0
            else:
                # Clear all (use with caution)
                await self.redis.flushdb()
                return -1  # Indicate full flush

        except Exception as e:
            logger.error(f"Error clearing Redis: {e}")
            return 0

    async def get_ttl(self, key: str, namespace: Optional[str] = None) -> Optional[int]:
        """Get TTL for a key."""
        if not self._initialized:
            return None

        try:
            full_key = self._make_key(key, namespace)
            ttl = await self.redis.ttl(full_key)
            return ttl if ttl > 0 else None

        except Exception as e:
            logger.error(f"Error getting TTL from Redis: {e}")
            return None

    async def set_expire(
        self,
        key: str,
        ttl: int,
        namespace: Optional[str] = None
    ) -> bool:
        """Set expiration for existing key."""
        if not self._initialized:
            return False

        try:
            full_key = self._make_key(key, namespace)
            return await self.redis.expire(full_key, ttl)

        except Exception as e:
            logger.error(f"Error setting expiration in Redis: {e}")
            return False

    async def increment(
        self,
        key: str,
        amount: int = 1,
        namespace: Optional[str] = None
    ) -> Optional[int]:
        """Increment a counter."""
        if not self._initialized:
            return None

        try:
            full_key = self._make_key(key, namespace)
            return await self.redis.incrby(full_key, amount)

        except Exception as e:
            logger.error(f"Error incrementing in Redis: {e}")
            return None

    async def get_stats(self) -> dict:
        """Get cache statistics."""
        if not self._initialized:
            return {"status": "not_initialized"}

        try:
            info = await self.redis.info()

            return {
                "status": "connected",
                "used_memory": info.get("used_memory_human", "N/A"),
                "connected_clients": info.get("connected_clients", 0),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(
                    info.get("keyspace_hits", 0),
                    info.get("keyspace_misses", 0)
                ),
                "db_keys": info.get("db0", {}).get("keys", 0) if "db0" in info else 0
            }

        except Exception as e:
            logger.error(f"Error getting Redis stats: {e}")
            return {"status": "error", "error": str(e)}

    def _make_key(self, key: str, namespace: Optional[str] = None) -> str:
        """Create full key with namespace."""
        if namespace:
            return f"{namespace}:{key}"
        return key

    def _calculate_hit_rate(self, hits: int, misses: int) -> float:
        """Calculate cache hit rate percentage."""
        total = hits + misses
        return (hits / total * 100) if total > 0 else 0.0
