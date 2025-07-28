"""
Item lookup and information tools for WoW Guild MCP Server
"""

import logging
from typing import Dict, Any, List

from .base import mcp_tool, with_supabase_logging
from ..api.blizzard_client import BlizzardAPIClient

logger = logging.getLogger(__name__)


@mcp_tool()
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
                "inventory_type": item_data.get('inventory_type', {}).get('name', 'Unknown'),
                "purchase_price": item_data.get('purchase_price', 0),
                "sell_price": item_data.get('sell_price', 0),
                "level": item_data.get('level', 0),
                "required_level": item_data.get('required_level', 0),
                "max_count": item_data.get('max_count', 0)
            })
            
            # Add preview URL if available
            if 'preview_item' in item_data:
                result["preview_url"] = item_data['preview_item'].get('item', {}).get('key', {}).get('href')
            
            return result
            
    except Exception as e:
        logger.error(f"Error looking up item {item_id}: {str(e)}")
        return {"error": f"Item lookup failed: {str(e)}"}


@mcp_tool()
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
            "items": results,
            "items_found": len(results),
            "failed_lookups": failed_lookups,
            "game_version": game_version
        }
        
    except Exception as e:
        logger.error(f"Error looking up items: {str(e)}")
        return {"error": f"Multiple item lookup failed: {str(e)}"}