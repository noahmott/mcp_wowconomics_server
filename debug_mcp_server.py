"""
Debug version of MCP server that includes raw API responses
"""
import os
import json
import asyncio
from datetime import datetime
from fastmcp import FastMCP

# Create FastMCP server
mcp = FastMCP("Debug WoW Analysis Server")

# Import the Blizzard API client
try:
    from app.api.blizzard_client import BlizzardAPIClient
    API_AVAILABLE = True
except ImportError:
    API_AVAILABLE = False

@mcp.tool()
async def debug_market_data(realm_slug: str = "stormrage", region: str = "us") -> str:
    """
    Get raw market data with API responses included.
    
    Returns both formatted analysis and raw API data.
    """
    if not API_AVAILABLE:
        return json.dumps({"error": "Blizzard API not available"}, indent=2)
    
    try:
        raw_data = {
            "timestamp": datetime.now().isoformat(),
            "request": {
                "realm_slug": realm_slug,
                "region": region
            },
            "api_responses": {}
        }
        
        async with BlizzardAPIClient() as client:
            # Get realm info
            realm_endpoint = f"/data/wow/realm/{realm_slug}"
            realm_data = await client.make_request(
                realm_endpoint, 
                {"namespace": f"dynamic-{region}", "locale": "en_US"}
            )
            raw_data["api_responses"]["realm_info"] = realm_data
            
            # Get auction data
            connected_realm_href = realm_data.get("connected_realm", {}).get("href", "")
            connected_realm_id = connected_realm_href.split("/")[-1].split("?")[0]
            
            auction_endpoint = f"/data/wow/connected-realm/{connected_realm_id}/auctions"
            auction_data = await client.make_request(
                auction_endpoint,
                {"namespace": f"dynamic-{region}", "locale": "en_US"}
            )
            
            # Include sample of auction data (first 10 items)
            raw_data["api_responses"]["auction_sample"] = {
                "total_auctions": len(auction_data.get("auctions", [])),
                "sample_auctions": auction_data.get("auctions", [])[:10]
            }
            
            # Calculate some statistics
            auctions = auction_data.get("auctions", [])
            item_count = {}
            price_ranges = {}
            
            for auction in auctions[:100]:  # Sample first 100
                item_id = auction.get('item', {}).get('id', 0)
                buyout = auction.get('buyout', 0)
                quantity = auction.get('quantity', 1)
                
                if item_id not in item_count:
                    item_count[item_id] = 0
                    price_ranges[item_id] = {"min": float('inf'), "max": 0}
                
                item_count[item_id] += 1
                if buyout > 0 and quantity > 0:
                    price_per_unit = buyout / quantity
                    price_ranges[item_id]["min"] = min(price_ranges[item_id]["min"], price_per_unit)
                    price_ranges[item_id]["max"] = max(price_ranges[item_id]["max"], price_per_unit)
            
            raw_data["analysis"] = {
                "unique_items_in_sample": len(item_count),
                "top_5_items_by_listings": sorted(item_count.items(), key=lambda x: x[1], reverse=True)[:5],
                "sample_price_ranges": {str(k): v for k, v in list(price_ranges.items())[:5]}
            }
            
            return json.dumps(raw_data, indent=2)
            
    except Exception as e:
        return json.dumps({
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }, indent=2)

@mcp.tool()
async def debug_token_price(region: str = "us") -> str:
    """
    Get raw WoW Token price data.
    """
    if not API_AVAILABLE:
        return json.dumps({"error": "Blizzard API not available"}, indent=2)
    
    try:
        async with BlizzardAPIClient() as client:
            token_endpoint = "/data/wow/token/index"
            token_data = await client.make_request(
                token_endpoint,
                {"namespace": f"dynamic-{region}", "locale": "en_US"}
            )
            
            return json.dumps({
                "timestamp": datetime.now().isoformat(),
                "region": region,
                "raw_api_response": token_data,
                "formatted": {
                    "price_copper": token_data.get("price", 0),
                    "price_gold": token_data.get("price", 0) // 10000,
                    "last_updated": token_data.get("last_updated_timestamp", 0)
                }
            }, indent=2)
            
    except Exception as e:
        return json.dumps({
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }, indent=2)

@mcp.tool()
async def debug_realm_list(region: str = "us") -> str:
    """
    Get list of realms in a region.
    """
    if not API_AVAILABLE:
        return json.dumps({"error": "Blizzard API not available"}, indent=2)
    
    try:
        async with BlizzardAPIClient() as client:
            realms_endpoint = "/data/wow/realm/index"
            realms_data = await client.make_request(
                realms_endpoint,
                {"namespace": f"dynamic-{region}", "locale": "en_US"}
            )
            
            # Get detailed info for first 5 realms
            realm_details = []
            for realm in realms_data.get("realms", [])[:5]:
                realm_slug = realm.get("slug", "")
                if realm_slug:
                    realm_detail = await client.make_request(
                        f"/data/wow/realm/{realm_slug}",
                        {"namespace": f"dynamic-{region}", "locale": "en_US"}
                    )
                    realm_details.append(realm_detail)
            
            return json.dumps({
                "timestamp": datetime.now().isoformat(),
                "region": region,
                "total_realms": len(realms_data.get("realms", [])),
                "realm_list_sample": realms_data.get("realms", [])[:10],
                "detailed_realm_info": realm_details
            }, indent=2)
            
    except Exception as e:
        return json.dumps({
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }, indent=2)

def main():
    """Run the debug server"""
    port = int(os.getenv("PORT", "8008"))
    
    print(f"Starting Debug WoW Analysis Server on port {port}")
    print("Available debug tools:")
    print("  - debug_market_data: Get raw auction house data")
    print("  - debug_token_price: Get raw token price data")
    print("  - debug_realm_list: Get realm information")
    
    mcp.run(
        transport="http",
        host="0.0.0.0",
        port=port
    )

if __name__ == "__main__":
    main()