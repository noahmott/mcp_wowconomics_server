"""
Blizzard API Infrastructure

Modern implementation of Blizzard API client with modular architecture.
"""

from .client import BlizzardAPIClient
from .oauth import BlizzardOAuthService
from .rate_limiter import BlizzardRateLimiter
from .retry_handler import RetryHandler, with_retry
from .models import (
    GuildProfile,
    CharacterProfile,
    CharacterEquipment,
    MythicPlusProfile,
    RaidProgression,
    AuctionData,
    TokenPrice
)

__all__ = [
    # Client
    "BlizzardAPIClient",

    # OAuth
    "BlizzardOAuthService",

    # Rate limiting
    "BlizzardRateLimiter",

    # Retry handling
    "RetryHandler",
    "with_retry",

    # Models
    "GuildProfile",
    "CharacterProfile",
    "CharacterEquipment",
    "MythicPlusProfile",
    "RaidProgression",
    "AuctionData",
    "TokenPrice"
]
