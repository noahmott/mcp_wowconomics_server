"""
Enhanced WoW Analysis MCP Server with Data Staging - Offline Capable
"""
import os
import logging
import sys
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dotenv import load_dotenv
from fastmcp import FastMCP
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Create FastMCP server
mcp = FastMCP(
    name="WoW Analysis Server (Staging)",
    host="0.0.0.0",
    port=int(os.getenv("PORT", "8000"))
)

# Import components
from app.services.wow_data_staging import WoWDataStagingService

# Global staging service - will be initialized on startup
staging_service: Optional[WoWDataStagingService] = None

async def init_staging_service():
    """Initialize the staging service with database and Redis connections"""
    global staging_service
    
    try:
        # Database connection
        database_url = os.getenv("DATABASE_URL")
        if database_url and database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
        
        engine = create_async_engine(database_url, echo=False)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        # Redis connection
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        redis_client = aioredis.from_url(redis_url)
        
        # Create staging service
        db_session = async_session()
        staging_service = WoWDataStagingService(db_session, redis_client)
        
        logger.info("✅ Staging service initialized successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize staging service: {str(e)}")
        staging_service = None

@mcp.tool()
async def analyze_realm_economy_cached(realm_slug: str, region: str = "us") -> str:
    """
    Comprehensive realm economic analysis using intelligent caching system.
    Works offline with cached data when API is restricted.
    
    Args:
        realm_slug: Realm slug (e.g., 'stormrage')
        region: Region code
    
    Returns:
        Economic health report with market trends and caching status
    """
    if not staging_service:
        return "❌ Staging service not available. Please check server configuration."
    
    try:
        # Get cached auction data
        auction_data = await staging_service.get_data('auction', realm_slug, region)
        realm_data = await staging_service.get_data('realm', realm_slug, region)
        
        realm_name = realm_data.get('data', {}).get('name', realm_slug.title())
        is_synthetic = auction_data.get('synthetic', False)
        data_age = auction_data.get('age_hours', 0)
        
        result = f"Economic Health Report - {realm_name}\\n\\n"
        
        # Data source indicator
        if is_synthetic:
            result += f"📊 **Data Source**: Example data (API currently restricted)\\n"
        else:
            result += f"📊 **Data Source**: Cached API data ({data_age:.1f} hours old)\\n"
        
        result += f"🌍 **Region**: {region.upper()}\\n\\n"
        
        auctions = auction_data.get('data', {}).get('auctions', [])
        
        if auctions:
            # Economic analysis
            total_auctions = len(auctions)
            total_value = sum(auction.get('buyout', 0) for auction in auctions if auction.get('buyout'))
            avg_value = total_value // total_auctions if total_auctions else 0
            
            # Economic health scoring
            if total_auctions > 15000:
                activity_level = "Very High"
                health_score = "Excellent"
            elif total_auctions > 10000:
                activity_level = "High"
                health_score = "Good"
            elif total_auctions > 5000:
                activity_level = "Medium"
                health_score = "Fair"
            else:
                activity_level = "Low"
                health_score = "Poor"
            
            result += f"**Economic Health: {health_score}**\\n"
            result += f"• Market Activity: {activity_level} ({total_auctions:,} auctions)\\n"
            result += f"• Total Market Value: {(total_value // 10000):,}g\\n"
            result += f"• Average Auction Price: {(avg_value // 10000):,}g\\n"
            result += f"• Market Liquidity: {'High' if total_auctions > 10000 else 'Medium' if total_auctions > 5000 else 'Low'}\\n"
            
            # Market insights based on data source
            result += f"\\n**Market Insights:**\\n"
            if health_score == "Excellent":
                result += f"• Strong economy with high liquidity - good for all trading activities\\n"
                result += f"• Competitive pricing - margins may be tight but volume is high\\n"
            elif health_score == "Good":
                result += f"• Healthy market with decent opportunities\\n"
                result += f"• Good balance of supply and demand\\n"
            else:
                result += f"• Limited market activity - higher margins possible but lower volume\\n"
                result += f"• Consider cross-realm arbitrage opportunities\\n"
            
            if is_synthetic:
                result += f"\\n**Note**: Analysis demonstrates system capabilities. Live data requires API access.\\n"
        else:
            result += f"**Economic Health: No Data Available**\\n"
            result += f"• No auction data available for analysis\\n"
        
        return result
        
    except Exception as e:
        logger.error(f"Error in cached realm economy analysis: {str(e)}")
        return f"Error analyzing realm economy: {str(e)}"

@mcp.tool()
async def analyze_guild_cached(realm: str, guild_name: str, region: str = "us") -> str:
    """
    Analyze guild performance using cached data with intelligent fallbacks.
    
    Args:
        realm: Server realm (e.g., 'stormrage')
        guild_name: Guild name
        region: Region code
    
    Returns:
        Guild analysis results with caching status
    """
    if not staging_service:
        return "❌ Staging service not available. Please check server configuration."
    
    try:
        cache_key = f"{realm}:{guild_name}"
        guild_data = await staging_service.get_data('guild', cache_key, region)
        
        is_synthetic = guild_data.get('synthetic', False)
        data_age = guild_data.get('age_hours', 0)
        
        result = f"Guild Analysis Results for {guild_name}\\n\\n"
        
        # Data source indicator
        if is_synthetic:
            result += f"📊 **Data Source**: Example data (API currently restricted)\\n"
        else:
            result += f"📊 **Data Source**: Cached API data ({data_age:.1f} hours old)\\n"
        
        guild_info = guild_data.get('data', {}).get('guild_info', {})
        members = guild_data.get('data', {}).get('members_data', [])
        
        result += f"\\n**Guild Summary:**\\n"
        result += f"• Name: {guild_info.get('name', guild_name)}\\n"
        result += f"• Realm: {guild_info.get('realm', {}).get('slug', realm)}\\n"
        result += f"• Member Count: {len(members)}\\n"
        result += f"• Achievement Points: {guild_info.get('achievement_points', 0):,}\\n"
        
        if members:
            # Calculate performance metrics
            levels = [m.get('level', 0) for m in members]
            item_levels = [m.get('equipment_summary', {}).get('average_item_level', 0) for m in members]
            
            avg_level = sum(levels) / len(levels) if levels else 0
            avg_item_level = sum(item_levels) / len(item_levels) if item_levels else 0
            max_level_count = sum(1 for level in levels if level >= 80)
            
            result += f"\\n**Performance Metrics:**\\n"
            result += f"• Average Level: {avg_level:.1f}\\n"
            result += f"• Average Item Level: {avg_item_level:.1f}\\n"
            result += f"• Max Level Members: {max_level_count} ({(max_level_count/len(members)*100):.1f}%)\\n"
            
            # Activity assessment
            if max_level_count / len(members) > 0.8:
                activity_level = "Very High - Most members at endgame"
            elif max_level_count / len(members) > 0.5:
                activity_level = "High - Good mix of active players"
            else:
                activity_level = "Moderate - Many leveling members"
            
            result += f"• Activity Level: {activity_level}\\n"
        
        if is_synthetic:
            result += f"\\n**Note**: This demonstrates guild analysis capabilities. Live data requires API access.\\n"
        
        return result
        
    except Exception as e:
        logger.error(f"Error in cached guild analysis: {str(e)}")
        return f"Error analyzing guild: {str(e)}"

@mcp.tool()
async def get_wow_token_price_cached(region: str = "us") -> str:
    """
    Get WoW Token price with intelligent caching and market analysis.
    
    Args:
        region: Region (us, eu, kr, tw, cn)
    
    Returns:
        Token price with market analysis and caching status
    """
    if not staging_service:
        return "❌ Staging service not available. Please check server configuration."
    
    try:
        token_data = await staging_service.get_data('token', 'current', region)
        
        is_synthetic = token_data.get('synthetic', False)
        data_age = token_data.get('age_hours', 0)
        
        price = token_data.get('data', {}).get('price', 0)
        last_updated = token_data.get('data', {}).get('last_updated_timestamp', 0)
        
        # Convert gold to readable format
        gold = price // 10000
        silver = (price % 10000) // 100
        copper = price % 100
        
        result = f"WoW Token Market Analysis ({region.upper()}):\\n\\n"
        
        # Data source indicator
        if is_synthetic:
            result += f"📊 **Data Source**: Example price (API currently restricted)\\n"
        else:
            result += f"📊 **Data Source**: Cached API data ({data_age:.1f} hours old)\\n"
        
        result += f"\\n**Current Price:**\\n"
        result += f"• {gold:,}g {silver}s {copper}c\\n"
        result += f"• Raw Value: {price:,} copper\\n"
        
        if not is_synthetic:
            result += f"• Last Updated: {last_updated}\\n"
        
        # Market analysis based on price ranges
        if gold < 100000:
            market_trend = "Very Low - Excellent buying opportunity"
            recommendation = "Strong Buy - Consider purchasing multiple tokens"
        elif gold < 150000:
            market_trend = "Low - Good buying opportunity"
            recommendation = "Buy - Good value for Battle.net balance"
        elif gold < 200000:
            market_trend = "Moderate - Fair pricing"
            recommendation = "Hold - Wait for better prices unless needed"
        elif gold < 300000:
            market_trend = "High - Consider selling gold instead"
            recommendation = "Avoid - High price, better to earn gold in-game"
        else:
            market_trend = "Very High - Peak pricing"
            recommendation = "Strong Avoid - Wait for price correction"
        
        result += f"\\n**Market Assessment:**\\n"
        result += f"• Price Level: {market_trend}\\n"
        result += f"• Recommendation: {recommendation}\\n"
        
        # Regional context
        result += f"\\n**Market Context:**\\n"
        if region.lower() == "us":
            result += f"• US servers typically have higher token prices\\n"
            result += f"• Best buying times: Tuesday maintenance, expansion lulls\\n"
        elif region.lower() == "eu":
            result += f"• EU prices often 10-20% lower than US\\n"
            result += f"• Wednesday reset affects token demand\\n"
        
        result += f"• Tokens are account-wide across {region.upper()} region\\n"
        result += f"• Price updates approximately every hour\\n"
        
        if is_synthetic:
            result += f"\\n**Note**: Example pricing demonstrates market analysis capabilities.\\n"
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting cached token price: {str(e)}")
        return f"Failed to get WoW Token price: {str(e)}"

@mcp.tool()
async def seed_wow_data(data_types: str, targets: str, region: str = "us") -> str:
    """
    Manually seed WoW data when API is accessible. This tool attempts to collect
    and cache live data for later offline use.
    
    Args:
        data_types: Comma-separated data types (auction,guild,realm,token)
        targets: Comma-separated targets (realm slugs, guild names)
        region: Region code
    
    Returns:
        Data seeding results and statistics
    """
    if not staging_service:
        return "❌ Staging service not available. Please check server configuration."
    
    try:
        # Parse inputs
        types_list = [t.strip() for t in data_types.split(',')]
        targets_list = [t.strip() for t in targets.split(',')]
        
        result = f"🌱 **Data Seeding Results** ({region.upper()})\\n\\n"
        
        # Attempt to seed data
        seed_results = await staging_service.seed_data(types_list, targets_list, region)
        
        result += f"**✅ Successful Collections:**\\n"
        if seed_results['success']:
            for success in seed_results['success']:
                result += f"• {success}\\n"
        else:
            result += f"• None - API access may be restricted\\n"
        
        result += f"\\n**❌ Failed Collections:**\\n"
        if seed_results['failed']:
            for failure in seed_results['failed']:
                result += f"• {failure}\\n"
        else:
            result += f"• None\\n"
        
        result += f"\\n**📊 Summary:**\\n"
        result += f"• Total Records Collected: {seed_results['total_records']:,}\\n"
        result += f"• Success Rate: {len(seed_results['success'])}/{len(seed_results['success']) + len(seed_results['failed'])}\\n"
        
        if seed_results['total_records'] == 0:
            result += f"\\n**💡 Note**: API access appears restricted. The system will use cached data and examples.\\n"
        else:
            result += f"\\n**✨ Success**: Data cached for offline analysis!\\n"
        
        return result
        
    except Exception as e:
        logger.error(f"Error seeding data: {str(e)}")
        return f"Error during data seeding: {str(e)}"

@mcp.tool()
async def get_cache_statistics() -> str:
    """
    Get statistics about cached WoW data and system performance.
    
    Returns:
        Cache statistics and system health information
    """
    if not staging_service:
        return "❌ Staging service not available. Please check server configuration."
    
    try:
        stats = await staging_service.get_cache_stats()
        
        if 'error' in stats:
            return f"Error getting cache statistics: {stats['error']}"
        
        result = f"📊 **WoW Data Cache Statistics**\\n\\n"
        
        result += f"**Cached Data Types:**\\n"
        for data_type, count in stats.get('cache_entries', {}).items():
            latest = stats.get('latest_updates', {}).get(data_type)
            if latest:
                age = datetime.utcnow() - latest
                age_str = f"{age.days}d {age.seconds//3600}h" if age.days > 0 else f"{age.seconds//3600}h {(age.seconds%3600)//60}m"
                result += f"• **{data_type.title()}**: {count:,} entries (latest: {age_str} ago)\\n"
            else:
                result += f"• **{data_type.title()}**: {count:,} entries\\n"
        
        total_items = stats.get('total_cached_items', 0)
        result += f"\\n**Total Cached Items**: {total_items:,}\\n"
        
        if total_items > 0:
            result += f"\\n**✅ System Status**: Operational with cached data\\n"
            result += f"**💡 Capability**: Full offline analysis available\\n"
        else:
            result += f"\\n**⚠️ System Status**: Limited to example data\\n"
            result += f"**💡 Suggestion**: Use 'seed_wow_data' when API access is available\\n"
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting cache statistics: {str(e)}")
        return f"Error retrieving cache statistics: {str(e)}"

@mcp.tool()
async def optimize_event_economics_cached(event_type: str, realm_slug: str, region: str = "us") -> str:
    """
    Provide market optimization strategies for WoW seasonal events using cached data.
    
    Args:
        event_type: Event name (darkmoon-faire, timewalking, holiday)
        realm_slug: Realm slug
        region: Region code
        
    Returns:
        Event-specific market opportunities and preparation strategies
    """
    if not staging_service:
        return "❌ Staging service not available. Please check server configuration."
    
    try:
        # Get realm data for context
        realm_data = await staging_service.get_data('realm', realm_slug, region)
        realm_name = realm_data.get('data', {}).get('name', realm_slug.title())
        is_synthetic = realm_data.get('synthetic', False)
        
        result = f"Event Economic Optimization - {event_type.title()}\\n\\n"
        result += f"**Server**: {realm_name} ({region.upper()})\\n"
        
        if is_synthetic:
            result += f"📊 **Data Source**: Strategic analysis (API currently restricted)\\n"
        
        result += f"\\n"
        
        # Event-specific strategies (these work regardless of API access)
        if "darkmoon" in event_type.lower():
            result += f"**Darkmoon Faire Economic Strategy:**\\n"
            result += f"• **Pre-Event Preparation (1 week before):**\\n"
            result += f"  - Stock up on profession materials\\n"
            result += f"  - Buy cheap toys and pets for resale\\n"
            result += f"  - Prepare consumables for faire activities\\n"
            result += f"• **During Event:**\\n"
            result += f"  - Sell profession boost materials at premium\\n"
            result += f"  - List rare transmog items (higher traffic)\\n"
            result += f"  - Price consumables 20-30% higher\\n"
            result += f"• **Post-Event:**\\n"
            result += f"  - Buy cheap profession materials from other sellers\\n"
            result += f"  - Stock up for next month's faire\\n"
            
        elif "timewalking" in event_type.lower():
            result += f"**Timewalking Event Strategy:**\\n"
            result += f"• **High Demand Items:**\\n"
            result += f"  - Legacy enchanting materials\\n"
            result += f"  - Old expansion gems and consumables\\n"
            result += f"  - Transmog gear from relevant expansion\\n"
            result += f"• **Pricing Strategy:**\\n"
            result += f"  - Increase legacy item prices by 50-100%\\n"
            result += f"  - Stock consumables for timewalking dungeons\\n"
            result += f"• **Preparation Timeline:**\\n"
            result += f"  - 2 weeks before: Buy cheap legacy materials\\n"
            result += f"  - 3 days before: List items at premium prices\\n"
            
        elif "holiday" in event_type.lower() or "seasonal" in event_type.lower():
            result += f"**Seasonal Holiday Strategy:**\\n"
            result += f"• **Universal Holiday Items:**\\n"
            result += f"  - Cooking materials for achievement recipes\\n"
            result += f"  - Cheap pets/toys for gift-giving\\n"
            result += f"  - Transmog items matching holiday themes\\n"
            result += f"• **Market Timing:**\\n"
            result += f"  - Week 1: Highest prices due to achievement hunters\\n"
            result += f"  - Week 2+: Prices stabilize, volume remains high\\n"
            result += f"• **Post-Holiday Opportunity:**\\n"
            result += f"  - Buy holiday-specific items cheap for next year\\n"
        
        # Market timing advice (always applicable)
        current_day = datetime.now().weekday()
        result += f"\\n**Current Market Timing:**\\n"
        if current_day < 2:  # Monday/Tuesday
            result += f"• **Early Week**: Good time to stock up on materials\\n"
            result += f"• **Strategy**: Buy low, prepare for weekend rush\\n"
        elif current_day < 5:  # Wed-Fri
            result += f"• **Mid Week**: Begin listing event items\\n"
            result += f"• **Strategy**: Test pricing, adjust for demand\\n"
        else:  # Weekend
            result += f"• **Weekend**: Peak selling time\\n"
            result += f"• **Strategy**: Premium pricing, high volume sales\\n"
        
        result += f"\\n**Risk Management:**\\n"
        result += f"• Don't invest more than 20% of liquid gold in event items\\n"
        result += f"• Diversify across multiple item categories\\n"
        result += f"• Have exit strategy if prices don't meet expectations\\n"
        result += f"• Monitor competition and adjust prices accordingly\\n"
        
        if is_synthetic:
            result += f"\\n**💡 Note**: Strategy works independently of live market data.\\n"
        
        return result
        
    except Exception as e:
        logger.error(f"Error in event optimization: {str(e)}")
        return f"Error optimizing event economics: {str(e)}"

def main():
    """Main entry point for enhanced MCP server with staging."""
    try:
        # Check for required credentials
        blizzard_client_id = os.getenv("BLIZZARD_CLIENT_ID")
        blizzard_client_secret = os.getenv("BLIZZARD_CLIENT_SECRET")
        database_url = os.getenv("DATABASE_URL")
        
        if not all([blizzard_client_id, blizzard_client_secret, database_url]):
            logger.warning("⚠️ Missing some credentials - limited functionality may be available")
        
        port = int(os.getenv("PORT", "8000"))
        
        logger.info("🚀 Enhanced WoW Analysis MCP Server with Data Staging")
        logger.info("🔧 Features: Intelligent caching, offline analysis, API fallbacks")
        logger.info("📊 Tools: Auction house intelligence, guild analysis, market prediction")
        logger.info(f"🌐 HTTP Server: 0.0.0.0:{port}")
        logger.info("✅ Starting server...")
        
        # Initialize staging service
        asyncio.create_task(init_staging_service())
        
        # Run server using FastMCP 2.0 HTTP transport
        mcp.run(transport="http")
        
    except Exception as e:
        logger.error(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()