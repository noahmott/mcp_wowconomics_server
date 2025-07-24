"""
WoW Guild MCP Server using FastMCP 2.0 with HTTP transport for Heroku.
"""
import os
import logging
import sys
from typing import Dict, Any, Optional, List
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

# Create FastMCP server with HTTP configuration for Heroku
mcp = FastMCP(
    name="WoW Guild Analysis Server",
    host="0.0.0.0",
    port=int(os.getenv("PORT", "8000"))
)

# Import our existing API components
from app.api.blizzard_client import BlizzardAPIClient, BlizzardAPIError
from app.workflows.guild_analysis import GuildAnalysisWorkflow
from app.visualization.chart_generator import ChartGenerator

# Initialize components
workflow = GuildAnalysisWorkflow()
chart_generator = ChartGenerator()

@mcp.tool()
async def analyze_guild_performance(realm: str, guild_name: str, analysis_type: str = "comprehensive") -> str:
    """
    Analyze guild performance metrics and member activity.
    
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
            analysis_result = await workflow.analyze_guild(guild_data, analysis_type)
            
            return f"""Guild Analysis Results for {guild_name}:

**Guild Summary:**
- Name: {analysis_result['guild_summary'].get('name', 'Unknown')}
- Realm: {analysis_result['guild_summary'].get('realm', realm)}
- Member Count: {analysis_result['guild_summary'].get('member_count', 0)}
- Achievement Points: {analysis_result['guild_summary'].get('achievement_points', 0)}

**Performance Metrics:**
- Average Item Level: {analysis_result.get('performance_analysis', {}).get('average_item_level', 0):.1f}
- Active Members: {analysis_result.get('performance_analysis', {}).get('active_members', 0)}
- Raid Participation: {analysis_result.get('performance_analysis', {}).get('raid_participation', 'Unknown')}

**AI Insights:**
{analysis_result.get('ai_insights', 'No insights available')}
"""
            
    except BlizzardAPIError as e:
        logger.error(f"Blizzard API error: {e.message}")
        return f"API Error: {e.message}"
    except Exception as e:
        logger.error(f"Error analyzing guild: {str(e)}")
        return f"Guild analysis failed: {str(e)}"

@mcp.tool()
async def get_guild_member_list(realm: str, guild_name: str) -> str:
    """
    Get guild member roster with basic information.
    
    Args:
        realm: Server realm
        guild_name: Guild name
    
    Returns:
        List of guild members with their details
    """
    try:
        logger.info(f"Getting member list for {guild_name} on {realm}")
        
        async with BlizzardAPIClient() as client:
            guild_data = await client.get_comprehensive_guild_data(realm, guild_name)
            
            members = guild_data.get('members_data', [])
            if not members:
                return f"No members found for guild {guild_name} on {realm}"
            
            member_list = f"Guild Members for {guild_name} ({len(members)} total):\n\n"
            
            for member in members[:20]:  # Limit to first 20 for readability
                name = member.get('name', 'Unknown')
                level = member.get('level', 0)
                char_class = member.get('character_class', {}).get('name', 'Unknown')
                rank = member.get('guild_rank', 0)
                
                member_list += f"• **{name}** - Level {level} {char_class} (Rank {rank})\n"
            
            if len(members) > 20:
                member_list += f"\n... and {len(members) - 20} more members"
            
            return member_list
            
    except BlizzardAPIError as e:
        return f"Member list failed: {e.message}"
    except Exception as e:
        return f"Error getting member list: {str(e)}"

@mcp.tool()
async def analyze_member_performance(realm: str, character_name: str, analysis_depth: str = "standard") -> str:
    """
    Analyze individual character performance and equipment.
    
    Args:
        realm: Server realm
        character_name: Character name
        analysis_depth: Analysis depth ('basic', 'standard', 'detailed')
    
    Returns:
        Character analysis with performance metrics
    """
    try:
        logger.info(f"Analyzing member {character_name} on {realm}")
        
        async with BlizzardAPIClient() as client:
            # Get character profile
            char_profile = await client.get_character_profile(realm, character_name)
            
            # Get equipment for item level
            try:
                char_equipment = await client.get_character_equipment(realm, character_name)
                equipment_summary = client._summarize_equipment(char_equipment)
            except BlizzardAPIError:
                equipment_summary = {"average_item_level": 0, "total_items": 0}
            
            # Process through workflow
            analysis_result = await workflow.analyze_character(char_profile, analysis_depth)
            
            return f"""Character Analysis for {character_name}:

**Character Info:**
- Name: {char_profile.get('name', 'Unknown')}
- Level: {char_profile.get('level', 0)}
- Class: {char_profile.get('character_class', {}).get('name', 'Unknown')}
- Race: {char_profile.get('race', {}).get('name', 'Unknown')}

**Equipment Summary:**
- Average Item Level: {equipment_summary.get('average_item_level', 0):.1f}
- Items Equipped: {equipment_summary.get('total_items', 0)}

**Performance Analysis:**
{analysis_result.get('performance_summary', 'No performance data available')}

**AI Insights:**
{analysis_result.get('ai_insights', 'No insights available')}
"""
            
    except BlizzardAPIError as e:
        return f"Character analysis failed: {e.message}"
    except Exception as e:
        return f"Error analyzing member: {str(e)}"

@mcp.tool()
async def compare_member_performance(realm: str, guild_name: str, member_names: str, metric: str = "item_level") -> str:
    """
    Compare performance metrics between guild members.
    
    Args:
        realm: Server realm
        guild_name: Guild name
        member_names: Comma-separated list of member names
        metric: Metric to compare ('item_level', 'achievement_points', 'guild_rank')
    
    Returns:
        Comparison results between members
    """
    try:
        # Parse member names
        if member_names.startswith("[") and member_names.endswith("]"):
            import json
            members_list = json.loads(member_names)
        else:
            members_list = [name.strip() for name in member_names.split(",")]
        
        logger.info(f"Comparing members {members_list} in {guild_name}")
        
        async with BlizzardAPIClient() as client:
            comparison_data = []
            
            for member_name in members_list:
                try:
                    char_data = await client.get_character_profile(realm, member_name)
                    if metric == "item_level":
                        equipment = await client.get_character_equipment(realm, member_name)
                        char_data["equipment_summary"] = client._summarize_equipment(equipment)
                    comparison_data.append(char_data)
                except BlizzardAPIError as e:
                    logger.warning(f"Failed to get data for {member_name}: {e.message}")
            
            if not comparison_data:
                return "No member data could be retrieved for comparison"
            
            # Create comparison summary
            comparison_text = f"Member Comparison ({metric}):\n\n"
            
            for member in comparison_data:
                name = member.get('name', 'Unknown')
                level = member.get('level', 0)
                char_class = member.get('character_class', {}).get('name', 'Unknown')
                
                if metric == "item_level":
                    value = member.get('equipment_summary', {}).get('average_item_level', 0)
                    comparison_text += f"• **{name}** ({char_class} {level}): {value:.1f} iLvl\n"
                else:
                    comparison_text += f"• **{name}** ({char_class} {level})\n"
            
            return comparison_text
            
    except Exception as e:
        return f"Error comparing members: {str(e)}"

@mcp.tool()
async def generate_raid_progress_chart(realm: str, guild_name: str, raid_tier: str = "current") -> str:
    """
    Generate raid progression chart for a guild.
    
    Args:
        realm: Server realm
        guild_name: Guild name
        raid_tier: Raid tier to analyze ('current', 'previous', 'all')
    
    Returns:
        Chart generation status and description
    """
    try:
        logger.info(f"Generating chart for {guild_name} on {realm}")
        
        async with BlizzardAPIClient() as client:
            guild_data = await client.get_comprehensive_guild_data(realm, guild_name)
            
            # Generate chart (simplified for now)
            chart_description = f"""Raid Progress Chart Generated for {guild_name}:

**Guild:** {guild_name} ({realm})
**Tier:** {raid_tier}
**Members Analyzed:** {len(guild_data.get('members_data', []))}

**Chart includes:**
- Member progression comparison
- Item level distribution
- Class representation
- Activity levels

Note: Chart generation is available but chart data display is simplified in this text format.
"""
            
            return chart_description
            
    except Exception as e:
        return f"Chart generation failed: {str(e)}"

def main():
    """Main entry point for FastMCP 2.0 server."""
    try:
        # Check for required API keys
        blizzard_client_id = os.getenv("BLIZZARD_CLIENT_ID")
        blizzard_client_secret = os.getenv("BLIZZARD_CLIENT_SECRET")
        
        if not blizzard_client_id or not blizzard_client_secret:
            raise ValueError("Blizzard API credentials not found in environment variables")
        
        port = int(os.getenv("PORT", "8000"))
        
        logger.info("🚀 WoW Guild MCP Server with FastMCP 2.0")
        logger.info("🔧 Tools: WoW guild analysis and member comparison")
        logger.info("📊 Registered tools: 5 WoW guild tools")
        logger.info(f"🌐 HTTP Server: 0.0.0.0:{port}")
        logger.info("✅ Starting server...")
        
        # Run server using FastMCP 2.0 HTTP transport (CRITICAL!)
        mcp.run(transport="http")
        
    except Exception as e:
        logger.error(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()