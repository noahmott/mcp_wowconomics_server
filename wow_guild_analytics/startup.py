"""
Startup Script for Modular Architecture

Initializes all components and integrates with existing system.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from wow_guild_analytics.core.config import ConfigLoader
from wow_guild_analytics.core.container import (
    initialize_container,
    shutdown_container,
    get_container
)
from wow_guild_analytics.infrastructure.database import (
    initialize_database,
    shutdown_database
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def startup():
    """Initialize all components for the modular system."""
    try:
        logger.info("Starting modular WoW Guild Analytics system...")

        # Load configuration
        settings = ConfigLoader.load_config()
        logger.info(f"Configuration loaded (debug={settings.debug})")

        # Validate configuration
        if not ConfigLoader.validate_config():
            logger.error("Configuration validation failed")
            return False

        # Initialize dependency injection container
        container = await initialize_container(test_mode=settings.debug)
        logger.info("Dependency injection container initialized")

        # Initialize database
        await initialize_database(settings)
        logger.info("Database initialized")

        # Initialize cache
        cache = container.cache()
        if hasattr(cache, 'health_check'):
            health = await cache.health_check()
            logger.info(f"Cache health check: {health}")

        logger.info("Modular system startup complete")
        return True

    except Exception as e:
        logger.error(f"Startup failed: {e}", exc_info=True)
        return False


async def shutdown():
    """Shutdown all components gracefully."""
    try:
        logger.info("Shutting down modular system...")

        # Shutdown container (includes cache)
        await shutdown_container()

        # Shutdown database
        await shutdown_database()

        logger.info("Modular system shutdown complete")

    except Exception as e:
        logger.error(f"Shutdown error: {e}", exc_info=True)


async def health_check():
    """Check health of all components."""
    try:
        container = get_container()

        # Check cache
        cache = container.cache()
        cache_health = await cache.health_check()

        # Check database
        from wow_guild_analytics.infrastructure.database import get_database
        db = await get_database()
        db_health = await db.health_check()

        return {
            "status": "healthy" if (cache_health and db_health) else "unhealthy",
            "cache": cache_health,
            "database": db_health
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


async def migrate_existing_server():
    """
    Migrate existing MCP server to use modular components.

    This function patches the existing server to use our new
    modular components while maintaining compatibility.
    """
    try:
        logger.info("Migrating existing MCP server to modular architecture...")

        # Import existing server
        from app.mcp_server import WoWGuildMCPServer
        from wow_guild_analytics.presentation.mcp import ModularMCPServer

        # Monkey patch to use modular components
        original_init = WoWGuildMCPServer.__init__

        def new_init(self, app):
            # Call original init
            original_init(self, app)

            # Get container
            container = get_container()

            # Create modular server
            self._modular_server = ModularMCPServer(app, container)
            self._modular_server.set_mcp_instance(self.mcp)

            # Override methods to use modular implementations
            self._original_analyze_guild = self.analyze_guild_performance

            # Patch methods
            async def analyze_guild_wrapper(*args, **kwargs):
                return await self._modular_server.analyze_guild_performance(
                    *args, **kwargs
                )

            # Register wrapped function
            if hasattr(self.mcp, 'tools'):
                self.mcp.tools['analyze_guild_performance'] = analyze_guild_wrapper

            logger.info("MCP server migrated to use modular components")

        # Apply patch
        WoWGuildMCPServer.__init__ = new_init

        logger.info("Migration patch applied successfully")
        return True

    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        return False


async def main():
    """Main entry point for testing the modular system."""
    try:
        # Startup
        success = await startup()
        if not success:
            logger.error("Startup failed")
            sys.exit(1)

        # Run health check
        health = await health_check()
        logger.info(f"Health check result: {health}")

        # Migrate existing server
        if await migrate_existing_server():
            logger.info("System ready for use")

        # Keep running (for testing)
        logger.info("Press Ctrl+C to shutdown")
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("Shutdown requested")

    finally:
        # Cleanup
        await shutdown()


if __name__ == "__main__":
    asyncio.run(main())
