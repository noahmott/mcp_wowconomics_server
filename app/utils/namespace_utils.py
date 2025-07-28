"""
Utility functions for handling WoW API namespaces
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_dynamic_namespace(region: str, game_version: Optional[str] = None) -> str:
    """
    Get the appropriate dynamic namespace for auction/realm data.
    
    Args:
        region: The region (e.g., "us", "eu")
        game_version: "classic" or "retail" (defaults to env WOW_VERSION)
    
    Returns:
        The namespace string (e.g., "dynamic-us" or "dynamic-classic-us")
    """
    version = (game_version or os.getenv("WOW_VERSION", "classic")).lower()
    
    if version == "classic":
        return f"dynamic-classic-{region}"
    else:
        return f"dynamic-{region}"


def get_static_namespace(region: str, game_version: Optional[str] = None) -> str:
    """
    Get the appropriate static namespace for item/spell data.
    
    Args:
        region: The region (e.g., "us", "eu")
        game_version: "classic" or "retail" (defaults to env WOW_VERSION)
    
    Returns:
        The namespace string (e.g., "static-us" or "static-classic-us")
    """
    version = (game_version or os.getenv("WOW_VERSION", "classic")).lower()
    
    if version == "classic":
        return f"static-classic-{region}"
    else:
        return f"static-{region}"


def get_profile_namespace(region: str, game_version: Optional[str] = None) -> str:
    """
    Get the appropriate profile namespace for character data.
    
    Args:
        region: The region (e.g., "us", "eu")
        game_version: "classic" or "retail" (defaults to env WOW_VERSION)
    
    Returns:
        The namespace string (e.g., "profile-us" or "profile-classic-us")
    """
    version = (game_version or os.getenv("WOW_VERSION", "classic")).lower()
    
    if version == "classic":
        return f"profile-classic-{region}"
    else:
        return f"profile-{region}"


async def get_connected_realm_id(realm: str, game_version: str = "retail", client = None) -> Optional[int]:
    """Get connected realm ID with fallback to hardcoded values"""
    from ..core.constants import KNOWN_CLASSIC_REALMS, KNOWN_RETAIL_REALMS
    
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