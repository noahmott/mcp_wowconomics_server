"""
Guild analysis and management tools for WoW Guild MCP Server
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

from .base import mcp_tool, with_supabase_logging, get_or_initialize_services
from ..api.blizzard_client import BlizzardAPIClient
from ..workflows.guild_analysis import GuildAnalysisWorkflow
from ..core.constants import KNOWN_CLASSIC_REALMS

# Create workflow instance
guild_workflow = GuildAnalysisWorkflow()

logger = logging.getLogger(__name__)


@mcp_tool()
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
        service_mgr = await get_or_initialize_services()
        redis_client = service_mgr.redis_client
        activity_logger = service_mgr.activity_logger
        
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
            
    except Exception as e:
        logger.error(f"Error analyzing guild: {str(e)}")
        
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        # Log error response
        if activity_logger and log_id:
            await activity_logger.log_response(
                log_id=log_id,
                response_data=None,
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
        
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@mcp_tool()
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
        service_mgr = await get_or_initialize_services()
        redis_client = service_mgr.redis_client
        
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
                            "cache_age_days": cache_age_days,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                    else:
                        logger.info(f"Cache too old ({cache_age_days} days), fetching fresh data")
            except Exception as e:
                logger.warning(f"Error reading cache: {e}")
        
        # Default API-based fetching
        async with BlizzardAPIClient(game_version=game_version) as client:
            # Get guild roster
            roster = await client.get_guild_roster(realm, guild_name)
            
            if not roster.get("members"):
                return {
                    "success": False,
                    "error": "No members found or guild not found",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            
            # Sort and limit members
            members = roster["members"][:limit]
            
            # Sort members based on criteria
            if sort_by == "guild_rank":
                members.sort(key=lambda x: x.get("rank", 999))
            elif sort_by == "level":
                members.sort(key=lambda x: x.get("character", {}).get("level", 0), reverse=True)
            elif sort_by == "name":
                members.sort(key=lambda x: x.get("character", {}).get("name", "").lower())
            
            # Prepare member list with extracted info
            member_list = []
            for member in members:
                character = member.get("character", {})
                member_info = {
                    "name": character.get("name", "Unknown"),
                    "level": character.get("level", 0),
                    "class": character.get("playable_class", {}).get("name", "Unknown"),
                    "race": character.get("playable_race", {}).get("name", "Unknown"),
                    "guild_rank": member.get("rank", 999),
                    "realm": character.get("realm", {}).get("name", realm)
                }
                member_list.append(member_info)
            
            return {
                "success": True,
                "guild_name": guild_name,
                "realm": realm,
                "members": member_list,
                "members_returned": len(member_list),
                "total_members": len(roster["members"]),
                "sorted_by": sort_by,
                "quick_mode": quick_mode,
                "from_cache": False,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error getting guild member list: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }