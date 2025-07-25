"""
Improved WoW Analysis MCP Server - Better API Endpoints & Data Access
"""
import os
import logging
import sys
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
from fastmcp import FastMCP

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Create FastMCP server
mcp = FastMCP(
    name="WoW Analysis Server (Improved)",
    host="0.0.0.0",
    port=int(os.getenv("PORT", "8000"))
)

# Import API components
from app.api.blizzard_client import BlizzardAPIClient, BlizzardAPIError

@mcp.tool()
async def search_realm_info(region: str = "us", locale: str = "en_US") -> str:
    """
    Get available realms and their status - uses accessible Game Data API.
    
    Args:
        region: Region (us, eu, kr, tw, cn)
        locale: Locale (en_US, es_MX, pt_BR, etc.)
    
    Returns:
        List of available realms with population and status data
    """
    try:
        async with BlizzardAPIClient() as client:
            # Use Game Data API for realm index - more accessible
            endpoint = "/data/wow/realm/index"
            params = {
                "namespace": f"dynamic-{region}",
                "locale": locale
            }
            realm_data = await client.make_request(endpoint, params)
            
            realms = realm_data.get("realms", [])[:20]  # Limit to first 20
            
            realm_list = f"Available Realms ({region.upper()}):\n\n"
            for realm in realms:
                name = realm.get("name", "Unknown")
                slug = realm.get("slug", "unknown")
                realm_list += f"• **{name}** ({slug})\n"
            
            return realm_list
            
    except Exception as e:
        return f"Failed to get realm data: {str(e)}"

@mcp.tool()
async def get_character_media(realm: str, character_name: str, media_type: str = "avatar") -> str:
    """
    Get character visual media (avatar, render, etc.) - often more accessible than equipment.
    
    Args:
        realm: Server realm slug
        character_name: Character name
        media_type: Type of media to retrieve
    
    Returns:
        Character media information and URLs
    """
    try:
        async with BlizzardAPIClient() as client:
            # Character media endpoint - often works when equipment doesn't
            encoded_name = character_name.lower().replace(" ", "")
            endpoint = f"/profile/wow/character/{realm.lower()}/{encoded_name}/character-media"
            
            media_data = await client.make_request(endpoint)
            
            result = f"Character Media for {character_name}:\n\n"
            
            assets = media_data.get("assets", [])
            for asset in assets:
                asset_type = asset.get("key", "unknown")
                asset_url = asset.get("value", "No URL")
                result += f"• **{asset_type.title()}**: {asset_url}\n"
            
            if not assets:
                result += "No media assets found for this character.\n"
            
            return result
            
    except BlizzardAPIError as e:
        return f"Character media lookup failed: {e.message}"
    except Exception as e:
        return f"Error getting character media: {str(e)}"

@mcp.tool()
async def analyze_realm_population(realm_slug: str, region: str = "us") -> str:
    """
    Analyze realm population and activity using accessible endpoints.
    
    Args:
        realm_slug: Realm slug (e.g., 'stormrage', 'area-52')
        region: Region code
    
    Returns:
        Realm analysis with population indicators and connected realms
    """
    try:
        async with BlizzardAPIClient() as client:
            # Get specific realm data
            endpoint = f"/data/wow/realm/{realm_slug.lower()}"
            params = {
                "namespace": f"dynamic-{region}",
                "locale": "en_US"
            }
            realm_data = await client.make_request(endpoint, params)
            
            result = f"Realm Analysis: {realm_data.get('name', 'Unknown')}\n\n"
            
            # Basic realm info
            result += f"**Realm Details:**\n"
            result += f"• Name: {realm_data.get('name', 'Unknown')}\n"
            result += f"• Type: {realm_data.get('type', {}).get('name', 'Unknown')}\n"
            result += f"• Population: {realm_data.get('population', {}).get('name', 'Unknown')}\n"
            result += f"• Timezone: {realm_data.get('timezone', 'Unknown')}\n"
            
            # Connected realms
            connected_realms = realm_data.get("connected_realm", {})
            if connected_realms:
                result += f"• Connected Realm Group: Yes\n"
            else:
                result += f"• Connected Realm Group: Standalone\n"
            
            return result
            
    except BlizzardAPIError as e:
        return f"Realm analysis failed: {e.message}"
    except Exception as e:
        return f"Error analyzing realm: {str(e)}"

@mcp.tool()
async def get_wow_token_price(region: str = "us") -> str:
    """
    Get current WoW Token price - reliable Game Data API endpoint.
    
    Args:
        region: Region (us, eu, kr, tw, cn)
    
    Returns:
        Current WoW Token price information
    """
    try:
        async with BlizzardAPIClient() as client:
            endpoint = "/data/wow/token/index"
            params = {
                "namespace": f"dynamic-{region}",
                "locale": "en_US"
            }
            token_data = await client.make_request(endpoint, params)
            
            price = token_data.get("price", 0)
            last_updated = token_data.get("last_updated_timestamp", 0)
            
            # Convert gold to readable format
            gold = price // 10000
            silver = (price % 10000) // 100
            copper = price % 100
            
            result = f"WoW Token Price ({region.upper()}):\n\n"
            result += f"• **Price**: {gold:,}g {silver}s {copper}c\n"
            result += f"• **Raw Price**: {price:,} copper\n"
            result += f"• **Last Updated**: {last_updated}\n"
            
            return result
            
    except Exception as e:
        return f"Failed to get WoW Token price: {str(e)}"

@mcp.tool()
async def search_auction_house_data(realm_slug: str, item_search: str = "", region: str = "us") -> str:
    """
    Search auction house data for realm economic analysis.
    
    Args:
        realm_slug: Realm slug
        item_search: Optional item name to search for
        region: Region code
    
    Returns:
        Auction house summary and economic indicators
    """
    try:
        async with BlizzardAPIClient() as client:
            # Get connected realm info first
            realm_endpoint = f"/data/wow/realm/{realm_slug.lower()}"
            realm_params = {
                "namespace": f"dynamic-{region}",
                "locale": "en_US"
            }
            realm_data = await client.make_request(realm_endpoint, realm_params)
            
            # Get connected realm ID for auction data
            connected_realm_href = realm_data.get("connected_realm", {}).get("href", "")
            if not connected_realm_href:
                return f"No connected realm data available for {realm_slug}"
            
            # Extract connected realm ID from href
            connected_realm_id = connected_realm_href.split("/")[-1]
            
            # Get auction house data
            auction_endpoint = f"/data/wow/connected-realm/{connected_realm_id}/auctions"
            auction_params = {
                "namespace": f"dynamic-{region}",
                "locale": "en_US"
            }
            
            auction_data = await client.make_request(auction_endpoint, auction_params)
            
            auctions = auction_data.get("auctions", [])
            
            result = f"Auction House Analysis - {realm_data.get('name', realm_slug)}\n\n"
            result += f"**Market Overview:**\n"
            result += f"• Total Auctions: {len(auctions):,}\n"
            
            if auctions:
                # Calculate some basic economics
                total_value = sum(auction.get("buyout", 0) for auction in auctions if auction.get("buyout"))
                avg_value = total_value // len(auctions) if auctions else 0
                
                # Convert to gold
                avg_gold = avg_value // 10000
                
                result += f"• Average Auction Value: {avg_gold:,}g\n"
                result += f"• Market Activity: {'High' if len(auctions) > 10000 else 'Medium' if len(auctions) > 5000 else 'Low'}\n"
                
                # Show sample auctions if searching for specific item
                if item_search:
                    matching_auctions = [
                        auction for auction in auctions[:100] 
                        if item_search.lower() in auction.get("item", {}).get("id", "").lower()
                    ]
                    result += f"\n**Search Results for '{item_search}':**\n"
                    result += f"• Found {len(matching_auctions)} matching auctions\n"
            
            return result
            
    except BlizzardAPIError as e:
        return f"Auction house analysis failed: {e.message}"
    except Exception as e:
        return f"Error analyzing auction house: {str(e)}"

@mcp.tool()
async def get_mythic_plus_season_info(region: str = "us") -> str:
    """
    Get current Mythic+ season information and affixes.
    
    Args:
        region: Region code
    
    Returns:
        Current M+ season data and weekly affixes
    """
    try:
        async with BlizzardAPIClient() as client:
            # Get current M+ season
            season_endpoint = "/data/wow/mythic-keystone/season/index"
            params = {
                "namespace": f"dynamic-{region}",
                "locale": "en_US"
            }
            season_data = await client.make_request(season_endpoint, params)
            
            current_season = season_data.get("current_season", {})
            
            result = f"Mythic+ Season Information ({region.upper()}):\n\n"
            
            if current_season:
                season_id = current_season.get("id", "Unknown")
                result += f"• **Current Season**: {season_id}\n"
                
                # Try to get season details
                try:
                    detail_endpoint = f"/data/wow/mythic-keystone/season/{season_id}"
                    season_details = await client.make_request(detail_endpoint, params)
                    
                    start_timestamp = season_details.get("start_timestamp")
                    end_timestamp = season_details.get("end_timestamp")
                    
                    if start_timestamp:
                        result += f"• **Season Start**: {start_timestamp}\n"
                    if end_timestamp:
                        result += f"• **Season End**: {end_timestamp}\n"
                        
                except BlizzardAPIError:
                    result += f"• **Season Details**: Available but restricted\n"
            
            # Try to get current period/affixes
            try:
                period_endpoint = "/data/wow/mythic-keystone/period/index"
                period_data = await client.make_request(period_endpoint, params)
                
                current_period = period_data.get("current_period", {})
                if current_period:
                    period_id = current_period.get("id", "Unknown")
                    result += f"• **Current Period**: {period_id}\n"
                    
            except BlizzardAPIError:
                result += f"• **Weekly Rotation**: Data restricted\n"
            
            return result
            
    except Exception as e:
        return f"Failed to get M+ season info: {str(e)}"

def main():
    """Main entry point for improved FastMCP server."""
    try:
        # Check for required API keys
        blizzard_client_id = os.getenv("BLIZZARD_CLIENT_ID")
        blizzard_client_secret = os.getenv("BLIZZARD_CLIENT_SECRET")
        
        if not blizzard_client_id or not blizzard_client_secret:
            raise ValueError("Blizzard API credentials not found in environment variables")
        
        port = int(os.getenv("PORT", "8000"))
        
        logger.info("🚀 Improved WoW Analysis MCP Server")
        logger.info("🔧 Tools: Realm analysis, character media, auction house, M+ data")
        logger.info("📊 Registered tools: 6 improved WoW analysis tools")
        logger.info(f"🌐 HTTP Server: 0.0.0.0:{port}")
        logger.info("✅ Starting server...")
        
        # Run server using FastMCP 2.0 HTTP transport
        mcp.run(transport="http")
        
    except Exception as e:
        logger.error(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()