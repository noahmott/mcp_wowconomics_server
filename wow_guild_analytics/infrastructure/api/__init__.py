"""
API Infrastructure

Base API client implementations.
"""

from .base_client import BaseAPIClient, PaginatedAPIClient
from .blizzard import (
    BlizzardAPIClient,
    BlizzardOAuthService,
    BlizzardRateLimiter
)

__all__ = [
    # Base clients
    "BaseAPIClient",
    "PaginatedAPIClient",

    # Blizzard API
    "BlizzardAPIClient",
    "BlizzardOAuthService",
    "BlizzardRateLimiter"
]
