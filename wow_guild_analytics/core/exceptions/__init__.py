"""
Core Exceptions

Base exception classes for the application.
"""

from .base import (
    WoWGuildError,
    APIError,
    ValidationError,
    NotFoundError,
    ConfigurationError,
    ServiceError,
)

__all__ = [
    "WoWGuildError",
    "APIError",
    "ValidationError",
    "NotFoundError",
    "ConfigurationError",
    "ServiceError",
]
