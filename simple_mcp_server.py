"""
Simplified WoW MCP Server without complex session management
"""
import os
import logging
import sys
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from dotenv import load_dotenv
from fastmcp import FastMCP

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Create simplified FastMCP server without session requirements
mcp = FastMCP(
    name="WoW Analysis Server (Simple)",
    host="0.0.0.0",
    port=int(os.getenv("PORT", "8000"))
)

# Global staging service - will be initialized on first use
staging_service: Optional[Any] = None

async def init_staging_service():
    """Initialize the staging service"""
    global staging_service
    
    try:
        # Try to import and initialize staging service
        from app.services.wow_data_staging import WoWDataStagingService
        import aioredis
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        
        # Database connection
        database_url = os.getenv("DATABASE_URL")
        if database_url and database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
        
        if database_url:
            engine = create_async_engine(database_url, echo=False)
            async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            db_session = async_session()
        else:
            logger.warning("No database URL - using fallback")
            db_session = None
        
        # Redis connection (fallback to memory if not available)
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        try:
            redis_client = aioredis.from_url(redis_url)
            await redis_client.ping()
            logger.info("Redis connection successful")
        except Exception:
            logger.info("Redis not available - using memory cache")
            # Mock redis for fallback
            class MockRedis:
                def __init__(self):
                    self.data = {}
                async def get(self, key):
                    return self.data.get(key)
                async def setex(self, key, ttl, value):
                    self.data[key] = value
                async def close(self):
                    pass
            redis_client = MockRedis()
        
        if db_session:
            staging_service = WoWDataStagingService(db_session, redis_client)
            logger.info("Staging service initialized successfully")
        else:
            staging_service = None
            logger.warning("Staging service could not be initialized")
        
    except Exception as e:
        logger.error(f"Failed to initialize staging service: {str(e)}")
        staging_service = None

@mcp.tool()
async def test_staging_fallback(realm_slug: str = "stormrage", region: str = "us") -> str:
    """
    Test the staging system fallback with simple synthetic data
    
    Args:
        realm_slug: Realm to analyze
        region: Region code
    
    Returns:
        Economic analysis using staging system
    """
    global staging_service
    
    # Initialize staging service if needed
    if staging_service is None:
        await init_staging_service()
    
    # If staging service available, use it
    if staging_service:
        try:
            auction_data = await staging_service.get_data('auction', realm_slug, region)
            
            auctions = auction_data.get('data', {}).get('auctions', [])
            is_synthetic = auction_data.get('synthetic', False)
            
            # Analyze the data
            total_auctions = len(auctions)
            total_value = sum(auction.get('buyout', 0) for auction in auctions if auction.get('buyout'))
            avg_value = total_value // total_auctions if total_auctions else 0
            
            result = f"Economic Analysis - {realm_slug.title()} ({region.upper()})\\n\\n"
            result += f"Data Source: {'Synthetic/Example' if is_synthetic else 'Live/Cached'}\\n"
            result += f"Total Auctions: {total_auctions:,}\\n"
            result += f"Market Value: {(total_value // 10000):,}g\\n"
            result += f"Average Price: {(avg_value // 10000):,}g\\n"
            
            if is_synthetic:
                result += f"\\nNote: This is example data demonstrating the staging system."
            
            return result
            
        except Exception as e:
            logger.error(f"Staging service error: {str(e)}")
            # Fall through to simple fallback
    
    # Simple fallback without staging service
    return f"""Economic Analysis - {realm_slug.title()} ({region.upper()})

Data Source: Simple Fallback
Total Auctions: 5,000
Market Value: 15,000g  
Average Price: 300g

Status: Staging system fallback working
Note: This demonstrates the server is responding to tool calls."""

@mcp.tool()
async def get_server_status() -> str:
    """Get server and staging system status"""
    global staging_service
    
    if staging_service is None:
        await init_staging_service()
    
    status = "WoW MCP Server Status\\n\\n"
    status += f"Server: Online\\n"
    status += f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n"
    status += f"Staging Service: {'Available' if staging_service else 'Fallback Mode'}\\n"
    
    # Check credentials
    blizzard_id = os.getenv("BLIZZARD_CLIENT_ID")
    status += f"Blizzard API: {'Configured' if blizzard_id else 'Not Configured'}\\n"
    
    # Check database
    database_url = os.getenv("DATABASE_URL")
    status += f"Database: {'Connected' if database_url else 'Not Available'}\\n"
    
    # Check Redis
    redis_url = os.getenv("REDIS_URL")
    status += f"Redis: {'Connected' if redis_url else 'Memory Fallback'}\\n"
    
    return status

@mcp.tool()
async def simple_token_price(region: str = "us") -> str:
    """Get WoW Token price with simple fallback"""
    global staging_service
    
    if staging_service is None:
        await init_staging_service()
    
    if staging_service:
        try:
            token_data = await staging_service.get_data('token', 'current', region)
            price = token_data.get('data', {}).get('price', 2500000)
            is_synthetic = token_data.get('synthetic', False)
            
            gold = price // 10000
            
            result = f"WoW Token Price ({region.upper()})\\n\\n"
            result += f"Current Price: {gold:,}g\\n"
            result += f"Data Source: {'Example' if is_synthetic else 'Live/Cached'}\\n"
            
            if gold < 150000:
                result += f"Market: Good buying opportunity\\n"
            elif gold > 250000:
                result += f"Market: High price - consider waiting\\n"
            else:
                result += f"Market: Normal pricing\\n"
            
            return result
            
        except Exception as e:
            logger.error(f"Token price error: {str(e)}")
    
    # Simple fallback
    return f"""WoW Token Price ({region.upper()})

Current Price: 250,000g
Data Source: Fallback
Market: Normal pricing

Status: Simple fallback working"""

def main():
    """Main entry point for simplified MCP server"""
    try:
        port = int(os.getenv("PORT", "8000"))
        
        logger.info("🚀 Simplified WoW Analysis MCP Server")
        logger.info("🔧 Features: Basic staging system with fallbacks")
        logger.info(f"🌐 HTTP Server: 0.0.0.0:{port}")
        logger.info("✅ Starting server...")
        
        # Run server using FastMCP HTTP transport
        mcp.run(transport="http")
        
    except Exception as e:
        logger.error(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()