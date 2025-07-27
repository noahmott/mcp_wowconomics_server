"""
Application Settings

Configuration classes using Pydantic for validation.
"""

from typing import Dict, Optional, Any
from pydantic import validator, Field
from pydantic_settings import BaseSettings


class APIConfig(BaseSettings):
    """API configuration settings."""

    blizzard_client_id: str = Field(
        ...,
        description="Blizzard API client ID"
    )
    blizzard_client_secret: str = Field(
        ...,
        description="Blizzard API client secret"
    )
    blizzard_region: str = Field(
        default="us",
        description="Blizzard API region"
    )
    blizzard_locale: str = Field(
        default="en_US",
        description="Blizzard API locale"
    )

    # Rate limiting
    rate_limit_requests: int = Field(
        default=100,
        description="Max requests per time window"
    )
    rate_limit_window: int = Field(
        default=1,
        description="Time window in seconds"
    )

    # Game version
    wow_version: str = Field(
        default="classic",
        description="WoW version (classic or retail)"
    )

    class Config:
        env_prefix = "API_"
        case_sensitive = False

    @validator("blizzard_region")
    def validate_region(cls, v):
        """Validate region value."""
        valid_regions = {"us", "eu", "kr", "tw", "cn"}
        if v not in valid_regions:
            raise ValueError(
                f"Invalid region: {v}. Must be one of {valid_regions}"
            )
        return v


class DatabaseConfig(BaseSettings):
    """Database configuration settings."""

    url: str = Field(
        ...,
        description="Database connection URL"
    )
    pool_size: int = Field(
        default=20,
        description="Connection pool size"
    )
    max_overflow: int = Field(
        default=0,
        description="Max overflow connections"
    )
    echo: bool = Field(
        default=False,
        description="Echo SQL statements"
    )

    class Config:
        env_prefix = "DB_"
        case_sensitive = False

    @validator("url")
    def fix_postgres_url(cls, v):
        """Fix Heroku postgres URL format."""
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        return v


class CacheConfig(BaseSettings):
    """Cache configuration settings."""

    redis_url: str = Field(
        default="redis://localhost:6379",
        description="Redis connection URL"
    )

    # Default TTL values in seconds
    default_ttl: Dict[str, int] = Field(
        default={
            "guild": 1800,      # 30 minutes
            "member": 3600,     # 1 hour
            "raid": 3600,       # 1 hour
            "chart": 7200,      # 2 hours
            "api": 600,         # 10 minutes
            "auction": 3600,    # 1 hour
            "token": 1800,      # 30 minutes
        },
        description="Default TTL values by cache type"
    )

    # Cache prefixes
    cache_prefixes: Dict[str, str] = Field(
        default={
            "guild": "guild:",
            "member": "member:",
            "raid": "raid:",
            "chart": "chart:",
            "api": "api:",
            "auction": "auction:",
            "token": "token:",
        },
        description="Cache key prefixes by type"
    )

    class Config:
        env_prefix = "CACHE_"
        case_sensitive = False


class WorkerConfig(BaseSettings):
    """Worker configuration settings."""

    # Scheduler settings
    update_interval: int = Field(
        default=3600,
        description="Update interval in seconds"
    )
    max_realms_per_update: int = Field(
        default=5,
        description="Max realms to update per run"
    )
    max_items_per_realm: int = Field(
        default=200,
        description="Max items to track per realm"
    )

    # Resource limits
    max_execution_time: int = Field(
        default=300,
        description="Max execution time in seconds"
    )
    min_seconds_between_updates: int = Field(
        default=60,
        description="Min time between updates"
    )

    class Config:
        env_prefix = "WORKER_"
        case_sensitive = False


class Settings(BaseSettings):
    """Main application settings."""

    # Application info
    app_name: str = Field(
        default="WoW Guild Analytics",
        description="Application name"
    )
    app_version: str = Field(
        default="2.0.0",
        description="Application version"
    )
    env: str = Field(
        default="development",
        description="Environment"
    )
    debug: bool = Field(
        default=False,
        description="Debug mode"
    )

    # API settings (mapped from environment)
    class APIConfig(BaseSettings):
        client_id: str = Field(alias="BLIZZARD_CLIENT_ID")
        client_secret: str = Field(alias="BLIZZARD_CLIENT_SECRET")
        region: str = Field(default="eu", alias="BLIZZARD_REGION")
        locale: str = Field(default="en_GB", alias="BLIZZARD_LOCALE")
        wow_version: str = Field(default="retail", alias="WOW_VERSION")
        oauth_url: str = Field(default="https://oauth.battle.net/token")
        api_url: str = Field(default="https://eu.api.blizzard.com")
        rate_limit: int = Field(default=100)
        timeout: int = Field(default=30)

        class Config:
            populate_by_name = True
            env_file = ".env"
            env_file_encoding = "utf-8"
            case_sensitive = False
            extra = "ignore"

    # Database settings
    class DatabaseConfig(BaseSettings):
        url: str = Field(alias="DATABASE_URL")
        echo: bool = Field(default=False)
        pool_size: int = Field(default=20)
        max_overflow: int = Field(default=0)

        class Config:
            populate_by_name = True
            env_file = ".env"
            env_file_encoding = "utf-8"
            case_sensitive = False
            extra = "ignore"

    # Cache settings
    class CacheConfig(BaseSettings):
        redis_url: str = Field(default="redis://localhost:6379", alias="REDIS_URL")
        default_ttl: int = Field(default=300)
        key_prefix: str = Field(default="wow")

        class Config:
            populate_by_name = True
            env_file = ".env"
            env_file_encoding = "utf-8"
            case_sensitive = False
            extra = "ignore"

    # Server settings
    class ServerConfig(BaseSettings):
        host: str = Field(default="0.0.0.0")
        port: int = Field(default=8000)
        reload: bool = Field(default=False)
        workers: int = Field(default=1)

        class Config:
            populate_by_name = True
            env_file = ".env"
            env_file_encoding = "utf-8"
            case_sensitive = False
            extra = "ignore"

    api: APIConfig
    database: DatabaseConfig
    cache: CacheConfig
    server: ServerConfig

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env

    def __init__(self, **kwargs):
        # Create sub-configs from environment
        api_config = self.APIConfig()
        database_config = self.DatabaseConfig()
        cache_config = self.CacheConfig()
        server_config = self.ServerConfig()

        super().__init__(
            api=api_config,
            database=database_config,
            cache=cache_config,
            server=server_config,
            **kwargs
        )

    def is_production(self) -> bool:
        """Check if running in production mode."""
        return not self.debug

    def get_database_url(self) -> str:
        """Get database URL."""
        return self.database.url

    def get_redis_url(self) -> str:
        """Get Redis URL."""
        return self.cache.redis_url
