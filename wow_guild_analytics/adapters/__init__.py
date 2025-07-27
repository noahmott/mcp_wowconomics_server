"""
Adapter Layer

Provides backward compatibility with existing code.
"""

from .legacy_blizzard_client import LegacyBlizzardClientAdapter
from .legacy_cache_manager import LegacyCacheManagerAdapter

__all__ = [
    "LegacyBlizzardClientAdapter",
    "LegacyCacheManagerAdapter",
]
