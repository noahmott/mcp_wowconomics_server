"""
Debug API MCP Server - Shows exact API calls and responses
"""
import os
import logging
import sys
import asyncio
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from collections import defaultdict, deque
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
mcp = FastMCP("WoW Analysis Server (Debug Mode)")

# API call history - stores last 10 calls
api_call_history = deque(maxlen=10)

# Simple cache
cache = {}
cache_ttl = {}

# Import the Blizzard API client
try:
    from app.api.blizzard_client import BlizzardAPIClient
    API_AVAILABLE = True
except ImportError:
    logger.warning("BlizzardAPIClient not available")
    API_AVAILABLE = False

def log_api_call(endpoint: str, params: dict, response: Any, error: Optional[str] = None):
    """Log detailed API call information"""
    call_info = {
        "timestamp": datetime.now().isoformat(),
        "endpoint": endpoint,
        "params": params,
        "response_size": len(str(response)) if response else 0,
        "error": error,
        "success": error is None
    }
    
    # Store sample of response data
    if response and isinstance(response, dict):
        if "auctions" in response:
            call_info["auction_count"] = len(response.get("auctions", []))
            call_info["sample_auctions"] = response.get("auctions", [])[:3]  # First 3 auctions
        elif "price" in response:
            call_info["token_price"] = response.get("price", 0)
        elif "name" in response:
            call_info["realm_name"] = response.get("name")
            
    api_call_history.append(call_info)
    logger.info(f"API Call Logged: {endpoint} - Success: {error is None}")

@mcp.tool
async def analyze_realm_debug(realm_slug: str = "stormrage", region: str = "us") -> str:
    """
    Analyze realm with full API debugging information.
    
    Args:
        realm_slug: Realm to analyze
        region: Region code
    
    Returns:
        Analysis with complete API call details
    """
    try:
        # Check cache
        cache_key = f"realm_{region}_{realm_slug}"
        if cache_key in cache and cache_key in cache_ttl:
            if datetime.now() - cache_ttl[cache_key] < timedelta(minutes=15):
                cached_data = cache[cache_key]
                return f"""{cached_data}

**Data Source:** CACHED (Age: {int((datetime.now() - cache_ttl[cache_key]).total_seconds() / 60)} minutes)
**Last Cache Update:** {cache_ttl[cache_key].strftime('%Y-%m-%d %H:%M:%S')}"""

        if not API_AVAILABLE:
            return "Error: Blizzard API client not available"
        
        # Make API calls with full logging
        async with BlizzardAPIClient() as client:
            # Call 1: Get realm info
            realm_endpoint = f"/data/wow/realm/{realm_slug}"
            realm_params = {"namespace": f"dynamic-{region}", "locale": "en_US"}
            
            logger.info(f"Making API Call: {realm_endpoint}")
            realm_start = datetime.now()
            
            realm_data = await client.make_request(realm_endpoint, realm_params)
            
            realm_time = (datetime.now() - realm_start).total_seconds()
            log_api_call(realm_endpoint, realm_params, realm_data)
            
            realm_name = realm_data.get("name", realm_slug.title())
            connected_realm_href = realm_data.get("connected_realm", {}).get("href", "")
            connected_realm_id = connected_realm_href.split("/")[-1].split("?")[0]
            
            # Call 2: Get auction data
            auction_endpoint = f"/data/wow/connected-realm/{connected_realm_id}/auctions"
            auction_params = {"namespace": f"dynamic-{region}", "locale": "en_US"}
            
            logger.info(f"Making API Call: {auction_endpoint}")
            auction_start = datetime.now()
            
            auction_data = await client.make_request(auction_endpoint, auction_params)
            
            auction_time = (datetime.now() - auction_start).total_seconds()
            log_api_call(auction_endpoint, auction_params, auction_data)
            
            auctions = auction_data.get("auctions", [])
            total_auctions = len(auctions)
            
            # Sample auction data
            sample_auctions = auctions[:5] if auctions else []
            
            result = f"""Realm Analysis - {realm_name} ({region.upper()})

**API CALL DETAILS:**

📞 **Call 1: Realm Info**
• Endpoint: GET {realm_endpoint}
• Params: {json.dumps(realm_params, indent=2)}
• Response Time: {realm_time:.2f}s
• Response: Realm Name: {realm_name}, Connected Realm ID: {connected_realm_id}

📞 **Call 2: Auction Data**
• Endpoint: GET {auction_endpoint}
• Params: {json.dumps(auction_params, indent=2)}
• Response Time: {auction_time:.2f}s
• Response Size: {total_auctions:,} auctions
• Data Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}

**SAMPLE AUCTION DATA (First 5):**"""

            for i, auction in enumerate(sample_auctions, 1):
                item_id = auction.get('item', {}).get('id', 'Unknown')
                buyout = auction.get('buyout', 0)
                quantity = auction.get('quantity', 0)
                result += f"\n{i}. Item #{item_id}: {buyout // 10000}g (qty: {quantity})"

            result += f"""

**MARKET SUMMARY:**
• Total Auctions: {total_auctions:,}
• Market Activity: {'Extremely High' if total_auctions > 100000 else 'Very High' if total_auctions > 50000 else 'High'}
• Data Source: LIVE BLIZZARD API
• Total API Calls Made: 2"""

            # Cache the result
            cache[cache_key] = result
            cache_ttl[cache_key] = datetime.now()
            
            return result
            
    except Exception as e:
        log_api_call("error", {}, None, str(e))
        logger.error(f"API Error: {str(e)}")
        return f"""API Error: {str(e)}

**Debug Info:**
• Endpoint Attempted: {locals().get('auction_endpoint', 'Unknown')}
• Error Type: {type(e).__name__}
• Check /api_call_history for details"""

@mcp.tool
async def get_token_debug(region: str = "us") -> str:
    """
    Get token price with full API debug info.
    
    Args:
        region: Region code
    
    Returns:
        Token price with API call details
    """
    try:
        if not API_AVAILABLE:
            return "Error: Blizzard API client not available"
        
        async with BlizzardAPIClient() as client:
            endpoint = "/data/wow/token/index"
            params = {"namespace": f"dynamic-{region}", "locale": "en_US"}
            
            logger.info(f"Making API Call: {endpoint}")
            start_time = datetime.now()
            
            token_data = await client.make_request(endpoint, params)
            
            response_time = (datetime.now() - start_time).total_seconds()
            log_api_call(endpoint, params, token_data)
            
            price = token_data.get("price", 0)
            last_updated = token_data.get("last_updated_timestamp", 0)
            
            # Convert timestamp
            update_time = datetime.fromtimestamp(last_updated / 1000)
            
            return f"""WoW Token Price ({region.upper()})

**API CALL DETAILS:**

📞 **Token Price Request**
• Endpoint: GET {endpoint}
• Params: {json.dumps(params, indent=2)}
• Response Time: {response_time:.2f}s
• Call Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}

**RESPONSE DATA:**
• Price: {price:,} copper ({price // 10000:,}g {(price % 10000) // 100}s)
• Last Updated: {update_time.strftime('%Y-%m-%d %H:%M:%S')}
• Raw Response: {json.dumps(token_data, indent=2)}

**Data Source:** LIVE BLIZZARD API"""
            
    except Exception as e:
        log_api_call("error", {}, None, str(e))
        return f"API Error: {str(e)}"

@mcp.tool
def get_api_call_history() -> str:
    """
    Show detailed history of recent API calls.
    
    Returns:
        Complete log of recent API calls with request/response details
    """
    if not api_call_history:
        return "No API calls have been made yet."
    
    result = f"""API Call History (Last {len(api_call_history)} calls)
{'=' * 60}"""
    
    for i, call in enumerate(reversed(list(api_call_history)), 1):
        result += f"""

**Call #{i}**
• Timestamp: {call['timestamp']}
• Endpoint: {call['endpoint']}
• Parameters: {json.dumps(call['params'], indent=2) if call['params'] else 'None'}
• Success: {'✅ Yes' if call['success'] else '❌ No'}
• Response Size: {call['response_size']} bytes"""
        
        if call.get('error'):
            result += f"\n• Error: {call['error']}"
        
        if call.get('auction_count'):
            result += f"\n• Auctions Retrieved: {call['auction_count']:,}"
            
        if call.get('sample_auctions'):
            result += f"\n• Sample Data: {len(call['sample_auctions'])} auctions shown"
            
        if call.get('token_price'):
            result += f"\n• Token Price: {call['token_price'] // 10000:,}g"
            
        if call.get('realm_name'):
            result += f"\n• Realm Name: {call['realm_name']}"
    
    result += f"""

**Summary:**
• Total Calls in History: {len(api_call_history)}
• Successful Calls: {sum(1 for c in api_call_history if c['success'])}
• Failed Calls: {sum(1 for c in api_call_history if not c['success'])}
• Most Recent: {api_call_history[-1]['timestamp'] if api_call_history else 'N/A'}"""
    
    return result

@mcp.tool
async def test_live_connection() -> str:
    """
    Test live API connection with raw request/response logging.
    
    Returns:
        Raw API test results
    """
    try:
        if not API_AVAILABLE:
            return "Error: Blizzard API client not available"
        
        results = []
        
        async with BlizzardAPIClient() as client:
            # Test 1: Simple token call
            endpoint = "/data/wow/token/index"
            params = {"namespace": "dynamic-us", "locale": "en_US"}
            
            start = datetime.now()
            logger.info(f"TEST: Calling {endpoint}")
            
            try:
                response = await client.make_request(endpoint, params)
                elapsed = (datetime.now() - start).total_seconds()
                
                results.append(f"""✅ TOKEN API TEST
• Request: GET {endpoint}
• Params: {json.dumps(params)}
• Response Time: {elapsed:.3f}s
• Response: {json.dumps(response, indent=2)[:500]}...
• Full Response Size: {len(json.dumps(response))} bytes""")
                
                log_api_call(endpoint, params, response)
                
            except Exception as e:
                results.append(f"❌ TOKEN API TEST FAILED: {str(e)}")
                log_api_call(endpoint, params, None, str(e))
        
        return f"""Live API Connection Test
{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}
{'=' * 60}

{chr(10).join(results)}

**Credentials Status:**
• Client ID: {os.getenv('BLIZZARD_CLIENT_ID', 'NOT SET')[:20]}...
• Client Secret: {'SET' if os.getenv('BLIZZARD_CLIENT_SECRET') else 'NOT SET'}

Use /api_call_history to see detailed logs."""
        
    except Exception as e:
        return f"Connection test failed: {str(e)}"

@mcp.tool
def clear_cache() -> str:
    """
    Clear all cached data to force fresh API calls.
    
    Returns:
        Cache clear confirmation
    """
    cache.clear()
    cache_ttl.clear()
    return f"""Cache cleared successfully!

• All cached data removed
• Next calls will hit live API
• Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Ready for fresh API calls."""

def main():
    """Main entry point"""
    try:
        port = int(os.getenv("PORT", "8000"))
        
        logger.info("🚀 WoW Analysis MCP Server (Debug Mode)")
        logger.info("🔧 Features: Full API request/response logging")
        logger.info("📊 Tools: Debug analysis with detailed API info")
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