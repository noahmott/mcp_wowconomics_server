"""
Dependency Injection Container

Central container for managing application dependencies.
"""

import logging
from typing import Optional

from dependency_injector import containers, providers
from dependency_injector.wiring import Provide, inject

from .config import Settings, ConfigLoader
from ..infrastructure.cache import RedisCache, MemoryCache

logger = logging.getLogger(__name__)


def _create_cache():
    """Create cache with fallback."""
    try:
        import redis
        # Test Redis connection
        r = redis.from_url(ConfigLoader.load_config().cache.redis_url)
        r.ping()
        return RedisCache(redis_url=ConfigLoader.load_config().cache.redis_url)
    except Exception:
        logger.warning("Redis not available, using memory cache")
        return MemoryCache()


class Container(containers.DeclarativeContainer):
    """Main DI container for the application."""

    # Configuration
    config = providers.Configuration()

    # Load settings
    settings = providers.Singleton(
        ConfigLoader.load_config
    )

    # Infrastructure - Cache
    # Try Redis first, fallback to memory
    cache = providers.Singleton(
        _create_cache,
    )

    # Infrastructure - Database
    database_url = providers.Callable(
        lambda settings: settings.database.url,
        settings=settings
    )

    # Infrastructure - Blizzard API Client
    # Will be initialized when needed using integrated client

    # Services - These will be added as we implement them
    # data_staging_service = providers.Factory(...)
    # market_analysis_service = providers.Factory(...)
    # guild_analysis_service = providers.Factory(...)

    # Presentation - These will be added as we implement them
    # chart_generator = providers.Singleton(...)
    # guild_workflow = providers.Singleton(...)


class TestContainer(Container):
    """Test container with mocked dependencies."""

    # Override with test implementations
    cache = providers.Singleton(
        MemoryCache,
        max_size=100
    )

    # Override settings for testing
    settings = providers.Singleton(
        ConfigLoader.load_config,
        overrides={
            "DEBUG": "true",
            "DB_URL": "sqlite+aiosqlite:///:memory:",
            "CACHE_REDIS_URL": "memory://",
        }
    )


# Global container instance
_container: Optional[Container] = None


def get_container() -> Container:
    """Get the global container instance."""
    global _container
    if _container is None:
        _container = Container()
        settings = ConfigLoader.load_config()
        # Convert settings to dict for container config
        config_dict = {
            "api": {
                "client_id": settings.api.client_id,
                "client_secret": settings.api.client_secret,
                "region": settings.api.region,
                "locale": settings.api.locale,
                "rate_limit": settings.api.rate_limit,
            },
            "cache": {
                "redis_url": settings.cache.redis_url,
                "default_ttl": settings.cache.default_ttl,
            },
            "database": {
                "url": settings.database.url,
                "pool_size": settings.database.pool_size,
            }
        }
        _container.config.from_dict(config_dict)
    return _container


def set_container(container: Container) -> None:
    """Set the global container instance."""
    global _container
    _container = container


async def initialize_container(test_mode: bool = False) -> Container:
    """
    Initialize the container with all dependencies.

    Args:
        test_mode: Whether to use test configuration

    Returns:
        Initialized container
    """
    if test_mode:
        container = TestContainer()
    else:
        container = Container()

    # Load configuration
    settings = ConfigLoader.load_config()
    container.config.from_dict(settings.__dict__)

    # Initialize infrastructure components
    cache = container.cache()
    await cache.initialize()

    # Set global container
    set_container(container)

    logger.info(
        f"Container initialized in {'test' if test_mode else 'production'} mode"
    )

    return container


async def shutdown_container() -> None:
    """Shutdown the container and cleanup resources."""
    container = get_container()

    if container:
        # Shutdown cache
        cache = container.cache()
        if hasattr(cache, 'shutdown'):
            await cache.shutdown()

        # Clear container
        set_container(None)

        logger.info("Container shutdown complete")


# Wire the modules that will use DI
def wire_modules():
    """Wire modules for dependency injection."""
    container = get_container()

    modules_to_wire = [
        # Add module paths as we implement them
        # "wow_guild_analytics.application.services",
        # "wow_guild_analytics.presentation.api",
        # "wow_guild_analytics.adapters",
    ]

    container.wire(modules=modules_to_wire)
    logger.info(f"Wired {len(modules_to_wire)} modules for DI")
