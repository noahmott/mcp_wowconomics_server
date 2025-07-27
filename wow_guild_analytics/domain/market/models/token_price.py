"""
Token Price History Model

Tracks WoW Token price changes over time.
"""

from datetime import datetime

from sqlalchemy import Column, String, Integer, DateTime, Index

from ....core.models import BaseModel


class TokenPriceHistory(BaseModel):
    """Track WoW Token price changes over time."""

    __tablename__ = "token_price_history"

    # Region and price data
    region = Column(String(10), nullable=False, index=True)
    price = Column(Integer, nullable=False)  # Price in copper

    # Timestamp data
    timestamp = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True
    )
    last_updated_timestamp = Column(Integer)  # From API

    # Game version (classic doesn't have tokens but keep for consistency)
    game_version = Column(String(20), default='retail')

    # Composite indexes
    __table_args__ = (
        Index('idx_token_region_time', 'region', 'timestamp'),
        Index('idx_token_version_region', 'game_version', 'region'),
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<TokenPriceHistory(region={self.region}, "
            f"price={self.price}, time={self.timestamp})>"
        )

    @property
    def price_in_gold(self) -> float:
        """Get price in gold units."""
        return self.price / 10000  # Convert copper to gold

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": str(self.id),
            "region": self.region,
            "price": self.price,
            "price_gold": self.price_in_gold,
            "timestamp": self.timestamp.isoformat(),
            "last_updated": self.last_updated_timestamp,
            "game_version": self.game_version
        }
