"""
Service Protocol Definition

Defines the interface for application services.
"""

from typing import Protocol, runtime_checkable
from abc import abstractmethod


@runtime_checkable
class ServiceProtocol(Protocol):
    """Base protocol for all services."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the service."""
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown the service gracefully."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the service is healthy.

        Returns:
            True if healthy, False otherwise
        """
        ...
