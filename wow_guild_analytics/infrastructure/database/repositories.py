"""
Base Repository Implementation

Base repository class for data access.
"""

import logging
from typing import (
    TypeVar, Generic, Optional, List, Type, Any, Dict
)
from uuid import UUID

from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...core.models import BaseModel
from ...core.protocols import RepositoryProtocol

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)


class BaseRepository(Generic[T], RepositoryProtocol[T]):
    """Base repository implementation for SQLAlchemy models."""

    def __init__(self, model: Type[T], session: AsyncSession):
        """
        Initialize repository.

        Args:
            model: SQLAlchemy model class
            session: Database session
        """
        self.model = model
        self.session = session

    async def get_by_id(self, id: UUID) -> Optional[T]:
        """Retrieve an entity by its ID."""
        try:
            stmt = select(self.model).where(self.model.id == id)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting {self.model.__name__} by id: {e}")
            raise

    async def get_all(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[T]:
        """Retrieve all entities with optional pagination."""
        try:
            stmt = select(self.model)

            if offset:
                stmt = stmt.offset(offset)
            if limit:
                stmt = stmt.limit(limit)

            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting all {self.model.__name__}: {e}")
            raise

    async def create(self, entity: T) -> T:
        """Create a new entity."""
        try:
            self.session.add(entity)
            await self.session.flush()
            await self.session.refresh(entity)
            return entity
        except Exception as e:
            logger.error(f"Error creating {self.model.__name__}: {e}")
            await self.session.rollback()
            raise

    async def update(self, entity: T) -> T:
        """Update an existing entity."""
        try:
            # Merge the entity into session
            merged = await self.session.merge(entity)
            await self.session.flush()
            await self.session.refresh(merged)
            return merged
        except Exception as e:
            logger.error(f"Error updating {self.model.__name__}: {e}")
            await self.session.rollback()
            raise

    async def delete(self, id: UUID) -> bool:
        """Delete an entity by ID."""
        try:
            entity = await self.get_by_id(id)
            if entity:
                await self.session.delete(entity)
                await self.session.flush()
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting {self.model.__name__}: {e}")
            await self.session.rollback()
            raise

    async def exists(self, id: UUID) -> bool:
        """Check if an entity exists."""
        try:
            stmt = select(
                func.count()
            ).select_from(
                self.model
            ).where(
                self.model.id == id
            )
            result = await self.session.execute(stmt)
            count = result.scalar()
            return count > 0
        except Exception as e:
            logger.error(f"Error checking existence of {self.model.__name__}: {e}")
            raise

    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count entities with optional filters."""
        try:
            stmt = select(func.count()).select_from(self.model)

            if filters:
                conditions = []
                for key, value in filters.items():
                    if hasattr(self.model, key):
                        conditions.append(
                            getattr(self.model, key) == value
                        )
                if conditions:
                    stmt = stmt.where(and_(*conditions))

            result = await self.session.execute(stmt)
            return result.scalar()
        except Exception as e:
            logger.error(f"Error counting {self.model.__name__}: {e}")
            raise

    async def find_by(
        self,
        filters: Dict[str, Any],
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        order_by: Optional[str] = None,
        order_desc: bool = False
    ) -> List[T]:
        """Find entities by filters."""
        try:
            stmt = select(self.model)

            # Apply filters
            conditions = []
            for key, value in filters.items():
                if hasattr(self.model, key):
                    conditions.append(
                        getattr(self.model, key) == value
                    )

            if conditions:
                stmt = stmt.where(and_(*conditions))

            # Apply ordering
            if order_by and hasattr(self.model, order_by):
                order_column = getattr(self.model, order_by)
                if order_desc:
                    stmt = stmt.order_by(desc(order_column))
                else:
                    stmt = stmt.order_by(order_column)

            # Apply pagination
            if offset:
                stmt = stmt.offset(offset)
            if limit:
                stmt = stmt.limit(limit)

            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error finding {self.model.__name__}: {e}")
            raise

    async def find_one_by(
        self,
        filters: Dict[str, Any]
    ) -> Optional[T]:
        """Find one entity by filters."""
        results = await self.find_by(filters, limit=1)
        return results[0] if results else None

    async def bulk_create(self, entities: List[T]) -> List[T]:
        """Create multiple entities."""
        try:
            self.session.add_all(entities)
            await self.session.flush()

            # Refresh all entities
            for entity in entities:
                await self.session.refresh(entity)

            return entities
        except Exception as e:
            logger.error(f"Error bulk creating {self.model.__name__}: {e}")
            await self.session.rollback()
            raise

    async def bulk_update(self, entities: List[T]) -> List[T]:
        """Update multiple entities."""
        try:
            # Use bulk_save_objects for efficiency
            await self.session.execute(
                self.model.__table__.update(),
                [
                    {
                        "id": entity.id,
                        **{
                            k: v for k, v in entity.__dict__.items()
                            if not k.startswith('_')
                        }
                    }
                    for entity in entities
                ]
            )
            await self.session.flush()

            # Refresh entities
            refreshed = []
            for entity in entities:
                refreshed_entity = await self.get_by_id(entity.id)
                if refreshed_entity:
                    refreshed.append(refreshed_entity)

            return refreshed
        except Exception as e:
            logger.error(f"Error bulk updating {self.model.__name__}: {e}")
            await self.session.rollback()
            raise
