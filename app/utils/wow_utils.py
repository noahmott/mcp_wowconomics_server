"""
WoW API utility functions for handling Classic and Retail differences
"""
from typing import Dict, Any, Union, Optional


def get_localized_name(data: Dict[str, Any], field: str = "name", locale: str = "en_US") -> str:
    """
    Extract name from WoW API response, handling both Classic and Retail formats.
    
    Classic format: {"name": "Item Name"}
    Retail format: {"name": {"en_US": "Item Name", "es_MX": "Nombre del Artículo"}}
    
    Args:
        data: API response data
        field: Field name to extract (default: "name")
        locale: Locale to use for Retail format (default: "en_US")
    
    Returns:
        The localized name string, or "Unknown" if not found
    """
    if not data or field not in data:
        return "Unknown"
    
    name_data = data[field]
    
    # Classic format: direct string
    if isinstance(name_data, str):
        return name_data
    
    # Retail format: nested object with locales
    if isinstance(name_data, dict):
        return name_data.get(locale, name_data.get("en_US", "Unknown"))
    
    return "Unknown"


def parse_quality(quality_data: Union[Dict[str, Any], str, None]) -> str:
    """
    Parse quality information from API response.
    
    Args:
        quality_data: Quality data from API
    
    Returns:
        Quality name string
    """
    if not quality_data:
        return "Unknown"
    
    if isinstance(quality_data, str):
        return quality_data
    
    if isinstance(quality_data, dict):
        # Try getting name directly or from nested structure
        if "name" in quality_data:
            return get_localized_name({"name": quality_data["name"]})
        return quality_data.get("type", "Unknown")
    
    return "Unknown"


def parse_class_info(class_data: Union[Dict[str, Any], str, None]) -> str:
    """
    Parse character class information from API response.
    
    Args:
        class_data: Class data from API
    
    Returns:
        Class name string
    """
    if not class_data:
        return "Unknown"
    
    if isinstance(class_data, str):
        return class_data
    
    if isinstance(class_data, dict):
        return get_localized_name(class_data)
    
    return "Unknown"


def parse_realm_info(realm_data: Union[Dict[str, Any], str, None]) -> Dict[str, Any]:
    """
    Parse realm information from API response.
    
    Args:
        realm_data: Realm data from API
    
    Returns:
        Dictionary with realm name and slug
    """
    if not realm_data:
        return {"name": "Unknown", "slug": "unknown"}
    
    if isinstance(realm_data, str):
        return {"name": realm_data, "slug": realm_data.lower().replace(" ", "-")}
    
    if isinstance(realm_data, dict):
        return {
            "name": get_localized_name(realm_data),
            "slug": realm_data.get("slug", "unknown")
        }
    
    return {"name": "Unknown", "slug": "unknown"}


def is_classic_response(data: Dict[str, Any]) -> bool:
    """
    Detect if the response is from Classic or Retail based on data structure.
    
    Args:
        data: API response data
    
    Returns:
        True if response appears to be from Classic API
    """
    # Check if any name fields are simple strings (Classic format)
    name_fields = ["name", "realm", "faction", "character_class", "race"]
    
    for field in name_fields:
        if field in data and isinstance(data[field], str):
            return True
    
    # Check nested structures
    if "_links" in data and "self" in data["_links"]:
        href = data["_links"]["self"].get("href", "")
        if "classic" in href:
            return True
    
    return False