"""
WoW Guild MCP Server using FastMCP 2.0 with HTTP transport for Heroku
"""
import os
import logging
from dotenv import load_dotenv
from fastmcp import FastMCP
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import asyncio
import redis.asyncio as aioredis

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastMCP server with proper configuration
mcp = FastMCP("WoW Guild Analytics MCP")

# Import the actual implementations
from .api.blizzard_client import BlizzardAPIClient, BlizzardAPIError
from .api.guild_optimizations import OptimizedGuildFetcher
from .visualization.chart_generator import ChartGenerator
from .workflows.guild_analysis import GuildAnalysisWorkflow
from .services.auction_aggregator import AuctionAggregatorService
from .services.market_history import MarketHistoryService
from .services.redis_staging import RedisDataStagingService
from .services.activity_logger import ActivityLogger, initialize_activity_logger
from .services.supabase_streaming import initialize_streaming_service

# Initialize service instances
chart_generator = ChartGenerator()
guild_workflow = GuildAnalysisWorkflow()
auction_aggregator = AuctionAggregatorService()
market_history = MarketHistoryService()

# Global instances for Redis and logging
redis_client: Optional[aioredis.Redis] = None
activity_logger: Optional[ActivityLogger] = None
streaming_service = None

# Register WoW Guild tools using FastMCP decorators
@mcp.tool()
async def analyze_guild_performance(
    realm: str,
    guild_name: str,
    analysis_type: str = "comprehensive",
    game_version: str = "retail"
) -> Dict[str, Any]:
    """
    Analyze guild performance metrics and member activity
    
    Args:
        realm: Server realm (e.g., 'stormrage', 'area-52')
        guild_name: Guild name
        analysis_type: Type of analysis ('comprehensive', 'basic', 'performance')
        game_version: WoW version ('retail' or 'classic')
    
    Returns:
        Guild analysis results with performance metrics
    """
    start_time = datetime.now(timezone.utc)
    log_id = ""
    
    try:
        logger.info(f"Analyzing guild {guild_name} on {realm} ({game_version})")
        
        # Log the request if activity logger is available
        if activity_logger:
            log_id = await activity_logger.log_request(
                session_id="fastmcp-session",  # TODO: Get actual session ID from FastMCP
                tool_name="analyze_guild_performance",
                request_data={
                    "realm": realm,
                    "guild_name": guild_name,
                    "analysis_type": analysis_type,
                    "game_version": game_version
                }
            )
        
        async with BlizzardAPIClient(game_version=game_version) as client:
            # Get comprehensive guild data
            guild_data = await client.get_comprehensive_guild_data(realm, guild_name)
            
            # Process through workflow
            analysis_result = await guild_workflow.analyze_guild(
                guild_data, analysis_type
            )
            
            # Extract the formatted response from the workflow state
            formatted = analysis_result.get("analysis_results", {}).get("formatted_response", {})
            
            result = {
                "success": True,
                "guild_info": formatted.get("guild_summary", {}),
                "member_data": formatted.get("member_analysis", {}),
                "analysis_results": formatted.get("performance_insights", {}),
                "visualization_urls": formatted.get("chart_urls", []),
                "analysis_type": analysis_type,
                "timestamp": guild_data["fetch_timestamp"]
            }
            
            # Log successful response
            if activity_logger and log_id:
                duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                await activity_logger.log_response(
                    log_id=log_id,
                    response_data={"success": True, "guild_name": guild_name},
                    duration_ms=duration_ms,
                    success=True
                )
            
            return result
            
    except BlizzardAPIError as e:
        logger.error(f"Blizzard API error: {e.message}")
        if activity_logger:
            await activity_logger.log_error(
                session_id="fastmcp-session",
                error_message=f"API Error: {e.message}",
                tool_name="analyze_guild_performance",
                metadata={"realm": realm, "guild_name": guild_name}
            )
        return {"error": f"API Error: {e.message}"}
    except Exception as e:
        logger.error(f"Unexpected error analyzing guild: {str(e)}")
        if activity_logger:
            await activity_logger.log_error(
                session_id="fastmcp-session",
                error_message=str(e),
                tool_name="analyze_guild_performance",
                metadata={"realm": realm, "guild_name": guild_name}
            )
        return {"error": f"Analysis failed: {str(e)}"}

@mcp.tool()
async def get_guild_member_list(
    realm: str,
    guild_name: str,
    sort_by: str = "guild_rank",
    limit: int = 50,
    quick_mode: bool = False,
    game_version: str = "retail"
) -> Dict[str, Any]:
    """
    Get detailed guild member list with sorting options
    
    Args:
        realm: Server realm
        guild_name: Guild name
        sort_by: Sort criteria ('guild_rank', 'level', 'name', 'last_login')
        limit: Maximum number of members to return
        quick_mode: Use optimized fetcher for faster results
        game_version: WoW version ('retail' or 'classic')
    
    Returns:
        Detailed member list with metadata
    """
    try:
        logger.info(f"Getting member list for {guild_name} on {realm} ({game_version})")
        
        async with BlizzardAPIClient(game_version=game_version) as client:
            if quick_mode:
                # Use optimized fetcher for quick mode
                fetcher = OptimizedGuildFetcher(client)
                roster_data = await fetcher.get_guild_roster_basic(realm, guild_name)
                
                # Format members for response
                members_raw = roster_data["members"][:limit]
                members = []
                for m in members_raw:
                    char = m.get("character", {})
                    members.append({
                        "name": char.get("name"),
                        "level": char.get("level"),
                        "character_class": char.get("playable_class", {}).get("name", "Unknown"),
                        "guild_rank": m.get("rank")
                    })
                total_members = roster_data["member_count"]
                guild_info = roster_data.get("guild", {})
            else:
                # Full comprehensive data
                guild_data = await client.get_comprehensive_guild_data(realm, guild_name)
                members = guild_data.get("members_data", [])[:limit]
                total_members = len(guild_data.get("members_data", []))
                guild_info = guild_data.get("guild_info", {})
            
            # Sort members based on criteria
            if sort_by == "guild_rank":
                members.sort(key=lambda x: x.get("guild_rank", 999))
            elif sort_by == "level":
                members.sort(key=lambda x: x.get("level", 0), reverse=True)
            elif sort_by == "name":
                members.sort(key=lambda x: x.get("name", "").lower())
            
            return {
                "success": True,
                "guild_name": guild_name,
                "realm": realm,
                "members": members,
                "members_returned": len(members),
                "total_members": total_members,
                "sorted_by": sort_by,
                "quick_mode": quick_mode,
                "guild_summary": guild_info
            }
            
    except BlizzardAPIError as e:
        logger.error(f"Blizzard API error: {e.message}")
        return {"error": f"API Error: {e.message}"}
    except Exception as e:
        logger.error(f"Error getting member list: {str(e)}")
        return {"error": f"Member list failed: {str(e)}"}

@mcp.tool()
async def analyze_member_performance(
    realm: str,
    character_name: str,
    analysis_depth: str = "standard",
    game_version: str = "retail"
) -> Dict[str, Any]:
    """
    Analyze individual member performance and progression
    
    Args:
        realm: Server realm
        character_name: Character name to analyze
        analysis_depth: Analysis depth ('basic', 'standard', 'detailed')
        game_version: WoW version ('retail' or 'classic')
    
    Returns:
        Comprehensive member analysis
    """
    try:
        logger.info(f"Analyzing member {character_name} on {realm} ({game_version})")
        
        async with BlizzardAPIClient(game_version=game_version) as client:
            # Get character profile
            char_profile = await client.get_character_profile(realm, character_name)
            
            # Get equipment
            char_equipment = await client.get_character_equipment(realm, character_name)
            char_profile["equipment_summary"] = client._summarize_equipment(char_equipment)
            
            # Get achievements if detailed analysis
            if analysis_depth in ["standard", "detailed"]:
                try:
                    char_achievements = await client.get_character_achievements(realm, character_name)
                    char_profile["recent_achievements"] = char_achievements
                except BlizzardAPIError:
                    char_profile["recent_achievements"] = {}
            
            # Get mythic+ data if detailed analysis
            if analysis_depth == "detailed":
                try:
                    mythic_data = await client.get_character_mythic_keystone(realm, character_name)
                    char_profile["mythic_plus_data"] = mythic_data
                except BlizzardAPIError:
                    char_profile["mythic_plus_data"] = {}
            
            # Process through member analysis workflow
            analysis_result = await guild_workflow.analyze_member(
                char_profile, analysis_depth
            )
            
            return {
                "success": True,
                "character_name": character_name,
                "realm": realm,
                "member_info": analysis_result["character_summary"],
                "performance_metrics": analysis_result["performance_analysis"],
                "equipment_analysis": analysis_result["equipment_insights"],
                "progression_summary": analysis_result.get("progression_summary", {}),
                "analysis_depth": analysis_depth
            }
            
    except BlizzardAPIError as e:
        logger.error(f"Blizzard API error: {e.message}")
        return {"error": f"API Error: {e.message}"}
    except Exception as e:
        logger.error(f"Error analyzing member: {str(e)}")
        return {"error": f"Member analysis failed: {str(e)}"}

@mcp.tool()
async def generate_raid_progress_chart(
    realm: str,
    guild_name: str,
    raid_tier: str = "current",
    game_version: str = "retail"
) -> str:
    """
    Generate visual raid progression charts
    
    Args:
        realm: Server realm
        guild_name: Guild name
        raid_tier: Raid tier ('current', 'dragonflight', 'shadowlands')
        game_version: WoW version ('retail' or 'classic')
    
    Returns:
        Base64 encoded image of the raid progression chart
    """
    try:
        logger.info(f"Generating raid chart for {guild_name} on {realm} ({game_version})")
        
        async with BlizzardAPIClient(game_version=game_version) as client:
            guild_data = await client.get_comprehensive_guild_data(realm, guild_name)
            
            # Generate raid progression chart
            chart_data = await chart_generator.create_raid_progress_chart(
                guild_data, raid_tier
            )
            
            return chart_data  # Base64 encoded PNG
            
    except BlizzardAPIError as e:
        logger.error(f"Blizzard API error: {e.message}")
        return f"Error: API Error: {e.message}"
    except Exception as e:
        logger.error(f"Error generating chart: {str(e)}")
        return f"Error: Chart generation failed: {str(e)}"

@mcp.tool()
async def compare_member_performance(
    realm: str,
    guild_name: str,
    member_names: List[str],
    metric: str = "item_level",
    game_version: str = "retail"
) -> Dict[str, Any]:
    """
    Compare performance metrics across guild members
    
    Args:
        realm: Server realm
        guild_name: Guild name
        member_names: List of character names to compare
        metric: Metric to compare ('item_level', 'achievement_points', 'guild_rank')
        game_version: WoW version ('retail' or 'classic')
    
    Returns:
        Comparison results with chart data
    """
    try:
        logger.info(f"Comparing members {member_names} in {guild_name} ({game_version})")
        
        async with BlizzardAPIClient(game_version=game_version) as client:
            # Get data for specific members
            comparison_data = []
            
            for member_name in member_names:
                try:
                    char_data = await client.get_character_profile(realm, member_name)
                    if metric == "item_level":
                        equipment = await client.get_character_equipment(realm, member_name)
                        char_data["equipment_summary"] = client._summarize_equipment(equipment)
                    comparison_data.append(char_data)
                except BlizzardAPIError as e:
                    logger.warning(f"Failed to get data for {member_name}: {e.message}")
            
            # Generate comparison chart
            chart_data = await chart_generator.create_member_comparison_chart(
                comparison_data, metric
            )
            
            return {
                "success": True,
                "member_data": comparison_data,
                "comparison_metric": metric,
                "chart_data": chart_data,
                "member_count": len(comparison_data)
            }
            
    except Exception as e:
        logger.error(f"Error comparing members: {str(e)}")
        return {"error": f"Comparison failed: {str(e)}"}

@mcp.tool()
async def get_auction_house_snapshot(
    realm: str,
    item_search: Optional[str] = None,
    max_results: int = 100,
    game_version: str = "retail"
) -> Dict[str, Any]:
    """
    Get current auction house snapshot for a realm
    
    Args:
        realm: Server realm (e.g., 'stormrage', 'area-52')
        item_search: Optional item name or ID to search for
        max_results: Maximum number of items to return
        game_version: WoW version ('retail' or 'classic')
    
    Returns:
        Current auction house data with market analysis
    """
    try:
        logger.info(f"Getting auction house data for realm {realm} ({game_version})")
        
        async with BlizzardAPIClient(game_version=game_version) as client:
            # Get connected realm ID
            realm_info = await client._get_realm_info(realm)
            connected_realm_id = realm_info.get('connected_realm', {}).get('id')
            
            if not connected_realm_id:
                return {"error": "Could not find connected realm ID"}
            
            # Get auction house data
            ah_data = await client.get_auction_house_data(connected_realm_id)
            
            if not ah_data or 'auctions' not in ah_data:
                return {"error": "No auction data available"}
            
            # Aggregate auction data
            aggregated = auction_aggregator.aggregate_auction_data(ah_data['auctions'])
            
            # Filter results if item search provided
            if item_search:
                if item_search.isdigit():
                    # Search by item ID
                    item_id = int(item_search)
                    if item_id in aggregated:
                        aggregated = {item_id: aggregated[item_id]}
                else:
                    # TODO: Implement item name search
                    logger.warning("Item name search not yet implemented")
            
            # Sort by total market value and limit results
            sorted_items = sorted(
                aggregated.items(),
                key=lambda x: x[1]['total_market_value'],
                reverse=True
            )[:max_results]
            
            return {
                "success": True,
                "realm": realm,
                "connected_realm_id": connected_realm_id,
                "timestamp": datetime.utcnow().isoformat(),
                "total_items": len(aggregated),
                "items_returned": len(sorted_items),
                "market_data": dict(sorted_items)
            }
            
    except Exception as e:
        logger.error(f"Error getting auction house data: {str(e)}")
        return {"error": f"Auction house data failed: {str(e)}"}

@mcp.tool()
async def analyze_item_market_history(
    realm: str,
    item_id: int,
    days: int = 7,
    game_version: str = "retail"
) -> Dict[str, Any]:
    """
    Analyze historical market trends for a specific item
    
    Args:
        realm: Server realm
        item_id: Item ID to analyze
        days: Number of days of history to analyze (default 7)
        game_version: WoW version ('retail' or 'classic')
    
    Returns:
        Historical market analysis with trends and predictions
    """
    try:
        logger.info(f"Analyzing market history for item {item_id} on {realm}")
        
        # Get realm info
        async with BlizzardAPIClient(game_version=game_version) as client:
            realm_info = await client._get_realm_info(realm)
            connected_realm_id = realm_info.get('connected_realm', {}).get('id')
            
            if not connected_realm_id:
                return {"error": "Could not find connected realm ID"}
            
            # TODO: Implement actual historical data retrieval
            # For now, return mock analysis
            return {
                "success": True,
                "realm": realm,
                "item_id": item_id,
                "analysis_period_days": days,
                "market_trends": {
                    "price_trend": "stable",
                    "volume_trend": "increasing",
                    "volatility": "low",
                    "recommended_action": "hold"
                },
                "note": "Historical data retrieval not yet implemented"
            }
            
    except Exception as e:
        logger.error(f"Error analyzing market history: {str(e)}")
        return {"error": f"Market analysis failed: {str(e)}"}

@mcp.tool()
async def find_market_opportunities(
    realm: str,
    min_profit_margin: float = 20.0,
    max_results: int = 20,
    game_version: str = "retail"
) -> Dict[str, Any]:
    """
    Find profitable market opportunities based on current auction data
    
    Args:
        realm: Server realm
        min_profit_margin: Minimum profit margin percentage (default 20%)
        max_results: Maximum number of opportunities to return
        game_version: WoW version ('retail' or 'classic')
    
    Returns:
        List of profitable market opportunities
    """
    try:
        logger.info(f"Finding market opportunities on {realm} ({game_version})")
        
        async with BlizzardAPIClient(game_version=game_version) as client:
            # Get connected realm ID
            realm_info = await client._get_realm_info(realm)
            connected_realm_id = realm_info.get('connected_realm', {}).get('id')
            
            if not connected_realm_id:
                return {"error": "Could not find connected realm ID"}
            
            # Get current auction data
            ah_data = await client.get_auction_house_data(connected_realm_id)
            
            if not ah_data or 'auctions' not in ah_data:
                return {"error": "No auction data available"}
            
            # Aggregate auction data
            aggregated = auction_aggregator.aggregate_auction_data(ah_data['auctions'])
            
            # Find opportunities (items with high price variance)
            opportunities = []
            for item_id, data in aggregated.items():
                if data['auction_count'] < 2:
                    continue
                    
                # Calculate potential profit margin
                price_range = data['max_price'] - data['min_price']
                if data['min_price'] > 0:
                    margin_pct = (price_range / data['min_price']) * 100
                    
                    if margin_pct >= min_profit_margin:
                        opportunities.append({
                            'item_id': item_id,
                            'min_price': data['min_price'],
                            'max_price': data['max_price'],
                            'avg_price': data['avg_price'],
                            'profit_margin_pct': round(margin_pct, 2),
                            'total_quantity': data['total_quantity'],
                            'auction_count': data['auction_count']
                        })
            
            # Sort by profit margin
            opportunities.sort(key=lambda x: x['profit_margin_pct'], reverse=True)
            
            return {
                "success": True,
                "realm": realm,
                "opportunities_found": len(opportunities),
                "opportunities": opportunities[:max_results],
                "min_profit_margin_filter": min_profit_margin
            }
            
    except Exception as e:
        logger.error(f"Error finding market opportunities: {str(e)}")
        return {"error": f"Market opportunity search failed: {str(e)}"}

async def initialize_services():
    """Initialize Redis, activity logger, and Supabase streaming"""
    global redis_client, activity_logger, streaming_service
    
    try:
        # Initialize Redis connection
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        
        # Configure SSL for Heroku Redis
        if redis_url.startswith("rediss://"):
            logger.info("Configuring Redis with TLS for Heroku")
            redis_client = await aioredis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=False,
                max_connections=50,
                ssl_cert_reqs=None  # Disable SSL verification for self-signed certs
            )
        else:
            redis_client = await aioredis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=False,
                max_connections=50
            )
        
        # Test Redis connection
        await redis_client.ping()
        logger.info(f"Connected to Redis at {redis_url}")
        
        # Initialize activity logger
        activity_logger = await initialize_activity_logger(redis_client)
        logger.info("Activity logger initialized")
        
        # Initialize Supabase streaming service (optional)
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        if supabase_url and supabase_key:
            try:
                streaming_service = await initialize_streaming_service(redis_client)
                logger.info("Supabase streaming service initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Supabase streaming service: {e}")
                streaming_service = None
        else:
            logger.warning("Supabase environment variables not set - logging to Supabase disabled")
            
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise


def main():
    """Main entry point for FastMCP server"""
    try:
        # Check for required environment variables
        blizzard_client_id = os.getenv("BLIZZARD_CLIENT_ID")
        blizzard_client_secret = os.getenv("BLIZZARD_CLIENT_SECRET")
        
        if not blizzard_client_id or not blizzard_client_secret:
            raise ValueError("Blizzard API credentials not found in environment variables")
        
        port = int(os.getenv("PORT", "8000"))
        
        logger.info("🚀 WoW Guild MCP Server with FastMCP 2.0")
        logger.info("🔧 Tools: Guild analysis, visualization, and auction house")
        logger.info(f"📊 Registered tools: {len(mcp._tool_manager._tools)}")
        logger.info(f"🌐 HTTP Server: 0.0.0.0:{port}")
        
        # Initialize services in a new event loop
        logger.info("📦 Initializing Redis and logging services...")
        asyncio.run(initialize_services())
        
        logger.info("✅ Starting server...")
        
        # Run server using FastMCP 2.0 HTTP transport
        mcp.run(
            transport="http",
            host="0.0.0.0",
            port=port,
            path="/mcp"
        )
        
    except Exception as e:
        logger.error(f"❌ Error starting server: {e}")
        import sys
        sys.exit(1)

if __name__ == "__main__":
    main()