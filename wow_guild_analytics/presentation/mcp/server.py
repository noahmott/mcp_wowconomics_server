"""
Modular MCP Server

MCP server implementation that uses the new modular architecture
while maintaining compatibility with existing MCP tools.
"""

import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI

from ...core.container import Container
from ...adapters import LegacyBlizzardClientAdapter
from app.visualization.chart_generator import ChartGenerator
from app.workflows.guild_analysis import GuildAnalysisWorkflow

logger = logging.getLogger(__name__)


class ModularMCPServer:
    """
    MCP Server using modular architecture.

    This is a wrapper that maintains the same interface as WoWGuildMCPServer
    but uses the new modular components internally.
    """

    def __init__(self, app: FastAPI, container: Container):
        """
        Initialize modular MCP server.

        Args:
            app: FastAPI application
            container: Dependency injection container
        """
        self.app = app
        self.container = container

        # Get services from container
        self.cache = container.cache()
        self.config = container.settings()

        # Create components using new architecture
        self.blizzard_client = LegacyBlizzardClientAdapter(
            game_version=self.config.api.wow_version
        )

        # Use existing components for now (will be migrated later)
        self.chart_generator = ChartGenerator()
        self.guild_workflow = GuildAnalysisWorkflow()

        # Store original MCP instance for compatibility
        self.mcp = None

    def set_mcp_instance(self, mcp_instance):
        """Set the MCP instance for tool registration."""
        self.mcp = mcp_instance

    async def analyze_guild_performance(
        self,
        realm: str,
        guild_name: str,
        analysis_type: str = "comprehensive"
    ) -> Dict[str, Any]:
        """
        Analyze guild performance metrics and member activity.

        Uses the new modular architecture internally.
        """
        try:
            logger.info(
                f"Analyzing guild {guild_name} on {realm} "
                f"using modular architecture"
            )

            # Use the adapted Blizzard client
            async with self.blizzard_client as client:
                # Get comprehensive guild data
                guild_data = await client.get_comprehensive_guild_data(
                    realm, guild_name
                )

                # Process through workflow
                analysis_result = await self.guild_workflow.analyze_guild(
                    guild_data, analysis_type
                )

                return {
                    "success": True,
                    "guild_info": analysis_result["guild_summary"],
                    "member_data": analysis_result["member_analysis"],
                    "analysis_results": analysis_result["performance_insights"],
                    "visualization_urls": analysis_result.get("chart_urls", []),
                    "analysis_type": analysis_type,
                    "timestamp": guild_data["fetch_timestamp"]
                }

        except Exception as e:
            logger.error(f"Error analyzing guild: {str(e)}")
            raise

    async def generate_raid_progress_chart(
        self,
        realm: str,
        guild_name: str,
        raid_tier: str = "current"
    ) -> str:
        """Generate visual raid progression charts."""
        try:
            logger.info(
                f"Generating raid chart for {guild_name} on {realm}"
            )

            async with self.blizzard_client as client:
                guild_data = await client.get_comprehensive_guild_data(
                    realm, guild_name
                )

                # Generate raid progression chart
                chart_data = await self.chart_generator.create_raid_progress_chart(
                    guild_data, raid_tier
                )

                return chart_data  # Base64 encoded PNG

        except Exception as e:
            logger.error(f"Error generating chart: {str(e)}")
            raise

    async def compare_member_performance(
        self,
        realm: str,
        guild_name: str,
        member_names: list[str],
        metric: str = "item_level"
    ) -> Dict[str, Any]:
        """Compare performance metrics across guild members."""
        try:
            logger.info(f"Comparing members {member_names} in {guild_name}")

            async with self.blizzard_client as client:
                # Get data for specific members
                comparison_data = []

                for member_name in member_names:
                    try:
                        char_data = await client.get_character_profile(
                            realm, member_name
                        )
                        if metric == "item_level":
                            equipment = await client.get_character_equipment(
                                realm, member_name
                            )
                            char_data["equipment_summary"] = (
                                client._summarize_equipment(equipment)
                            )
                        comparison_data.append(char_data)
                    except Exception as e:
                        logger.warning(
                            f"Failed to get data for {member_name}: {e}"
                        )

                # Generate comparison chart
                chart_data = await self.chart_generator.create_member_comparison_chart(
                    comparison_data, metric
                )

                return {
                    "success": True,
                    "member_data": comparison_data,
                    "comparison_metric": metric,
                    "chart_data": chart_data,
                    "member_count": len(comparison_data)
                }

        except Exception as e:
            logger.error(f"Error comparing members: {str(e)}")
            raise

    async def health_check(self) -> Dict[str, Any]:
        """Check health of all services."""
        health_status = {
            "status": "healthy",
            "services": {}
        }

        # Check cache
        try:
            cache_healthy = await self.cache.health_check()
            health_status["services"]["cache"] = {
                "status": "healthy" if cache_healthy else "unhealthy",
                "type": type(self.cache).__name__
            }
        except Exception as e:
            health_status["services"]["cache"] = {
                "status": "error",
                "error": str(e)
            }
            health_status["status"] = "degraded"

        # Check database
        try:
            from ...infrastructure.database import get_database
            db = await get_database()
            db_healthy = await db.health_check()
            health_status["services"]["database"] = {
                "status": "healthy" if db_healthy else "unhealthy"
            }
        except Exception as e:
            health_status["services"]["database"] = {
                "status": "error",
                "error": str(e)
            }
            health_status["status"] = "degraded"

        return health_status
