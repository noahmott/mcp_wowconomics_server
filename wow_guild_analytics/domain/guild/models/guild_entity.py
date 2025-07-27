"""
Guild Entity Model

Main guild entity for persistent storage.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column, String, Integer, DateTime, Boolean, JSON, Index
)
from sqlalchemy.orm import relationship

from ....core.models import TimestampedModel


class Guild(TimestampedModel):
    """Guild entity model."""

    __tablename__ = "guilds"

    # Guild identification
    realm = Column(String(50), nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)
    region = Column(String(10), nullable=False, default='us')
    game_version = Column(String(20), default='retail')

    # Guild information
    faction = Column(String(20))  # Alliance/Horde
    level = Column(Integer, default=0)
    member_count = Column(Integer, default=0)
    achievement_points = Column(Integer, default=0)

    # Metadata
    created_date = Column(DateTime)  # When guild was created in game
    last_crawled = Column(DateTime)  # When we last fetched data
    is_active = Column(Boolean, default=True)

    # Raw API data storage
    raw_data = Column(JSON)

    # Relationships
    members = relationship(
        "Member",
        back_populates="guild",
        cascade="all, delete-orphan"
    )
    raid_progress = relationship(
        "RaidProgress",
        back_populates="guild",
        cascade="all, delete-orphan"
    )

    # Composite indexes for efficient lookups
    __table_args__ = (
        Index('idx_guild_realm_name', 'realm', 'name'),
        Index('idx_guild_updated', 'updated_at'),
        Index('idx_guild_active', 'is_active'),
        Index('idx_guild_version_region', 'game_version', 'region'),
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<Guild(name={self.name}, realm={self.realm}, "
            f"faction={self.faction})>"
        )

    @property
    def full_name(self) -> str:
        """Get full guild name with realm."""
        return f"{self.name} - {self.realm}"

    @property
    def is_alliance(self) -> bool:
        """Check if guild is Alliance."""
        return self.faction and self.faction.lower() == 'alliance'

    @property
    def is_horde(self) -> bool:
        """Check if guild is Horde."""
        return self.faction and self.faction.lower() == 'horde'

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": str(self.id),
            "realm": self.realm,
            "name": self.name,
            "region": self.region,
            "game_version": self.game_version,
            "faction": self.faction,
            "level": self.level,
            "member_count": self.member_count,
            "achievement_points": self.achievement_points,
            "created_date": self.created_date.isoformat()
            if self.created_date else None,
            "last_crawled": self.last_crawled.isoformat()
            if self.last_crawled else None,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
