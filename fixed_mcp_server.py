"""
Fixed WoW MCP Server that actually uses the Blizzard API
"""
import os
import logging
import sys
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
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
mcp = FastMCP("WoW Analysis Server (Fixed)")

# Import the actual Blizzard API client
try:
    from app.api.blizzard_client import BlizzardAPIClient
    API_AVAILABLE = True
except ImportError:
    logger.warning("BlizzardAPIClient not available")
    API_AVAILABLE = False

@mcp.tool
async def analyze_realm_economy_live(realm_slug: str = "stormrage", region: str = "us") -> str:
    """
    Analyze realm economy using LIVE Blizzard API data.
    
    Args:
        realm_slug: Realm to analyze (e.g. 'stormrage')
        region: Region code (e.g. 'us', 'eu')
    
    Returns:
        Economic analysis with live auction data
    """
    try:
        if not API_AVAILABLE:
            return "Error: Blizzard API client not available"
        
        # Initialize API client
        async with BlizzardAPIClient() as client:
            # Get realm info first
            realm_endpoint = f"/data/wow/realm/{realm_slug}"
            realm_params = {"namespace": f"dynamic-{region}", "locale": "en_US"}
            
            try:
                realm_data = await client.make_request(realm_endpoint, realm_params)
                realm_name = realm_data.get("name", realm_slug.title())
                
                # Get connected realm ID
                connected_realm_href = realm_data.get("connected_realm", {}).get("href", "")
                if not connected_realm_href:
                    return f"Error: Could not find connected realm for {realm_slug}"
                
                connected_realm_id = connected_realm_href.split("/")[-1].split("?")[0]
                
                # Get auction data
                auction_endpoint = f"/data/wow/connected-realm/{connected_realm_id}/auctions"
                auction_params = {"namespace": f"dynamic-{region}", "locale": "en_US"}
                
                auction_response = await client.make_request(auction_endpoint, auction_params)
                
                auctions = auction_response.get("auctions", [])
                
                # Analyze the live data
                total_auctions = len(auctions)
                total_value = sum(auction.get('buyout', 0) for auction in auctions if auction.get('buyout'))
                avg_value = total_value // total_auctions if total_auctions else 0
                
                # Economic health scoring based on real data
                if total_auctions > 100000:
                    health = "Excellent"
                    activity = "Very High"
                elif total_auctions > 50000:
                    health = "Good"
                    activity = "High"
                elif total_auctions > 20000:
                    health = "Fair"
                    activity = "Medium"
                else:
                    health = "Poor"
                    activity = "Low"
                
                result = f"""Economic Analysis - {realm_name} ({region.upper()})

Data Source: LIVE Blizzard API
Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**Economic Health: {health}**
• Market Activity: {activity} ({total_auctions:,} auctions)
• Total Market Value: {(total_value // 10000):,}g
• Average Auction Price: {(avg_value // 10000):,}g
• Connected Realm ID: {connected_realm_id}

**Market Insights:**
• Real-time auction house data
• {'Massive economy with exceptional liquidity' if total_auctions > 100000 else 'Strong active market' if total_auctions > 50000 else 'Moderate market activity'}
• Data freshness: Live pull from Blizzard API

**API Status:**
✅ Blizzard API: Connected
✅ OAuth Token: Valid
✅ Data Source: Live
✅ Region: {region.upper()} properly configured"""

                return result
                
            except Exception as api_error:
                # If API fails, show the error
                return f"""Economic Analysis - {realm_slug} ({region.upper()})

Data Source: API Error
Error: {str(api_error)}

**Troubleshooting:**
• Check if realm slug is correct: {realm_slug}
• Verify region is correct: {region}
• API endpoint might be temporarily down
• Rate limits might be exceeded

Try again in a few moments."""
                
    except Exception as e:
        logger.error(f"Error in live realm analysis: {str(e)}")
        return f"Error: {str(e)}"

@mcp.tool
async def get_wow_token_price_live(region: str = "us") -> str:
    """
    Get LIVE WoW Token price from Blizzard API.
    
    Args:
        region: Region code (us, eu, kr, tw, cn)
    
    Returns:
        Live token price and market analysis
    """
    try:
        if not API_AVAILABLE:
            return "Error: Blizzard API client not available"
        
        async with BlizzardAPIClient() as client:
            endpoint = "/data/wow/token/index"
            params = {"namespace": f"dynamic-{region}", "locale": "en_US"}
            
            try:
                token_data = await client.make_request(endpoint, params)
                
                price = token_data.get("price", 0)
                last_updated = token_data.get("last_updated_timestamp", 0)
                
                gold = price // 10000
                silver = (price % 10000) // 100
                copper = price % 100
                
                # Market analysis based on real price
                if gold < 150000:
                    trend = "Very Low - Excellent buying opportunity"
                    recommendation = "Strong Buy"
                elif gold < 200000:
                    trend = "Low - Good buying opportunity"  
                    recommendation = "Buy"
                elif gold < 300000:
                    trend = "Moderate - Fair pricing"
                    recommendation = "Hold"
                elif gold < 400000:
                    trend = "High - Consider alternatives"
                    recommendation = "Avoid"
                else:
                    trend = "Very High - Historical peak"
                    recommendation = "Strong Avoid"
                
                # Convert timestamp
                from datetime import datetime
                update_time = datetime.fromtimestamp(last_updated / 1000).strftime('%Y-%m-%d %H:%M:%S')
                
                result = f"""WoW Token Market Analysis ({region.upper()})

Data Source: LIVE Blizzard API
Last Updated: {update_time}

**Current Price:**
• {gold:,}g {silver}s {copper}c
• Raw: {price:,} copper

**Market Assessment:**
• Price Level: {trend}
• Recommendation: {recommendation}
• Data Age: Live from Blizzard

**24h Statistics:**
• Current: {gold:,}g
• Region: {region.upper()}
• Update Frequency: ~20 minutes

**Trading Strategy:**
• Buy below: {int(gold * 0.9):,}g
• Sell above: {int(gold * 1.1):,}g
• Fair value: {gold:,}g

**API Status:**
✅ Token API: Connected
✅ Price Data: Live
✅ Region: {region.upper()} confirmed"""

                return result
                
            except Exception as api_error:
                return f"""WoW Token Price ({region.upper()})

Data Source: API Error
Error: {str(api_error)}

**Common Issues:**
• Invalid region code (use: us, eu, kr, tw, cn)
• API temporarily unavailable
• Rate limit exceeded

Please try again in a moment."""
                
    except Exception as e:
        logger.error(f"Error getting live token price: {str(e)}")
        return f"Error: {str(e)}"

@mcp.tool
def get_api_status() -> str:
    """
    Check Blizzard API connection status.
    
    Returns:
        Detailed API status report
    """
    try:
        # Check credentials
        client_id = os.getenv("BLIZZARD_CLIENT_ID")
        client_secret = os.getenv("BLIZZARD_CLIENT_SECRET")
        
        result = f"""Blizzard API Status Report

**Credentials:**
• Client ID: {'✅ Set' if client_id else '❌ Missing'} {f'({client_id[:10]}...)' if client_id else ''}
• Client Secret: {'✅ Set' if client_secret else '❌ Missing'}

**Configuration:**
• API Module: {'✅ Available' if API_AVAILABLE else '❌ Not Found'}
• Server Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**Available Tools:**
• analyze_realm_economy_live - Live auction house data
• get_wow_token_price_live - Live token prices
• get_api_status - This status check

**How to Test:**
1. Try: "analyze realm economy live for stormrage"
2. Try: "get wow token price live for us"
3. Check the "Data Source" line in responses

**Expected Live Data Indicators:**
• Data Source: LIVE Blizzard API
• Auction counts > 10,000 (not exactly 5,000)
• Precise token prices (not round numbers)
• Timestamps showing recent updates"""

        return result
        
    except Exception as e:
        return f"Error checking API status: {str(e)}"

def main():
    """Main entry point"""
    try:
        port = int(os.getenv("PORT", "8000"))
        
        logger.info("🚀 WoW Analysis MCP Server (Fixed - Live API)")
        logger.info("🔧 Features: Direct Blizzard API integration")
        logger.info("📊 Tools: Live auction data, real token prices")
        logger.info(f"🌐 HTTP Server: 0.0.0.0:{port}")
        logger.info("✅ Starting server...")
        
        # Show API status
        client_id = os.getenv("BLIZZARD_CLIENT_ID")
        if client_id:
            logger.info(f"✅ Blizzard API configured: {client_id[:10]}...")
        else:
            logger.warning("⚠️ No Blizzard API credentials found")
        
        # Run server
        mcp.run(transport="http", host="0.0.0.0", port=port)
        
    except Exception as e:
        logger.error(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()