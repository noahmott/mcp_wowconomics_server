"""
Blizzard Battle.net API Client
"""

import os
import aiohttp
import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from aiohttp import ClientSession, ClientResponseError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import json
from urllib.parse import quote

from ..models.guild import Guild
from ..models.member import Member

logger = logging.getLogger(__name__)


class BlizzardAPIError(Exception):
    """Custom exception for Blizzard API errors"""
    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Dict] = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class RateLimiter:
    """Simple rate limiter for API requests"""
    def __init__(self, max_requests: int = 100, time_window: int = 1):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """Acquire permission to make a request"""
        async with self._lock:
            now = datetime.now()
            # Remove old requests outside the time window
            self.requests = [req_time for req_time in self.requests 
                           if (now - req_time).seconds < self.time_window]
            
            if len(self.requests) >= self.max_requests:
                sleep_time = self.time_window - (now - self.requests[0]).seconds
                await asyncio.sleep(sleep_time)
                return await self.acquire()
            
            self.requests.append(now)


class BlizzardAPIClient:
    """Blizzard Battle.net API client with OAuth2 authentication"""
    
    BASE_URL = "https://us.api.blizzard.com"
    AUTH_URL = "https://oauth.battle.net/token"
    
    def __init__(self):
        self.client_id = os.getenv("BLIZZARD_CLIENT_ID")
        self.client_secret = os.getenv("BLIZZARD_CLIENT_SECRET")
        self.region = os.getenv("BLIZZARD_REGION", "us")
        self.locale = os.getenv("BLIZZARD_LOCALE", "en_US")
        
        if not self.client_id or not self.client_secret:
            raise ValueError("BLIZZARD_CLIENT_ID and BLIZZARD_CLIENT_SECRET must be set")
        
        self.access_token = None
        self.token_expires_at = None
        self.session: Optional[ClientSession] = None
        self.rate_limiter = RateLimiter(100, 1)  # 100 requests per second
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def get_access_token(self) -> str:
        """Get OAuth2 access token using client credentials flow"""
        if self.access_token and self.token_expires_at and datetime.now() < self.token_expires_at:
            return self.access_token
        
        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")
        
        auth = aiohttp.BasicAuth(self.client_id, self.client_secret)
        data = {"grant_type": "client_credentials"}
        
        try:
            async with self.session.post(self.AUTH_URL, auth=auth, data=data) as response:
                if response.status != 200:
                    raise BlizzardAPIError(
                        f"Failed to get access token: {response.status}",
                        status_code=response.status
                    )
                
                token_data = await response.json()
                self.access_token = token_data["access_token"]
                expires_in = token_data.get("expires_in", 3600)
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 60)  # 1 minute buffer
                
                logger.info("Successfully obtained Blizzard API access token")
                return self.access_token
                
        except aiohttp.ClientError as e:
            raise BlizzardAPIError(f"Network error getting access token: {str(e)}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(aiohttp.ClientError)
    )
    async def make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make authenticated API request with retry logic"""
        await self.rate_limiter.acquire()
        
        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")
        
        access_token = await self.get_access_token()
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        
        # Default parameters
        default_params = {
            "namespace": f"profile-{self.region}",
            "locale": self.locale
        }
        
        if params:
            default_params.update(params)
        
        url = f"{self.BASE_URL}{endpoint}"
        
        try:
            async with self.session.get(url, headers=headers, params=default_params) as response:
                if response.status == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"Rate limited. Retrying after {retry_after} seconds")
                    await asyncio.sleep(retry_after)
                    raise BlizzardAPIError("Rate limited", status_code=429)
                
                if response.status == 404:
                    # Don't retry 404s - the resource doesn't exist
                    text = await response.text()
                    logger.info(f"Resource not found at {url}: {text}")
                    raise BlizzardAPIError("Resource not found", status_code=404)
                
                if response.status != 200:
                    text = await response.text()
                    logger.error(f"API request to {url} failed: {response.status} - {text}")
                    raise BlizzardAPIError(
                        f"API request failed: {response.status} - {text}",
                        status_code=response.status
                    )
                
                return await response.json()
                
        except aiohttp.ClientError as e:
            raise BlizzardAPIError(f"Network error: {str(e)}")
    
    # Guild API methods
    async def get_guild_info(self, realm: str, guild_name: str) -> Dict[str, Any]:
        """Get guild information"""
        # URL encode the guild name to handle special characters
        encoded_guild = quote(guild_name.lower(), safe='')
        endpoint = f"/data/wow/guild/{realm.lower()}/{encoded_guild}"
        return await self.make_request(endpoint)
    
    async def get_guild_roster(self, realm: str, guild_name: str) -> Dict[str, Any]:
        """Get guild roster"""
        encoded_guild = quote(guild_name.lower(), safe='')
        endpoint = f"/data/wow/guild/{realm.lower()}/{encoded_guild}/roster"
        return await self.make_request(endpoint)
    
    async def get_guild_achievements(self, realm: str, guild_name: str) -> Dict[str, Any]:
        """Get guild achievements"""
        encoded_guild = quote(guild_name.lower(), safe='')
        endpoint = f"/data/wow/guild/{realm.lower()}/{encoded_guild}/achievements"
        return await self.make_request(endpoint)
    
    async def get_guild_activity(self, realm: str, guild_name: str) -> Dict[str, Any]:
        """Get guild activity"""
        encoded_guild = quote(guild_name.lower(), safe='')
        endpoint = f"/data/wow/guild/{realm.lower()}/{encoded_guild}/activity"
        return await self.make_request(endpoint)
    
    # Character API methods
    async def get_character_profile(self, realm: str, character_name: str) -> Dict[str, Any]:
        """Get character profile"""
        # URL encode the character name to handle special characters like é, ñ, etc.
        encoded_name = quote(character_name.lower(), safe='')
        endpoint = f"/profile/wow/character/{realm.lower()}/{encoded_name}"
        return await self.make_request(endpoint)
    
    async def get_character_equipment(self, realm: str, character_name: str) -> Dict[str, Any]:
        """Get character equipment"""
        encoded_name = quote(character_name.lower(), safe='')
        endpoint = f"/profile/wow/character/{realm.lower()}/{encoded_name}/equipment"
        return await self.make_request(endpoint)
    
    async def get_character_achievements(self, realm: str, character_name: str) -> Dict[str, Any]:
        """Get character achievements"""
        encoded_name = quote(character_name.lower(), safe='')
        endpoint = f"/profile/wow/character/{realm.lower()}/{encoded_name}/achievements"
        return await self.make_request(endpoint)
    
    async def get_character_mythic_keystone(self, realm: str, character_name: str) -> Dict[str, Any]:
        """Get character mythic keystone profile"""
        endpoint = f"/profile/wow/character/{realm.lower()}/{character_name.lower()}/mythic-keystone-profile"
        return await self.make_request(endpoint)
    
    # Comprehensive guild analysis
    async def get_comprehensive_guild_data(self, realm: str, guild_name: str) -> Dict[str, Any]:
        """Get comprehensive guild data including roster and member details"""
        logger.info(f"Fetching comprehensive data for guild {guild_name} on {realm}")
        
        # Get basic guild info and roster
        guild_info = await self.get_guild_info(realm, guild_name)
        guild_roster = await self.get_guild_roster(realm, guild_name)
        
        # Get additional guild data
        try:
            guild_achievements = await self.get_guild_achievements(realm, guild_name)
        except BlizzardAPIError as e:
            logger.warning(f"Failed to get guild achievements: {e.message}")
            guild_achievements = {}
        
        # Process member data
        members_data = []
        if "members" in guild_roster:
            # Limit to first 50 members to avoid rate limits
            members = guild_roster["members"][:50]
            
            for member in members:
                character = member.get("character", {})
                character_name = character.get("name")
                character_realm = character.get("realm", {}).get("slug", realm)
                
                if character_name:
                    try:
                        # Get character profile
                        char_profile = await self.get_character_profile(character_realm, character_name)
                        
                        # Get equipment for item level
                        try:
                            char_equipment = await self.get_character_equipment(character_realm, character_name)
                            char_profile["equipment_summary"] = self._summarize_equipment(char_equipment)
                        except BlizzardAPIError:
                            char_profile["equipment_summary"] = {}
                        
                        # Add guild rank info
                        char_profile["guild_rank"] = member.get("rank", 0)
                        
                        members_data.append(char_profile)
                        
                    except BlizzardAPIError as e:
                        logger.warning(f"Failed to get data for character {character_name}: {e.message}")
                        # Add basic member info even if detailed fetch fails
                        members_data.append({
                            "name": character_name,
                            "realm": {"slug": character_realm},
                            "guild_rank": member.get("rank", 0),
                            "level": character.get("level", 0),
                            "character_class": character.get("character_class", {}),
                            "error": f"Failed to fetch details: {e.message}"
                        })
        
        return {
            "guild_info": guild_info,
            "guild_roster": guild_roster,
            "guild_achievements": guild_achievements,
            "members_data": members_data,
            "fetch_timestamp": datetime.now().isoformat()
        }
    
    def _summarize_equipment(self, equipment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize equipment data for analysis"""
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