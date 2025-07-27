"""
Legacy Blizzard Client Adapter

Maintains backward compatibility with existing BlizzardAPIClient usage.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class LegacyBlizzardClientAdapter:
    """
    Adapter to maintain compatibility with existing BlizzardAPIClient.

    This adapter wraps the new modular client implementation and
    provides the same interface as the original BlizzardAPIClient.
    """

    def __init__(self, game_version: Optional[str] = None):
        """
        Initialize the adapter.

        Args:
            game_version: 'retail' or 'classic'
        """
        # Use new integrated API client
        from ..infrastructure.api.blizzard.integrated_client import IntegratedBlizzardClient
        from ..core.config import ConfigLoader
        from ..core.container import get_container

        settings = ConfigLoader.load_config()
        self.game_version = game_version or settings.api.wow_version

        # Get cache from container if available
        try:
            container = get_container()
            cache = container.cache()
        except Exception:
            cache = None

        self.integrated_client = IntegratedBlizzardClient(
            settings=settings,
            cache_client=cache
        )

        # Maintain compatibility attributes
        self.client_id = settings.api.client_id
        self.client_secret = settings.api.client_secret
        self.region = settings.api.region or "eu"
        self.locale = settings.api.locale or "en_GB"
        self.base_url = f"https://{self.region}.api.blizzard.com"

        # OAuth service for compatibility
        self.oauth_service = self.integrated_client.client.oauth_service

        # Rate limiter for compatibility
        self.rate_limiter = self.integrated_client.rate_limiter

        # EU realms for compatibility
        self.eu_realms = {
            'tarren-mill', 'draenor', 'kazzak', 'argent-dawn',
            'silvermoon', 'stormrage-eu', 'ragnaros-eu',
            'twisting-nether', 'outland', 'frostmane',
            'ravencrest', 'chamber-of-aspects', 'defias-brotherhood'
        }

    async def __aenter__(self):
        """Async context manager entry."""
        await self.integrated_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.integrated_client.__aexit__(exc_type, exc_val, exc_tb)

    async def get_access_token(self) -> str:
        """Get OAuth2 access token."""
        token_data = await self.oauth_service.get_access_token()
        return token_data["access_token"]

    def detect_realm_region(self, realm: str) -> str:
        """Detect the likely region for a realm."""
        realm_lower = realm.lower()
        if realm_lower in self.eu_realms:
            return 'eu'
        return self.region

    async def make_request(
        self,
        endpoint: str,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make authenticated API request."""
        # Use integrated client's get method
        return await self.integrated_client.client.get(endpoint, params=params)

    def _get_namespace(self, endpoint: str) -> str:
        """Get appropriate namespace for endpoint."""
        if self.game_version == "classic":
            if "/profile/" in endpoint:
                return f"profile-classic-{self.region}"
            else:
                return f"static-classic-{self.region}"
        else:
            if "/profile/" in endpoint:
                return f"profile-{self.region}"
            elif "/data/" in endpoint:
                return f"dynamic-{self.region}"
            else:
                return f"profile-{self.region}"

    # Compatibility methods
    async def get_guild_info(
        self,
        realm: str,
        guild_name: str
    ) -> Dict[str, Any]:
        """Get guild information."""
        return await self.integrated_client.get_guild(realm, guild_name)

    async def get_guild_roster(
        self,
        realm: str,
        guild_name: str
    ) -> Dict[str, Any]:
        """Get guild roster."""
        return await self.integrated_client.get_guild_roster(realm, guild_name)

    async def get_character_profile(
        self,
        realm: str,
        character_name: str
    ) -> Dict[str, Any]:
        """Get character profile."""
        return await self.integrated_client.get_character(realm, character_name)

    async def get_character_equipment(
        self,
        realm: str,
        character_name: str
    ) -> Dict[str, Any]:
        """Get character equipment."""
        return await self.integrated_client.get_character_equipment(realm, character_name)

    async def get_comprehensive_guild_data(
        self,
        realm: str,
        guild_name: str
    ) -> Dict[str, Any]:
        """Get comprehensive guild data including roster and member details."""
        # Use integrated client's comprehensive method
        return await self.integrated_client.get_comprehensive_guild_data(realm, guild_name)

    def _summarize_equipment(
        self,
        equipment_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Summarize equipment data for analysis."""
        if not equipment_data.get("equipped_items"):
            return {"average_item_level": 0, "total_items": 0}

        items = equipment_data["equipped_items"]
        item_levels = []

        for item in items:
            if "item_level" in item:
                item_levels.append(item["item_level"])

        avg_ilvl = sum(item_levels) / len(item_levels) if item_levels else 0

        return {
            "average_item_level": round(avg_ilvl, 1),
            "total_items": len(items),
            "item_levels": item_levels
        }
