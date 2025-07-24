"""
Discord Bot Client for WoW Guild Analysis
"""

import os
import io
import logging
import asyncio
import base64
from typing import Optional, List
import discord
from discord.ext import commands
import aiohttp
from PIL import Image

logger = logging.getLogger(__name__)


class WoWGuildBot(commands.Bot):
    """Discord bot for WoW guild analysis"""
    
    def __init__(self):
        # Set up intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        
        super().__init__(
            command_prefix='!wow ',
            intents=intents,
            description="World of Warcraft Guild Analysis Bot"
        )
        
        # MCP server endpoint
        self.mcp_endpoint = os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp")
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Add cogs/commands
        self.setup_commands()
    
    async def setup_hook(self):
        """Initialize bot components"""
        logger.info("Setting up WoW Guild Bot...")
        
        # Initialize HTTP session
        self.session = aiohttp.ClientSession()
        
        logger.info("Bot setup completed")
    
    async def close(self):
        """Cleanup on bot shutdown"""
        if self.session:
            await self.session.close()
        await super().close()
    
    async def on_ready(self):
        """Called when bot is ready"""
        logger.info(f"Bot logged in as {self.user.name} (ID: {self.user.id})")
        
        # Set bot status
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="WoW guilds | !wow help"
        )
        await self.change_presence(activity=activity)
    
    async def on_command_error(self, ctx, error):
        """Global command error handler"""
        if isinstance(error, commands.CommandNotFound):
            await ctx.send("⚠️ Command not found. Use `!wow wowhelp` for available commands.")
        
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"⚠️ Missing required argument: **{error.param.name}**")
        
        elif isinstance(error, commands.BadArgument):
            await ctx.send("⚠️ Invalid argument provided. Please check your input.")
        
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏰ Command on cooldown. Try again in {error.retry_after:.1f} seconds.")
        
        else:
            logger.error(f"Unexpected error in command {ctx.command}: {error}", exc_info=True)
            await ctx.send("❌ An unexpected error occurred. Please try again later.")
    
    def setup_commands(self):
        """Setup all bot commands"""
        
        @self.command(name='wowhelp', aliases=['h'])
        async def help_command(ctx):
            """Show help information"""
            embed = discord.Embed(
                title="🏰 WoW Guild Analysis Bot",
                description="Analyze World of Warcraft guilds with AI-powered insights",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="📊 Guild Commands",
                value="`!wow guild <realm> <guild_name>` - Comprehensive guild analysis\n"
                      "`!wow members <realm> <guild_name>` - Guild member list\n"
                      "`!wow progress <realm> <guild_name>` - Raid progression",
                inline=False
            )
            
            embed.add_field(
                name="👤 Member Commands",
                value="`!wow member <realm> <character_name>` - Individual member analysis\n"
                      "`!wow compare <realm> <guild_name> <member1> <member2>...` - Compare members",
                inline=False
            )
            
            embed.add_field(
                name="📈 Chart Commands",
                value="`!wow chart <realm> <guild_name>` - Generate guild charts\n"
                      "`!wow classes <realm> <guild_name>` - Class distribution chart",
                inline=False
            )
            
            embed.set_footer(text="Use quotes around names with spaces: 'Guild Name' | Use !wow wowhelp for help")
            await ctx.send(embed=embed)
        
        @self.command(name='guild', aliases=['g'])
        @commands.cooldown(1, 30, commands.BucketType.user)
        async def analyze_guild(ctx, realm: str, *, guild_name: str):
            """Analyze guild performance and display results"""
            try:
                # Show typing indicator
                async with ctx.typing():
                    # Call MCP server
                    result = await self._call_mcp_tool(
                        "analyze_guild_performance",
                        {
                            "realm": realm.lower(),
                            "guild_name": guild_name.lower(),
                            "analysis_type": "comprehensive"
                        }
                    )
                
                if not result or "error" in result:
                    error_msg = result.get("error", "Unknown error occurred") if result else "No response from server"
                    await ctx.send(f"❌ **Error:** {error_msg}")
                    return
                
                # Create rich embed response
                guild_info = result.get("guild_info", {})
                embed = discord.Embed(
                    title=f"🏰 Guild Analysis: {guild_info.get('name', guild_name)}",
                    description=f"**Realm:** {realm.title()}",
                    color=discord.Color.blue()
                )
                
                # Add guild statistics
                if guild_info:
                    embed.add_field(
                        name="📊 Guild Stats",
                        value=f"**Members:** {guild_info.get('member_count', 'N/A')}\n"
                              f"**Faction:** {guild_info.get('faction', 'Unknown')}\n"
                              f"**Achievement Points:** {guild_info.get('achievement_points', 'N/A'):,}",
                        inline=True
                    )
                
                # Add member analysis if available
                member_data = result.get("member_data", {})
                if member_data and not member_data.get("error"):
                    member_stats = member_data.get("member_statistics", {})
                    embed.add_field(
                        name="👥 Member Analysis",
                        value=f"**Total Members:** {member_stats.get('total_members', 'N/A')}\n"
                              f"**Max Level:** {member_stats.get('max_level_members', 'N/A')}\n"
                              f"**Avg Item Level:** {member_stats.get('average_item_level', 0):.1f}",
                        inline=True
                    )
                
                # Add AI insights
                insights = result.get("analysis_results", {}).get("insights", {})
                if insights and not insights.get("error"):
                    ai_insights = insights.get("ai_insights", "")
                    if ai_insights and len(ai_insights) < 1000:
                        embed.add_field(
                            name="🤖 AI Insights",
                            value=ai_insights[:500] + ("..." if len(ai_insights) > 500 else ""),
                            inline=False
                        )
                
                # Add timestamp
                embed.timestamp = discord.utils.utcnow()
                embed.set_footer(text="WoW Guild Analysis Bot")
                
                await ctx.send(embed=embed)
                
            except Exception as e:
                logger.error(f"Error in guild analysis: {str(e)}")
                await ctx.send("❌ An error occurred while analyzing the guild. Please try again.")
        
        @self.command(name='members', aliases=['m'])
        @commands.cooldown(1, 20, commands.BucketType.user)
        async def get_members(ctx, realm: str, *, guild_name: str):
            """Get guild member list with details"""
            try:
                async with ctx.typing():
                    result = await self._call_mcp_tool(
                        "get_guild_member_list",
                        {
                            "realm": realm.lower(),
                            "guild_name": guild_name.lower(),
                            "sort_by": "guild_rank",
                            "limit": 25
                        }
                    )
                
                if not result or "error" in result:
                    error_msg = result.get("error", "Unknown error occurred") if result else "No response from server"
                    await ctx.send(f"❌ **Error:** {error_msg}")
                    return
                
                members = result.get("members", [])
                if not members:
                    await ctx.send("❌ No members found for this guild.")
                    return
                
                # Create member list embed
                embed = discord.Embed(
                    title=f"👥 Guild Members: {guild_name.title()}",
                    description=f"**Realm:** {realm.title()} | **Total:** {len(members)}",
                    color=discord.Color.green()
                )
                
                # Group members by rank (show top 20)
                member_text = ""
                for i, member in enumerate(members[:20]):
                    name = member.get("name", "Unknown")
                    level = member.get("level", 0)
                    char_class = member.get("character_class", {})
                    class_name = char_class.get("name", "Unknown") if isinstance(char_class, dict) else "Unknown"
                    
                    # Get item level if available
                    eq_summary = member.get("equipment_summary", {})
                    ilvl = eq_summary.get("average_item_level", 0)
                    ilvl_text = f"({ilvl:.0f})" if ilvl > 0 else ""
                    
                    member_text += f"**{name}** - {class_name} {level} {ilvl_text}\n"
                    
                    # Split into multiple fields if too long
                    if len(member_text) > 900:
                        embed.add_field(
                            name=f"Members {max(1, i-19)}-{i}",
                            value=member_text,
                            inline=False
                        )
                        member_text = ""
                
                # Add remaining members
                if member_text:
                    embed.add_field(
                        name="Members",
                        value=member_text,
                        inline=False
                    )
                
                if len(members) > 20:
                    embed.set_footer(text=f"Showing first 20 of {len(members)} members")
                
                await ctx.send(embed=embed)
                
            except Exception as e:
                logger.error(f"Error getting members: {str(e)}")
                await ctx.send("❌ An error occurred while fetching guild members.")
        
        @self.command(name='member', aliases=['char'])
        @commands.cooldown(1, 15, commands.BucketType.user)
        async def analyze_member(ctx, realm: str, *, character_name: str):
            """Analyze individual member performance"""
            try:
                async with ctx.typing():
                    result = await self._call_mcp_tool(
                        "analyze_member_performance",
                        {
                            "realm": realm.lower(),
                            "character_name": character_name.lower(),
                            "analysis_depth": "standard"
                        }
                    )
                
                if not result or "error" in result:
                    error_msg = result.get("error", "Unknown error occurred") if result else "No response from server"
                    await ctx.send(f"❌ **Error:** {error_msg}")
                    return
                
                # Create member analysis embed
                member_info = result.get("member_info", {})
                embed = discord.Embed(
                    title=f"⚔️ Character Analysis: {member_info.get('name', character_name)}",
                    description=f"**Realm:** {realm.title()}",
                    color=discord.Color.purple()
                )
                
                # Character details
                embed.add_field(
                    name="📋 Character Info",
                    value=f"**Level:** {member_info.get('level', 'N/A')}\n"
                          f"**Class:** {member_info.get('class', 'Unknown')}\n"
                          f"**Race:** {member_info.get('race', 'Unknown')}\n"
                          f"**Guild Rank:** {member_info.get('guild_rank', 'N/A')}",
                    inline=True
                )
                
                # Performance metrics
                performance = result.get("performance_metrics", {})
                if performance:
                    embed.add_field(
                        name="⚡ Performance",
                        value=f"**Item Level:** {performance.get('item_level', 0):.1f}\n"
                              f"**Equipment:** {performance.get('equipment_quality', 'Unknown')}\n"
                              f"**Gear Score:** {performance.get('gear_score', 0):.0f}",
                        inline=True
                    )
                
                # Equipment analysis
                equipment = result.get("equipment_analysis", {})
                if equipment:
                    embed.add_field(
                        name="🛡️ Equipment",
                        value=f"**Status:** {equipment.get('gear_status', 'Unknown')}\n"
                              f"**Items Equipped:** {equipment.get('total_equipped', 0)}\n"
                              f"**Avg Item Level:** {equipment.get('average_item_level', 0):.1f}",
                        inline=True
                    )
                
                embed.timestamp = discord.utils.utcnow()
                await ctx.send(embed=embed)
                
            except Exception as e:
                logger.error(f"Error analyzing member: {str(e)}")
                await ctx.send("❌ An error occurred while analyzing the character.")
        
        @self.command(name='compare', aliases=['comp'])
        @commands.cooldown(1, 30, commands.BucketType.user)
        async def compare_members(ctx, realm: str, guild_name: str, *member_names):
            """Compare performance metrics between guild members"""
            try:
                if len(member_names) < 2:
                    await ctx.send("❌ Please provide at least 2 member names to compare.")
                    return
                
                if len(member_names) > 5:
                    await ctx.send("❌ Maximum 5 members can be compared at once.")
                    return
                
                async with ctx.typing():
                    # Generate comparison chart
                    result = await self._call_mcp_tool(
                        "compare_member_performance",
                        {
                            "realm": realm.lower(),
                            "guild_name": guild_name.lower(),
                            "member_names": list(member_names),
                            "metric": "item_level"
                        }
                    )
                
                if not result or "error" in result:
                    error_msg = result.get("error", "Unknown error occurred") if result else "No response from server"
                    await ctx.send(f"❌ **Error:** {error_msg}")
                    return
                
                # Send comparison results
                member_data = result.get("member_data", [])
                embed = discord.Embed(
                    title="⚖️ Member Comparison",
                    description=f"**Guild:** {guild_name.title()} | **Realm:** {realm.title()}",
                    color=discord.Color.orange()
                )
                
                comparison_text = ""
                for member in member_data:
                    name = member.get("name", "Unknown")
                    level = member.get("level", 0)
                    char_class = member.get("character_class", {})
                    class_name = char_class.get("name", "Unknown") if isinstance(char_class, dict) else "Unknown"
                    
                    eq_summary = member.get("equipment_summary", {})
                    ilvl = eq_summary.get("average_item_level", 0)
                    
                    comparison_text += f"**{name}** ({class_name} {level}): {ilvl:.1f} iLvl\n"
                
                embed.add_field(
                    name="📊 Item Level Comparison",
                    value=comparison_text or "No data available",
                    inline=False
                )
                
                # Send chart if available
                chart_data = result.get("chart_data")
                if chart_data:
                    # Convert base64 chart to Discord file
                    chart_buffer = await self._base64_to_buffer(chart_data)
                    if chart_buffer:
                        file = discord.File(chart_buffer, filename="member_comparison.png")
                        embed.set_image(url="attachment://member_comparison.png")
                        await ctx.send(embed=embed, file=file)
                        return
                
                await ctx.send(embed=embed)
                
            except Exception as e:
                logger.error(f"Error comparing members: {str(e)}")
                await ctx.send("❌ An error occurred while comparing members.")
        
        @self.command(name='chart', aliases=['graph'])
        @commands.cooldown(1, 45, commands.BucketType.user)
        async def generate_chart(ctx, realm: str, *, guild_name: str):
            """Generate raid progression chart"""
            try:
                async with ctx.typing():
                    chart_data = await self._call_mcp_tool(
                        "generate_raid_progress_chart",
                        {
                            "realm": realm.lower(),
                            "guild_name": guild_name.lower(),
                            "raid_tier": "current"
                        }
                    )
                
                if not chart_data:
                    await ctx.send("❌ Unable to generate chart. Please try again.")
                    return
                
                # Convert base64 chart to Discord file
                chart_buffer = await self._base64_to_buffer(chart_data)
                if chart_buffer:
                    file = discord.File(chart_buffer, filename="raid_progress.png")
                    
                    embed = discord.Embed(
                        title=f"📈 Raid Progression: {guild_name.title()}",
                        description=f"**Realm:** {realm.title()}",
                        color=discord.Color.red()
                    )
                    embed.set_image(url="attachment://raid_progress.png")
                    
                    await ctx.send(embed=embed, file=file)
                else:
                    await ctx.send("❌ Error processing chart data.")
                
            except Exception as e:
                logger.error(f"Error generating chart: {str(e)}")
                await ctx.send("❌ An error occurred while generating the chart.")
    
    async def _call_mcp_tool(self, tool_name: str, arguments: dict) -> Optional[dict]:
        """Call MCP server tool"""
        if not self.session:
            logger.error("HTTP session not initialized")
            return None
        
        try:
            url = f"{self.mcp_endpoint}/tools/call"
            payload = {
                "name": tool_name,
                "arguments": arguments
            }
            
            async with self.session.post(url, json=payload, timeout=60) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"MCP call failed: {response.status}")
                    text = await response.text()
                    logger.error(f"Error response: {text}")
                    return {"error": f"Server error: {response.status}"}
                    
        except asyncio.TimeoutError:
            logger.error("MCP call timed out")
            return {"error": "Request timed out"}
        except Exception as e:
            logger.error(f"Error calling MCP server: {str(e)}")
            return {"error": f"Connection error: {str(e)}"}
    
    async def _base64_to_buffer(self, base64_data: str) -> Optional[io.BytesIO]:
        """Convert base64 image data to BytesIO buffer"""
        try:
            image_data = base64.b64decode(base64_data)
            return io.BytesIO(image_data)
        except Exception as e:
            logger.error(f"Error converting base64 to buffer: {str(e)}")
            return None


async def main():
    """Main function to run the Discord bot"""
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        logger.error("DISCORD_BOT_TOKEN environment variable not set")
        return
    
    bot = WoWGuildBot()
    
    try:
        await bot.start(token)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot error: {str(e)}")
    finally:
        await bot.close()


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run the bot
    asyncio.run(main())