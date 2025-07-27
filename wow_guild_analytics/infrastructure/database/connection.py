"""
Database Connection Management

Handles database connections and session management.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    AsyncEngine,
    async_sessionmaker
)
from sqlalchemy.pool import NullPool

from ...core.config import Settings
from ...core.models import Base

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Manages database connections and sessions."""

    def __init__(self, database_url: str, echo: bool = False):
        """
        Initialize database connection.

        Args:
            database_url: Database connection URL
            echo: Whether to echo SQL statements
        """
        # Handle Heroku postgres URL format
        if database_url.startswith("postgres://"):
            database_url = database_url.replace(
                "postgres://", "postgresql+asyncpg://", 1
            )

        self.database_url = database_url
        self.echo = echo
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker] = None

    async def initialize(self) -> None:
        """Initialize the database engine and session factory."""
        try:
            # Create engine
            self._engine = create_async_engine(
                self.database_url,
                echo=self.echo,
                pool_size=20,
                max_overflow=0,
                pool_pre_ping=True,  # Verify connections
                pool_recycle=3600,   # Recycle connections after 1 hour
            )

            # Create session factory
            self._session_factory = async_sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False
            )

            # Test connection
            async with self._engine.begin() as conn:
                from sqlalchemy import text
                await conn.run_sync(lambda c: c.execute(text("SELECT 1")))

            logger.info("Database connection initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    async def create_tables(self) -> None:
        """Create all database tables."""
        if not self._engine:
            raise RuntimeError("Database not initialized")

        try:
            async with self._engine.begin() as conn:
                # Import all models to ensure they're registered
                from ...domain.guild.models import Guild, GuildCache
                from ...domain.market.models import (
                    AuctionSnapshot,
                    TokenPriceHistory,
                    RealmStatus
                )
                from ..database.models import WoWDataCache, DataCollectionLog

                # Create tables
                await conn.run_sync(Base.metadata.create_all)

            logger.info("Database tables created successfully")

        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            raise

    async def drop_tables(self) -> None:
        """Drop all database tables."""
        if not self._engine:
            raise RuntimeError("Database not initialized")

        try:
            async with self._engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)

            logger.info("Database tables dropped")

        except Exception as e:
            logger.error(f"Failed to drop tables: {e}")
            raise

    async def shutdown(self) -> None:
        """Shutdown database connection."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("Database connection shutdown")

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get a database session.

        Yields:
            Database session
        """
        if not self._session_factory:
            raise RuntimeError("Database not initialized")

        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def health_check(self) -> bool:
        """Check database health."""
        if not self._engine:
            return False

        try:
            async with self._engine.connect() as conn:
                from sqlalchemy import text
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    @property
    def engine(self) -> Optional[AsyncEngine]:
        """Get the database engine."""
        return self._engine

    @property
    def session_factory(self) -> Optional[async_sessionmaker]:
        """Get the session factory."""
        return self._session_factory


# Global database instance
_database: Optional[DatabaseConnection] = None


async def initialize_database(settings: Settings) -> DatabaseConnection:
    """
    Initialize global database connection.

    Args:
        settings: Application settings

    Returns:
        Database connection instance
    """
    global _database

    if _database is None:
        _database = DatabaseConnection(
            database_url=settings.database.url,
            echo=settings.database.echo
        )
        await _database.initialize()

        # Only create tables if they don't exist
        try:
            await _database.create_tables()
        except Exception as e:
            # Ignore errors if tables already exist
            if "already exists" not in str(e):
                logger.error(f"Failed to create tables: {e}")
                raise

    return _database


async def get_database() -> DatabaseConnection:
    """Get global database instance."""
    if _database is None:
        raise RuntimeError("Database not initialized")
    return _database


async def shutdown_database() -> None:
    """Shutdown global database connection."""
    global _database

    if _database:
        await _database.shutdown()
        _database = None


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get a database session from global connection.

    Yields:
        Database session
    """
    db = await get_database()
    async with db.get_session() as session:
        yield session
