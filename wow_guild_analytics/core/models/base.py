"""
Base Model Classes

Provides base classes and mixins for all database models.
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import Column, DateTime, Boolean, String, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.declarative import declared_attr


Base = declarative_base()


class BaseModel(Base):
    """Base model with common fields."""

    __abstract__ = True

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )

    @declared_attr
    def __tablename__(cls) -> str:
        """Generate table name from class name."""
        # Convert CamelCase to snake_case
        name = cls.__name__
        result = [name[0].lower()]
        for char in name[1:]:
            if char.isupper():
                result.append('_')
            result.append(char.lower())
        return ''.join(result) + 's'  # Pluralize

    def __repr__(self) -> str:
        """String representation."""
        return f"<{self.__class__.__name__}(id={self.id})>"


class TimestampedModel(BaseModel):
    """Mixin for models with timestamp fields."""

    __abstract__ = True

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        index=True
    )


class CacheableModel(TimestampedModel):
    """Mixin for models that can be cached."""

    __abstract__ = True

    cache_key = Column(
        String(200),
        index=True,
        nullable=True
    )

    expires_at = Column(
        DateTime,
        nullable=True,
        index=True
    )

    cache_version = Column(
        Integer,
        default=1,
        nullable=False
    )

    @property
    def is_expired(self) -> bool:
        """Check if cache has expired."""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at

    def generate_cache_key(self) -> str:
        """Generate a cache key for this model."""
        return f"{self.__class__.__name__}:{self.id}"


class SoftDeleteModel(BaseModel):
    """Mixin for models with soft delete functionality."""

    __abstract__ = True

    is_deleted = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True
    )

    deleted_at = Column(
        DateTime,
        nullable=True,
        index=True
    )

    deleted_by = Column(
        String(100),
        nullable=True
    )

    def soft_delete(self, deleted_by: Optional[str] = None) -> None:
        """Mark the record as deleted."""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        self.deleted_by = deleted_by

    def restore(self) -> None:
        """Restore a soft-deleted record."""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
