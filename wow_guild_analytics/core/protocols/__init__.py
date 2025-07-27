"""
Core Protocol Definitions

This module defines the interfaces that all implementations must follow.
"""

from .cache_protocol import CacheProtocol
from .repository_protocol import RepositoryProtocol
from .api_client_protocol import APIClientProtocol
from .service_protocol import ServiceProtocol
from .oauth_protocol import OAuthProtocol

__all__ = [
    "CacheProtocol",
    "RepositoryProtocol",
    "APIClientProtocol",
    "ServiceProtocol",
    "OAuthProtocol",
]
