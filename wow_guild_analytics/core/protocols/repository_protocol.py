"""
Repository Protocol Definition

Defines the interface for all repository implementations.
"""

from typing import Protocol, Optional, List, Any, TypeVar, Generic
from abc import abstractmethod
from uuid import UUID

T = TypeVar('T')


class RepositoryProtocol(Protocol, Generic[T]):
    """Protocol for repository implementations."""

    async def get_by_id(self, id: UUID) -> Optional[T]:
        """
        Retrieve an entity by its ID.

        Args:
            id: Entity ID

        Returns:
            Entity or None if not found
        """
        ...

    async def get_all(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[T]:
        """
        Retrieve all entities with optional pagination.

        Args:
            limit: Maximum number of entities to return
            offset: Number of entities to skip

        Returns:
            List of entities
        """
        ...

    async def create(self, entity: T) -> T:
        """
        Create a new entity.

        Args:
            entity: Entity to create

        Returns:
            Created entity with ID
        """
        ...

    async def update(self, entity: T) -> T:
        """
        Update an existing entity.

        Args:
            entity: Entity with updated values

        Returns:
            Updated entity
        """
        ...

    async def delete(self, id: UUID) -> bool:
        """
        Delete an entity by ID.

        Args:
            id: Entity ID

        Returns:
            True if deleted, False otherwise
        """
        ...

    async def exists(self, id: UUID) -> bool:
        """
        Check if an entity exists.

        Args:
            id: Entity ID

        Returns:
            True if exists, False otherwise
        """
        ...
