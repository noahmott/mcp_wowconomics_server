"""
WoW Data Cache Model

Universal cache table for all WoW API data.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column, String, DateTime, JSON, Boolean, Index
)

from ....core.models import CacheableModel


class WoWDataCache(CacheableModel):
    """Universal cache table for all WoW API data."""

    __tablename__ = "wow_data_cache"

    # Cache identification
    data_type = Column(
        String(50),
        nullable=False,
        index=True
    )  # 'auction', 'guild', 'realm', 'character'

    cache_key = Column(
        String(200),
        nullable=False,
        index=True
    )  # realm-slug, guild-realm-name, etc.

    # Region and version
    region = Column(
        String(10),
        nullable=False,
        default='us',
        index=True
    )
    game_version = Column(
        String(20),
        default='retail',
        index=True
    )

    # Cached data
    data = Column(JSON, nullable=False)  # The actual API response

    # Cache metadata
    timestamp = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True
    )
    is_valid = Column(
        Boolean,
        default=True,
        index=True
    )  # Mark as invalid if outdated

    # Data source
    api_source = Column(
        String(50),
        default='blizzard'
    )  # Track data source

    # Composite indexes for fast lookups
    __table_args__ = (
        Index(
            'idx_cache_lookup',
            'data_type',
            'cache_key',
            'region',
            'game_version'
        ),
        Index('idx_cache_timestamp', 'timestamp'),
        Index('idx_cache_expires', 'expires_at'),
        Index('idx_cache_valid', 'is_valid'),
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<WoWDataCache(type={self.data_type}, "
            f"key={self.cache_key}, region={self.region})>"
        )

    def generate_cache_key(self) -> str:
        """Generate full cache key."""
        return (
            f"{self.data_type}:{self.game_version}:"
            f"{self.region}:{self.cache_key}"
        )

    @property
    def age_minutes(self) -> float:
        """Get cache age in minutes."""
        if self.timestamp:
            delta = datetime.utcnow() - self.timestamp
            return delta.total_seconds() / 60
        return float('inf')

    def invalidate(self) -> None:
        """Mark cache entry as invalid."""
        self.is_valid = False
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": str(self.id),
            "data_type": self.data_type,
            "cache_key": self.cache_key,
            "region": self.region,
            "game_version": self.game_version,
            "timestamp": self.timestamp.isoformat(),
            "age_minutes": self.age_minutes,
            "is_valid": self.is_valid,
            "is_expired": self.is_expired,
            "api_source": self.api_source
        }
