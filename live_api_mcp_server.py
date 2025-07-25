"""
Live API MCP Server - Actually uses Blizzard API with proper tracking
"""
import os
import logging
import sys
import asyncio
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from collections import defaultdict
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
mcp = FastMCP("WoW Analysis Server (Live API)")

# Global API usage tracking
api_stats = {
    "total_calls": 0,
    "live_calls": 0,
    "cache_hits": 0,
    "errors": 0,
    "last_live_call": None,
    "endpoints_called": defaultdict(int),
    "start_time": datetime.now()
}

# Simple cache with TTL
cache = {}
cache_ttl = {}

# Import the Blizzard API client
try:
    from app.api.blizzard_client import BlizzardAPIClient
    API_AVAILABLE = True
except ImportError:
    logger.warning("BlizzardAPIClient not available")
    API_AVAILABLE = False

def get_from_cache(key: str, ttl_minutes: int = 30) -> Optional[Any]:
    """Get data from cache if not expired"""
    if key in cache and key in cache_ttl:
        if datetime.now() - cache_ttl[key] < timedelta(minutes=ttl_minutes):
            api_stats["cache_hits"] += 1
            logger.info(f"Cache HIT for {key}")
            return cache[key]
    return None

def set_cache(key: str, data: Any):
    """Store data in cache"""
    cache[key] = data
    cache_ttl[key] = datetime.now()

@mcp.tool
async def analyze_realm_live(realm_slug: str = "stormrage", region: str = "us") -> str:
    """
    Analyze realm economy using LIVE Blizzard API data.
    
    Args:
        realm_slug: Realm to analyze
        region: Region code
    
    Returns:
        Live economic analysis with tracking info
    """
    api_stats["total_calls"] += 1
    
    try:
        # Check cache first
        cache_key = f"realm_{region}_{realm_slug}"
        cached_data = get_from_cache(cache_key, ttl_minutes=15)
        
        if cached_data:
            return f"""{cached_data}

**API Tracking:**
• Data Source: CACHED (< 15 min old)
• Total API Calls: {api_stats['total_calls']}
• Live API Calls: {api_stats['live_calls']}
• Cache Efficiency: {(api_stats['cache_hits'] / api_stats['total_calls'] * 100):.1f}%"""

        if not API_AVAILABLE:
            return "Error: Blizzard API client not available"
        
        # Make LIVE API call
        api_stats["live_calls"] += 1
        api_stats["last_live_call"] = datetime.now()
        
        async with BlizzardAPIClient() as client:
            # Get realm info
            realm_endpoint = f"/data/wow/realm/{realm_slug}"
            api_stats["endpoints_called"][realm_endpoint] += 1
            
            realm_data = await client.make_request(
                realm_endpoint, 
                {"namespace": f"dynamic-{region}", "locale": "en_US"}
            )
            
            realm_name = realm_data.get("name", realm_slug.title())
            
            # Get connected realm ID
            connected_realm_href = realm_data.get("connected_realm", {}).get("href", "")
            connected_realm_id = connected_realm_href.split("/")[-1].split("?")[0]
            
            # Get auction data
            auction_endpoint = f"/data/wow/connected-realm/{connected_realm_id}/auctions"
            api_stats["endpoints_called"][auction_endpoint] += 1
            
            auction_data = await client.make_request(
                auction_endpoint,
                {"namespace": f"dynamic-{region}", "locale": "en_US"}
            )
            
            auctions = auction_data.get("auctions", [])
            total_auctions = len(auctions)
            
            # Calculate statistics
            if auctions:
                prices = [a.get('buyout', 0) for a in auctions[:1000] if a.get('buyout', 0) > 0]
                avg_price = sum(prices) / len(prices) if prices else 0
                min_price = min(prices) if prices else 0
                max_price = max(prices) if prices else 0
            else:
                avg_price = min_price = max_price = 0
            
            result = f"""Economic Analysis - {realm_name} ({region.upper()})

Data Source: **LIVE BLIZZARD API**
Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**Market Overview:**
• Total Auctions: {total_auctions:,}
• Sample Size: {len(prices):,} items analyzed
• Average Price: {int(avg_price // 10000):,}g
• Price Range: {int(min_price // 10000):,}g - {int(max_price // 10000):,}g

**Market Health:**
• Activity Level: {'Extremely High' if total_auctions > 100000 else 'Very High' if total_auctions > 50000 else 'High' if total_auctions > 20000 else 'Moderate'}
• Liquidity: {'Excellent' if total_auctions > 80000 else 'Good' if total_auctions > 40000 else 'Fair'}
• Connected Realm ID: {connected_realm_id}"""

            # Cache the result
            set_cache(cache_key, result)
            
            return f"""{result}

**API Tracking:**
• Data Source: LIVE API CALL
• Total API Calls: {api_stats['total_calls']}
• Live API Calls: {api_stats['live_calls']}
• Cache Efficiency: {(api_stats['cache_hits'] / api_stats['total_calls'] * 100):.1f}%"""
            
    except Exception as e:
        api_stats["errors"] += 1
        logger.error(f"Error in live realm analysis: {str(e)}")
        return f"""Error analyzing {realm_slug}: {str(e)}

**API Tracking:**
• Total Calls: {api_stats['total_calls']}
• Errors: {api_stats['errors']}"""

@mcp.tool
async def get_token_price_live(region: str = "us") -> str:
    """
    Get LIVE WoW Token price from Blizzard API.
    
    Args:
        region: Region code
    
    Returns:
        Live token price with tracking
    """
    api_stats["total_calls"] += 1
    
    try:
        # Check cache
        cache_key = f"token_{region}"
        cached_data = get_from_cache(cache_key, ttl_minutes=20)
        
        if cached_data:
            return f"""{cached_data}

**API Tracking:**
• Data Source: CACHED (< 20 min old)
• Total API Calls: {api_stats['total_calls']}
• Live API Calls: {api_stats['live_calls']}"""

        if not API_AVAILABLE:
            return "Error: Blizzard API client not available"
        
        # Make LIVE API call
        api_stats["live_calls"] += 1
        api_stats["last_live_call"] = datetime.now()
        
        async with BlizzardAPIClient() as client:
            endpoint = "/data/wow/token/index"
            api_stats["endpoints_called"][endpoint] += 1
            
            token_data = await client.make_request(
                endpoint,
                {"namespace": f"dynamic-{region}", "locale": "en_US"}
            )
            
            price = token_data.get("price", 0)
            last_updated = token_data.get("last_updated_timestamp", 0)
            
            gold = price // 10000
            silver = (price % 10000) // 100
            
            # Convert timestamp
            update_time = datetime.fromtimestamp(last_updated / 1000).strftime('%Y-%m-%d %H:%M:%S')
            
            result = f"""WoW Token Price ({region.upper()})

Data Source: **LIVE BLIZZARD API**
Last Updated: {update_time}

**Current Price:**
• {gold:,}g {silver}s
• Raw: {price:,} copper

**Market Analysis:**
• Price Level: {'Low' if gold < 200000 else 'Moderate' if gold < 300000 else 'High'}
• Trend: Based on live data
• Update Frequency: ~20 minutes"""

            # Cache the result
            set_cache(cache_key, result)
            
            return f"""{result}

**API Tracking:**
• Data Source: LIVE API CALL
• Total API Calls: {api_stats['total_calls']}
• Live API Calls: {api_stats['live_calls']}"""
            
    except Exception as e:
        api_stats["errors"] += 1
        logger.error(f"Error getting live token price: {str(e)}")
        return f"Error: {str(e)}"

@mcp.tool
async def compare_realms_live(realms: str, region: str = "us") -> str:
    """
    Compare multiple realms using live data.
    
    Args:
        realms: Comma-separated realm names
        region: Region code
    
    Returns:
        Comparative analysis with live data
    """
    api_stats["total_calls"] += 1
    
    try:
        realm_list = [r.strip() for r in realms.split(",")][:3]  # Limit to 3
        results = []
        
        for realm in realm_list:
            cache_key = f"realm_{region}_{realm}"
            cached_data = get_from_cache(cache_key, ttl_minutes=30)
            
            if cached_data:
                # Extract auction count from cached data
                import re
                match = re.search(r'Total Auctions: ([\d,]+)', cached_data)
                count = int(match.group(1).replace(',', '')) if match else 0
                results.append({"realm": realm, "count": count, "source": "Cached"})
            else:
                # Make live API call
                if API_AVAILABLE:
                    try:
                        api_stats["live_calls"] += 1
                        async with BlizzardAPIClient() as client:
                            realm_endpoint = f"/data/wow/realm/{realm}"
                            realm_data = await client.make_request(
                                realm_endpoint,
                                {"namespace": f"dynamic-{region}", "locale": "en_US"}
                            )
                            
                            connected_realm_href = realm_data.get("connected_realm", {}).get("href", "")
                            connected_realm_id = connected_realm_href.split("/")[-1].split("?")[0]
                            
                            auction_endpoint = f"/data/wow/connected-realm/{connected_realm_id}/auctions"
                            auction_data = await client.make_request(
                                auction_endpoint,
                                {"namespace": f"dynamic-{region}", "locale": "en_US"}
                            )
                            
                            count = len(auction_data.get("auctions", []))
                            results.append({"realm": realm, "count": count, "source": "Live API"})
                    except:
                        results.append({"realm": realm, "count": 0, "source": "Error"})
                else:
                    results.append({"realm": realm, "count": 0, "source": "API Unavailable"})
        
        # Sort by count
        results.sort(key=lambda x: x["count"], reverse=True)
        
        output = f"""Realm Comparison ({region.upper()})
Data Sources: Mixed (Live + Cached)

**Market Size Ranking:**"""
        
        for i, r in enumerate(results, 1):
            output += f"\n{i}. {r['realm'].title()}: {r['count']:,} auctions ({r['source']})"
        
        output += f"""

**API Tracking:**
• Total API Calls: {api_stats['total_calls']}
• Live API Calls: {api_stats['live_calls']}
• Cache Hits: {api_stats['cache_hits']}"""
        
        return output
        
    except Exception as e:
        api_stats["errors"] += 1
        return f"Error: {str(e)}"

@mcp.tool
def get_api_tracking_report() -> str:
    """
    Get detailed API usage tracking report.
    
    Returns:
        Comprehensive tracking statistics
    """
    uptime = datetime.now() - api_stats["start_time"]
    uptime_minutes = int(uptime.total_seconds() / 60)
    
    # Calculate rates
    calls_per_minute = api_stats["total_calls"] / max(1, uptime_minutes)
    cache_efficiency = (api_stats["cache_hits"] / max(1, api_stats["total_calls"])) * 100
    error_rate = (api_stats["errors"] / max(1, api_stats["total_calls"])) * 100
    
    result = f"""API Usage Tracking Report

**Server Status:**
• Server Start: {api_stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}
• Uptime: {uptime_minutes} minutes
• Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**Call Statistics:**
• Total API Calls: {api_stats['total_calls']}
• Live Blizzard API Calls: {api_stats['live_calls']}
• Cached Responses: {api_stats['cache_hits']}
• Errors: {api_stats['errors']}

**Performance Metrics:**
• Calls per Minute: {calls_per_minute:.1f}
• Cache Efficiency: {cache_efficiency:.1f}%
• Error Rate: {error_rate:.1f}%
• Last Live API Call: {api_stats['last_live_call'].strftime('%H:%M:%S') if api_stats['last_live_call'] else 'Never'}

**Endpoint Usage:**"""
    
    for endpoint, count in sorted(api_stats["endpoints_called"].items(), key=lambda x: x[1], reverse=True)[:5]:
        result += f"\n• {endpoint}: {count} calls"
    
    result += f"""

**API Credentials:**
• Client ID: {'✅ Set' if os.getenv('BLIZZARD_CLIENT_ID') else '❌ Missing'}
• Client Secret: {'✅ Set' if os.getenv('BLIZZARD_CLIENT_SECRET') else '❌ Missing'}
• API Module: {'✅ Available' if API_AVAILABLE else '❌ Not Found'}

**Cache Status:**
• Cached Items: {len(cache)}
• Cache TTL: 15-30 minutes
• Memory Usage: Minimal

**Recommendations:**
• {'✅ System operating efficiently' if cache_efficiency > 50 else '⚠️ Consider increasing cache TTL'}
• {'✅ Error rate acceptable' if error_rate < 5 else '⚠️ Investigate error causes'}
• {'✅ Live API working' if api_stats['live_calls'] > 0 else '❌ No live API calls made yet'}"""
    
    return result

@mcp.tool
async def test_api_connectivity() -> str:
    """
    Test Blizzard API connectivity and credentials.
    
    Returns:
        Detailed connectivity test results
    """
    api_stats["total_calls"] += 1
    
    if not API_AVAILABLE:
        return "Error: Blizzard API client not available"
    
    results = []
    
    try:
        api_stats["live_calls"] += 1
        async with BlizzardAPIClient() as client:
            # Test 1: Token endpoint (simplest)
            try:
                token_data = await client.make_request(
                    "/data/wow/token/index",
                    {"namespace": "dynamic-us", "locale": "en_US"}
                )
                price = token_data.get("price", 0) // 10000
                results.append(f"✅ Token API: Success ({price:,}g)")
            except Exception as e:
                results.append(f"❌ Token API: {str(e)}")
            
            # Test 2: Realm endpoint
            try:
                realm_data = await client.make_request(
                    "/data/wow/realm/stormrage",
                    {"namespace": "dynamic-us", "locale": "en_US"}
                )
                realm_name = realm_data.get("name", "Unknown")
                results.append(f"✅ Realm API: Success ({realm_name})")
            except Exception as e:
                results.append(f"❌ Realm API: {str(e)}")
            
            # Test 3: Auction endpoint
            try:
                # Get Stormrage's connected realm
                realm_data = await client.make_request(
                    "/data/wow/realm/stormrage",
                    {"namespace": "dynamic-us", "locale": "en_US"}
                )
                connected_href = realm_data.get("connected_realm", {}).get("href", "")
                connected_id = connected_href.split("/")[-1].split("?")[0]
                
                auction_data = await client.make_request(
                    f"/data/wow/connected-realm/{connected_id}/auctions",
                    {"namespace": "dynamic-us", "locale": "en_US"}
                )
                auction_count = len(auction_data.get("auctions", []))
                results.append(f"✅ Auction API: Success ({auction_count:,} auctions)")
            except Exception as e:
                results.append(f"❌ Auction API: {str(e)}")
            
    except Exception as e:
        results.append(f"❌ Client initialization: {str(e)}")
    
    return f"""Blizzard API Connectivity Test

**Test Results:**
{chr(10).join(results)}

**Summary:**
• Tests Run: {len(results)}
• Successful: {sum(1 for r in results if '✅' in r)}
• Failed: {sum(1 for r in results if '❌' in r)}

**API Tracking:**
• Total Calls: {api_stats['total_calls']}
• Live Calls: {api_stats['live_calls']}

**Next Steps:**
{'✅ All tests passed! API is working correctly.' if all('✅' in r for r in results) else '⚠️ Some tests failed. Check credentials and network.'}"""

def main():
    """Main entry point"""
    try:
        port = int(os.getenv("PORT", "8000"))
        
        logger.info("🚀 WoW Analysis MCP Server (Live API with Tracking)")
        logger.info("🔧 Features: Live Blizzard API, usage tracking, caching")
        logger.info("📊 Tools: 5 analysis functions with real data")
        logger.info(f"🌐 HTTP Server: 0.0.0.0:{port}")
        logger.info("✅ Starting server...")
        
        # Check API availability
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