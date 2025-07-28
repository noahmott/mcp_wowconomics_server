"""
Character and member analysis tools for WoW Guild MCP Server
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

from .base import mcp_tool, with_supabase_logging, get_or_initialize_services
from ..api.blizzard_client import BlizzardAPIClient, BlizzardAPIError
from ..workflows.guild_analysis import GuildAnalysisWorkflow

# Create workflow instance
guild_workflow = GuildAnalysisWorkflow()

logger = logging.getLogger(__name__)


@mcp_tool()
@with_supabase_logging
async def analyze_member_performance(
    realm: str,
    character_name: str,
    analysis_depth: str = "standard",
    game_version: str = "retail"
) -> Dict[str, Any]:
    """
    Analyze individual member performance and progression
    
    Args:
        realm: Server realm
        character_name: Character name to analyze
        analysis_depth: Analysis depth ('basic', 'standard', 'detailed')
        game_version: WoW version ('retail' or 'classic')
    
    Returns:
        Comprehensive member analysis
    """
    try:
        logger.info(f"Analyzing member {character_name} on {realm} ({game_version})")
        
        async with BlizzardAPIClient(game_version=game_version) as client:
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
            analysis_result = await guild_workflow.analyze_member(
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
        return {"error": f"API Error: {e.message}"}
    except Exception as e:
        logger.error(f"Error analyzing member: {str(e)}")
        return {"error": f"Member analysis failed: {str(e)}"}


@mcp_tool()
@with_supabase_logging
async def get_character_details(
    realm: str,
    character_name: str,
    sections: List[str] = ["profile", "equipment", "specializations"],
    game_version: str = "retail"
) -> Dict[str, Any]:
    """
    Get comprehensive character details including gear, specializations, and other information
    
    Args:
        realm: Server realm
        character_name: Character name
        sections: Data sections to retrieve. Available options:
            - profile: Basic character information (default)
            - equipment: Current gear and item levels (default)
            - specializations: Talent specializations (default)
            - achievements: Achievement points and recent achievements
            - statistics: Character statistics
            - media: Character avatar and media
            - pvp: PvP statistics and ratings
            - appearance: Character appearance customization
            - collections: Mounts and pets
            - titles: Available titles
            - mythic_plus: Mythic+ dungeon data
            - all: Retrieve all available data
        game_version: WoW version ('retail' or 'classic')
    
    Returns:
        Comprehensive character information based on requested sections
    """
    try:
        logger.info(f"Getting character details for {character_name} on {realm} ({game_version})")
        
        # If 'all' is specified, get all sections
        all_sections = ["profile", "equipment", "specializations", "achievements", 
                       "statistics", "media", "pvp", "appearance", "collections", 
                       "titles", "mythic_plus"]
        
        if "all" in sections:
            sections = all_sections
        
        character_data = {}
        errors = []
        
        async with BlizzardAPIClient(game_version=game_version) as client:
            # Always get basic profile
            if "profile" in sections or True:  # Always include profile
                try:
                    profile = await client.get_character_profile(realm, character_name)
                    
                    # Handle case where profile might not be a dict
                    if not isinstance(profile, dict):
                        logger.error(f"Profile data is not a dict: {type(profile)} - {profile}")
                        return {"error": f"Invalid profile data received from API"}
                    
                    # Safe navigation for nested fields - handle both nested and direct string formats
                    race_data = profile.get("race", {})
                    if isinstance(race_data, dict):
                        race_name = race_data.get("name")
                        if isinstance(race_name, dict):
                            race_name = race_name.get("en_US", "Unknown")
                        elif not race_name:
                            race_name = "Unknown"
                    else:
                        race_name = str(race_data) if race_data else "Unknown"
                    
                    class_data = profile.get("character_class", {})
                    if isinstance(class_data, dict):
                        class_name = class_data.get("name")
                        if isinstance(class_name, dict):
                            class_name = class_name.get("en_US", "Unknown")
                        elif not class_name:
                            class_name = "Unknown"
                    else:
                        class_name = str(class_data) if class_data else "Unknown"
                    
                    spec_data = profile.get("active_spec", {})
                    if isinstance(spec_data, dict):
                        spec_name = spec_data.get("name")
                        if isinstance(spec_name, dict):
                            spec_name = spec_name.get("en_US", "Unknown")
                        elif not spec_name:
                            spec_name = "Unknown"
                    else:
                        spec_name = str(spec_data) if spec_data else "Unknown"
                    
                    realm_data = profile.get("realm", {})
                    if isinstance(realm_data, dict):
                        realm_name = realm_data.get("name", "Unknown")
                    else:
                        realm_name = str(realm_data) if realm_data else "Unknown"
                    
                    faction_data = profile.get("faction", {})
                    if isinstance(faction_data, dict):
                        faction_name = faction_data.get("name", "Unknown")
                    else:
                        faction_name = str(faction_data) if faction_data else "Unknown"
                    
                    guild_data = profile.get("guild")
                    guild_name = guild_data.get("name") if isinstance(guild_data, dict) else None
                    
                    character_data["profile"] = {
                        "name": profile.get("name"),
                        "level": profile.get("level"),
                        "race": race_name,
                        "class": class_name,
                        "active_spec": spec_name,
                        "realm": realm_name,
                        "faction": faction_name,
                        "guild": guild_name,
                        "achievement_points": profile.get("achievement_points", 0),
                        "equipped_item_level": profile.get("equipped_item_level", 0),
                        "average_item_level": profile.get("average_item_level", 0),
                        "last_login": profile.get("last_login_timestamp")
                    }
                except BlizzardAPIError as e:
                    errors.append(f"Profile: {str(e)}")
                    return {"error": f"Character not found: {str(e)}"}
            
            # Get equipment details
            if "equipment" in sections:
                try:
                    equipment = await client.get_character_equipment(realm, character_name)
                    
                    # Handle case where equipment might not be a dict
                    if not isinstance(equipment, dict):
                        logger.warning(f"Equipment data is not a dict: {type(equipment)}")
                        equipment = {}
                    
                    equipped_items = []
                    
                    for item in equipment.get("equipped_items", []):
                        # Safe navigation for item fields
                        slot_data = item.get("slot", {})
                        if isinstance(slot_data, dict):
                            slot_name = slot_data.get("name", "Unknown")
                        else:
                            slot_name = str(slot_data) if slot_data else "Unknown"
                        
                        # Handle name - it's often a direct string
                        item_name = item.get("name", "Unknown")
                        
                        level_data = item.get("level", {})
                        item_level = level_data.get("value", 0) if isinstance(level_data, dict) else 0
                        
                        quality_data = item.get("quality", {})
                        if isinstance(quality_data, dict):
                            quality_name = quality_data.get("name", "Unknown")
                        else:
                            quality_name = str(quality_data) if quality_data else "Unknown"
                        
                        item_info = {
                            "slot": slot_name,
                            "name": item_name,
                            "item_level": item_level,
                            "quality": quality_name
                        }
                        
                        equipped_items.append(item_info)
                    
                    character_data["equipment"] = {
                        "equipped_items": equipped_items,
                        "item_count": len(equipped_items)
                    }
                except BlizzardAPIError as e:
                    errors.append(f"Equipment: {str(e)}")
            
            # Get specializations
            if "specializations" in sections:
                try:
                    specs = await client.get_character_specializations(realm, character_name)
                    logger.debug(f"Raw specializations data type: {type(specs)}")
                    logger.debug(f"Raw specializations data: {specs}")
                    
                    # Handle case where specs might not be a dict
                    if not isinstance(specs, dict):
                        logger.warning(f"Specializations data is not a dict: {type(specs)}")
                        specs = {}
                    
                    spec_data = []
                    
                    for spec in specs.get("specializations", []):
                        # Safe navigation for specialization data
                        spec_detail = spec.get("specialization", {})
                        if isinstance(spec_detail, dict):
                            spec_name = spec_detail.get("name")
                            # Handle both nested dict and direct string formats
                            if isinstance(spec_name, dict):
                                spec_name = spec_name.get("en_US", "Unknown")
                            elif isinstance(spec_name, str):
                                # Name is already a string, use as-is
                                pass
                            else:
                                spec_name = "Unknown"
                        else:
                            spec_name = "Unknown"
                        
                        spec_role = spec_detail.get("role", {}) if isinstance(spec_detail, dict) else {}
                        if isinstance(spec_role, dict):
                            role_name = spec_role.get("name", "Unknown")
                        else:
                            role_name = str(spec_role) if spec_role else "Unknown"
                        
                        spec_info = {
                            "name": spec_name,
                            "role": role_name,
                            "talents": [],
                            "pvp_talents": []
                        }
                        
                        # Get talent names
                        for talent in spec.get("talents", []):
                            talent_detail = talent.get("talent", {})
                            if isinstance(talent_detail, dict):
                                talent_name = talent_detail.get("name", "Unknown")
                                # Handle both nested dict and direct string formats
                                if isinstance(talent_name, dict):
                                    talent_name = talent_name.get("en_US", "Unknown")
                                elif not isinstance(talent_name, str):
                                    talent_name = "Unknown"
                            else:
                                talent_name = "Unknown"
                            spec_info["talents"].append(talent_name)
                        
                        # Get PvP talent names
                        for pvp_talent in spec.get("pvp_talents", []):
                            pvp_talent_detail = pvp_talent.get("talent", {})
                            if isinstance(pvp_talent_detail, dict):
                                pvp_talent_name = pvp_talent_detail.get("name", "Unknown")
                                # Handle both nested dict and direct string formats
                                if isinstance(pvp_talent_name, dict):
                                    pvp_talent_name = pvp_talent_name.get("en_US", "Unknown")
                                elif not isinstance(pvp_talent_name, str):
                                    pvp_talent_name = "Unknown"
                            else:
                                pvp_talent_name = "Unknown"
                            spec_info["pvp_talents"].append(pvp_talent_name)
                        
                        spec_data.append(spec_info)
                    
                    character_data["specializations"] = spec_data
                except BlizzardAPIError as e:
                    errors.append(f"Specializations: {str(e)}")
            
            # Get achievements
            if "achievements" in sections:
                try:
                    achievements = await client.get_character_achievements(realm, character_name)
                    
                    # Handle case where achievements might not be a dict
                    if not isinstance(achievements, dict):
                        logger.warning(f"Achievements data is not a dict: {type(achievements)}")
                        achievements = {}
                    
                    character_data["achievements"] = {
                        "total_points": achievements.get("total_points", 0),
                        "recent_achievements": achievements.get("recent_achievements", [])[:10]
                    }
                except BlizzardAPIError as e:
                    errors.append(f"Achievements: {str(e)}")
            
            # Get statistics
            if "statistics" in sections:
                try:
                    stats = await client.get_character_statistics(realm, character_name)
                    character_data["statistics"] = stats
                except BlizzardAPIError as e:
                    errors.append(f"Statistics: {str(e)}")
            
            # Get media
            if "media" in sections:
                try:
                    media = await client.get_character_media(realm, character_name)
                    character_data["media"] = media
                except BlizzardAPIError as e:
                    errors.append(f"Media: {str(e)}")
            
            # Get PvP data
            if "pvp" in sections:
                try:
                    pvp = await client.get_character_pvp_summary(realm, character_name)
                    character_data["pvp"] = pvp
                except BlizzardAPIError as e:
                    errors.append(f"PvP: {str(e)}")
            
            # Get titles
            if "titles" in sections:
                try:
                    titles = await client.get_character_titles(realm, character_name)
                    
                    # Handle case where titles might not be a dict
                    if not isinstance(titles, dict):
                        logger.warning(f"Titles data is not a dict: {type(titles)}")
                        titles = {}
                    
                    # Safe navigation for title data
                    title_list = []
                    for title in titles.get("titles", []):
                        title_detail = title.get("title", {})
                        if isinstance(title_detail, dict):
                            title_name = title_detail.get("name")
                            # Handle both nested dict and direct string formats
                            if isinstance(title_name, dict):
                                title_name = title_name.get("en_US", "Unknown")
                            elif isinstance(title_name, str):
                                # Title name is already a string, use as-is
                                pass
                            else:
                                title_name = "Unknown"
                        else:
                            title_name = "Unknown"
                        
                        title_list.append({
                            "name": title_name,
                            "is_active": title.get("is_active", False)
                        })
                    
                    character_data["titles"] = {
                        "active_title": next((t["name"] for t in title_list if t["is_active"]), None),
                        "available_titles": [t["name"] for t in title_list],
                        "title_count": len(title_list)
                    }
                except BlizzardAPIError as e:
                    errors.append(f"Titles: {str(e)}")
            
            # Get Mythic+ data
            if "mythic_plus" in sections:
                try:
                    mythic = await client.get_character_mythic_keystone(realm, character_name)
                    character_data["mythic_plus"] = mythic
                except BlizzardAPIError as e:
                    errors.append(f"Mythic+: {str(e)}")
            
            # Add timestamp and metadata
            character_data["metadata"] = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "requested_sections": sections,
                "errors": errors if errors else None,
                "game_version": game_version
            }
            
            return character_data
            
    except BlizzardAPIError as e:
        logger.error(f"Blizzard API error: {e.message}")
        return {"error": f"API Error: {e.message}"}
    except Exception as e:
        logger.error(f"Error getting character details: {str(e)}")
        return {"error": f"Failed to retrieve character details: {str(e)}"}