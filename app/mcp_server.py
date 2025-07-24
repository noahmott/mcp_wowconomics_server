"""
MCP Server Implementation for WoW Guild Analysis
"""

import os
import logging
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import json

# MCP imports - will be available when MCP is properly installed
# from mcp.server.fastapi import FastMCPServer
# from mcp.server.models import Tool
# from mcp.types import TextContent, ImageContent

# For now, create a mock MCP server class
class MockMCPServer:
    def __init__(self, name: str, version: str, description: str):
        self.name = name
        self.version = version
        self.description = description
        self.tools = {}
    
    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func
        return decorator

from .api.blizzard_client import BlizzardAPIClient, BlizzardAPIError
from .visualization.chart_generator import ChartGenerator
from .workflows.guild_analysis import GuildAnalysisWorkflow

logger = logging.getLogger(__name__)


class WoWGuildMCPServer:
    """MCP Server for WoW Guild Analysis"""
    
    def __init__(self, app: FastAPI):
        self.app = app
        self.chart_generator = ChartGenerator()
        self.guild_workflow = GuildAnalysisWorkflow()
        
        # Create MCP server (using mock for now)
        self.mcp = MockMCPServer(
            name="WoW Guild Analytics",
            version="1.0.0",
            description="Comprehensive World of Warcraft guild analysis and insights"
        )
        
        # Register tools
        self._register_tools()
        
    def _register_tools(self):
        """Register MCP tools"""
        
        @self.mcp.tool()
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
                    analysis_result = await self.guild_workflow.analyze_guild(
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
                raise HTTPException(status_code=400, detail=f"API Error: {e.message}")
            except Exception as e:
                logger.error(f"Unexpected error analyzing guild: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
        
        @self.mcp.tool()
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
                    chart_data = await self.chart_generator.create_raid_progress_chart(
                        guild_data, raid_tier
                    )
                    
                    return chart_data  # Base64 encoded PNG
                    
            except BlizzardAPIError as e:
                logger.error(f"Blizzard API error: {e.message}")
                raise HTTPException(status_code=400, detail=f"API Error: {e.message}")
            except Exception as e:
                logger.error(f"Error generating chart: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Chart generation failed: {str(e)}")
        
        @self.mcp.tool()
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
                    chart_data = await self.chart_generator.create_member_comparison_chart(
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
                raise HTTPException(status_code=500, detail=f"Comparison failed: {str(e)}")
        
        @self.mcp.tool()
        async def get_guild_member_list(
            realm: str,
            guild_name: str,
            sort_by: str = "guild_rank",
            limit: int = 50
        ) -> Dict[str, Any]:
            """
            Get detailed guild member list with sorting options
            
            Args:
                realm: Server realm
                guild_name: Guild name
                sort_by: Sort criteria ('guild_rank', 'level', 'name', 'last_login')
                limit: Maximum number of members to return
            
            Returns:
                Detailed member list with metadata
            """
            try:
                logger.info(f"Getting member list for {guild_name} on {realm}")
                
                async with BlizzardAPIClient() as client:
                    guild_data = await client.get_comprehensive_guild_data(realm, guild_name)
                    
                    members = guild_data.get("members_data", [])[:limit]
                    
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
                        "total_members": len(members),
                        "sorted_by": sort_by,
                        "guild_summary": guild_data.get("guild_info", {}),
                        "timestamp": guild_data["fetch_timestamp"]
                    }
                    
            except BlizzardAPIError as e:
                logger.error(f"Blizzard API error: {e.message}")
                raise HTTPException(status_code=400, detail=f"API Error: {e.message}")
            except Exception as e:
                logger.error(f"Error getting member list: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Member list failed: {str(e)}")
        
        @self.mcp.tool()
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
                    analysis_result = await self.guild_workflow.analyze_member(
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
                raise HTTPException(status_code=400, detail=f"API Error: {e.message}")
            except Exception as e:
                logger.error(f"Error analyzing member: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Member analysis failed: {str(e)}")


def setup_mcp_server(app: FastAPI):
    """Setup MCP server with FastAPI app"""
    try:
        mcp_server = WoWGuildMCPServer(app)
        
        # Simple bearer token authentication
        security = HTTPBearer()
        
        async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
            """Verify the bearer token"""
            token = credentials.credentials
            expected_token = os.getenv("MCP_AUTH_TOKEN", "default-token-please-change")
            
            if token != expected_token:
                raise HTTPException(status_code=401, detail="Invalid authentication token")
            return token
        
        # MCP protocol endpoints
        @app.get("/mcp")
        async def mcp_info():
            """MCP server information"""
            return {
                "mcp_version": "1.0",
                "server_name": "wow-guild-mcp",
                "description": "World of Warcraft Guild Analysis MCP Server",
                "auth_required": True
            }
        
        @app.get("/mcp/tools", dependencies=[Depends(verify_token)])
        async def list_tools():
            """List available MCP tools"""
            tools = []
            for name, func in mcp_server.mcp.tools.items():
                tools.append({
                    "name": name,
                    "description": func.__doc__.strip() if func.__doc__ else "",
                    "input_schema": {
                        "type": "object",
                        "properties": {},  # TODO: Extract from function signature
                        "required": []
                    }
                })
            return {"tools": tools}
        
        @app.post("/mcp/tools/call", dependencies=[Depends(verify_token)])
        async def call_tool(request: dict):
            """Call an MCP tool"""
            tool_name = request.get("name")
            arguments = request.get("arguments", {})
            
            if tool_name in mcp_server.mcp.tools:
                tool_func = mcp_server.mcp.tools[tool_name]
                try:
                    result = await tool_func(**arguments)
                    return {"content": [{"type": "text", "text": json.dumps(result)}]}
                except Exception as e:
                    logger.error(f"Tool execution error: {str(e)}")
                    raise HTTPException(status_code=500, detail=str(e))
            else:
                raise HTTPException(status_code=404, detail=f"Tool {tool_name} not found")
        
        # Add OPTIONS handler for CORS preflight
        @app.options("/mcp/tools/call")
        async def options_handler():
            return {"status": "ok"}
        
        logger.info("MCP server setup completed with authentication")
        
        return mcp_server
        
    except Exception as e:
        logger.error(f"Failed to setup MCP server: {str(e)}")
        raise