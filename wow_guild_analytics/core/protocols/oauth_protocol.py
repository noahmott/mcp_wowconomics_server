"""
OAuth Protocol Definition

Protocol for OAuth2 authentication services.
"""

from typing import Protocol, Dict, Any, runtime_checkable


@runtime_checkable
class OAuthProtocol(Protocol):
    """Protocol for OAuth2 authentication."""

    async def get_access_token(self) -> Dict[str, Any]:
        """
        Get OAuth2 access token.

        Returns:
            Token data including access_token and expires_in
        """
        ...

    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh OAuth2 token.

        Args:
            refresh_token: Refresh token

        Returns:
            New token data
        """
        ...

    async def revoke_token(self, token: str) -> bool:
        """
        Revoke OAuth2 token.

        Args:
            token: Access token to revoke

        Returns:
            True if successful
        """
        ...

    async def validate_token(self, token: str) -> bool:
        """
        Validate OAuth2 token.

        Args:
            token: Access token to validate

        Returns:
            True if valid
        """
        ...
