"""
API Client Protocol Definition

Defines the interface for external API client implementations.
"""

from typing import Protocol, Dict, Any, Optional


class APIClientProtocol(Protocol):
    """Protocol for API client implementations."""

    async def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Make a GET request to the API.

        Args:
            endpoint: API endpoint path
            params: Query parameters
            headers: Additional headers

        Returns:
            Response data as dictionary
        """
        ...

    async def post(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Make a POST request to the API.

        Args:
            endpoint: API endpoint path
            data: Request body data
            params: Query parameters
            headers: Additional headers

        Returns:
            Response data as dictionary
        """
        ...

    async def authenticate(self) -> bool:
        """
        Authenticate with the API.

        Returns:
            True if authentication successful
        """
        ...

    async def is_authenticated(self) -> bool:
        """
        Check if client is authenticated.

        Returns:
            True if authenticated
        """
        ...
