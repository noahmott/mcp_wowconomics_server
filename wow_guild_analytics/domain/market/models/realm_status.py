"""
Realm Status Model

Tracks realm population and status over time.
"""

from datetime import datetime
from typing import Optional, List

from sqlalchemy import Column, String, DateTime, JSON, Index

from ....core.models import TimestampedModel


class RealmStatus(TimestampedModel):
    """Track realm population and status over time."""

    __tablename__ = "realm_status"

    # Realm identification
    realm_slug = Column(String(100), nullable=False, index=True)
    realm_name = Column(String(100), nullable=False)
    region = Column(String(10), nullable=False, index=True)
    game_version = Column(String(20), default='retail')

    # Realm information
    population = Column(String(20))  # Low, Medium, High, Full
    timezone = Column(String(50))
    realm_type = Column(String(20))  # PvP, PvE, RP, etc.
    locale = Column(String(10), default='en_US')

    # Connected realms
    connected_realms = Column(JSON)  # List of connected realm slugs
    connected_realm_id = Column(String(50))

    # Status tracking
    is_online = Column(String(10), default='true')  # API returns string
    last_updated = Column(DateTime, default=datetime.utcnow)

    # Composite indexes
    __table_args__ = (
        Index('idx_realm_lookup', 'realm_slug', 'region'),
        Index('idx_realm_updated', 'last_updated'),
        Index('idx_realm_version', 'game_version', 'region'),
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<RealmStatus(name={self.realm_name}, "
            f"region={self.region}, pop={self.population})>"
        )

    @property
    def is_connected(self) -> bool:
        """Check if realm is part of connected realms."""
        return bool(self.connected_realms and len(self.connected_realms) > 1)

    @property
    def population_level(self) -> int:
        """Get numeric population level."""
        levels = {
            "Low": 1,
            "Medium": 2,
            "High": 3,
            "Full": 4
        }
        return levels.get(self.population, 0)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": str(self.id),
            "realm_slug": self.realm_slug,
            "realm_name": self.realm_name,
            "region": self.region,
            "game_version": self.game_version,
            "population": self.population,
            "timezone": self.timezone,
            "realm_type": self.realm_type,
            "connected_realms": self.connected_realms,
            "is_online": self.is_online == 'true',
            "last_updated": self.last_updated.isoformat()
        }
