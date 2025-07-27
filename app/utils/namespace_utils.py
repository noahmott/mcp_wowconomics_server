"""
Utility functions for handling WoW API namespaces
"""
import os
from typing import Optional


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