"""
Auction Snapshot Model

Stores periodic auction house snapshots for market analysis.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column, String, Integer, DateTime, JSON, Index
)

from ....core.models import TimestampedModel


class AuctionSnapshot(TimestampedModel):
    """Store periodic auction house snapshots."""

    __tablename__ = "auction_snapshots"

    # Realm information
    realm_slug = Column(String(100), nullable=False, index=True)
    connected_realm_id = Column(String(50), nullable=False, index=True)
    region = Column(String(10), nullable=False, index=True)
    game_version = Column(String(20), default='retail')

    # Snapshot data
    snapshot_time = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True
    )
    auction_count = Column(Integer, default=0)
    total_value = Column(Integer, default=0)  # Total buyout value in copper
    average_value = Column(Integer, default=0)  # Average auction value

    # Data integrity
    data_hash = Column(String(64), index=True)  # Hash for deduplication
    raw_data = Column(JSON)  # Store raw auction data

    # Composite indexes for efficient lookups
    __table_args__ = (
        Index('idx_auction_realm_time', 'realm_slug', 'snapshot_time'),
        Index('idx_auction_region_time', 'region', 'snapshot_time'),
        Index(
            'idx_auction_version_realm',
            'game_version',
            'realm_slug',
            'snapshot_time'
        ),
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<AuctionSnapshot(realm={self.realm_slug}, "
            f"time={self.snapshot_time}, count={self.auction_count})>"
        )

    @property
    def average_price_per_item(self) -> float:
        """Calculate average price per item."""
        if self.auction_count > 0:
            return self.total_value / self.auction_count
        return 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": str(self.id),
            "realm_slug": self.realm_slug,
            "connected_realm_id": self.connected_realm_id,
            "region": self.region,
            "game_version": self.game_version,
            "snapshot_time": self.snapshot_time.isoformat(),
            "auction_count": self.auction_count,
            "total_value": self.total_value,
            "average_value": self.average_value,
            "created_at": self.created_at.isoformat()
        }
