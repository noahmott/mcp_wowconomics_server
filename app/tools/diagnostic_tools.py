"""
Testing and diagnostic tools for WoW Guild MCP Server
"""

import os
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any

from .base import mcp_tool, with_supabase_logging, get_or_initialize_services
from ..api.blizzard_client import BlizzardAPIClient
from ..services.supabase_client import ActivityLogEntry

logger = logging.getLogger(__name__)


@mcp_tool()
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
            "note": "Use 'classic' game_version for Classic Progression servers"
        }
        
    except Exception as e:
        logger.error(f"Error testing Classic auction house: {str(e)}")
        return {"error": f"Classic auction house test failed: {str(e)}"}


@mcp_tool()
@with_supabase_logging
async def test_supabase_connection() -> Dict[str, Any]:
    """Test Supabase connection and logging functionality"""
    try:
        # Initialize services
        service_mgr = await get_or_initialize_services()
        supabase_client = service_mgr.supabase_client
        
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