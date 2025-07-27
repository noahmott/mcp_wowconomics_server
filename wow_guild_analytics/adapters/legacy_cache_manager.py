"""
Legacy Cache Manager Adapter

Maintains backward compatibility with existing CacheManager usage.
"""

import json
import logging
from typing import Any, Optional, Dict
from functools import wraps
import asyncio

logger = logging.getLogger(__name__)


class LegacyCacheManagerAdapter:
    """
    Adapter to maintain compatibility with existing CacheManager.

    This adapter wraps the new cache protocol implementation and
    provides the same interface as the original CacheManager.
    """

    def __init__(self):
        """Initialize the adapter."""
        # Import new components
        from ..core.config import ConfigLoader
        from ..core.protocols import CacheProtocol

        # Load configuration
        self.config = ConfigLoader.load_config()

        # Cache implementation will be injected
        self.cache: Optional[CacheProtocol] = None
        self.connected = False

        # Maintain compatibility attributes
        self.redis_url = self.config.cache.redis_url
        self.redis = None  # Will be set if using Redis implementation

        # Cache prefixes from config with defaults
        self.prefixes = {
            "guild": "guild:",
            "member": "member:",
            "raid": "raid:",
            "chart": "chart:",
            "api": "api:",
            "auction": "auction:",
            "token": "token:",
        }
        self.default_ttl = getattr(self.config.cache, 'default_ttl', 300)

    async def connect(self):
        """Initialize cache connection."""
        try:
            # Import and create Redis cache implementation
            from ..infrastructure.cache import RedisCache

            self.cache = RedisCache(self.redis_url)
            await self.cache.initialize()

            self.connected = True
            self.redis = getattr(self.cache, 'redis', None)

            logger.info("Successfully connected to cache")

        except Exception as e:
            logger.error(f"Failed to connect to cache: {str(e)}")
            self.connected = False
            self.cache = None

    async def disconnect(self):
        """Close cache connection."""
        if self.cache:
            await self.cache.shutdown()
            self.connected = False
            logger.info("Disconnected from cache")

    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key from arguments."""
        import hashlib

        # Create a consistent key from arguments
        key_data = json.dumps(
            [args, sorted(kwargs.items())],
            sort_keys=True,
            default=str
        )
        key_hash = hashlib.md5(key_data.encode()).hexdigest()
        return f"{self.prefixes.get(prefix, 'misc:')}{key_hash}"

    async def get(self, prefix: str, *args, **kwargs) -> Optional[Any]:
        """Get value from cache."""
        if not self.connected or not self.cache:
            return None

        try:
            key = self._generate_key(prefix, *args, **kwargs)
            cached_data = await self.cache.get(key)

            if cached_data:
                logger.debug(f"Cache hit for key: {key}")
                if isinstance(cached_data, str):
                    return json.loads(cached_data)
                return cached_data

            logger.debug(f"Cache miss for key: {key}")
            return None

        except Exception as e:
            logger.error(f"Error getting from cache: {str(e)}")
            return None

    async def set(
        self,
        prefix: str,
        value: Any,
        ttl: Optional[int] = None,
        *args,
        **kwargs
    ) -> bool:
        """Set value in cache."""
        if not self.connected or not self.cache:
            return False

        try:
            key = self._generate_key(prefix, *args, **kwargs)

            # Serialize value
            if not isinstance(value, str):
                serialized_value = json.dumps(value, default=str)
            else:
                serialized_value = value

            # Use default TTL if not specified
            if ttl is None:
                ttl = self.default_ttl.get(prefix, 3600)

            await self.cache.set(key, serialized_value, ttl=ttl)
            logger.debug(f"Cache set for key: {key} (TTL: {ttl}s)")
            return True

        except Exception as e:
            logger.error(f"Error setting cache: {str(e)}")
            return False

    async def delete(self, prefix: str, *args, **kwargs) -> bool:
        """Delete value from cache."""
        if not self.connected or not self.cache:
            return False

        try:
            key = self._generate_key(prefix, *args, **kwargs)
            result = await self.cache.delete(key)
            logger.debug(f"Cache delete for key: {key}")
            return result

        except Exception as e:
            logger.error(f"Error deleting from cache: {str(e)}")
            return False

    async def exists(self, prefix: str, *args, **kwargs) -> bool:
        """Check if key exists in cache."""
        if not self.connected or not self.cache:
            return False

        try:
            key = self._generate_key(prefix, *args, **kwargs)
            return await self.cache.exists(key)

        except Exception as e:
            logger.error(f"Error checking cache existence: {str(e)}")
            return False

    async def flush_prefix(self, prefix: str) -> int:
        """Delete all keys with given prefix."""
        if not self.connected or not self.cache:
            return 0

        try:
            namespace = self.prefixes.get(prefix, 'misc:')
            count = await self.cache.clear(namespace=namespace)
            logger.info(f"Flushed {count} keys with prefix: {prefix}")
            return count

        except Exception as e:
            logger.error(f"Error flushing cache prefix: {str(e)}")
            return 0

    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self.connected:
            return {"error": "Not connected to cache"}

        return {
            "connected": self.connected,
            "backend": type(self.cache).__name__ if self.cache else "None"
        }


# Global cache manager instance for compatibility
cache_manager = LegacyCacheManagerAdapter()


def cached(
    prefix: str,
    ttl: Optional[int] = None,
    key_args: Optional[list] = None,
    skip_cache: bool = False
):
    """
    Decorator for caching function results.

    Maintains compatibility with existing cached decorator.
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Skip cache if requested or not connected
            if skip_cache or not cache_manager.connected:
                return await func(*args, **kwargs)

            try:
                # Filter arguments for cache key if specified
                if key_args:
                    filtered_kwargs = {
                        k: v for k, v in kwargs.items()
                        if k in key_args
                    }
                    cache_args = args if not key_args else ()
                else:
                    filtered_kwargs = kwargs
                    cache_args = args

                # Try to get from cache
                cached_result = await cache_manager.get(
                    prefix, *cache_args, **filtered_kwargs
                )
                if cached_result is not None:
                    logger.debug(f"Cache hit for function: {func.__name__}")
                    return cached_result

                # Execute function
                logger.debug(f"Cache miss for function: {func.__name__}")
                result = await func(*args, **kwargs)

                # Cache the result
                if result is not None:
                    await cache_manager.set(
                        prefix, result, ttl, *cache_args, **filtered_kwargs
                    )

                return result

            except Exception as e:
                logger.error(
                    f"Error in cached wrapper for {func.__name__}: {str(e)}"
                )
                return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, just execute normally
            logger.warning(
                f"Sync function {func.__name__} called with cache "
                f"decorator - caching skipped"
            )
            return func(*args, **kwargs)

        return (
            async_wrapper if asyncio.iscoroutinefunction(func)
            else sync_wrapper
        )

    return decorator
