"""
Configuration management for WoW Guild MCP Server
"""

import os
from typing import Optional
try:
    from pydantic import BaseSettings, Field
except ImportError:
    from pydantic.v1 import BaseSettings, Field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Blizzard API Settings
    blizzard_client_id: str = Field(..., env="BLIZZARD_CLIENT_ID")
    blizzard_client_secret: str = Field(..., env="BLIZZARD_CLIENT_SECRET")
    blizzard_region: str = Field("us", env="BLIZZARD_REGION")
    blizzard_locale: str = Field("en_US", env="BLIZZARD_LOCALE")
    wow_version: str = Field("retail", env="WOW_VERSION")
    
    # Redis Settings
    redis_url: Optional[str] = Field(None, env="REDIS_URL")
    
    # Supabase Settings
    supabase_url: Optional[str] = Field(None, env="SUPABASE_URL")
    supabase_key: Optional[str] = Field(None, env="SUPABASE_KEY")
    
    # OpenAI Settings
    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4o-mini", env="OPENAI_MODEL")
    
    # Server Settings
    port: int = Field(8000, env="PORT")
    host: str = Field("0.0.0.0", env="HOST")
    
    # API Timeout Settings
    api_timeout_total: int = Field(300, env="API_TIMEOUT_TOTAL")
    api_timeout_connect: int = Field(10, env="API_TIMEOUT_CONNECT")
    api_timeout_read: int = Field(60, env="API_TIMEOUT_READ")
    
    # Feature Flags
    enable_redis_caching: bool = Field(True, env="ENABLE_REDIS_CACHING")
    enable_supabase_logging: bool = Field(True, env="ENABLE_SUPABASE_LOGGING")
    enable_ai_analysis: bool = Field(True, env="ENABLE_AI_ANALYSIS")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()