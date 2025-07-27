"""
Blizzard OAuth2 Service

Handles OAuth2 authentication for Blizzard API.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

import httpx

from ....core.protocols import OAuthProtocol

logger = logging.getLogger(__name__)


class BlizzardOAuthService(OAuthProtocol):
    """Blizzard OAuth2 service implementation."""

    OAUTH_URLS = {
        "us": "https://oauth.battle.net/token",
        "eu": "https://oauth.battle.net/token",
        "kr": "https://oauth.battle.net/token",
        "tw": "https://oauth.battle.net/token",
        "cn": "https://oauth.battlenet.com.cn/token"
    }

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        region: str = "eu"
    ):
        """
        Initialize OAuth service.

        Args:
            client_id: Blizzard API client ID
            client_secret: Blizzard API client secret
            region: API region
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.region = region.lower()
        self.oauth_url = self.OAUTH_URLS.get(self.region, self.OAUTH_URLS["eu"])

        self._token_cache: Optional[Dict[str, Any]] = None
        self._token_expires: Optional[datetime] = None

    async def get_access_token(self) -> Dict[str, Any]:
        """
        Get OAuth2 access token.

        Returns:
            Token data including access_token and expires_in
        """
        # Check cache
        if self._token_cache and self._token_expires:
            if datetime.now() < self._token_expires:
                logger.debug("Using cached OAuth token")
                return self._token_cache

        logger.info("Fetching new OAuth token")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.oauth_url,
                data={
                    "grant_type": "client_credentials"
                },
                auth=(self.client_id, self.client_secret),
                timeout=10.0
            )

            response.raise_for_status()
            token_data = response.json()

            # Cache token
            self._token_cache = token_data
            expires_in = token_data.get("expires_in", 86400)
            # Set expiration with 5 minute buffer
            self._token_expires = datetime.now() + timedelta(
                seconds=expires_in - 300
            )

            logger.info(f"OAuth token obtained, expires in {expires_in} seconds")

            return token_data

    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh OAuth2 token.

        Note: Blizzard API uses client credentials flow,
        so this is not typically used.

        Args:
            refresh_token: Refresh token (not used)

        Returns:
            New token data
        """
        # Blizzard uses client credentials flow, so just get new token
        return await self.get_access_token()

    async def revoke_token(self, token: str) -> bool:
        """
        Revoke OAuth2 token.

        Note: Blizzard doesn't provide token revocation endpoint.

        Args:
            token: Access token to revoke

        Returns:
            Always returns True
        """
        # Clear cache
        self._token_cache = None
        self._token_expires = None

        logger.info("OAuth token cache cleared")
        return True

    async def validate_token(self, token: str) -> bool:
        """
        Validate OAuth2 token.

        Args:
            token: Access token to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            # Try to use token on a simple endpoint
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://{self.region}.api.blizzard.com/data/wow/realm/index",
                    headers={
                        "Authorization": f"Bearer {token}"
                    },
                    params={
                        "namespace": f"dynamic-{self.region}",
                        "locale": "en_US"
                    },
                    timeout=5.0
                )

                return response.status_code == 200

        except Exception as e:
            logger.error(f"Token validation failed: {e}")
            return False

    def clear_cache(self) -> None:
        """Clear cached token."""
        self._token_cache = None
        self._token_expires = None
        logger.debug("OAuth cache cleared")
