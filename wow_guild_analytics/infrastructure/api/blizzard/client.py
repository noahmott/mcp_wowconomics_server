"""
Blizzard API Client

Modern implementation of Blizzard API client using modular architecture.
"""

import logging
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from ....core.config import Settings
from ..base_client import BaseAPIClient
from .oauth import BlizzardOAuthService
from .models import (
    GuildProfile,
    CharacterProfile,
    CharacterEquipment,
    MythicPlusProfile,
    RaidProgression,
    AuctionData,
    TokenPrice
)

logger = logging.getLogger(__name__)


class BlizzardAPIClient(BaseAPIClient):
    """Blizzard API client with OAuth2 authentication."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        region: str = "eu",
        locale: str = "en_GB",
        game_version: str = "retail",
        **kwargs
    ):
        """
        Initialize Blizzard API client.

        Args:
            client_id: Blizzard API client ID
            client_secret: Blizzard API client secret
            region: API region (us, eu, kr, tw, cn)
            locale: API locale
            game_version: Game version (retail, classic)
            **kwargs: Additional arguments for base client
        """
        # Set base URL based on region
        base_url = f"https://{region}.api.blizzard.com"

        super().__init__(base_url=base_url, **kwargs)

        self.region = region
        self.locale = locale
        self.game_version = game_version
        self.namespace = self._get_namespace()

        # OAuth service
        self.oauth_service = BlizzardOAuthService(
            client_id=client_id,
            client_secret=client_secret,
            region=region
        )

        self._access_token: Optional[str] = None
        self._token_expires: Optional[datetime] = None

    def _get_namespace(self) -> str:
        """Get namespace for API requests."""
        if self.game_version == "classic":
            return f"static-classic-{self.region}"
        return f"profile-{self.region}"

    def _get_default_headers(self) -> Dict[str, str]:
        """Get default headers for requests."""
        return {
            "Accept": "application/json",
            "Accept-Language": self.locale
        }

    async def _ensure_authenticated(self) -> None:
        """Ensure we have a valid access token."""
        if not self._access_token or (
            self._token_expires and datetime.now() >= self._token_expires
        ):
            token_data = await self.oauth_service.get_access_token()
            self._access_token = token_data["access_token"]

            # Set expiration with buffer
            expires_in = token_data.get("expires_in", 86400)
            self._token_expires = datetime.now() + timedelta(
                seconds=expires_in - 300  # 5 minute buffer
            )

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Any:
        """Make authenticated request."""
        await self._ensure_authenticated()

        # Add auth header
        headers = kwargs.get("headers", {})
        headers["Authorization"] = f"Bearer {self._access_token}"
        kwargs["headers"] = headers

        # Add namespace to params
        params = kwargs.get("params", {})
        params["namespace"] = self.namespace
        params["locale"] = self.locale
        kwargs["params"] = params

        return await super()._make_request(method, endpoint, **kwargs)

    # Guild endpoints
    async def get_guild(
        self,
        realm_slug: str,
        guild_name: str
    ) -> GuildProfile:
        """Get guild profile."""
        endpoint = f"/data/wow/guild/{realm_slug}/{guild_name.lower()}"
        data = await self.get(endpoint)
        return GuildProfile(**data)

    async def get_guild_roster(
        self,
        realm_slug: str,
        guild_name: str
    ) -> Dict[str, Any]:
        """Get guild roster."""
        endpoint = f"/data/wow/guild/{realm_slug}/{guild_name.lower()}/roster"
        return await self.get(endpoint)

    async def get_guild_achievements(
        self,
        realm_slug: str,
        guild_name: str
    ) -> Dict[str, Any]:
        """Get guild achievements."""
        endpoint = f"/data/wow/guild/{realm_slug}/{guild_name.lower()}/achievements"
        return await self.get(endpoint)

    async def get_guild_activity(
        self,
        realm_slug: str,
        guild_name: str
    ) -> Dict[str, Any]:
        """Get guild activity feed."""
        endpoint = f"/data/wow/guild/{realm_slug}/{guild_name.lower()}/activity"
        return await self.get(endpoint)

    # Character endpoints
    async def get_character(
        self,
        realm_slug: str,
        character_name: str
    ) -> CharacterProfile:
        """Get character profile."""
        endpoint = f"/profile/wow/character/{realm_slug}/{character_name.lower()}"
        data = await self.get(endpoint)
        return CharacterProfile(**data)

    async def get_character_equipment(
        self,
        realm_slug: str,
        character_name: str
    ) -> CharacterEquipment:
        """Get character equipment."""
        endpoint = f"/profile/wow/character/{realm_slug}/{character_name.lower()}/equipment"
        data = await self.get(endpoint)
        return CharacterEquipment(**data)

    async def get_character_mythic_plus(
        self,
        realm_slug: str,
        character_name: str
    ) -> MythicPlusProfile:
        """Get character Mythic+ profile."""
        endpoint = f"/profile/wow/character/{realm_slug}/{character_name.lower()}/mythic-keystone-profile"
        data = await self.get(endpoint)
        return MythicPlusProfile(**data)

    async def get_character_raid_progression(
        self,
        realm_slug: str,
        character_name: str
    ) -> RaidProgression:
        """Get character raid progression."""
        endpoint = f"/profile/wow/character/{realm_slug}/{character_name.lower()}/encounters/raids"
        data = await self.get(endpoint)
        return RaidProgression(**data)

    # Auction House endpoints
    async def get_auctions(
        self,
        connected_realm_id: int
    ) -> AuctionData:
        """Get auction house data."""
        endpoint = f"/data/wow/connected-realm/{connected_realm_id}/auctions"
        data = await self.get(endpoint)
        return AuctionData(**data)

    # Token endpoint
    async def get_token_price(self) -> TokenPrice:
        """Get WoW Token price."""
        endpoint = "/data/wow/token/index"
        params = {"namespace": f"dynamic-{self.region}"}
        data = await self.get(endpoint, params=params)
        return TokenPrice(**data)

    # Realm endpoints
    async def get_realms(self) -> List[Dict[str, Any]]:
        """Get all realms."""
        endpoint = "/data/wow/realm/index"
        params = {"namespace": f"dynamic-{self.region}"}
        data = await self.get(endpoint, params=params)
        return data.get("realms", [])

    async def get_realm(self, realm_slug: str) -> Dict[str, Any]:
        """Get specific realm."""
        endpoint = f"/data/wow/realm/{realm_slug}"
        params = {"namespace": f"dynamic-{self.region}"}
        return await self.get(endpoint, params=params)

    async def get_connected_realm(self, connected_realm_id: int) -> Dict[str, Any]:
        """Get connected realm."""
        endpoint = f"/data/wow/connected-realm/{connected_realm_id}"
        params = {"namespace": f"dynamic-{self.region}"}
        return await self.get(endpoint, params=params)

    # Comprehensive data methods
    async def get_comprehensive_guild_data(
        self,
        realm_slug: str,
        guild_name: str
    ) -> Dict[str, Any]:
        """Get comprehensive guild data including roster and achievements."""
        # Get base guild data
        guild = await self.get_guild(realm_slug, guild_name)

        # Get additional data in parallel
        roster_task = self.get_guild_roster(realm_slug, guild_name)
        achievements_task = self.get_guild_achievements(realm_slug, guild_name)
        activity_task = self.get_guild_activity(realm_slug, guild_name)

        roster, achievements, activity = await asyncio.gather(
            roster_task,
            achievements_task,
            activity_task,
            return_exceptions=True
        )

        # Combine data
        return {
            **guild.dict(),
            "roster": roster if not isinstance(roster, Exception) else None,
            "achievements": achievements if not isinstance(achievements, Exception) else None,
            "activity": activity if not isinstance(activity, Exception) else None,
            "fetch_timestamp": datetime.utcnow().isoformat()
        }

    async def get_character_profile(
        self,
        realm_slug: str,
        character_name: str
    ) -> Dict[str, Any]:
        """Get comprehensive character profile."""
        # Get base character data
        character = await self.get_character(realm_slug, character_name)

        # Get additional data in parallel
        equipment_task = self.get_character_equipment(realm_slug, character_name)
        mythic_plus_task = self.get_character_mythic_plus(realm_slug, character_name)
        raid_task = self.get_character_raid_progression(realm_slug, character_name)

        equipment, mythic_plus, raids = await asyncio.gather(
            equipment_task,
            mythic_plus_task,
            raid_task,
            return_exceptions=True
        )

        # Combine data
        return {
            **character.dict(),
            "equipment": equipment.dict() if not isinstance(equipment, Exception) else None,
            "mythic_plus": mythic_plus.dict() if not isinstance(mythic_plus, Exception) else None,
            "raid_progression": raids.dict() if not isinstance(raids, Exception) else None,
            "fetch_timestamp": datetime.utcnow().isoformat()
        }
