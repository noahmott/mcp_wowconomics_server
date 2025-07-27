"""
Service Interfaces

Protocols for application services.
"""

from typing import Protocol, Optional, Dict, Any, List
from datetime import datetime

from ...core.protocols import ServiceProtocol


class DataStagingService(ServiceProtocol):
    """Protocol for data staging services."""

    async def get_data(
        self,
        data_type: str,
        cache_key: str,
        region: str = 'us',
        force_refresh: bool = False,
        game_version: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get data with intelligent fallback strategy.

        Args:
            data_type: Type of data to retrieve
            cache_key: Cache key for the data
            region: Game region
            force_refresh: Force refresh from source
            game_version: Game version override

        Returns:
            Data dictionary or None
        """
        ...

    async def cache_data(
        self,
        data_type: str,
        cache_key: str,
        data: Dict[str, Any],
        region: str = 'us',
        game_version: Optional[str] = None
    ) -> bool:
        """
        Cache data in storage.

        Args:
            data_type: Type of data
            cache_key: Cache key
            data: Data to cache
            region: Game region
            game_version: Game version

        Returns:
            True if successful
        """
        ...

    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Cache statistics dictionary
        """
        ...


class MarketAnalysisService(ServiceProtocol):
    """Protocol for market analysis services."""

    async def analyze_market_opportunities(
        self,
        realm: str,
        region: str = 'us',
        game_version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze market opportunities for a realm.

        Args:
            realm: Realm slug
            region: Game region
            game_version: Game version

        Returns:
            Market analysis results
        """
        ...

    async def get_price_trends(
        self,
        realm: str,
        item_id: int,
        hours: int = 24,
        region: str = 'us'
    ) -> Dict[str, Any]:
        """
        Get price trends for an item.

        Args:
            realm: Realm slug
            item_id: Item ID
            hours: Hours of history
            region: Game region

        Returns:
            Price trend data
        """
        ...

    async def aggregate_auction_data(
        self,
        auctions: List[Dict[str, Any]]
    ) -> Dict[int, Dict[str, Any]]:
        """
        Aggregate raw auction data.

        Args:
            auctions: List of auction data

        Returns:
            Aggregated data by item ID
        """
        ...


class GuildAnalysisService(ServiceProtocol):
    """Protocol for guild analysis services."""

    async def analyze_guild(
        self,
        realm: str,
        guild_name: str,
        analysis_type: str = "comprehensive",
        region: str = 'us'
    ) -> Dict[str, Any]:
        """
        Analyze guild performance and metrics.

        Args:
            realm: Realm slug
            guild_name: Guild name
            analysis_type: Type of analysis
            region: Game region

        Returns:
            Guild analysis results
        """
        ...

    async def analyze_member(
        self,
        realm: str,
        character_name: str,
        analysis_depth: str = "standard",
        region: str = 'us'
    ) -> Dict[str, Any]:
        """
        Analyze individual member performance.

        Args:
            realm: Realm slug
            character_name: Character name
            analysis_depth: Depth of analysis
            region: Game region

        Returns:
            Member analysis results
        """
        ...

    async def get_guild_rankings(
        self,
        realm: str,
        metric: str = "achievement_points",
        limit: int = 10,
        region: str = 'us'
    ) -> List[Dict[str, Any]]:
        """
        Get guild rankings by metric.

        Args:
            realm: Realm slug
            metric: Ranking metric
            limit: Number of results
            region: Game region

        Returns:
            List of ranked guilds
        """
        ...
