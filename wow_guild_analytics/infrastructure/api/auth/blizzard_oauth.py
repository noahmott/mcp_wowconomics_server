"""
Blizzard OAuth2 Client

Handles OAuth2 authentication with the Blizzard API.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import aiohttp
from aiohttp import ClientSession, BasicAuth

from ....core.exceptions import WoWGuildError

logger = logging.getLogger(__name__)


class BlizzardOAuth2Client:
    """OAuth2 client for Blizzard API authentication."""

    AUTH_URL = "https://oauth.battle.net/token"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        region: str = "us"
    ):
        """
        Initialize OAuth2 client.

        Args:
            client_id: Blizzard API client ID
            client_secret: Blizzard API client secret
            region: API region (us, eu, kr, tw, cn)
        """
        if not client_id or not client_secret:
            raise ValueError(
                "client_id and client_secret are required"
            )

        self.client_id = client_id
        self.client_secret = client_secret
        self.region = region

        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self.session: Optional[ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    async def authenticate(self) -> str:
        """
        Authenticate and get access token.

        Returns:
            Access token

        Raises:
            WoWGuildError: If authentication fails
        """
        # Check if we have a valid token
        if self._is_token_valid():
            return self.access_token

        # Request new token
        return await self._request_token()

    async def _request_token(self) -> str:
        """
        Request a new access token from Blizzard.

        Returns:
            Access token

        Raises:
            WoWGuildError: If token request fails
        """
        if not self.session:
            raise RuntimeError(
                "Session not initialized. Use async context manager."
            )

        auth = BasicAuth(self.client_id, self.client_secret)
        data = {"grant_type": "client_credentials"}

        try:
            async with self.session.post(
                self.AUTH_URL,
                auth=auth,
                data=data
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise WoWGuildError(
                        f"Failed to get access token: {response.status} - "
                        f"{error_text}"
                    )

                token_data = await response.json()
                self._store_token(token_data)

                logger.info(
                    "Successfully obtained Blizzard API access token"
                )
                return self.access_token

        except aiohttp.ClientError as e:
            raise WoWGuildError(
                f"Network error getting access token: {str(e)}"
            )

    def _store_token(self, token_data: Dict[str, Any]) -> None:
        """
        Store token data.

        Args:
            token_data: Token response from Blizzard
        """
        self.access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600)

        # Set expiration with 1 minute buffer
        self.token_expires_at = datetime.utcnow() + timedelta(
            seconds=expires_in - 60
        )

    def _is_token_valid(self) -> bool:
        """
        Check if current token is valid.

        Returns:
            True if token is valid
        """
        if not self.access_token or not self.token_expires_at:
            return False

        return datetime.utcnow() < self.token_expires_at

    def get_headers(self) -> Dict[str, str]:
        """
        Get authorization headers.

        Returns:
            Headers dict with authorization
        """
        if not self.access_token:
            raise RuntimeError("Not authenticated")

        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json"
        }

    def invalidate_token(self) -> None:
        """Invalidate the current token."""
        self.access_token = None
        self.token_expires_at = None
