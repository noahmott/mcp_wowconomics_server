"""
Redis caching utilities
"""

import os
import json
import hashlib
import asyncio
import logging
from typing import Any, Optional, Dict, Union
from functools import wraps
from datetime import datetime, timedelta

import redis.asyncio as aioredis
from redis.asyncio import Redis

from .errors import WoWGuildError, ErrorType

logger = logging.getLogger(__name__)


class CacheManager:
    """Redis cache manager for WoW Guild application"""
    
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis: Optional[Redis] = None
        self.connected = False
        
        # Cache prefixes
        self.prefixes = {
            "guild": "guild:",
            "member": "member:",
            "raid": "raid:",
            "chart": "chart:",
            "api": "api:"
        }
        
        # Default TTL values (in seconds)
        self.default_ttl = {
            "guild": 1800,  # 30 minutes
            "member": 3600,  # 1 hour
            "raid": 3600,   # 1 hour
            "chart": 7200,  # 2 hours
            "api": 600      # 10 minutes
        }
    
    async def connect(self):
        """Initialize Redis connection"""
        try:
            self.redis = aioredis.from_url(
                self.redis_url,
                decode_responses=True,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Test connection
            await self.redis.ping()
            self.connected = True
            logger.info("Successfully connected to Redis")
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            self.connected = False
            self.redis = None
    
    async def disconnect(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()
            self.connected = False
            logger.info("Disconnected from Redis")
    
    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key from arguments"""
        # Create a consistent key from arguments
        key_data = json.dumps([args, sorted(kwargs.items())], sort_keys=True, default=str)
        key_hash = hashlib.md5(key_data.encode()).hexdigest()
        return f"{self.prefixes.get(prefix, 'misc:')}{key_hash}"
    
    async def get(self, prefix: str, *args, **kwargs) -> Optional[Any]:
        """Get value from cache"""
        if not self.connected or not self.redis:
            return None
        
        try:
            key = self._generate_key(prefix, *args, **kwargs)
            cached_data = await self.redis.get(key)
            
            if cached_data:
                logger.debug(f"Cache hit for key: {key}")
                return json.loads(cached_data)
            
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
        """Set value in cache"""
        if not self.connected or not self.redis:
            return False
        
        try:
            key = self._generate_key(prefix, *args, **kwargs)
            serialized_value = json.dumps(value, default=str)
            
            # Use default TTL if not specified
            if ttl is None:
                ttl = self.default_ttl.get(prefix, 3600)
            
            await self.redis.setex(key, ttl, serialized_value)
            logger.debug(f"Cache set for key: {key} (TTL: {ttl}s)")
            return True
            
        except Exception as e:
            logger.error(f"Error setting cache: {str(e)}")
            return False
    
    async def delete(self, prefix: str, *args, **kwargs) -> bool:
        """Delete value from cache"""
        if not self.connected or not self.redis:
            return False
        
        try:
            key = self._generate_key(prefix, *args, **kwargs)
            result = await self.redis.delete(key)
            logger.debug(f"Cache delete for key: {key}")
            return result > 0
            
        except Exception as e:
            logger.error(f"Error deleting from cache: {str(e)}")
            return False
    
    async def exists(self, prefix: str, *args, **kwargs) -> bool:
        """Check if key exists in cache"""
        if not self.connected or not self.redis:
            return False
        
        try:
            key = self._generate_key(prefix, *args, **kwargs)
            result = await self.redis.exists(key)
            return result > 0
            
        except Exception as e:
            logger.error(f"Error checking cache existence: {str(e)}")
            return False
    
    async def get_ttl(self, prefix: str, *args, **kwargs) -> Optional[int]:
        """Get TTL for a cached key"""
        if not self.connected or not self.redis:
            return None
        
        try:
            key = self._generate_key(prefix, *args, **kwargs)
            ttl = await self.redis.ttl(key)
            return ttl if ttl > 0 else None
            
        except Exception as e:
            logger.error(f"Error getting TTL: {str(e)}")
            return None
    
    async def flush_prefix(self, prefix: str) -> int:
        """Delete all keys with given prefix"""
        if not self.connected or not self.redis:
            return 0
        
        try:
            pattern = f"{self.prefixes.get(prefix, 'misc:')}*"
            keys = await self.redis.keys(pattern)
            
            if keys:
                deleted = await self.redis.delete(*keys)
                logger.info(f"Flushed {deleted} keys with prefix: {prefix}")
                return deleted
            
            return 0
            
        except Exception as e:
            logger.error(f"Error flushing cache prefix: {str(e)}")
            return 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if not self.connected or not self.redis:
            return {"error": "Not connected to Redis"}
        
        try:
            info = await self.redis.info()
            
            return {
                "connected": self.connected,
                "keys": info.get("db0", {}).get("keys", 0),
                "memory_used": info.get("used_memory_human", "N/A"),
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(
                    info.get("keyspace_hits", 0),
                    info.get("keyspace_misses", 0)
                )
            }
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {str(e)}")
            return {"error": str(e)}
    
    def _calculate_hit_rate(self, hits: int, misses: int) -> float:
        """Calculate cache hit rate percentage"""
        total = hits + misses
        return (hits / total * 100) if total > 0 else 0.0


# Global cache manager instance
cache_manager = CacheManager()


def cached(
    prefix: str,
    ttl: Optional[int] = None,
    key_args: Optional[list] = None,
    skip_cache: bool = False
):
    """
    Decorator for caching function results
    
    Args:
        prefix: Cache prefix to use
        ttl: Time to live in seconds
        key_args: Specific argument names to use for cache key (if None, uses all args)
        skip_cache: Skip cache for testing purposes
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
                    filtered_kwargs = {k: v for k, v in kwargs.items() if k in key_args}
                    cache_args = args if not key_args else ()
                else:
                    filtered_kwargs = kwargs
                    cache_args = args
                
                # Try to get from cache
                cached_result = await cache_manager.get(prefix, *cache_args, **filtered_kwargs)
                if cached_result is not None:
                    logger.debug(f"Cache hit for function: {func.__name__}")
                    return cached_result
                
                # Execute function
                logger.debug(f"Cache miss for function: {func.__name__}")
                result = await func(*args, **kwargs)
                
                # Cache the result (don't cache None results)
                if result is not None:
                    await cache_manager.set(prefix, result, ttl, *cache_args, **filtered_kwargs)
                
                return result
                
            except Exception as e:
                logger.error(f"Error in cached wrapper for {func.__name__}: {str(e)}")
                # Fall back to executing function without cache
                return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, just execute normally (no caching)
            logger.warning(f"Sync function {func.__name__} called with cache decorator - caching skipped")
            return func(*args, **kwargs)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


class CacheWarmup:
    """Cache warming utilities"""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
    
    async def warm_guild_cache(self, popular_guilds: list):
        """Pre-warm cache for popular guilds"""
        logger.info(f"Warming cache for {len(popular_guilds)} popular guilds")
        
        # This would integrate with the actual API client
        # For now, it's a placeholder showing the concept
        warmed_count = 0
        
        for realm, guild_name in popular_guilds:
            try:
                # Check if already cached
                if await self.cache_manager.exists("guild", realm, guild_name):
                    continue
                
                # Here you would call the actual API to get guild data
                # guild_data = await api_client.get_guild_data(realm, guild_name)
                # await self.cache_manager.set("guild", guild_data, realm=realm, guild_name=guild_name)
                
                warmed_count += 1
                
                # Rate limiting
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error warming cache for {guild_name}@{realm}: {str(e)}")
        
        logger.info(f"Cache warming completed: {warmed_count} guilds cached")
    
    async def refresh_expired_cache(self):
        """Refresh expired cache entries"""
        # This would identify and refresh cache entries that are about to expire
        # Implementation would depend on your specific caching strategy
        pass


# Utility functions
async def invalidate_guild_cache(realm: str, guild_name: str):
    """Invalidate all cache entries related to a guild"""
    await cache_manager.delete("guild", realm, guild_name)
    await cache_manager.delete("member", realm, guild_name)
    await cache_manager.flush_prefix("chart")  # Charts might be affected
    logger.info(f"Invalidated cache for guild {guild_name}@{realm}")


async def get_cache_health() -> Dict[str, Any]:
    """Get cache health status"""
    stats = await cache_manager.get_stats()
    
    health = {
        "status": "healthy" if cache_manager.connected else "unhealthy",
        "connected": cache_manager.connected,
        "stats": stats
    }
    
    # Add health indicators
    if cache_manager.connected and "hit_rate" in stats:
        hit_rate = stats["hit_rate"]
        if hit_rate > 70:
            health["performance"] = "excellent"
        elif hit_rate > 50:
            health["performance"] = "good"
        elif hit_rate > 30:
            health["performance"] = "fair"
        else:
            health["performance"] = "poor"
    
    return health


# Initialize cache on import
async def initialize_cache():
    """Initialize cache manager"""
    await cache_manager.connect()


# Cleanup function
async def cleanup_cache():
    """Cleanup cache resources"""
    await cache_manager.disconnect()