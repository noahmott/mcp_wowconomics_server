"""
Guild Cache Model

Caches guild information with member data.
"""

from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import Column, String, Integer, DateTime, JSON, Index

from ....core.models import CacheableModel


class GuildCache(CacheableModel):
    """Cache guild information with member data."""

    __tablename__ = "guild_cache"

    # Guild identification
    guild_name = Column(String(100), nullable=False, index=True)
    realm_slug = Column(String(100), nullable=False, index=True)
    region = Column(String(10), nullable=False, index=True)
    game_version = Column(String(20), default='retail')

    # Guild statistics
    member_count = Column(Integer, default=0)
    achievement_points = Column(Integer, default=0)
    average_item_level = Column(Integer, default=0)
    guild_level = Column(Integer, default=0)

    # Guild information
    faction = Column(String(20))  # Alliance, Horde
    created_timestamp = Column(Integer)  # Unix timestamp from API

    # Cached data
    guild_data = Column(JSON)  # Full guild information
    roster_data = Column(JSON)  # Member roster
    achievement_data = Column(JSON)  # Guild achievements

    # Cache metadata
    last_updated = Column(DateTime, default=datetime.utcnow)
    data_version = Column(Integer, default=1)

    # Composite indexes
    __table_args__ = (
        Index(
            'idx_guild_lookup',
            'guild_name',
            'realm_slug',
            'region'
        ),
        Index('idx_guild_updated', 'last_updated'),
        Index(
            'idx_guild_version',
            'game_version',
            'region',
            'realm_slug'
        ),
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<GuildCache(name={self.guild_name}, "
            f"realm={self.realm_slug}, members={self.member_count})>"
        )

    def generate_cache_key(self) -> str:
        """Generate cache key for this guild."""
        return (
            f"guild:{self.game_version}:{self.region}:"
            f"{self.realm_slug}:{self.guild_name}"
        )

    @property
    def age_hours(self) -> float:
        """Get cache age in hours."""
        if self.last_updated:
            delta = datetime.utcnow() - self.last_updated
            return delta.total_seconds() / 3600
        return float('inf')

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": str(self.id),
            "guild_name": self.guild_name,
            "realm_slug": self.realm_slug,
            "region": self.region,
            "game_version": self.game_version,
            "member_count": self.member_count,
            "achievement_points": self.achievement_points,
            "average_item_level": self.average_item_level,
            "faction": self.faction,
            "last_updated": self.last_updated.isoformat(),
            "cache_age_hours": self.age_hours,
            "is_expired": self.is_expired
        }
