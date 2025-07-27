"""
Data Collection Log Model

Tracks data collection attempts and success rates.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column, String, Integer, DateTime, Text, Index
)

from ....core.models import BaseModel


class DataCollectionLog(BaseModel):
    """Track data collection attempts and success rates."""

    __tablename__ = "data_collection_log"

    # Collection information
    collection_type = Column(
        String(50),
        nullable=False,
        index=True
    )  # 'auction', 'guild', etc.

    target = Column(
        String(200),
        nullable=False
    )  # realm, guild name, etc.

    region = Column(
        String(10),
        nullable=False,
        index=True
    )

    game_version = Column(
        String(20),
        default='retail'
    )

    # Status tracking
    status = Column(
        String(20),
        nullable=False,
        index=True
    )  # 'success', 'failed', 'partial'

    error_message = Column(Text)

    # Metrics
    records_collected = Column(Integer, default=0)
    execution_time = Column(Integer)  # Milliseconds

    # Timestamp
    timestamp = Column(
        DateTime,
        default=datetime.utcnow,
        index=True
    )

    # Request metadata
    request_id = Column(String(100))
    api_calls_made = Column(Integer, default=0)

    # Composite indexes
    __table_args__ = (
        Index(
            'idx_collection_type_time',
            'collection_type',
            'timestamp'
        ),
        Index('idx_collection_status', 'status'),
        Index(
            'idx_collection_target',
            'collection_type',
            'target',
            'timestamp'
        ),
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<DataCollectionLog(type={self.collection_type}, "
            f"target={self.target}, status={self.status})>"
        )

    @property
    def was_successful(self) -> bool:
        """Check if collection was successful."""
        return self.status == 'success'

    @property
    def execution_time_seconds(self) -> float:
        """Get execution time in seconds."""
        if self.execution_time:
            return self.execution_time / 1000.0
        return 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": str(self.id),
            "collection_type": self.collection_type,
            "target": self.target,
            "region": self.region,
            "game_version": self.game_version,
            "status": self.status,
            "error_message": self.error_message,
            "records_collected": self.records_collected,
            "execution_time_ms": self.execution_time,
            "execution_time_s": self.execution_time_seconds,
            "timestamp": self.timestamp.isoformat(),
            "api_calls_made": self.api_calls_made
        }
