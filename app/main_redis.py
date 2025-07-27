"""
WoW Guild Analysis MCP Server - Main Application with Redis
"""

import os
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import redis.asyncio as aioredis
import time

from .mcp_server_redis import setup_mcp_server
from .services.activity_logger import initialize_activity_logger, get_activity_logger
from .services.supabase_streaming import initialize_streaming_service

# Configure logging for Docker compatibility
import sys

log_level = logging.DEBUG if os.getenv("DEBUG", "false").lower() == "true" else logging.INFO

logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),  # Ensure logs go to stdout for Docker
    ],
    force=True  # Override any existing logging configuration
)

logger = logging.getLogger(__name__)

# Global Redis client
redis_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global redis_client
    
    logger.info("Starting WoW Guild Analysis MCP Server with Redis...")
    
    # Initialize Redis connection
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # Configure SSL for Heroku Redis (uses self-signed certificates)
    ssl_config = None
    if redis_url.startswith("rediss://"):
        import ssl
        ssl_config = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_config.check_hostname = False
        ssl_config.verify_mode = ssl.CERT_NONE
        logger.info("Configuring Redis with TLS for Heroku")
    
    redis_client = await aioredis.from_url(
        redis_url,
        encoding="utf-8",
        decode_responses=False,  # We'll handle decoding ourselves
        max_connections=50,
        ssl=ssl_config if ssl_config else None
    )
    
    # Test Redis connection
    try:
        await redis_client.ping()
        logger.info(f"Connected to Redis at {redis_url}")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise
    
    # Store Redis client in app state
    app.state.redis = redis_client
    
    # Initialize activity logger
    try:
        app.state.activity_logger = await initialize_activity_logger(redis_client)
        logger.info("Activity logger initialized")
    except Exception as e:
        logger.error(f"Failed to initialize activity logger: {e}")
        raise
    
    # Initialize Supabase streaming service (optional - continues without Supabase if fails)
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if supabase_url and supabase_key:
        try:
            app.state.supabase_streaming = await initialize_streaming_service(redis_client)
            logger.info("Supabase streaming service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase streaming service: {e}")
            logger.error(f"SUPABASE_URL: {supabase_url[:20]}..." if supabase_url else "SUPABASE_URL: None")
            logger.error(f"SUPABASE_KEY: {'SET' if supabase_key else 'NOT SET'}")
            app.state.supabase_streaming = None
    else:
        logger.warning("Supabase environment variables not set - logging to Supabase disabled")
        logger.warning(f"SUPABASE_URL: {'SET' if supabase_url else 'NOT SET'}")
        logger.warning(f"SUPABASE_KEY: {'SET' if supabase_key else 'NOT SET'}")
        app.state.supabase_streaming = None
    
    yield
    
    # Cleanup
    logger.info("Shutting down WoW Guild Analysis MCP Server...")
    
    # Stop Supabase streaming service
    if hasattr(app.state, 'supabase_streaming') and app.state.supabase_streaming:
        try:
            await app.state.supabase_streaming.stop_streaming()
            logger.info("Supabase streaming service stopped")
        except Exception as e:
            logger.error(f"Error stopping Supabase streaming: {e}")
    
    if redis_client:
        await redis_client.close()


# Create FastAPI application
app = FastAPI(
    title="WoW Guild Analysis MCP Server",
    description="AI-powered World of Warcraft guild analytics MCP server with Redis staging",
    version="2.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request timing and activity logging middleware
@app.middleware("http")
async def activity_logging_middleware(request: Request, call_next):
    """Add request processing time and activity logging"""
    start_time = time.time()
    
    # Log request if it's an MCP request
    session_id = request.headers.get("mcp-session-id")
    user_agent = request.headers.get("user-agent")
    client_ip = request.client.host if hasattr(request, 'client') and request.client else None
    
    # Process request
    response = await call_next(request)
    
    # Calculate processing time
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    
    # Log activity for MCP requests - only for requests without session_id
    # (detailed tool calls are logged by the MCP endpoint itself)
    if hasattr(app.state, 'activity_logger') and request.url.path.startswith('/mcp') and not session_id:
        try:
            activity_logger = app.state.activity_logger
            # Log general MCP access for anonymous requests only
            await activity_logger.log_activity(
                session_id="anonymous", 
                activity_type="mcp_access",
                metadata={
                    "path": str(request.url.path),
                    "method": request.method,
                    "user_agent": user_agent,
                    "client_ip": client_ip,
                    "duration_ms": process_time * 1000
                }
            )
        except Exception as e:
            logger.error(f"Error in activity logging: {e}")
    
    return response


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check Redis connection
        if hasattr(app.state, 'redis'):
            await app.state.redis.ping()
            redis_status = "healthy"
        else:
            redis_status = "not connected"
            
        return {
            "status": "healthy",
            "service": "wow-guild-mcp",
            "version": "2.0.0",
            "redis": redis_status
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "wow-guild-mcp",
            "error": str(e)
        }


# Redis stats endpoint
@app.get("/redis/stats")
async def redis_stats():
    """Get Redis statistics"""
    if not hasattr(app.state, 'redis'):
        return {"error": "Redis not connected"}
    
    try:
        # Get Redis info
        info = await app.state.redis.info()
        
        # Get key count by pattern
        key_stats = {}
        patterns = [
            "wow:cache:*",
            "wow:meta:*",
            "wow:stats:*",
            "wow:log:*",
            "wow:index:*"
        ]
        
        for pattern in patterns:
            count = 0
            async for _ in app.state.redis.scan_iter(match=pattern):
                count += 1
            key_type = pattern.split(':')[1]
            key_stats[key_type] = count
        
        return {
            "redis_version": info.get("redis_version", "unknown"),
            "used_memory_human": info.get("used_memory_human", "unknown"),
            "connected_clients": info.get("connected_clients", 0),
            "total_commands_processed": info.get("total_commands_processed", 0),
            "uptime_in_seconds": info.get("uptime_in_seconds", 0),
            "key_statistics": key_stats,
            "total_keys": sum(key_stats.values())
        }
    except Exception as e:
        return {"error": f"Failed to get Redis stats: {str(e)}"}


# Clear cache endpoint
@app.post("/redis/clear-cache")
async def clear_cache(data_type: str = None):
    """Clear Redis cache"""
    if not hasattr(app.state, 'redis'):
        return {"error": "Redis not connected"}
    
    try:
        from .services.redis_staging import RedisDataStagingService
        staging = RedisDataStagingService(app.state.redis)
        
        count = await staging.clear_cache(data_type=data_type)
        
        return {
            "success": True,
            "cleared": count,
            "data_type": data_type or "all"
        }
    except Exception as e:
        return {"error": f"Failed to clear cache: {str(e)}"}


# Setup MCP server
setup_mcp_server(app)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "WoW Guild Analysis MCP Server",
        "version": "2.0.0",
        "storage": "Redis",
        "endpoints": {
            "health": "/health",
            "mcp": "/mcp",
            "redis_stats": "/redis/stats",
            "clear_cache": "/redis/clear-cache",
            "docs": "/docs"
        }
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)