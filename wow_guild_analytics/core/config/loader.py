"""
Configuration Loader

Handles loading and validation of configuration.
"""

import os
import logging
from typing import Optional, Dict, Any
from pathlib import Path

from .settings import Settings

logger = logging.getLogger(__name__)


class ConfigLoader:
    """Loads and manages application configuration."""

    _instance: Optional['ConfigLoader'] = None
    _settings: Optional[Settings] = None

    def __new__(cls):
        """Singleton pattern implementation."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def load_config(
        cls,
        env_file: Optional[str] = None,
        overrides: Optional[Dict[str, Any]] = None
    ) -> Settings:
        """
        Load configuration from environment and files.

        Args:
            env_file: Path to .env file
            overrides: Dictionary of config overrides

        Returns:
            Loaded settings
        """
        if cls._settings is not None:
            return cls._settings

        # Set env file path if provided
        if env_file:
            os.environ["ENV_FILE"] = env_file

        # Apply overrides to environment
        if overrides:
            for key, value in overrides.items():
                os.environ[key.upper()] = str(value)

        try:
            # Load settings
            cls._settings = Settings()

            logger.info(
                f"Configuration loaded successfully "
                f"(debug={cls._settings.debug})"
            )

            # Log non-sensitive config info
            cls._log_config_info()

            return cls._settings

        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise

    @classmethod
    def get_settings(cls) -> Settings:
        """
        Get current settings instance.

        Returns:
            Current settings

        Raises:
            RuntimeError: If config not loaded
        """
        if cls._settings is None:
            raise RuntimeError(
                "Configuration not loaded. Call load_config() first."
            )
        return cls._settings

    @classmethod
    def reload_config(
        cls,
        env_file: Optional[str] = None,
        overrides: Optional[Dict[str, Any]] = None
    ) -> Settings:
        """
        Reload configuration.

        Args:
            env_file: Path to .env file
            overrides: Dictionary of config overrides

        Returns:
            Reloaded settings
        """
        cls._settings = None
        return cls.load_config(env_file, overrides)

    @classmethod
    def _log_config_info(cls) -> None:
        """Log non-sensitive configuration information."""
        if not cls._settings:
            return

        logger.info(f"App: {cls._settings.app_name} v{cls._settings.app_version}")
        logger.info(f"Server: {cls._settings.server.host}:{cls._settings.server.port}")
        logger.info(f"WoW Version: {cls._settings.api.wow_version}")
        logger.info(f"Region: {cls._settings.api.region}")
        logger.info(f"Database Pool Size: {cls._settings.database.pool_size}")
        logger.info(f"Rate Limit: {cls._settings.api.rate_limit}/s")

    @classmethod
    def validate_config(cls) -> bool:
        """
        Validate current configuration.

        Returns:
            True if config is valid
        """
        if not cls._settings:
            logger.error("No configuration loaded")
            return False

        # Check required fields
        required_checks = [
            (cls._settings.api.client_id, "Blizzard Client ID"),
            (cls._settings.api.client_secret, "Blizzard Client Secret"),
            (cls._settings.database.url, "Database URL"),
        ]

        for value, name in required_checks:
            if not value:
                logger.error(f"Missing required config: {name}")
                return False

        # Validate database URL format
        db_url = cls._settings.database.url
        if not any(db_url.startswith(prefix) for prefix in [
            "postgresql://", "postgresql+asyncpg://", "sqlite://", "sqlite+aiosqlite://"
        ]):
            logger.error(f"Invalid database URL format: {db_url}")
            return False

        return True

    @classmethod
    def get_env_info(cls) -> Dict[str, str]:
        """
        Get environment information.

        Returns:
            Environment info dict
        """
        return {
            "environment": "production" if cls._settings and cls._settings.is_production() else "development",
            "python_version": os.sys.version,
            "platform": os.sys.platform,
            "debug": str(cls._settings.debug) if cls._settings else "unknown",
        }


# Convenience function
def get_settings() -> Settings:
    """Get current settings instance."""
    return ConfigLoader.get_settings()
