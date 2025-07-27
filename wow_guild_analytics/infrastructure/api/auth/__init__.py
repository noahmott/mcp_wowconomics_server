"""
Authentication Module

Handles OAuth2 authentication for external APIs.
"""

from .blizzard_oauth import BlizzardOAuth2Client
from .token_manager import TokenManager

__all__ = [
    "BlizzardOAuth2Client",
    "TokenManager",
]
