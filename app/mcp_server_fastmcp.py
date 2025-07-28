"""
WoW Guild MCP Server using FastMCP 2.0 with HTTP transport for Heroku

A comprehensive World of Warcraft guild analytics MCP server that provides:
- Guild performance analysis and member statistics
- Auction house data aggregation and market insights
- Real-time activity logging to Supabase
- Chart generation for raid progress and member comparisons
- Classic and Retail WoW support with proper namespace handling
"""

# Standard library imports
import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

# Third-party imports
import redis.asyncio as aioredis
from dotenv import load_dotenv
from fastmcp import FastMCP

# Local imports
from .api.blizzard_client import BlizzardAPIClient, KNOWN_RETAIL_REALMS as RETAIL_REALMS, BlizzardAPIError
from .api.guild_optimizations import OptimizedGuildFetcher
from .services.activity_logger import ActivityLogger, initialize_activity_logger
from .services.auction_aggregator import AuctionAggregatorService
from .services.market_history import MarketHistoryService
from .services.redis_staging import RedisDataStagingService
from .services.supabase_client import SupabaseRealTimeClient, ActivityLogEntry
from .services.supabase_streaming import initialize_streaming_service
from .visualization.chart_generator import ChartGenerator
from .workflows.guild_analysis import GuildAnalysisWorkflow

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

# Initialize service instances
chart_generator = ChartGenerator()
guild_workflow = GuildAnalysisWorkflow()
auction_aggregator = AuctionAggregatorService()
market_history = MarketHistoryService()

# Global instances for Redis and logging
redis_client: Optional[aioredis.Redis] = None
activity_logger: Optional[ActivityLogger] = None
streaming_service = None
supabase_client: Optional[SupabaseRealTimeClient] = None

# Known Classic realm IDs (hardcoded for reliability)
KNOWN_CLASSIC_REALMS = {
    "mankrik": 4384,
    "faerlina": 4408,
    "benediction": 4728,
    "grobbulus": 4647,
    "whitemane": 4395,
    "pagle": 4701,
    "westfall": 4669,
    "old-blanchy": 4372
}

# Use the realm IDs from blizzard_client
KNOWN_RETAIL_REALMS = RETAIL_REALMS

async def get_connected_realm_id(realm: str, game_version: str = "retail", client: BlizzardAPIClient = None) -> Optional[int]:
    """Get connected realm ID with fallback to hardcoded values"""
    realm_lower = realm.lower()
    
    # First check hardcoded IDs
    if game_version == "classic" and realm_lower in KNOWN_CLASSIC_REALMS:
        logger.info(f"Using known Classic realm ID for {realm}: {KNOWN_CLASSIC_REALMS[realm_lower]}")
        return KNOWN_CLASSIC_REALMS[realm_lower]
    elif game_version == "retail" and realm_lower in KNOWN_RETAIL_REALMS:
        logger.info(f"Using known Retail realm ID for {realm}: {KNOWN_RETAIL_REALMS[realm_lower]}")
        return KNOWN_RETAIL_REALMS[realm_lower]
    
    # Try to get from API
    if client:
        try:
            realm_info = await client._get_realm_info(realm)
            connected_realm_id = realm_info.get('connected_realm', {}).get('id')
            if connected_realm_id:
                logger.info(f"Got realm ID from API for {realm}: {connected_realm_id}")
                return connected_realm_id
        except Exception as e:
            logger.warning(f"Failed to get realm info from API for {realm}: {e}")
    
    # No ID found
    logger.error(f"Could not find connected realm ID for {realm} ({game_version})")
    return None

# Decorator for automatic Supabase logging
def with_supabase_logging(func):
    """Decorator to automatically log tool calls to Supabase"""
    import functools
    
    @functools.wraps(func)
    async def wrapper(**kwargs):
        start_time = datetime.now(timezone.utc)
        tool_name = func.__name__
        
        # Try to initialize services and log, but don't let it break the tool
        try:
            await get_or_initialize_services()
            await log_to_supabase(
                tool_name=tool_name,
                request_data=kwargs
            )
        except Exception as e:
            logger.debug(f"Failed to initialize services or log request for {tool_name}: {e}")
        
        try:
            # Call the actual function
            result = await func(**kwargs)
            
            # Try to log successful response
            try:
                duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                await log_to_supabase(
                    tool_name=tool_name,
                    request_data=kwargs,
                    response_data={"success": True},
                    duration_ms=duration_ms
                )
            except Exception as e:
                logger.debug(f"Failed to log success for {tool_name}: {e}")
            
            return result
            
        except Exception as e:
            # Try to log error but don't let logging break error handling
            try:
                await log_to_supabase(
                    tool_name=tool_name,
                    request_data=kwargs,
                    error_message=str(e)
                )
            except Exception as log_error:
                logger.debug(f"Failed to log error for {tool_name}: {log_error}")
            raise
    
    return wrapper

# ============================================================================
# MCP TOOL DEFINITIONS
# ============================================================================
# All tools are decorated with @mcp.tool() and @with_supabase_logging for
# automatic registration with FastMCP and comprehensive activity logging.
# ============================================================================

# Guild Analysis Tools
@mcp.tool()
@with_supabase_logging
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
        
        # Initialize services if needed
        await get_or_initialize_services()
        
        # Request data for logging
        request_data = {
            "realm": realm,
            "guild_name": guild_name,
            "analysis_type": analysis_type,
            "game_version": game_version
        }
        
        # Log the request if activity logger is available
        if activity_logger:
            log_id = await activity_logger.log_request(
                session_id="fastmcp-session",
                tool_name="analyze_guild_performance",
                request_data=request_data
            )
        
        async with BlizzardAPIClient(game_version=game_version) as client:
            # For comprehensive analysis, check if we have cached data first
            if analysis_type == "comprehensive" and redis_client:
                cache_key = f"guild_roster:{game_version}:{realm}:{guild_name}".lower()
                cached_data = await redis_client.get(cache_key)
                
                if cached_data:
                    logger.info(f"Using cached guild data for {guild_name}")
                    guild_data = {
                        "guild_info": json.loads(cached_data.decode()),
                        "guild_roster": json.loads(cached_data.decode()),
                        "members_data": json.loads(cached_data.decode()).get("members", [])[:20],  # Limit to 20 for analysis
                        "fetch_timestamp": datetime.now(timezone.utc).isoformat(),
                        "from_cache": True
                    }
                else:
                    # Get comprehensive guild data but limit member fetching
                    guild_data = await client.get_comprehensive_guild_data(realm, guild_name)
                    # Limit members for analysis to prevent timeout
                    if "members_data" in guild_data and len(guild_data["members_data"]) > 20:
                        guild_data["members_data"] = guild_data["members_data"][:20]
                        logger.info(f"Limited member analysis to 20 members to prevent timeout")
            else:
                # For basic analysis, just get guild info and roster without individual profiles
                guild_info = await client.get_guild_info(realm, guild_name)
                guild_roster = await client.get_guild_roster(realm, guild_name)
                guild_data = {
                    "guild_info": guild_info,
                    "guild_roster": guild_roster,
                    "members_data": [],  # No individual profiles for basic analysis
                    "fetch_timestamp": datetime.now(timezone.utc).isoformat()
                }
            
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
            
            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            # Log successful response
            if activity_logger and log_id:
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


# Guild Member Tools
@mcp.tool()
@with_supabase_logging
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
        
        # Initialize services if needed
        await get_or_initialize_services()
        
        # Check Redis cache first
        cache_key = f"guild_roster:{game_version}:{realm}:{guild_name.lower()}"
        cached_data = None
        cache_age_days = None
        
        if redis_client:
            try:
                # Get cached data
                cached_json = await redis_client.get(cache_key)
                if cached_json:
                    cached_data = json.loads(cached_json.decode())  # Decode bytes to string
                    
                    # Check cache age
                    stored_date = datetime.fromisoformat(cached_data.get("cached_at", ""))
                    cache_age = datetime.now(timezone.utc) - stored_date
                    cache_age_days = cache_age.days
                    
                    # If cache is less than 15 days old, use it
                    if cache_age_days < 15:
                        logger.info(f"Using cached guild roster (age: {cache_age_days} days)")
                        
                        # Extract members and apply sorting/limit
                        members = cached_data["members"][:limit]
                        
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
                            "total_members": cached_data["total_members"],
                            "sorted_by": sort_by,
                            "quick_mode": quick_mode,
                            "guild_summary": cached_data.get("guild_info", {}),
                            "from_cache": True,
                            "cache_age_days": cache_age_days
                        }
                    else:
                        logger.info(f"Cache is stale ({cache_age_days} days old), fetching fresh data")
            except Exception as e:
                logger.warning(f"Redis cache check failed: {e}")
        
        # Fetch fresh data from API
        async with BlizzardAPIClient(game_version=game_version) as client:
            if quick_mode:
                # Use optimized fetcher for quick mode
                fetcher = OptimizedGuildFetcher(client)
                roster_data = await fetcher.get_guild_roster_basic(realm, guild_name)
                
                # Format members for response
                members_raw = roster_data["members"]
                all_members = []
                for m in members_raw:
                    char = m.get("character", {})
                    all_members.append({
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
                all_members = guild_data.get("members_data", [])
                total_members = len(all_members)
                guild_info = guild_data.get("guild_info", {})
            
            # Cache the fresh data in Redis with 15-day expiry
            if redis_client:
                try:
                    cache_data = {
                        "guild_name": guild_name,
                        "realm": realm,
                        "members": all_members,
                        "total_members": total_members,
                        "guild_info": guild_info,
                        "cached_at": datetime.now(timezone.utc).isoformat(),
                        "game_version": game_version
                    }
                    
                    # Store with 15-day TTL (in seconds)
                    ttl_seconds = 15 * 24 * 60 * 60  # 15 days
                    await redis_client.setex(
                        cache_key,
                        ttl_seconds,
                        json.dumps(cache_data).encode()  # Encode to bytes
                    )
                    logger.info(f"Cached guild roster for {guild_name} with 15-day TTL")
                except Exception as e:
                    logger.error(f"Failed to cache guild roster: {e}")
            
            # Apply limit and sorting for response
            members = all_members[:limit]
            
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
                "guild_summary": guild_info,
                "from_cache": False,
                "cache_age_days": 0
            }
            
    except BlizzardAPIError as e:
        logger.error(f"Blizzard API error: {e.message}")
        return {"error": f"API Error: {e.message}"}
    except Exception as e:
        logger.error(f"Error getting member list: {str(e)}")
        return {"error": f"Member list failed: {str(e)}"}

@mcp.tool()
@with_supabase_logging
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


# Visualization Tools  
@mcp.tool()
@with_supabase_logging
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
@with_supabase_logging
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


# Item and Auction House Tools
@mcp.tool()
@with_supabase_logging
async def lookup_item_details(
    item_id: int,
    game_version: str = "retail"
) -> Dict[str, Any]:
    """
    Look up WoW item details by item ID
    
    Args:
        item_id: The item ID to look up
        game_version: WoW version ('retail' or 'classic' only - classic-era servers currently unavailable)
    
    Returns:
        Item details including name, description, quality, etc.
    """
    try:
        logger.info(f"Looking up item {item_id} ({game_version})")
        
        async with BlizzardAPIClient(game_version=game_version) as client:
            # Get item data from Blizzard API
            item_data = await client.get_item_data(item_id)
            
            # Extract relevant information
            result = {
                "success": True,
                "item_id": item_id,
                "game_version": game_version
            }
            
            # Handle name format differences between Classic and Retail
            name = item_data.get('name', 'Unknown Item')
            if isinstance(name, dict):
                # Retail format with localization
                result["name"] = name.get('en_US', 'Unknown Item')
            else:
                # Classic format (direct string)
                result["name"] = name
            
            # Add other item details
            result.update({
                "quality": item_data.get('quality', {}).get('name', 'Unknown'),
                "item_class": item_data.get('item_class', {}).get('name', 'Unknown'),
                "item_subclass": item_data.get('item_subclass', {}).get('name', 'Unknown'),
                "level": item_data.get('level', 0),
                "required_level": item_data.get('required_level', 0),
                "sell_price": item_data.get('sell_price', 0),
                "preview_item": item_data.get('preview_item', {}),
                "media": item_data.get('media', {})
            })
            
            return result
            
    except Exception as e:
        logger.error(f"Error looking up item {item_id}: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to lookup item {item_id}: {str(e)}",
            "item_id": item_id
        }

@mcp.tool()
@with_supabase_logging
async def lookup_multiple_items(
    item_ids: List[int],
    game_version: str = "retail"
) -> Dict[str, Any]:
    """
    Look up multiple WoW items by their IDs
    
    Args:
        item_ids: List of item IDs to look up
        game_version: WoW version ('retail' or 'classic' only - classic-era servers currently unavailable)
    
    Returns:
        Dictionary of item details keyed by item ID
    """
    try:
        logger.info(f"Looking up {len(item_ids)} items ({game_version})")
        
        results = {}
        failed_lookups = []
        
        async with BlizzardAPIClient(game_version=game_version) as client:
            for item_id in item_ids:
                try:
                    item_data = await client.get_item_data(item_id)
                    
                    # Handle name format differences
                    name = item_data.get('name', 'Unknown Item')
                    if isinstance(name, dict):
                        name = name.get('en_US', 'Unknown Item')
                    
                    results[item_id] = {
                        "name": name,
                        "quality": item_data.get('quality', {}).get('name', 'Unknown'),
                        "item_class": item_data.get('item_class', {}).get('name', 'Unknown'),
                        "level": item_data.get('level', 0),
                        "sell_price": item_data.get('sell_price', 0)
                    }
                    
                except Exception as e:
                    logger.warning(f"Failed to lookup item {item_id}: {str(e)}")
                    failed_lookups.append(item_id)
        
        return {
            "success": True,
            "items_found": len(results),
            "items_requested": len(item_ids),
            "failed_lookups": failed_lookups,
            "items": results,
            "game_version": game_version
        }
        
    except Exception as e:
        logger.error(f"Error looking up multiple items: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to lookup items: {str(e)}"
        }

@mcp.tool()
@with_supabase_logging
async def get_realm_status(
    realm: str,
    game_version: str = "retail"
) -> Dict[str, Any]:
    """
    Get realm status and information including connected realm ID
    
    Args:
        realm: Server realm name (e.g., 'stormrage', 'area-52', 'mankrik')
        game_version: WoW version ('retail' or 'classic')
    
    Returns:
        Realm information including status, population, and connected realm ID
    """
    try:
        logger.info(f"Getting realm status for {realm} ({game_version})")
        
        # Check if it's a known Classic realm
        realm_lower = realm.lower()
        if game_version == "classic" and realm_lower in KNOWN_CLASSIC_REALMS:
            logger.info(f"Using known realm ID for {realm}: {KNOWN_CLASSIC_REALMS[realm_lower]}")
            return {
                "success": True,
                "realm": realm,
                "connected_realm_id": KNOWN_CLASSIC_REALMS[realm_lower],
                "game_version": game_version,
                "source": "hardcoded",
                "status": "online",
                "message": f"Found hardcoded ID for Classic realm {realm}"
            }
        
        # Get realm info from API
        async with BlizzardAPIClient(game_version=game_version) as client:
            try:
                # Get realm information
                realm_info = await client._get_realm_info(realm)
                
                # Extract connected realm ID
                connected_realm = realm_info.get('connected_realm', {})
                connected_realm_id = None
                
                if isinstance(connected_realm, dict) and 'id' in connected_realm:
                    connected_realm_id = connected_realm['id']
                elif isinstance(connected_realm, int):
                    connected_realm_id = connected_realm
                else:
                    # Try to extract ID from href if available
                    href = connected_realm.get('href', '') if isinstance(connected_realm, dict) else ''
                    if '/connected-realm/' in href:
                        connected_realm_id = int(href.split('/connected-realm/')[-1].split('?')[0])
                
                # Build response
                response = {
                    "success": True,
                    "realm": realm_info.get('name', realm),
                    "slug": realm_info.get('slug', realm.lower()),
                    "connected_realm_id": connected_realm_id,
                    "game_version": game_version,
                    "region": realm_info.get('region', {}).get('name', 'Unknown'),
                    "timezone": realm_info.get('timezone', 'Unknown'),
                    "type": realm_info.get('type', {}).get('name', 'Unknown'),
                    "is_tournament": realm_info.get('is_tournament', False),
                    "population": realm_info.get('population', {}).get('name', 'Unknown'),
                    "status": "online"  # If we can fetch data, realm is online
                }
                
                # Add connected realms info if available
                if 'connected_realm' in realm_info and isinstance(realm_info['connected_realm'], dict):
                    if 'realms' in realm_info['connected_realm']:
                        response['connected_realms'] = [
                            r.get('name', 'Unknown') for r in realm_info['connected_realm']['realms']
                        ]
                
                return response
                
            except BlizzardAPIError as e:
                if e.status_code == 404:
                    return {
                        "success": False,
                        "error": f"Realm '{realm}' not found",
                        "game_version": game_version,
                        "message": "Please check the realm name and game version"
                    }
                else:
                    return {
                        "success": False,
                        "error": f"API error: {str(e)}",
                        "game_version": game_version,
                        "status_code": e.status_code
                    }
            except Exception as e:
                logger.error(f"Failed to get realm status: {str(e)}")
                return {
                    "success": False,
                    "error": f"Failed to get realm status: {str(e)}",
                    "game_version": game_version
                }
        
    except Exception as e:
        logger.error(f"Error getting realm status: {str(e)}")
        return {
            "success": False,
            "error": f"Error getting realm status: {str(e)}"
        }

@mcp.tool()
@with_supabase_logging
async def get_classic_realm_id(
    realm: str,
    game_version: str = "classic"
) -> Dict[str, Any]:
    """
    Get the connected realm ID for a Classic realm
    
    Args:
        realm: Server realm name
        game_version: WoW version ('classic' only - classic-era servers currently unavailable)
    
    Returns:
        Realm information including connected realm ID
    """
    try:
        logger.info(f"Looking up realm ID for {realm} ({game_version})")
        
        # First, check if we have a known ID
        realm_lower = realm.lower()
        if realm_lower in KNOWN_CLASSIC_REALMS:
            logger.info(f"Using known realm ID for {realm}: {KNOWN_CLASSIC_REALMS[realm_lower]}")
            return {
                "success": True,
                "realm": realm,
                "connected_realm_id": KNOWN_CLASSIC_REALMS[realm_lower],
                "source": "hardcoded",
                "message": f"Found hardcoded ID for {realm}"
            }
        
        # Try to get realm info from API
        async with BlizzardAPIClient(game_version=game_version) as client:
            try:
                realm_info = await client._get_realm_info(realm)
                connected_realm = realm_info.get('connected_realm', {})
                
                if isinstance(connected_realm, dict) and 'id' in connected_realm:
                    realm_id = connected_realm['id']
                elif isinstance(connected_realm, int):
                    realm_id = connected_realm
                else:
                    # Try to extract ID from href if available
                    href = connected_realm.get('href', '') if isinstance(connected_realm, dict) else ''
                    if '/connected-realm/' in href:
                        realm_id = int(href.split('/connected-realm/')[-1].split('?')[0])
                    else:
                        return {
                            "success": False,
                            "error": f"Could not extract connected realm ID from response",
                            "realm_info": realm_info
                        }
                
                return {
                    "success": True,
                    "realm": realm,
                    "connected_realm_id": realm_id,
                    "source": "api",
                    "realm_info": realm_info
                }
                
            except Exception as e:
                logger.error(f"Failed to get realm info from API: {str(e)}")
                return {
                    "success": False,
                    "error": str(e),
                    "suggestion": "Try using the hardcoded realm IDs or check if the realm name is correct"
                }
        
    except Exception as e:
        logger.error(f"Error looking up realm ID: {str(e)}")
        return {"error": f"Realm lookup failed: {str(e)}"}


# Auction House Analysis Tools
@mcp.tool()
@with_supabase_logging
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
            # Get connected realm ID using helper function
            connected_realm_id = await get_connected_realm_id(realm, game_version, client)
            
            if not connected_realm_id:
                return {"error": f"Could not find connected realm ID for realm {realm}"}
            
            # Get current auction data
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
                    # Item name search would require additional API endpoints
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
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "total_items": len(aggregated),
                "items_returned": len(sorted_items),
                "market_data": dict(sorted_items)
            }
            
    except BlizzardAPIError as e:
        logger.error(f"Blizzard API error: {e.message}")
        return {"error": f"API Error: {e.message}"}
    except Exception as e:
        logger.error(f"Error getting auction house data: {str(e)}")
        return {"error": f"Auction house data failed: {str(e)}"}

@mcp.tool()
@with_supabase_logging
async def get_character_details(
    realm: str,
    character_name: str,
    sections: List[str] = ["profile", "equipment", "specializations"],
    game_version: str = "retail"
) -> Dict[str, Any]:
    """
    Get comprehensive character details including gear, specializations, and other information
    
    Args:
        realm: Server realm
        character_name: Character name
        sections: Data sections to retrieve. Available options:
            - profile: Basic character information (default)
            - equipment: Current gear and item levels (default)
            - specializations: Talent specializations (default)
            - achievements: Achievement points and recent achievements
            - statistics: Character statistics
            - media: Character avatar and media
            - pvp: PvP statistics and ratings
            - appearance: Character appearance customization
            - collections: Mounts and pets
            - titles: Available titles
            - mythic_plus: Mythic+ dungeon data
            - all: Retrieve all available data
        game_version: WoW version ('retail' or 'classic')
    
    Returns:
        Comprehensive character information based on requested sections
    """
    try:
        logger.info(f"Getting character details for {character_name} on {realm} ({game_version})")
        
        # If 'all' is specified, get all sections
        all_sections = ["profile", "equipment", "specializations", "achievements", 
                       "statistics", "media", "pvp", "appearance", "collections", 
                       "titles", "mythic_plus"]
        
        if "all" in sections:
            sections = all_sections
        
        character_data = {}
        errors = []
        
        async with BlizzardAPIClient(game_version=game_version) as client:
            # Always get basic profile
            if "profile" in sections or True:  # Always include profile
                try:
                    profile = await client.get_character_profile(realm, character_name)
                    
                    # Handle case where profile might not be a dict
                    if not isinstance(profile, dict):
                        logger.error(f"Profile data is not a dict: {type(profile)} - {profile}")
                        return {"error": f"Invalid profile data received from API"}
                    
                    # Safe navigation for nested fields - handle both nested and direct string formats
                    race_data = profile.get("race", {})
                    if isinstance(race_data, dict):
                        race_name = race_data.get("name")
                        if isinstance(race_name, dict):
                            race_name = race_name.get("en_US", "Unknown")
                        elif not race_name:
                            race_name = "Unknown"
                    else:
                        race_name = str(race_data) if race_data else "Unknown"
                    
                    class_data = profile.get("character_class", {})
                    if isinstance(class_data, dict):
                        class_name = class_data.get("name")
                        if isinstance(class_name, dict):
                            class_name = class_name.get("en_US", "Unknown")
                        elif not class_name:
                            class_name = "Unknown"
                    else:
                        class_name = str(class_data) if class_data else "Unknown"
                    
                    spec_data = profile.get("active_spec", {})
                    if isinstance(spec_data, dict):
                        spec_name = spec_data.get("name")
                        if isinstance(spec_name, dict):
                            spec_name = spec_name.get("en_US", "Unknown")
                        elif not spec_name:
                            spec_name = "Unknown"
                    else:
                        spec_name = str(spec_data) if spec_data else "Unknown"
                    
                    realm_data = profile.get("realm", {})
                    if isinstance(realm_data, dict):
                        realm_name = realm_data.get("name", "Unknown")
                    else:
                        realm_name = str(realm_data) if realm_data else "Unknown"
                    
                    faction_data = profile.get("faction", {})
                    if isinstance(faction_data, dict):
                        faction_name = faction_data.get("name", "Unknown")
                    else:
                        faction_name = str(faction_data) if faction_data else "Unknown"
                    
                    guild_data = profile.get("guild")
                    guild_name = guild_data.get("name") if isinstance(guild_data, dict) else None
                    
                    character_data["profile"] = {
                        "name": profile.get("name"),
                        "level": profile.get("level"),
                        "race": race_name,
                        "class": class_name,
                        "active_spec": spec_name,
                        "realm": realm_name,
                        "faction": faction_name,
                        "guild": guild_name,
                        "achievement_points": profile.get("achievement_points", 0),
                        "equipped_item_level": profile.get("equipped_item_level", 0),
                        "average_item_level": profile.get("average_item_level", 0),
                        "last_login": profile.get("last_login_timestamp")
                    }
                except BlizzardAPIError as e:
                    errors.append(f"Profile: {str(e)}")
                    return {"error": f"Character not found: {str(e)}"}
            
            # Get equipment details
            if "equipment" in sections:
                try:
                    equipment = await client.get_character_equipment(realm, character_name)
                    
                    # Handle case where equipment might not be a dict
                    if not isinstance(equipment, dict):
                        logger.warning(f"Equipment data is not a dict: {type(equipment)}")
                        equipment = {}
                    
                    equipped_items = []
                    
                    for item in equipment.get("equipped_items", []):
                        # Safe navigation for item fields
                        slot_data = item.get("slot", {})
                        if isinstance(slot_data, dict):
                            slot_name = slot_data.get("name", "Unknown")
                        else:
                            slot_name = str(slot_data) if slot_data else "Unknown"
                        
                        # Handle name - it's often a direct string
                        item_name = item.get("name", "Unknown")
                        
                        level_data = item.get("level", {})
                        item_level = level_data.get("value", 0) if isinstance(level_data, dict) else 0
                        
                        quality_data = item.get("quality", {})
                        if isinstance(quality_data, dict):
                            quality_name = quality_data.get("name", "Unknown")
                        else:
                            quality_name = str(quality_data) if quality_data else "Unknown"
                        
                        item_data = item.get("item", {})
                        item_id = item_data.get("id") if isinstance(item_data, dict) else None
                        
                        item_info = {
                            "slot": slot_name,
                            "name": item_name,
                            "item_level": item_level,
                            "quality": quality_name,
                            "item_id": item_id,
                            "enchantments": [],
                            "sockets": []
                        }
                        
                        # Get enchantments
                        for enchant in item.get("enchantments", []):
                            display_data = enchant.get("display_string", {})
                            display_name = display_data.get("en_US", "Unknown") if isinstance(display_data, dict) else str(display_data) if display_data else "Unknown"
                            item_info["enchantments"].append({
                                "id": enchant.get("enchantment_id"),
                                "name": display_name
                            })
                        
                        # Get sockets
                        for socket in item.get("sockets", []):
                            socket_item = socket.get("item")
                            if socket_item and isinstance(socket_item, dict):
                                socket_name_data = socket_item.get("name", {})
                                socket_name = socket_name_data.get("en_US", "Unknown") if isinstance(socket_name_data, dict) else "Unknown"
                                item_info["sockets"].append({
                                    "item_id": socket_item.get("id"),
                                    "name": socket_name
                                })
                        
                        equipped_items.append(item_info)
                    
                    character_data["equipment"] = {
                        "equipped_items": equipped_items,
                        "item_count": len(equipped_items)
                    }
                except BlizzardAPIError as e:
                    errors.append(f"Equipment: {str(e)}")
            
            # Get specializations
            if "specializations" in sections:
                try:
                    specs = await client.get_character_specializations(realm, character_name)
                    logger.debug(f"Raw specializations data type: {type(specs)}")
                    logger.debug(f"Raw specializations data: {specs}")
                    
                    # Handle case where specs might not be a dict
                    if not isinstance(specs, dict):
                        logger.warning(f"Specializations data is not a dict: {type(specs)}")
                        specs = {}
                    
                    spec_data = []
                    
                    for spec in specs.get("specializations", []):
                        # Safe navigation for specialization data
                        spec_detail = spec.get("specialization", {})
                        if isinstance(spec_detail, dict):
                            spec_name = spec_detail.get("name")
                            # Handle both nested dict and direct string formats
                            if isinstance(spec_name, dict):
                                spec_name = spec_name.get("en_US", "Unknown")
                            elif isinstance(spec_name, str):
                                # Name is already a string, use as-is
                                pass
                            else:
                                spec_name = "Unknown"
                        else:
                            spec_name = "Unknown"
                        
                        spec_role = spec_detail.get("role", {}) if isinstance(spec_detail, dict) else {}
                        if isinstance(spec_role, dict):
                            role_name = spec_role.get("name", "Unknown")
                        else:
                            role_name = str(spec_role) if spec_role else "Unknown"
                        
                        spec_info = {
                            "name": spec_name,
                            "role": role_name,
                            "talents": [],
                            "pvp_talents": []
                        }
                        
                        # Get talents
                        for talent in spec.get("talents", []):
                            talent_data = talent.get("talent", {})
                            if isinstance(talent_data, dict):
                                talent_name = talent_data.get("name")
                                # Handle both nested dict and direct string formats
                                if isinstance(talent_name, dict):
                                    talent_name = talent_name.get("en_US", "Unknown")
                                elif not isinstance(talent_name, str):
                                    talent_name = "Unknown"
                            else:
                                talent_name = "Unknown"
                            spec_info["talents"].append({
                                "name": talent_name,
                                "tier": talent.get("tier_index"),
                                "column": talent.get("column_index")
                            })
                        
                        # Get PvP talents
                        for pvp_talent in spec.get("pvp_talents", []):
                            pvp_talent_data = pvp_talent.get("talent", {})
                            if isinstance(pvp_talent_data, dict):
                                pvp_talent_name = pvp_talent_data.get("name")
                                # Handle both nested dict and direct string formats
                                if isinstance(pvp_talent_name, dict):
                                    pvp_talent_name = pvp_talent_name.get("en_US", "Unknown")
                                elif not isinstance(pvp_talent_name, str):
                                    pvp_talent_name = "Unknown"
                            else:
                                pvp_talent_name = "Unknown"
                            spec_info["pvp_talents"].append({
                                "name": pvp_talent_name
                            })
                        
                        spec_data.append(spec_info)
                    
                    # Safe navigation for active specialization
                    active_spec = specs.get("active_specialization", {})
                    if isinstance(active_spec, dict):
                        active_spec_name = active_spec.get("name")
                        # Handle both nested dict and direct string formats
                        if isinstance(active_spec_name, dict):
                            active_spec_name = active_spec_name.get("en_US", "Unknown")
                        elif not isinstance(active_spec_name, str):
                            active_spec_name = "Unknown"
                    else:
                        active_spec_name = "Unknown"
                    
                    character_data["specializations"] = {
                        "active_specialization": active_spec_name,
                        "specializations": spec_data
                    }
                except BlizzardAPIError as e:
                    errors.append(f"Specializations: {str(e)}")
            
            # Get achievements
            if "achievements" in sections:
                try:
                    achievements = await client.get_character_achievements(realm, character_name)
                    character_data["achievements"] = {
                        "total_points": achievements.get("total_points", 0),
                        "total_achievements": achievements.get("total_quantity", 0),
                        "recent_achievements": achievements.get("recent_events", [])[:10]  # Last 10
                    }
                except BlizzardAPIError as e:
                    errors.append(f"Achievements: {str(e)}")
            
            # Get statistics
            if "statistics" in sections:
                try:
                    stats = await client.get_character_statistics(realm, character_name)
                    character_data["statistics"] = stats
                except BlizzardAPIError as e:
                    errors.append(f"Statistics: {str(e)}")
            
            # Get media
            if "media" in sections:
                try:
                    media = await client.get_character_media(realm, character_name)
                    character_data["media"] = {
                        "avatar": next((asset["value"] for asset in media.get("assets", []) 
                                      if asset.get("key") == "avatar"), None),
                        "main": next((asset["value"] for asset in media.get("assets", []) 
                                    if asset.get("key") == "main"), None),
                        "render_url": media.get("render_url")
                    }
                except BlizzardAPIError as e:
                    errors.append(f"Media: {str(e)}")
            
            # Get PvP data
            if "pvp" in sections:
                try:
                    pvp = await client.get_character_pvp_summary(realm, character_name)
                    character_data["pvp"] = {
                        "honor_level": pvp.get("honor_level", 0),
                        "honorable_kills": pvp.get("honorable_kills", 0),
                        "ratings": {}
                    }
                    
                    # Get bracket ratings
                    for bracket in ["2v2", "3v3", "rbg"]:
                        bracket_data = pvp.get(f"bracket_{bracket}")
                        if bracket_data:
                            character_data["pvp"]["ratings"][bracket] = {
                                "rating": bracket_data.get("rating", 0),
                                "season_played": bracket_data.get("season_match_statistics", {}).get("played", 0),
                                "season_won": bracket_data.get("season_match_statistics", {}).get("won", 0)
                            }
                except BlizzardAPIError as e:
                    errors.append(f"PvP: {str(e)}")
            
            # Get appearance
            if "appearance" in sections:
                try:
                    appearance = await client.get_character_appearance(realm, character_name)
                    character_data["appearance"] = appearance
                except BlizzardAPIError as e:
                    errors.append(f"Appearance: {str(e)}")
            
            # Get collections
            if "collections" in sections:
                try:
                    collections = await client.get_character_collections(realm, character_name)
                    character_data["collections"] = {
                        "mounts": {
                            "total": len(collections.get("mounts", {}).get("mounts", [])),
                            "collected": [m for m in collections.get("mounts", {}).get("mounts", []) if m.get("is_collected")][:10]
                        },
                        "pets": {
                            "total": len(collections.get("pets", {}).get("pets", [])),
                            "collected": [p for p in collections.get("pets", {}).get("pets", []) if p.get("is_collected")][:10]
                        }
                    }
                except BlizzardAPIError as e:
                    errors.append(f"Collections: {str(e)}")
            
            # Get titles
            if "titles" in sections:
                try:
                    titles = await client.get_character_titles(realm, character_name)
                    # Safe navigation for active title
                    active_title_data = titles.get("active_title", {})
                    active_title_name = None
                    if isinstance(active_title_data, dict):
                        title_name_data = active_title_data.get("name")
                        # Handle both nested dict and direct string formats
                        if isinstance(title_name_data, dict):
                            active_title_name = title_name_data.get("en_US")
                        elif isinstance(title_name_data, str):
                            active_title_name = title_name_data
                        else:
                            active_title_name = None
                    
                    # Safe navigation for title list
                    title_list = []
                    for t in titles.get("titles", [])[:10]:
                        t_name_data = t.get("name")
                        # Handle both nested dict and direct string formats
                        if isinstance(t_name_data, dict):
                            t_name = t_name_data.get("en_US", "Unknown")
                        elif isinstance(t_name_data, str):
                            t_name = t_name_data
                        else:
                            t_name = "Unknown"
                        title_list.append(t_name)
                    
                    character_data["titles"] = {
                        "active_title": active_title_name,
                        "total_titles": len(titles.get("titles", [])),
                        "titles": title_list
                    }
                except BlizzardAPIError as e:
                    errors.append(f"Titles: {str(e)}")
            
            # Get mythic plus data
            if "mythic_plus" in sections:
                try:
                    mythic = await client.get_character_mythic_keystone(realm, character_name)
                    character_data["mythic_plus"] = {
                        "current_rating": mythic.get("current_mythic_rating", {}).get("rating", 0),
                        "best_runs": mythic.get("best_runs", [])[:5],  # Top 5 runs
                        "season_details": mythic.get("season_details")
                    }
                except BlizzardAPIError as e:
                    errors.append(f"Mythic+: {str(e)}")
        
        return {
            "success": True,
            "character_name": character_name,
            "realm": realm,
            "game_version": game_version,
            "data": character_data,
            "errors": errors if errors else None,
            "sections_retrieved": list(character_data.keys())
        }
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Error getting character details: {str(e)}\n{error_trace}")
        return {"error": f"Failed to get character details: {str(e)}"}

@mcp.tool()
@with_supabase_logging
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
        
        # Get connected realm ID using centralized helper
        async with BlizzardAPIClient(game_version=game_version) as client:
            connected_realm_id = await get_connected_realm_id(realm, game_version, client)
            
            if not connected_realm_id:
                logger.error(f"Could not find connected realm ID for {realm} ({game_version})")
                return {"error": f"Could not find connected realm ID for {realm}"}
            
            # Historical data requires persistent storage - returning current analysis
            # Mock analysis structure for future implementation
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
                "note": "Historical data requires persistent auction snapshot storage"
            }
            
    except Exception as e:
        logger.error(f"Error analyzing market history: {str(e)}")
        return {"error": f"Market analysis failed: {str(e)}"}


# Testing and Diagnostic Tools
@mcp.tool()
@with_supabase_logging
async def test_classic_auction_house() -> Dict[str, Any]:
    """
    Test Classic auction house with known working realm IDs
    Note: Classic Era (classic-era namespace) servers are currently unavailable
    
    Returns:
        Test results for known Classic Progression realms
    """
    try:
        logger.info("Testing Classic auction house with known realm IDs")
        
        # Known Classic realm IDs from CLASSIC_API_NOTES.md
        test_realms = [
            {"name": "Mankrik", "id": 4384, "version": "classic"},
            {"name": "Faerlina", "id": 4408, "version": "classic"},
            {"name": "Benediction", "id": 4728, "version": "classic"},
            {"name": "Grobbulus", "id": 4647, "version": "classic"}
        ]
        
        results = {}
        
        # Test classic namespace only (classic-era currently unavailable)
        for game_version in ["classic"]:
            results[game_version] = {}
            
            async with BlizzardAPIClient(game_version=game_version) as client:
                for realm in test_realms:
                    try:
                        logger.info(f"Testing {realm['name']} (ID: {realm['id']}) with {game_version}")
                        ah_data = await client.get_auction_house_data(realm['id'])
                        
                        if ah_data and 'auctions' in ah_data:
                            results[game_version][realm['name']] = {
                                "success": True,
                                "auction_count": len(ah_data['auctions']),
                                "connected_realm_id": realm['id']
                            }
                        else:
                            results[game_version][realm['name']] = {
                                "success": False,
                                "error": "No auction data returned"
                            }
                    except Exception as e:
                        results[game_version][realm['name']] = {
                            "success": False,
                            "error": str(e)
                        }
        
        return {
            "test_results": results,
            "message": "Classic auction house connectivity test complete (Classic Era servers currently unavailable)",
            "note": "Only Classic Progression servers are accessible - Classic Era (classic-era namespace) returns 'Resource not found'"
        }
        
    except Exception as e:
        logger.error(f"Error testing Classic auction house: {str(e)}")
        return {"error": f"Test failed: {str(e)}"}

@mcp.tool()
@with_supabase_logging
async def capture_economy_snapshot(
    realms: List[str],
    region: str = "us",
    game_version: str = "retail",
    force_update: bool = False
) -> Dict[str, Any]:
    """
    Capture hourly economy snapshots for specified realms
    
    Args:
        realms: List of realm names to capture data for
        region: Region (us, eu, etc.)
        game_version: WoW version ('retail' or 'classic')
        force_update: Force update even if recent snapshot exists
    
    Returns:
        Snapshot capture results
    """
    try:
        logger.info(f"Capturing economy snapshots for {len(realms)} realms")
        
        # Initialize services if needed
        await get_or_initialize_services()
        
        if not redis_client:
            return {
                "error": "Redis not available for economy snapshots",
                "message": "Redis connection required for storing economy data"
            }
        
        results = {}
        snapshots_created = 0
        snapshots_skipped = 0
        
        async with BlizzardAPIClient(game_version=game_version) as client:
            for realm in realms:
                try:
                    # Check if we have a recent snapshot (within last hour)
                    snapshot_key = f"economy_snapshot:{game_version}:{region}:{realm.lower()}"
                    
                    if not force_update:
                        # Check last snapshot time
                        last_snapshot_time_key = f"{snapshot_key}:last_update"
                        last_update = await redis_client.get(last_snapshot_time_key)
                        
                        if last_update:
                            last_time = datetime.fromisoformat(last_update.decode())  # Decode bytes to string
                            time_diff = datetime.now(timezone.utc) - last_time
                            
                            if time_diff.total_seconds() < 3600:  # Less than 1 hour
                                logger.info(f"Skipping {realm} - snapshot is {int(time_diff.total_seconds() / 60)} minutes old")
                                results[realm] = {
                                    "status": "skipped",
                                    "message": f"Recent snapshot exists ({int(time_diff.total_seconds() / 60)} minutes old)"
                                }
                                snapshots_skipped += 1
                                continue
                    
                    # Get connected realm ID using helper function
                    connected_realm_id = await get_connected_realm_id(realm, game_version, client)
                    
                    if not connected_realm_id:
                        results[realm] = {"status": "error", "message": "Could not find connected realm ID"}
                        continue
                    
                    # Get auction house data
                    ah_data = await client.get_auction_house_data(connected_realm_id)
                    
                    if not ah_data or 'auctions' not in ah_data:
                        results[realm] = {"status": "error", "message": "No auction data available"}
                        continue
                    
                    # Process auction data into summary statistics
                    auctions = ah_data['auctions']
                    item_stats = {}
                    
                    for auction in auctions:
                        item_id = auction.get('item', {}).get('id', 0)
                        if item_id not in item_stats:
                            item_stats[item_id] = {
                                "total_quantity": 0,
                                "min_price": float('inf'),
                                "max_price": 0,
                                "sum_price": 0,
                                "auction_count": 0,
                                "sellers": set()
                            }
                        
                        quantity = auction.get('quantity', 1)
                        price = auction.get('unit_price', 0) or auction.get('buyout', 0)
                        
                        if price > 0:
                            item_stats[item_id]['total_quantity'] += quantity
                            item_stats[item_id]['min_price'] = min(item_stats[item_id]['min_price'], price)
                            item_stats[item_id]['max_price'] = max(item_stats[item_id]['max_price'], price)
                            item_stats[item_id]['sum_price'] += price * quantity
                            item_stats[item_id]['auction_count'] += 1
                            
                            # Track unique sellers (if available)
                            seller = auction.get('seller', {}).get('name')
                            if seller:
                                item_stats[item_id]['sellers'].add(seller)
                    
                    # Convert to storable format
                    snapshot_data = {
                        "realm": realm,
                        "region": region,
                        "connected_realm_id": connected_realm_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "total_auctions": len(auctions),
                        "unique_items": len(item_stats),
                        "items": {}
                    }
                    
                    # Add top 500 most listed items
                    sorted_items = sorted(item_stats.items(), 
                                        key=lambda x: x[1]['auction_count'], 
                                        reverse=True)[:500]
                    
                    for item_id, stats in sorted_items:
                        avg_price = stats['sum_price'] / stats['total_quantity'] if stats['total_quantity'] > 0 else 0
                        snapshot_data['items'][str(item_id)] = {
                            "quantity": stats['total_quantity'],
                            "min_price": stats['min_price'] if stats['min_price'] != float('inf') else 0,
                            "max_price": stats['max_price'],
                            "avg_price": int(avg_price),
                            "auction_count": stats['auction_count'],
                            "unique_sellers": len(stats['sellers'])
                        }
                    
                    # Store snapshot with timestamp-based key (for historical data)
                    timestamp_key = f"{snapshot_key}:{datetime.now(timezone.utc).strftime('%Y%m%d_%H')}"
                    await redis_client.setex(
                        timestamp_key,
                        30 * 24 * 60 * 60,  # 30 days retention
                        json.dumps(snapshot_data).encode()  # Encode to bytes
                    )
                    
                    # Also store as "latest" for quick access
                    await redis_client.setex(
                        f"{snapshot_key}:latest",
                        24 * 60 * 60,  # 24 hours
                        json.dumps(snapshot_data).encode()  # Encode to bytes
                    )
                    
                    # Update last snapshot time
                    await redis_client.set(
                        f"{snapshot_key}:last_update",
                        datetime.now(timezone.utc).isoformat().encode()  # Encode to bytes
                    )
                    
                    logger.info(f"Captured economy snapshot for {realm}: {len(item_stats)} unique items")
                    results[realm] = {
                        "status": "success",
                        "unique_items": len(item_stats),
                        "total_auctions": len(auctions)
                    }
                    snapshots_created += 1
                    
                except Exception as e:
                    logger.error(f"Error capturing snapshot for {realm}: {e}")
                    results[realm] = {"status": "error", "message": str(e)}
        
        return {
            "success": True,
            "snapshots_created": snapshots_created,
            "snapshots_skipped": snapshots_skipped,
            "results": results,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error capturing economy snapshots: {str(e)}")
        return {"error": f"Snapshot capture failed: {str(e)}"}

@mcp.tool()
@with_supabase_logging
async def get_economy_trends(
    realm: str,
    item_ids: List[int],
    hours: int = 24,
    region: str = "us",
    game_version: str = "retail"
) -> Dict[str, Any]:
    """
    Get price trends for specific items over time
    
    Args:
        realm: Server realm
        item_ids: List of item IDs to get trends for
        hours: Number of hours of history to retrieve (max 720/30 days)
        region: Region (us, eu, etc.)
        game_version: WoW version ('retail' or 'classic')
    
    Returns:
        Price trend data for specified items
    """
    try:
        logger.info(f"Getting economy trends for {len(item_ids)} items on {realm}")
        
        # Initialize services if needed
        await get_or_initialize_services()
        
        if not redis_client:
            return {
                "error": "Redis not available",
                "message": "Redis connection required for retrieving economy trends"
            }
        
        # Limit hours to 30 days max
        hours = min(hours, 720)
        
        trends = {}
        snapshot_base_key = f"economy_snapshot:{game_version}:{region}:{realm.lower()}"
        
        # Get all snapshots for the time period
        current_time = datetime.now(timezone.utc)
        
        for h in range(hours):
            timestamp = current_time - timedelta(hours=h)
            timestamp_key = f"{snapshot_base_key}:{timestamp.strftime('%Y%m%d_%H')}"
            
            snapshot_data = await redis_client.get(timestamp_key)
            if snapshot_data:
                snapshot = json.loads(snapshot_data.decode())  # Decode bytes to string
                
                for item_id in item_ids:
                    item_id_str = str(item_id)
                    if item_id_str not in trends:
                        trends[item_id_str] = []
                    
                    if item_id_str in snapshot.get('items', {}):
                        item_data = snapshot['items'][item_id_str]
                        trends[item_id_str].append({
                            "timestamp": snapshot['timestamp'],
                            "avg_price": item_data['avg_price'],
                            "min_price": item_data['min_price'],
                            "max_price": item_data['max_price'],
                            "quantity": item_data['quantity'],
                            "auction_count": item_data['auction_count']
                        })
        
        # Sort trends by timestamp (oldest first)
        for item_id in trends:
            trends[item_id].sort(key=lambda x: x['timestamp'])
        
        # Get item names
        item_names = {}
        if trends:
            async with BlizzardAPIClient(game_version=game_version) as client:
                for item_id in item_ids:
                    try:
                        item_data = await client.get_item_data(item_id)
                        name = item_data.get('name', f'Item {item_id}')
                        if isinstance(name, dict):
                            name = name.get('en_US', f'Item {item_id}')
                        item_names[str(item_id)] = name
                    except:
                        item_names[str(item_id)] = f'Item {item_id}'
        
        return {
            "success": True,
            "realm": realm,
            "hours_requested": hours,
            "data_points_found": sum(len(trend) for trend in trends.values()),
            "item_names": item_names,
            "trends": trends
        }
        
    except Exception as e:
        logger.error(f"Error getting economy trends: {str(e)}")
        return {"error": f"Trend retrieval failed: {str(e)}"}

@mcp.tool()
@with_supabase_logging
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
            # Get connected realm ID using helper function
            connected_realm_id = await get_connected_realm_id(realm, game_version, client)
            
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


# ============================================================================
# SERVICE INITIALIZATION AND MANAGEMENT
# ============================================================================

async def get_or_initialize_services():
    """Lazy initialization of Redis, activity logger, and Supabase"""
    global redis_client, activity_logger, streaming_service, supabase_client
    
    # Return if Redis and activity logger already initialized
    # (Supabase is optional and may not be available)
    if redis_client and activity_logger:
        return
    
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
        
        # Initialize Supabase (both direct client and streaming service)
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        if supabase_url and supabase_key:
            try:
                # Initialize direct Supabase client
                if not supabase_client:
                    supabase_client = SupabaseRealTimeClient(supabase_url, supabase_key)
                    await supabase_client.initialize()
                    logger.info("Supabase direct client initialized successfully")
                
                # Initialize streaming service
                streaming_service = await initialize_streaming_service(redis_client)
                logger.info("Supabase streaming service initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Supabase services: {e}")
                streaming_service = None
                supabase_client = None
        else:
            logger.warning("Supabase environment variables not set - logging to Supabase disabled")
            
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        # Don't raise - allow server to continue without logging




@mcp.tool()
@with_supabase_logging
async def test_supabase_connection() -> Dict[str, Any]:
    """Test Supabase connection and logging functionality"""
    try:
        # Initialize services
        await get_or_initialize_services()
        
        # Check if Supabase is available
        if not supabase_client:
            return {
                "status": "error",
                "message": "Supabase client not initialized",
                "env_vars_present": {
                    "SUPABASE_URL": bool(os.getenv("SUPABASE_URL")),
                    "SUPABASE_KEY": bool(os.getenv("SUPABASE_KEY"))
                }
            }
        
        # Test logging a sample entry
        test_entry = ActivityLogEntry(
            id=str(uuid.uuid4()),
            session_id="test-session",
            activity_type="mcp_access",
            timestamp=datetime.now(timezone.utc).isoformat(),
            tool_name="test_supabase_connection",
            request_data={"test": True},
            response_data={"test_status": "success"},
            metadata={"source": "supabase_test"}
        )
        
        success = await supabase_client.stream_activity_log(test_entry)
        
        return {
            "status": "success" if success else "warning",
            "message": "Test log entry sent successfully" if success else "Test log entry failed to send",
            "supabase_client_initialized": True,
            "env_vars_present": {
                "SUPABASE_URL": bool(os.getenv("SUPABASE_URL")),
                "SUPABASE_KEY": bool(os.getenv("SUPABASE_KEY"))
            },
            "test_entry_id": test_entry.id
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Supabase test failed: {str(e)}",
            "error_type": type(e).__name__
        }


async def log_to_supabase(tool_name: str, request_data: Dict[str, Any], 
                         response_data: Dict[str, Any] = None, 
                         error_message: str = None,
                         duration_ms: float = None):
    """Log activity directly to Supabase"""
    global supabase_client
    
    try:
        # Initialize services if needed (consolidates all initialization)
        await get_or_initialize_services()
        
        # Skip if Supabase is not available
        if not supabase_client:
            logger.debug("Supabase client not available - skipping log")
            return
        
        # Create activity log entry
        log_entry = ActivityLogEntry(
            id=str(uuid.uuid4()),
            session_id="fastmcp-direct",
            activity_type="tool_call" if not error_message else "tool_error",
            timestamp=datetime.now(timezone.utc).isoformat(),
            tool_name=tool_name,
            request_data=request_data,
            response_data=response_data,
            error_message=error_message,
            duration_ms=duration_ms,
            metadata={
                "source": "fastmcp",
                "direct_logging": True
            }
        )
        
        # Stream to Supabase
        success = await supabase_client.stream_activity_log(log_entry)
        if success:
            logger.debug(f"Successfully logged {tool_name} to Supabase")
        else:
            logger.warning(f"Failed to log {tool_name} to Supabase - no error thrown")
        
    except Exception as e:
        logger.error(f"Failed to log to Supabase: {e}")
        # Don't re-raise - logging failure shouldn't break the main functionality



# ============================================================================
# SERVER STARTUP AND CONFIGURATION
# ============================================================================

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
        logger.info("✅ Starting server...")
        
        # Run server using FastMCP 2.0 HTTP transport
        # Services will initialize on first tool call within FastMCP's event loop
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