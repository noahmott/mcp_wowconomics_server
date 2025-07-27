"""
Integrated Blizzard API Client

Full-featured Blizzard API client with rate limiting and retry handling.
"""

import logging
import asyncio
from typing import Optional, Dict, Any, List, AsyncIterator
from contextlib import asynccontextmanager

from .client import BlizzardAPIClient
from .rate_limiter import BlizzardRateLimiter
from .retry_handler import RetryHandler, with_retry
from ....core.config import Settings

logger = logging.getLogger(__name__)


class IntegratedBlizzardClient:
    """
    Integrated Blizzard API client with all features.

    Combines:
    - OAuth authentication
    - Rate limiting
    - Retry handling
    - Caching support
    """

    def __init__(
        self,
        settings: Settings,
        cache_client: Optional[Any] = None
    ):
        """
        Initialize integrated client.

        Args:
            settings: Application settings
            cache_client: Optional cache client
        """
        self.settings = settings
        self.cache = cache_client

        # Initialize components
        self.client = BlizzardAPIClient(
            client_id=settings.api.client_id,
            client_secret=settings.api.client_secret,
            region=settings.api.region,
            game_version=settings.api.wow_version,
            timeout=settings.api.timeout
        )

        self.rate_limiter = BlizzardRateLimiter(
            requests_per_second=settings.api.rate_limit
        )

        self.retry_handler = RetryHandler(
            max_retries=3,
            base_delay=1.0,
            max_delay=60.0
        )

    async def __aenter__(self):
        """Enter async context."""
        await self.client.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        await self.client.close()

    async def _get_cache_key(self, method: str, *args, **kwargs) -> str:
        """Generate cache key for request."""
        # Create a simple cache key
        parts = [method]
        parts.extend(str(arg) for arg in args)
        parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
        return ":".join(parts)

    async def _cached_request(
        self,
        method: str,
        cache_ttl: Optional[int] = None,
        *args,
        **kwargs
    ) -> Any:
        """
        Make cached request.

        Args:
            method: Client method name
            cache_ttl: Cache TTL in seconds
            *args: Method arguments
            **kwargs: Method keyword arguments

        Returns:
            Method result
        """
        # Check cache if available
        if self.cache and cache_ttl:
            cache_key = await self._get_cache_key(method, *args, **kwargs)
            cached = await self.cache.get(cache_key, namespace="blizzard_api")

            if cached is not None:
                logger.debug(f"Cache hit for {method}")
                return cached

        # Get the actual method
        client_method = getattr(self.client, method)

        # Make request with rate limiting and retry
        async with self.rate_limiter:
            result = await self.retry_handler.execute_with_retry(
                client_method,
                *args,
                **kwargs
            )

        # Cache result if available
        if self.cache and cache_ttl and result is not None:
            cache_key = await self._get_cache_key(method, *args, **kwargs)
            await self.cache.set(
                cache_key,
                result,
                ttl=cache_ttl,
                namespace="blizzard_api"
            )

        return result

    # Guild methods with caching
    async def get_guild(
        self,
        realm_slug: str,
        guild_name: str,
        cache_ttl: int = 300
    ) -> Dict[str, Any]:
        """Get guild profile with caching."""
        result = await self._cached_request(
            "get_guild",
            cache_ttl,
            realm_slug,
            guild_name
        )
        return result.dict() if hasattr(result, 'dict') else result

    async def get_guild_roster(
        self,
        realm_slug: str,
        guild_name: str,
        cache_ttl: int = 300
    ) -> Dict[str, Any]:
        """Get guild roster with caching."""
        return await self._cached_request(
            "get_guild_roster",
            cache_ttl,
            realm_slug,
            guild_name
        )

    async def get_comprehensive_guild_data(
        self,
        realm_slug: str,
        guild_name: str,
        cache_ttl: int = 300
    ) -> Dict[str, Any]:
        """Get comprehensive guild data with caching."""
        return await self._cached_request(
            "get_comprehensive_guild_data",
            cache_ttl,
            realm_slug,
            guild_name
        )

    # Character methods with caching
    async def get_character(
        self,
        realm_slug: str,
        character_name: str,
        cache_ttl: int = 300
    ) -> Dict[str, Any]:
        """Get character profile with caching."""
        result = await self._cached_request(
            "get_character",
            cache_ttl,
            realm_slug,
            character_name
        )
        return result.dict() if hasattr(result, 'dict') else result

    async def get_character_equipment(
        self,
        realm_slug: str,
        character_name: str,
        cache_ttl: int = 300
    ) -> Dict[str, Any]:
        """Get character equipment with caching."""
        result = await self._cached_request(
            "get_character_equipment",
            cache_ttl,
            realm_slug,
            character_name
        )
        return result.dict() if hasattr(result, 'dict') else result

    async def get_character_profile(
        self,
        realm_slug: str,
        character_name: str,
        cache_ttl: int = 300
    ) -> Dict[str, Any]:
        """Get comprehensive character profile with caching."""
        return await self._cached_request(
            "get_character_profile",
            cache_ttl,
            realm_slug,
            character_name
        )

    # Market data with short cache
    async def get_auctions(
        self,
        connected_realm_id: int,
        cache_ttl: int = 60  # 1 minute cache
    ) -> Dict[str, Any]:
        """Get auction house data with short cache."""
        result = await self._cached_request(
            "get_auctions",
            cache_ttl,
            connected_realm_id
        )
        return result.dict() if hasattr(result, 'dict') else result

    async def get_token_price(
        self,
        cache_ttl: int = 300  # 5 minute cache
    ) -> Dict[str, Any]:
        """Get WoW Token price with caching."""
        result = await self._cached_request(
            "get_token_price",
            cache_ttl
        )
        return result.dict() if hasattr(result, 'dict') else result

    # Realm data with long cache
    async def get_realms(
        self,
        cache_ttl: int = 3600  # 1 hour cache
    ) -> List[Dict[str, Any]]:
        """Get all realms with long cache."""
        return await self._cached_request(
            "get_realms",
            cache_ttl
        )

    async def get_realm(
        self,
        realm_slug: str,
        cache_ttl: int = 3600
    ) -> Dict[str, Any]:
        """Get specific realm with long cache."""
        return await self._cached_request(
            "get_realm",
            cache_ttl,
            realm_slug
        )

    # Statistics
    def get_rate_limit_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        return self.rate_limiter.get_statistics()

    async def health_check(self) -> bool:
        """Check if API is accessible."""
        try:
            async with self.rate_limiter:
                return await self.client.health_check()
        except Exception:
            return False
