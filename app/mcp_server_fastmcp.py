"""
WoW Guild MCP Server using FastMCP 2.0 with HTTP transport for Heroku
"""
import os
import logging
from dotenv import load_dotenv
from fastmcp import FastMCP
from typing import Dict, Any, List, Optional

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

# Initialize service instances
chart_generator = ChartGenerator()
guild_workflow = GuildAnalysisWorkflow()

# Register WoW Guild tools using FastMCP decorators
@mcp.tool()
async def analyze_guild_performance(
    realm: str,
    guild_name: str,
    analysis_type: str = "comprehensive"
) -> Dict[str, Any]:
    """
    Analyze guild performance metrics and member activity
    
    Args:
        realm: Server realm (e.g., 'stormrage', 'area-52')
        guild_name: Guild name
        analysis_type: Type of analysis ('comprehensive', 'basic', 'performance')
    
    Returns:
        Guild analysis results with performance metrics
    """
    try:
        logger.info(f"Analyzing guild {guild_name} on {realm}")
        
        async with BlizzardAPIClient() as client:
            # Get comprehensive guild data
            guild_data = await client.get_comprehensive_guild_data(realm, guild_name)
            
            # Process through workflow
            analysis_result = await guild_workflow.analyze_guild(
                guild_data, analysis_type
            )
            
            return {
                "success": True,
                "guild_info": analysis_result["guild_summary"],
                "member_data": analysis_result["member_analysis"],
                "analysis_results": analysis_result["performance_insights"],
                "visualization_urls": analysis_result.get("chart_urls", []),
                "analysis_type": analysis_type,
                "timestamp": guild_data["fetch_timestamp"]
            }
            
    except BlizzardAPIError as e:
        logger.error(f"Blizzard API error: {e.message}")
        return {"error": f"API Error: {e.message}"}
    except Exception as e:
        logger.error(f"Unexpected error analyzing guild: {str(e)}")
        return {"error": f"Analysis failed: {str(e)}"}

@mcp.tool()
async def get_guild_member_list(
    realm: str,
    guild_name: str,
    sort_by: str = "guild_rank",
    limit: int = 50,
    quick_mode: bool = False
) -> Dict[str, Any]:
    """
    Get detailed guild member list with sorting options
    
    Args:
        realm: Server realm
        guild_name: Guild name
        sort_by: Sort criteria ('guild_rank', 'level', 'name', 'last_login')
        limit: Maximum number of members to return
        quick_mode: Use optimized fetcher for faster results
    
    Returns:
        Detailed member list with metadata
    """
    try:
        logger.info(f"Getting member list for {guild_name} on {realm}")
        
        async with BlizzardAPIClient() as client:
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
    analysis_depth: str = "standard"
) -> Dict[str, Any]:
    """
    Analyze individual member performance and progression
    
    Args:
        realm: Server realm
        character_name: Character name to analyze
        analysis_depth: Analysis depth ('basic', 'standard', 'detailed')
    
    Returns:
        Comprehensive member analysis
    """
    try:
        logger.info(f"Analyzing member {character_name} on {realm}")
        
        async with BlizzardAPIClient() as client:
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
    raid_tier: str = "current"
) -> str:
    """
    Generate visual raid progression charts
    
    Args:
        realm: Server realm
        guild_name: Guild name
        raid_tier: Raid tier ('current', 'dragonflight', 'shadowlands')
    
    Returns:
        Base64 encoded image of the raid progression chart
    """
    try:
        logger.info(f"Generating raid chart for {guild_name} on {realm}")
        
        async with BlizzardAPIClient() as client:
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
    metric: str = "item_level"
) -> Dict[str, Any]:
    """
    Compare performance metrics across guild members
    
    Args:
        realm: Server realm
        guild_name: Guild name
        member_names: List of character names to compare
        metric: Metric to compare ('item_level', 'achievement_points', 'guild_rank')
    
    Returns:
        Comparison results with chart data
    """
    try:
        logger.info(f"Comparing members {member_names} in {guild_name}")
        
        async with BlizzardAPIClient() as client:
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
        logger.info("🔧 Tools: WoW guild analysis and visualization")
        logger.info(f"📊 Registered tools: {len(mcp._tool_manager._tools)}")
        logger.info(f"🌐 HTTP Server: 0.0.0.0:{port}")
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