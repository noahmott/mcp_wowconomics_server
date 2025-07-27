"""
MCP Server Implementation for WoW Guild Analysis with Redis
"""

import os
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Request
import json

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
from .api.guild_optimizations import OptimizedGuildFetcher
from .visualization.chart_generator import ChartGenerator
from .workflows.guild_analysis import GuildAnalysisWorkflow
from .services.redis_staging import RedisDataStagingService
from .services.activity_logger import ActivityLogger, get_activity_logger

logger = logging.getLogger(__name__)


class WoWGuildMCPServerRedis:
    """MCP Server for WoW Guild Analysis with Redis backend"""
    
    def __init__(self, app: FastAPI):
        self.app = app
        self.chart_generator = ChartGenerator()
        self.guild_workflow = GuildAnalysisWorkflow()
        self.activity_logger = None  # Will be initialized when Redis is available
        
        # Create MCP server (using mock for now)
        self.mcp = MockMCPServer(
            name="WoW Guild Analytics",
            version="2.0.0",
            description="Comprehensive World of Warcraft guild analysis with Redis caching"
        )
        
        # Register tools
        self._register_tools()
    
    def _get_redis_staging(self) -> RedisDataStagingService:
        """Get Redis staging service from app state"""
        if hasattr(self.app.state, 'redis'):
            return RedisDataStagingService(self.app.state.redis)
        raise RuntimeError("Redis not initialized")
    
    async def _get_activity_logger(self) -> ActivityLogger:
        """Get activity logger instance"""
        if self.activity_logger is None:
            if hasattr(self.app.state, 'redis'):
                self.activity_logger = await get_activity_logger(self.app.state.redis)
            else:
                raise RuntimeError("Redis not initialized")
        return self.activity_logger
    
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
                
                # Get data from Redis staging
                staging = self._get_redis_staging()
                cache_key = f"{realm}:{guild_name}"
                
                # Try to get from cache first
                guild_data = await staging.get_data('guild', cache_key)
                
                if guild_data:
                    # Process through workflow
                    analysis_result = await self.guild_workflow.analyze_guild(
                        guild_data, analysis_type
                    )
                    
                    # Extract data from nested workflow result structure
                    guild_overview = analysis_result.get("analysis_results", {}).get("guild_overview", {})
                    guild_summary = guild_overview.get("guild_summary", {})
                    member_stats = guild_overview.get("member_statistics", {})
                    
                    # Check cache metadata
                    cache_metadata = guild_data.get('_metadata', {})
                    cached_at = cache_metadata.get('cached_at', '')
                    ttl_remaining = cache_metadata.get('ttl', 0)
                    
                    return {
                        "success": True,
                        "guild_info": guild_summary,
                        "member_statistics": member_stats,
                        "analysis_results": analysis_result.get("analysis_results", {}),
                        "visualization_urls": analysis_result.get("visualization_urls", []),
                        "analysis_type": analysis_type,
                        "timestamp": datetime.utcnow().isoformat(),
                        "cached": not guild_data.get('synthetic', False),
                        "cache_info": {
                            "cached_at": cached_at,
                            "ttl_remaining_seconds": ttl_remaining if ttl_remaining > 0 else None,
                            "cache_source": cache_metadata.get('source', 'unknown'),
                            "data_type": "guild"
                        }
                    }
                else:
                    raise HTTPException(status_code=404, detail="Guild data not found")
                    
            except Exception as e:
                logger.error(f"Error analyzing guild: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
        
        @self.mcp.tool()
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
                quick_mode: Use optimized fetching for large guilds
            
            Returns:
                Detailed member list with metadata
            """
            try:
                logger.info(f"Getting member list for {guild_name} on {realm}")
                
                # Get data from Redis staging
                staging = self._get_redis_staging()
                cache_key = f"{realm}:{guild_name}"
                
                if quick_mode:
                    # Use roster endpoint for quick mode
                    roster_data = await staging.get_data('guild_roster', cache_key)
                    
                    if roster_data and 'members' in roster_data:
                        members = roster_data['members'][:limit]
                        
                        # Convert to simpler format
                        member_list = []
                        for m in members:
                            char = m.get('character', {})
                            member_list.append({
                                'name': char.get('name', 'Unknown'),
                                'level': char.get('level', 0),
                                'character_class': char.get('playable_class', {}).get('name', 'Unknown'),
                                'guild_rank': m.get('rank', 999)
                            })
                        
                        # Sort members
                        if sort_by == "guild_rank":
                            member_list.sort(key=lambda x: x.get('guild_rank', 999))
                        elif sort_by == "level":
                            member_list.sort(key=lambda x: x.get('level', 0), reverse=True)
                        elif sort_by == "name":
                            member_list.sort(key=lambda x: x.get('name', '').lower())
                        
                        # Check cache metadata
                        cache_metadata = roster_data.get('_metadata', {})
                        cached_at = cache_metadata.get('cached_at', '')
                        ttl_remaining = cache_metadata.get('ttl', 0)
                        
                        return {
                            "success": True,
                            "guild_name": guild_name,
                            "realm": realm,
                            "members": member_list,
                            "members_returned": len(member_list),
                            "total_members": len(roster_data.get('members', [])),
                            "sorted_by": sort_by,
                            "quick_mode": quick_mode,
                            "timestamp": datetime.utcnow().isoformat(),
                            "cached": not roster_data.get('synthetic', False),
                            "cache_info": {
                                "cached_at": cached_at,
                                "ttl_remaining_seconds": ttl_remaining if ttl_remaining > 0 else None,
                                "cache_source": cache_metadata.get('source', 'unknown'),
                                "data_type": "guild_roster"
                            }
                        }
                else:
                    # Get full guild data
                    guild_data = await staging.get_data('guild', cache_key)
                    
                    if guild_data and 'members_data' in guild_data:
                        members = guild_data['members_data'][:limit]
                        
                        # Sort members
                        if sort_by == "guild_rank":
                            members.sort(key=lambda x: x.get('guild_rank', 999))
                        elif sort_by == "level":
                            members.sort(key=lambda x: x.get('level', 0), reverse=True)
                        elif sort_by == "name":
                            members.sort(key=lambda x: x.get('name', '').lower())
                        
                        # Check cache metadata
                        cache_metadata = guild_data.get('_metadata', {})
                        cached_at = cache_metadata.get('cached_at', '')
                        ttl_remaining = cache_metadata.get('ttl', 0)
                        
                        return {
                            "success": True,
                            "guild_name": guild_name,
                            "realm": realm,
                            "members": members,
                            "members_returned": len(members),
                            "total_members": guild_data.get('guild_info', {}).get('member_count', len(members)),
                            "sorted_by": sort_by,
                            "quick_mode": quick_mode,
                            "guild_summary": guild_data.get('guild_info', {}),
                            "timestamp": datetime.utcnow().isoformat(),
                            "cached": not guild_data.get('synthetic', False),
                            "cache_info": {
                                "cached_at": cached_at,
                                "ttl_remaining_seconds": ttl_remaining if ttl_remaining > 0 else None,
                                "cache_source": cache_metadata.get('source', 'unknown'),
                                "data_type": "guild"
                            }
                        }
                
                raise HTTPException(status_code=404, detail="Guild not found")
                
            except Exception as e:
                logger.error(f"Error getting member list: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Failed to get member list: {str(e)}")
        
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
                
                # Get data from Redis staging
                staging = self._get_redis_staging()
                cache_key = f"{realm}:{character_name}"
                
                # Get character data
                char_data = await staging.get_data('character', cache_key)
                
                if char_data:
                    # Process through member analysis workflow
                    analysis_result = await self.guild_workflow.analyze_member(
                        char_data, analysis_depth
                    )
                    
                    return {
                        "success": True,
                        "character_name": character_name,
                        "realm": realm,
                        "member_info": analysis_result["character_summary"],
                        "performance_metrics": analysis_result["performance_analysis"],
                        "equipment_analysis": analysis_result["equipment_insights"],
                        "progression_summary": analysis_result.get("progression_summary", {}),
                        "analysis_depth": analysis_depth,
                        "timestamp": datetime.utcnow().isoformat(),
                        "cached": not char_data.get('synthetic', False)
                    }
                else:
                    raise HTTPException(status_code=404, detail="Character not found")
                    
            except Exception as e:
                logger.error(f"Error analyzing member: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Member analysis failed: {str(e)}")
        
        @self.mcp.tool()
        async def check_guild_cache_status(
            realm: str,
            guild_name: str
        ) -> Dict[str, Any]:
            """
            Check cache status for specific guild data
            
            Args:
                realm: Server realm (e.g., 'stormrage', 'area-52')
                guild_name: Guild name
                
            Returns:
                Cache status for guild data types
            """
            try:
                staging = self._get_redis_staging()
                cache_key = f"{realm}:{guild_name}"
                
                # Check different data types
                data_types = ['guild', 'guild_roster', 'guild_info']
                cache_status = {}
                
                for data_type in data_types:
                    # Build Redis key using same format as staging service
                    region = 'us'  # Default region
                    game_version = 'retail'  # Default game version
                    redis_key = f"{staging.key_prefixes['cache']}:{data_type}:{region}:{game_version}:{cache_key}"
                    
                    # Check if key exists
                    exists = await staging.redis.exists(redis_key)
                    if exists:
                        # Get TTL and metadata
                        ttl = await staging.redis.ttl(redis_key)
                        metadata_key = f"{staging.key_prefixes['meta']}:{data_type}:{region}:{game_version}:{cache_key}"
                        metadata = await staging.redis.hgetall(metadata_key)
                        
                        cache_status[data_type] = {
                            "cached": True,
                            "ttl_remaining_seconds": ttl if ttl > 0 else None,
                            "cached_at": metadata.get(b'cached_at', b'').decode('utf-8') if metadata else '',
                            "cache_source": metadata.get(b'source', b'unknown').decode('utf-8') if metadata else 'unknown',
                            "expires_in_minutes": round(ttl / 60, 1) if ttl > 0 else 0
                        }
                    else:
                        cache_status[data_type] = {
                            "cached": False,
                            "ttl_remaining_seconds": None,
                            "cached_at": None,
                            "cache_source": None,
                            "expires_in_minutes": 0
                        }
                
                return {
                    "success": True,
                    "guild_name": guild_name,
                    "realm": realm,
                    "cache_status": cache_status,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
            except Exception as e:
                logger.error(f"Error checking guild cache: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Failed to check guild cache: {str(e)}")
        
        @self.mcp.tool()
        async def get_cache_statistics() -> Dict[str, Any]:
            """
            Get Redis cache statistics
            
            Returns:
                Cache statistics and metadata
            """
            try:
                staging = self._get_redis_staging()
                stats = await staging.get_cache_stats()
                
                return {
                    "success": True,
                    "statistics": stats,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
            except Exception as e:
                logger.error(f"Error getting cache stats: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Failed to get cache stats: {str(e)}")


def setup_mcp_server(app: FastAPI):
    """Setup MCP server with FastAPI app"""
    try:
        mcp_server = WoWGuildMCPServerRedis(app)
        
        # MCP Server-Sent Events endpoint for Claude.ai
        from fastapi.responses import StreamingResponse
        import asyncio
        
        @app.get("/sse")
        async def mcp_sse():
            """MCP Server-Sent Events endpoint for Claude.ai"""
            
            async def event_stream():
                # Send server info on connection
                server_info = {
                    "jsonrpc": "2.0",
                    "method": "initialize",
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": {
                            "name": "wow-guild-mcp",
                            "version": "2.0.0"
                        },
                        "capabilities": {
                            "tools": {
                                tool_name: {
                                    "description": func.__doc__.strip() if func.__doc__ else "",
                                    "inputSchema": {
                                        "type": "object",
                                        "properties": {}
                                    }
                                } for tool_name, func in mcp_server.mcp.tools.items()
                            }
                        }
                    }
                }
                
                yield f"data: {json.dumps(server_info)}\n\n"
                
                # Keep connection alive
                while True:
                    await asyncio.sleep(30)
                    yield f"data: {json.dumps({'type': 'ping'})}\n\n"
            
            return StreamingResponse(
                event_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                }
            )
        
        @app.post("/mcp")
        async def mcp_jsonrpc(request_data: dict, request: Request):
            """Handle MCP JSON-RPC requests"""
            print("*** CRITICAL DEBUG: MCP ENDPOINT HIT ***")
            logger.info(f"*** CRITICAL DEBUG: MCP ENDPOINT HIT ***")
            logger.info(f"MCP request: {request_data}")
            
            # Log the full request details
            logger.info("="*60)
            logger.info("FULL MCP REQUEST DETAILS:")
            logger.info(f"Headers: {dict(request.headers)}")
            logger.info(f"Method: {request_data.get('method')}")
            logger.info(f"Params: {json.dumps(request_data.get('params', {}), indent=2)}")
            logger.info(f"ID: {request_data.get('id')}")
            logger.info("="*60)
            
            method = request_data.get("method")
            params = request_data.get("params", {})
            request_id = request_data.get("id")
            
            # Extract session ID from headers
            session_id = request.headers.get("mcp-session-id", "unknown")
            print(f"*** DEBUG: Method={method}, Session={session_id}, ID={request_id} ***")
            logger.info(f"=== MCP ENDPOINT DEBUG ===")
            logger.info(f"Method: {method}")
            logger.info(f"Session ID: {session_id}")
            logger.info(f"Request ID: {request_id}")
            
            if method == "initialize":
                # Handle MCP initialization
                import uuid
                session_id = str(uuid.uuid4()).replace("-", "")
                
                # Store session in app state for validation
                if not hasattr(app, "mcp_sessions"):
                    app.mcp_sessions = {}
                app.mcp_sessions[session_id] = {
                    "created": datetime.utcnow(),
                    "client_info": params.get("clientInfo", {})
                }
                
                from fastapi.responses import JSONResponse
                response = JSONResponse(
                    content={
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "protocolVersion": "2024-11-05",
                            "serverInfo": {
                                "name": "wow-guild-mcp",
                                "version": "2.0.0"
                            },
                            "capabilities": {
                                "tools": {}
                            }
                        }
                    },
                    headers={"mcp-session-id": session_id}
                )
                
                return response
            
            elif method == "tools/list":
                tools = []
                for name, func in mcp_server.mcp.tools.items():
                    tools.append({
                        "name": name,
                        "description": func.__doc__.strip() if func.__doc__ else "",
                        "inputSchema": {
                            "type": "object",
                            "properties": {}
                        }
                    })
                
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"tools": tools}
                }
            
            elif method == "tools/call":
                print("*** CRITICAL: ENTERING TOOLS/CALL SECTION ***")
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                reasoning = params.get("reasoning")  # Client's original query/context
                context = params.get("context")  # Additional context if provided
                print(f"*** TOOL CALL: {tool_name} with args {arguments} ***")
                
                # Test if this code block executes at all
                logger.info(f"=== ENTERING TOOL CALL SECTION ===")
                logger.info(f"Tool: {tool_name}")
                logger.info(f"Arguments: {arguments}")
                logger.info(f"Session: {session_id}")
                
                # Log client's original query if provided
                if reasoning:
                    logger.info(f"Client Query/Reasoning: {reasoning}")
                if context:
                    logger.info(f"Additional Context: {context}")
                
                # Simple test log first
                try:
                    logger.info("Testing activity logger availability...")
                    if hasattr(app.state, 'activity_logger'):
                        logger.info("app.state.activity_logger EXISTS")
                        if app.state.activity_logger:
                            logger.info("Activity logger is NOT None - attempting to log")
                            
                            # Manual test of basic logging
                            await app.state.activity_logger.log_activity(
                                session_id=session_id,
                                activity_type="tool_call",
                                tool_name=tool_name,
                                metadata={
                                    "arguments": arguments,
                                    "method": method,
                                    "request_id": request_id,
                                    "reasoning": reasoning,
                                    "context": context,
                                    "client_query": reasoning or context  # Store original query
                                }
                            )
                            logger.info("*** TOOL CALL LOGGED SUCCESSFULLY ***")
                        else:
                            logger.error("Activity logger is None")
                    else:
                        logger.error("app.state.activity_logger does NOT exist")
                except Exception as e:
                    logger.error(f"ACTIVITY LOGGING FAILED: {e}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
                
                if tool_name in mcp_server.mcp.tools:
                    try:
                        tool_func = mcp_server.mcp.tools[tool_name]
                        result = await tool_func(**arguments)
                        
                        # Log successful response
                        try:
                            if hasattr(app.state, 'activity_logger') and app.state.activity_logger:
                                await app.state.activity_logger.log_activity(
                                    session_id=session_id,
                                    activity_type="tool_response",
                                    tool_name=tool_name,
                                    metadata={
                                        "success": True,
                                        "result_size": len(str(result)) if result else 0
                                    }
                                )
                                logger.info(f"SUCCESS: Tool response logged for {tool_name}")
                        except Exception as e:
                            logger.error(f"ERROR: Failed to log tool response: {e}")
                        
                        response = {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "result": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": json.dumps(result)
                                    }
                                ]
                            }
                        }
                        
                        # Log the response
                        logger.info("="*60)
                        logger.info("MCP RESPONSE:")
                        logger.info(f"Tool: {tool_name}")
                        logger.info(f"Success: True")
                        logger.info(f"Response size: {len(json.dumps(response))} bytes")
                        logger.info(f"Content preview: {json.dumps(result)[:200]}...")
                        logger.info("="*60)
                        
                        return response
                    except Exception as e:
                        # Log error response
                        try:
                            if hasattr(app.state, 'activity_logger') and app.state.activity_logger:
                                await app.state.activity_logger.log_activity(
                                    session_id=session_id,
                                    activity_type="tool_error",
                                    tool_name=tool_name,
                                    metadata={
                                        "error_message": str(e),
                                        "success": False
                                    }
                                )
                                logger.info(f"SUCCESS: Tool error logged for {tool_name}")
                        except Exception as log_e:
                            logger.error(f"ERROR: Failed to log tool error: {log_e}")
                        
                        return {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "error": {
                                "code": -32603,
                                "message": str(e)
                            }
                        }
                else:
                    # Log tool not found
                    try:
                        if hasattr(app.state, 'activity_logger') and app.state.activity_logger:
                            await app.state.activity_logger.log_activity(
                                session_id=session_id,
                                activity_type="tool_error",
                                tool_name=tool_name,
                                metadata={
                                    "error_message": f"Tool {tool_name} not found",
                                    "success": False
                                }
                            )
                            logger.info(f"SUCCESS: Tool not found logged for {tool_name}")
                    except Exception as e:
                        logger.error(f"ERROR: Failed to log tool not found: {e}")
                    
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32601,
                            "message": f"Tool {tool_name} not found"
                        }
                    }
            
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method {method} not found"
                    }
                }
        
        logger.info("MCP server setup completed with Redis backend")
        
        return mcp_server
        
    except Exception as e:
        logger.error(f"Failed to setup MCP server: {str(e)}")
        raise