"""
Token Manager

Manages OAuth2 tokens with caching and refresh capabilities.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from ....core.protocols import CacheProtocol

logger = logging.getLogger(__name__)


class TokenManager:
    """Manages OAuth2 tokens with caching."""

    def __init__(
        self,
        cache: Optional[CacheProtocol] = None,
        cache_prefix: str = "oauth_token"
    ):
        """
        Initialize token manager.

        Args:
            cache: Optional cache implementation
            cache_prefix: Prefix for cache keys
        """
        self.cache = cache
        self.cache_prefix = cache_prefix

    async def get_token(
        self,
        client_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached token data.

        Args:
            client_id: OAuth client ID

        Returns:
            Token data or None if not cached
        """
        if not self.cache:
            return None

        cache_key = f"{self.cache_prefix}:{client_id}"

        try:
            cached_data = await self.cache.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.error(f"Error getting cached token: {e}")

        return None

    async def store_token(
        self,
        client_id: str,
        token_data: Dict[str, Any]
    ) -> None:
        """
        Store token data in cache.

        Args:
            client_id: OAuth client ID
            token_data: Token data to store
        """
        if not self.cache:
            return

        cache_key = f"{self.cache_prefix}:{client_id}"

        # Calculate TTL based on token expiration
        expires_in = token_data.get("expires_in", 3600)
        ttl = max(expires_in - 300, 60)  # 5 minute buffer, min 60s

        try:
            await self.cache.set(
                cache_key,
                json.dumps(token_data),
                ttl=ttl
            )
        except Exception as e:
            logger.error(f"Error caching token: {e}")

    async def invalidate_token(
        self,
        client_id: str
    ) -> None:
        """
        Invalidate cached token.

        Args:
            client_id: OAuth client ID
        """
        if not self.cache:
            return

        cache_key = f"{self.cache_prefix}:{client_id}"

        try:
            await self.cache.delete(cache_key)
        except Exception as e:
            logger.error(f"Error invalidating token: {e}")

    @staticmethod
    def is_token_valid(token_data: Dict[str, Any]) -> bool:
        """
        Check if token data is still valid.

        Args:
            token_data: Token data to check

        Returns:
            True if token is valid
        """
        if not token_data or "access_token" not in token_data:
            return False

        # Check expiration if available
        if "expires_at" in token_data:
            expires_at = datetime.fromisoformat(token_data["expires_at"])
            return datetime.utcnow() < expires_at

        # No expiration info, assume valid
        return True
