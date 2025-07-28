"""
Centralized service management for WoW Guild MCP Server
"""

import os
import logging
import redis.asyncio as aioredis
from typing import Optional
from datetime import datetime, timezone

from ..services.activity_logger import ActivityLogger, initialize_activity_logger
from ..services.supabase_client import SupabaseRealTimeClient
from ..services.supabase_streaming import initialize_streaming_service

logger = logging.getLogger(__name__)


class ServiceManager:
    """Manages initialization and access to all application services"""
    
    def __init__(self):
        self.redis_client: Optional[aioredis.Redis] = None
        self.activity_logger: Optional[ActivityLogger] = None
        self.supabase_client: Optional[SupabaseRealTimeClient] = None
        self.streaming_service = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize all services"""
        if self._initialized:
            logger.debug("Services already initialized")
            return
        
        try:
            # Initialize Redis
            await self._initialize_redis()
            
            # Initialize activity logger
            if self.redis_client:
                self.activity_logger = await initialize_activity_logger(self.redis_client)
                logger.info("Activity logger initialized")
            
            # Initialize Supabase services
            await self._initialize_supabase()
            
            self._initialized = True
            logger.info("All services initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
            raise
    
    async def _initialize_redis(self):
        """Initialize Redis connection"""
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            logger.warning("REDIS_URL not set - Redis features will be disabled")
            return
        
        logger.info("Initializing Redis connection...")
        
        # Check if this is a Heroku Redis URL (rediss://)
        if redis_url.startswith("rediss://"):
            logger.info("Configuring Redis with TLS for Heroku")
            # Heroku Redis requires TLS but uses self-signed certs
            self.redis_client = await aioredis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=False,
                max_connections=50,
                ssl_cert_reqs=None  # Disable SSL verification for self-signed certs
            )
        else:
            self.redis_client = await aioredis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=False,
                max_connections=50
            )
        
        # Test Redis connection
        await self.redis_client.ping()
        logger.info(f"Connected to Redis")
    
    async def _initialize_supabase(self):
        """Initialize Supabase services"""
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            logger.warning("Supabase environment variables not set - logging to Supabase disabled")
            return
        
        try:
            # Initialize direct Supabase client
            self.supabase_client = SupabaseRealTimeClient(supabase_url, supabase_key)
            await self.supabase_client.initialize()
            logger.info("Supabase direct client initialized successfully")
            
            # Initialize streaming service
            if self.redis_client:
                self.streaming_service = await initialize_streaming_service(self.redis_client)
                logger.info("Supabase streaming service initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize Supabase services: {e}")
            self.supabase_client = None
            self.streaming_service = None
    
    async def close(self):
        """Close all service connections"""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Redis connection closed")
        
        if self.supabase_client:
            # Supabase client cleanup if needed
            pass
        
        self._initialized = False
    
    def is_initialized(self) -> bool:
        """Check if services are initialized"""
        return self._initialized


# Global service manager instance
service_manager = ServiceManager()


async def get_service_manager() -> ServiceManager:
    """Get or initialize the global service manager"""
    if not service_manager.is_initialized():
        await service_manager.initialize()
    return service_manager