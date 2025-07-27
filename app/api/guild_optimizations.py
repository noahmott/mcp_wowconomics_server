"""
Guild data optimization strategies
"""
import asyncio
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class OptimizedGuildFetcher:
    """Optimized methods for fetching large guild data"""
    
    def __init__(self, client):
        self.client = client
    
    async def get_guild_roster_basic(self, realm: str, guild_name: str) -> Dict[str, Any]:
        """
        Get only basic roster information without detailed character data
        """
        roster = await self.client.get_guild_roster(realm, guild_name)
        
        # Return only essential data
        return {
            "guild": roster.get("guild"),
            "member_count": len(roster.get("members", [])),
            "members": [
                {
                    "character": {
                        "name": m["character"]["name"],
                        "id": m["character"]["id"],
                        "level": m["character"].get("level"),
                        "playable_class": m["character"].get("playable_class", {})
                    },
                    "rank": m.get("rank")
                }
                for m in roster.get("members", [])
            ]
        }
    
    async def get_guild_members_chunked(
        self, 
        realm: str, 
        guild_name: str, 
        chunk_size: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get guild members in chunks to avoid timeouts
        """
        # First get the roster
        roster = await self.client.get_guild_roster(realm, guild_name)
        members = roster.get("members", [])
        
        # Process members in chunks
        detailed_members = []
        
        for i in range(0, len(members), chunk_size):
            chunk = members[i:i + chunk_size]
            logger.info(f"Processing members {i} to {i + len(chunk)}")
            
            # Get detailed info for this chunk in parallel
            tasks = []
            for member in chunk:
                char_name = member["character"]["name"]
                tasks.append(
                    self._get_member_details_safe(realm, char_name)
                )
            
            # Wait for chunk to complete
            chunk_results = await asyncio.gather(*tasks)
            detailed_members.extend(chunk_results)
            
            # Small delay between chunks to avoid rate limiting
            if i + chunk_size < len(members):
                await asyncio.sleep(0.5)
        
        return detailed_members
    
    async def _get_member_details_safe(self, realm: str, character_name: str) -> Dict[str, Any]:
        """
        Get member details with error handling
        """
        try:
            return await self.client.get_character_profile(realm, character_name)
        except Exception as e:
            logger.warning(f"Failed to get details for {character_name}: {e}")
            return {"name": character_name, "error": str(e)}
    
    async def get_guild_summary(self, realm: str, guild_name: str) -> Dict[str, Any]:
        """
        Get a quick guild summary without fetching all member details
        """
        # Fetch data in parallel
        guild_info_task = self.client.get_guild_info(realm, guild_name)
        roster_task = self.client.get_guild_roster(realm, guild_name)
        
        guild_info, roster = await asyncio.gather(
            guild_info_task, 
            roster_task,
            return_exceptions=True
        )
        
        # Handle any errors
        if isinstance(guild_info, Exception):
            guild_info = {"error": str(guild_info)}
        if isinstance(roster, Exception):
            roster = {"members": []}
        
        # Create summary
        members = roster.get("members", [])
        
        # Group by class and level
        class_distribution = {}
        level_distribution = {"max_level": 0, "below_max": 0}
        
        for member in members:
            char = member.get("character", {})
            
            # Class distribution
            class_info = char.get("playable_class", {})
            class_name = class_info.get("name", "Unknown")
            class_distribution[class_name] = class_distribution.get(class_name, 0) + 1
            
            # Level distribution
            level = char.get("level", 0)
            if level >= 70:  # Assuming 70 is max for current expansion
                level_distribution["max_level"] += 1
            else:
                level_distribution["below_max"] += 1
        
        return {
            "guild_info": guild_info,
            "member_count": len(members),
            "class_distribution": class_distribution,
            "level_distribution": level_distribution,
            "last_updated": roster.get("last_updated")
        }