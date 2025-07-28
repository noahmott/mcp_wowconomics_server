"""
Realm status and information tools for WoW Guild MCP Server
"""

import logging
from typing import Dict, Any

from .base import mcp_tool, with_supabase_logging
from ..api.blizzard_client import BlizzardAPIClient, BlizzardAPIError
from ..core.constants import KNOWN_CLASSIC_REALMS, KNOWN_RETAIL_REALMS

logger = logging.getLogger(__name__)


@mcp_tool()
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
                    if 'connected-realm/' in href:
                        connected_realm_id = int(href.split('connected-realm/')[-1].split('?')[0])
                
                # Get realm status
                status = realm_info.get('status', {})
                status_type = status.get('type', 'UNKNOWN') if isinstance(status, dict) else 'UNKNOWN'
                status_name = status.get('name', 'Unknown') if isinstance(status, dict) else 'Unknown'
                
                return {
                    "success": True,
                    "realm": realm,
                    "connected_realm_id": connected_realm_id,
                    "game_version": game_version,
                    "status": status_type.lower(),
                    "status_name": status_name,
                    "population": realm_info.get('population', {}).get('name', 'Unknown'),
                    "timezone": realm_info.get('timezone', 'Unknown'),
                    "type": realm_info.get('type', {}).get('name', 'Unknown'),
                    "source": "api"
                }
                
            except BlizzardAPIError as e:
                logger.warning(f"API error for realm {realm}: {str(e)}")
                
                # Fall back to hardcoded IDs for known realms
                if game_version == "retail" and realm_lower in KNOWN_RETAIL_REALMS:
                    return {
                        "success": True,
                        "realm": realm,
                        "connected_realm_id": KNOWN_RETAIL_REALMS[realm_lower],
                        "game_version": game_version,
                        "source": "hardcoded",
                        "status": "unknown",
                        "message": f"API error, using hardcoded ID for {realm}"
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Realm not found: {str(e)}",
                        "realm": realm,
                        "game_version": game_version
                    }
                    
    except Exception as e:
        logger.error(f"Error getting realm status: {str(e)}")
        return {"error": f"Realm status lookup failed: {str(e)}"}


@mcp_tool()
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
                    if 'connected-realm/' in href:
                        realm_id = int(href.split('connected-realm/')[-1].split('?')[0])
                    else:
                        return {
                            "success": False,
                            "error": f"Could not extract realm ID from API response",
                            "realm": realm,
                            "connected_realm_data": connected_realm
                        }
                
                logger.info(f"Found realm ID {realm_id} for {realm} from API")
                
                return {
                    "success": True,
                    "realm": realm,
                    "connected_realm_id": realm_id,
                    "source": "api",
                    "message": f"Found realm ID from API"
                }
                
            except BlizzardAPIError as e:
                logger.error(f"API error looking up realm {realm}: {str(e)}")
                return {
                    "success": False,
                    "error": f"Realm not found in API: {str(e)}",
                    "realm": realm,
                    "suggestion": "Please check the realm name or try using one of the known Classic realms"
                }
                
    except Exception as e:
        logger.error(f"Error getting classic realm ID: {str(e)}")
        return {"error": f"Classic realm ID lookup failed: {str(e)}"}