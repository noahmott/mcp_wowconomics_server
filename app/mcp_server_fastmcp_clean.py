#!/usr/bin/env python3
"""
WoW Guild MCP Server

Main entry point for the WoW Guild MCP Server using FastMCP.
Tools are organized in modular files for maintainability.
"""

import os
import logging
import asyncio
from fastmcp import FastMCP
from app.core.config import settings
from app.core.service_manager import ServiceManager
from app.tools.base import set_mcp_instance, set_service_instances

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Disable noisy loggers
for logger_name in ["httpx", "httpcore", "hpack", "openai", "sse_starlette"]:
    logging.getLogger(logger_name).setLevel(logging.WARNING)

# Create FastMCP instance
mcp = FastMCP("WoW Guild MCP Server", version="2.0.0")
set_mcp_instance(mcp)

# Import all tools after MCP instance is set
from app.tools.guild_tools import analyze_guild_performance, get_guild_member_list
from app.tools.member_tools import analyze_member_performance, get_character_details
from app.tools.visualization_tools import generate_raid_progress_chart, compare_member_performance
from app.tools.auction_tools import (
    get_auction_house_snapshot, capture_economy_snapshot, get_economy_trends,
    find_market_opportunities, analyze_item_market_history
)
from app.tools.item_tools import lookup_item_details, lookup_multiple_items
from app.tools.realm_tools import get_realm_status, get_classic_realm_id
from app.tools.diagnostic_tools import test_classic_auction_house, test_supabase_connection

service_manager = None


def main():
    """Main entry point for the MCP server."""
    global service_manager
    
    try:
        logger.info("=" * 70)
        logger.info("Initializing WoW Guild MCP Server")
        logger.info("=" * 70)
        
        service_manager = ServiceManager()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(service_manager.initialize())
            set_service_instances(
                redis=service_manager.redis_client,
                activity=service_manager.activity_logger,
                supabase=service_manager.supabase_client,
                streaming=service_manager.streaming_service
            )
            logger.info("✅ All services initialized successfully")
        finally:
            loop.close()
        
        port = int(os.getenv("PORT", "8000"))
        
        logger.info("🚀 WoW Guild MCP Server with FastMCP 2.0")
        logger.info("🔧 Tools: Guild analysis, visualization, and auction house")
        logger.info(f"📊 Registered tools: {len(mcp._tool_manager._tools)}")
        logger.info(f"🌐 HTTP Server: 0.0.0.0:{port}")
        logger.info("✅ Starting server...")
        
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