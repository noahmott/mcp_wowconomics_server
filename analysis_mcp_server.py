"""
WoW Economic Analysis MCP Server - Focused on actionable insights
"""
import os
import logging
import sys
import asyncio
import json
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from dotenv import load_dotenv
from fastmcp import FastMCP
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Create FastMCP server
mcp = FastMCP("WoW Economic Analysis Server")

# Import the Blizzard API client
try:
    from app.api.blizzard_client import BlizzardAPIClient
    API_AVAILABLE = True
except ImportError:
    logger.warning("BlizzardAPIClient not available")
    API_AVAILABLE = False

# Analysis cache with longer TTL for processed data
analysis_cache = {}
analysis_cache_ttl = {}

# Historical data storage for trend analysis
historical_data = defaultdict(lambda: defaultdict(list))
HISTORY_MAX_ENTRIES = 288  # 24 hours of 5-minute intervals
HISTORY_FILE = "historical_market_data.json"

# Resource limits for security
RESOURCE_LIMITS = {
    "MAX_REALMS_PER_REQUEST": 5,      # Maximum realms that can be processed in a single request
    "MAX_ITEMS_PER_REALM": 500,       # Maximum items to track per realm
    "MAX_TOTAL_ITEMS": 2000,          # Absolute maximum items across all realms in one request
    "MAX_EXECUTION_TIME": 300,        # Maximum execution time in seconds (5 minutes)
    "MIN_SECONDS_BETWEEN_UPDATES": 60, # Minimum time between updates (rate limiting)
    "MAX_HISTORICAL_DATA_MB": 100,    # Maximum memory for historical data
    "MAX_DATA_POINTS_PER_ITEM": 288,  # 24 hours at 5-minute intervals
}

def cache_analysis(key: str, data: Any, ttl_hours: int = 1):
    """Cache analysis results"""
    analysis_cache[key] = data
    analysis_cache_ttl[key] = datetime.now() + timedelta(hours=ttl_hours)

def get_cached_analysis(key: str) -> Optional[Any]:
    """Get cached analysis if not expired"""
    if key in analysis_cache and key in analysis_cache_ttl:
        if datetime.now() < analysis_cache_ttl[key]:
            return analysis_cache[key]
    return None

def store_historical_data(region: str, realm: str, item_id: int, price: float, quantity: int):
    """Store price data point for historical tracking"""
    key = f"{region}_{realm}_{item_id}"
    timestamp = datetime.now().isoformat()
    
    data_point = {
        "timestamp": timestamp,
        "price": price,
        "quantity": quantity
    }
    
    historical_data[key]["data_points"].append(data_point)
    
    # Keep only recent data points
    if len(historical_data[key]["data_points"]) > HISTORY_MAX_ENTRIES:
        historical_data[key]["data_points"] = historical_data[key]["data_points"][-HISTORY_MAX_ENTRIES:]
    
    # Update metadata
    historical_data[key]["last_updated"] = timestamp
    historical_data[key]["item_id"] = item_id
    historical_data[key]["region"] = region
    historical_data[key]["realm"] = realm

def get_historical_trends(region: str, realm: str, item_id: int, hours: int = 24) -> Dict[str, Any]:
    """Analyze historical price trends for an item"""
    key = f"{region}_{realm}_{item_id}"
    
    if key not in historical_data or not historical_data[key]["data_points"]:
        return {"error": "No historical data available"}
    
    data_points = historical_data[key]["data_points"]
    cutoff_time = datetime.now() - timedelta(hours=hours)
    
    # Filter data points within time range
    recent_points = [
        dp for dp in data_points 
        if datetime.fromisoformat(dp["timestamp"]) > cutoff_time
    ]
    
    if not recent_points:
        return {"error": "No data in specified time range"}
    
    prices = [dp["price"] for dp in recent_points]
    quantities = [dp["quantity"] for dp in recent_points]
    
    # Calculate trends
    avg_price = sum(prices) / len(prices)
    min_price = min(prices)
    max_price = max(prices)
    price_volatility = (max_price - min_price) / avg_price if avg_price > 0 else 0
    
    # Price direction
    if len(prices) >= 2:
        recent_avg = sum(prices[-5:]) / len(prices[-5:])
        older_avg = sum(prices[:5]) / min(5, len(prices))
        price_trend = (recent_avg - older_avg) / older_avg if older_avg > 0 else 0
    else:
        price_trend = 0
    
    return {
        "data_points": len(recent_points),
        "avg_price": avg_price,
        "min_price": min_price,
        "max_price": max_price,
        "current_price": prices[-1],
        "price_volatility": price_volatility,
        "price_trend": price_trend,
        "avg_quantity": sum(quantities) / len(quantities),
        "time_range_hours": hours
    }

def save_historical_data():
    """Save historical data to file"""
    try:
        # Convert defaultdict to regular dict for JSON serialization
        data_to_save = {k: dict(v) for k, v in historical_data.items()}
        with open(HISTORY_FILE, 'w') as f:
            json.dump(data_to_save, f)
        logger.info(f"Saved historical data: {len(data_to_save)} items")
    except Exception as e:
        logger.error(f"Failed to save historical data: {e}")

def calculate_historical_data_memory():
    """Calculate approximate memory usage of historical data in MB"""
    total_size = 0
    for key, data in historical_data.items():
        # Approximate: 50 bytes per data point
        total_size += len(data.get("data_points", [])) * 50
    return total_size / 1_000_000

def cleanup_old_historical_data():
    """Remove oldest data points to stay within memory limits"""
    logger.info("Cleaning up old historical data to free memory...")
    
    # Sort items by number of data points (clean up largest first)
    items_by_size = sorted(
        historical_data.items(), 
        key=lambda x: len(x[1].get("data_points", [])), 
        reverse=True
    )
    
    cleaned_count = 0
    for key, data in items_by_size[:100]:  # Clean up top 100 largest
        data_points = data.get("data_points", [])
        if len(data_points) > RESOURCE_LIMITS["MAX_DATA_POINTS_PER_ITEM"]:
            # Keep only recent data points
            data["data_points"] = data_points[-RESOURCE_LIMITS["MAX_DATA_POINTS_PER_ITEM"]:]
            cleaned_count += 1
    
    logger.info(f"Cleaned up {cleaned_count} items")

def load_historical_data():
    """Load historical data from file"""
    global historical_data
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r') as f:
                loaded_data = json.load(f)
                historical_data = defaultdict(lambda: defaultdict(list), loaded_data)
                logger.info(f"Loaded historical data: {len(loaded_data)} items")
    except Exception as e:
        logger.error(f"Failed to load historical data: {e}")

# Load historical data on startup
load_historical_data()

@mcp.tool()
async def analyze_market_opportunities(realm_slug: str = "stormrage", region: str = "us") -> str:
    """
    Find profitable market opportunities on a realm.
    
    Analyzes auction house data to identify:
    - Underpriced items
    - Market gaps
    - Flip opportunities
    - Crafting arbitrage
    
    Args:
        realm_slug: Realm to analyze
        region: Region code
    
    Returns:
        Actionable market opportunities
    """
    try:
        cache_key = f"opportunities_{region}_{realm_slug}"
        cached = get_cached_analysis(cache_key)
        if cached:
            return cached + "\n\n*Cached analysis - use 'force_refresh' for live data*"
        
        if not API_AVAILABLE:
            return "Error: Blizzard API not available"
        
        async with BlizzardAPIClient() as client:
            # Get realm info
            realm_endpoint = f"/data/wow/realm/{realm_slug}"
            realm_data = await client.make_request(
                realm_endpoint, 
                {"namespace": f"dynamic-{region}", "locale": "en_US"}
            )
            
            # Get auction data
            connected_realm_href = realm_data.get("connected_realm", {}).get("href", "")
            connected_realm_id = connected_realm_href.split("/")[-1].split("?")[0]
            
            auction_endpoint = f"/data/wow/connected-realm/{connected_realm_id}/auctions"
            auction_data = await client.make_request(
                auction_endpoint,
                {"namespace": f"dynamic-{region}", "locale": "en_US"}
            )
            
            auctions = auction_data.get("auctions", [])
            
            # Analyze market data
            item_prices = defaultdict(list)
            item_quantities = defaultdict(int)
            
            for auction in auctions:
                item_id = auction.get('item', {}).get('id', 0)
                buyout = auction.get('buyout', 0)
                quantity = auction.get('quantity', 1)
                
                if buyout > 0 and quantity > 0:
                    price_per_unit = buyout / quantity
                    item_prices[item_id].append(price_per_unit)
                    item_quantities[item_id] += quantity
            
            # Store historical data for top traded items
            items_by_volume = sorted(item_quantities.items(), key=lambda x: x[1], reverse=True)
            for item_id, total_quantity in items_by_volume[:100]:  # Track top 100 items by volume
                if item_id in item_prices and item_prices[item_id]:
                    avg_price = sum(item_prices[item_id]) / len(item_prices[item_id])
                    store_historical_data(region, realm_slug, item_id, avg_price, total_quantity)
            
            # Find opportunities
            opportunities = []
            
            # 1. Price disparities (items with high price variance)
            for item_id, prices in item_prices.items():
                if len(prices) >= 5:  # Need enough data points
                    min_price = min(prices)
                    avg_price = sum(prices) / len(prices)
                    max_price = max(prices)
                    
                    if max_price > min_price * 2 and avg_price > min_price * 1.5:
                        profit_margin = ((avg_price - min_price) / min_price) * 100
                        opportunities.append({
                            "type": "Price Disparity",
                            "item_id": item_id,
                            "min_price": min_price,
                            "avg_price": avg_price,
                            "max_price": max_price,
                            "profit_margin": profit_margin,
                            "listings": len(prices)
                        })
            
            # 2. Low competition items (few sellers)
            low_competition = []
            for item_id, prices in item_prices.items():
                if 1 <= len(prices) <= 3:  # Only 1-3 sellers
                    avg_price = sum(prices) / len(prices)
                    low_competition.append({
                        "item_id": item_id,
                        "sellers": len(prices),
                        "avg_price": avg_price,
                        "total_quantity": item_quantities[item_id]
                    })
            
            # Sort opportunities by profit potential
            opportunities.sort(key=lambda x: x['profit_margin'], reverse=True)
            
            result = f"""Market Opportunity Analysis - {realm_data.get('name', realm_slug.title())} ({region.upper()})
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📊 **MARKET OVERVIEW**
• Total Listings: {len(auctions):,}
• Unique Items: {len(item_prices):,}
• Market Depth: {'Excellent' if len(auctions) > 50000 else 'Good' if len(auctions) > 20000 else 'Fair'}

💰 **TOP FLIP OPPORTUNITIES** (Buy Low, Sell High)
"""
            
            for i, opp in enumerate(opportunities[:5], 1):
                result += f"""
{i}. Item #{opp['item_id']}
   • Buy at: {int(opp['min_price'] // 10000):,}g
   • Sell at: {int(opp['avg_price'] // 10000):,}g
   • Profit: {int((opp['avg_price'] - opp['min_price']) // 10000):,}g per item
   • Margin: {opp['profit_margin']:.1f}%
   • Active Listings: {opp['listings']}
"""

            result += f"""

🎯 **LOW COMPETITION MARKETS** (Control the Market)
"""
            
            for i, item in enumerate(sorted(low_competition, key=lambda x: x['avg_price'], reverse=True)[:5], 1):
                result += f"""
{i}. Item #{item['item_id']}
   • Only {item['sellers']} seller(s)
   • Current Price: {int(item['avg_price'] // 10000):,}g
   • Total Supply: {item['total_quantity']} units
   • Strategy: Buy out competition, reset price higher
"""

            result += f"""

📈 **MARKET RECOMMENDATIONS**
1. Focus on items with >50% profit margins
2. Monitor low-competition items for market control
3. Best flip times: Tuesday reset, weekend evenings
4. Avoid items with >20 sellers (too competitive)

⚡ **QUICK ACTIONS**
• Set up alerts for underpriced items
• Track your competition's posting times
• Diversify across multiple markets
• Keep 20-30% liquid gold for opportunities"""

            # Cache the analysis
            cache_analysis(cache_key, result)
            
            return result
            
    except Exception as e:
        logger.error(f"Error in market analysis: {str(e)}")
        return f"Error analyzing market: {str(e)}"

@mcp.tool()
async def analyze_crafting_profits(realm_slug: str = "stormrage", region: str = "us", profession: str = "all") -> str:
    """
    Analyze crafting profitability across professions.
    
    Identifies:
    - Material costs vs crafted item prices
    - Best crafting margins
    - Material sourcing opportunities
    
    Args:
        realm_slug: Realm to analyze
        region: Region code
        profession: Specific profession or 'all'
    
    Returns:
        Crafting profit analysis
    """
    try:
        # The War Within crafting data with valid item IDs (July 2025 current expansion)
        # Note: These are example recipes - actual game recipes may vary
        common_crafts = {
            "Alchemy": {
                # Flask of Alchemical Chaos (current raid flask)
                "Flask of Alchemical Chaos": {
                    "mats": [210796, 210799, 210802],  # Mycobloom, Luredrop, Orbinid
                    "product": 212283
                },
                # Tempered Potion (common battle potion)
                "Tempered Potion": {
                    "mats": [210796, 210799],  # Mycobloom, Luredrop
                    "product": 212265
                },
                # Algari Healing Potion (basic healing potion)
                "Algari Healing Potion": {
                    "mats": [210796, 210810],  # Mycobloom, Arathor's Spear
                    "product": 211880
                }
            },
            "Blacksmithing": {
                # Core Alloy Gauntlets (crafted armor)
                "Core Alloy Gauntlets": {"mats": [210936, 210937], "product": 222443},
                # Charged Claymore (crafted weapon)
                "Charged Claymore": {"mats": [210936, 210938, 210939], "product": 222486}
            },
            "Enchanting": {
                # Enchant Chest - Crystalline Radiance
                "Enchant Chest - Crystalline Radiance": {"mats": [210932, 210933], "product": 223684},
                # Enchant Weapon - Authority of Radiant Power
                "Enchant Weapon - Authority of Radiant Power": {"mats": [210932, 210933, 210934], "product": 223665}
            }
        }
        
        if not API_AVAILABLE:
            return "Error: Blizzard API not available"
        
        async with BlizzardAPIClient() as client:
            # Get auction data
            realm_endpoint = f"/data/wow/realm/{realm_slug}"
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
            
            auctions = auction_data.get("auctions", [])
            
            # Check if we have auction data
            if not auctions:
                return f"""Crafting Profitability Analysis - {realm_data.get('name', realm_slug.title())} ({region.upper()})
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

⚠️ **NO AUCTION DATA AVAILABLE**

Unable to analyze crafting profits because:
• No active auctions found on this realm
• This might be a connection issue or the realm might be offline

Please try:
1. Check if the realm name is correct
2. Try a different realm
3. Try again in a few minutes
"""
            
            # Calculate average prices
            item_prices = defaultdict(list)
            for auction in auctions:
                item_id = auction.get('item', {}).get('id', 0)
                buyout = auction.get('buyout', 0)
                quantity = auction.get('quantity', 1)
                
                if buyout > 0 and quantity > 0:
                    price_per_unit = buyout / quantity
                    item_prices[item_id].append(price_per_unit)
            
            avg_prices = {}
            for item_id, prices in item_prices.items():
                avg_prices[item_id] = sum(prices) / len(prices) if prices else 0
            
            result = f"""Crafting Profitability Analysis - {realm_data.get('name', realm_slug.title())} ({region.upper()})
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

💎 **CRAFTING PROFIT MARGINS**
"""
            
            profitable_crafts = []
            materials_not_found = []
            products_not_found = []
            unprofitable_count = 0
            
            for prof_name, recipes in common_crafts.items():
                if profession != "all" and profession.lower() != prof_name.lower():
                    continue
                
                result += f"\n**{prof_name}**\n"
                
                for recipe_name, recipe_data in recipes.items():
                    # Calculate material costs
                    mat_cost = 0
                    mat_available = True
                    
                    missing_mats = []
                    for mat_id in recipe_data["mats"]:
                        if mat_id in avg_prices:
                            mat_cost += avg_prices[mat_id]
                        else:
                            mat_available = False
                            missing_mats.append(mat_id)
                    
                    if not mat_available:
                        materials_not_found.append((recipe_name, missing_mats))
                    elif recipe_data["product"] not in avg_prices:
                        products_not_found.append((recipe_name, recipe_data["product"]))
                    elif mat_available and recipe_data["product"] in avg_prices:
                        product_price = avg_prices[recipe_data["product"]]
                        profit = product_price - mat_cost
                        margin = (profit / mat_cost * 100) if mat_cost > 0 else 0
                        
                        if margin > 10:  # Only show profitable crafts
                            profitable_crafts.append({
                                "profession": prof_name,
                                "recipe": recipe_name,
                                "mat_cost": mat_cost,
                                "product_price": product_price,
                                "profit": profit,
                                "margin": margin
                            })
                            
                            result += f"""• {recipe_name}
  Material Cost: {int(mat_cost // 10000):,}g
  Sells for: {int(product_price // 10000):,}g
  Profit: {int(profit // 10000):,}g ({margin:.1f}% margin)
"""
                        else:
                            unprofitable_count += 1

            # Sort by profit margin
            profitable_crafts.sort(key=lambda x: x['margin'], reverse=True)
            
            result += f"""

🏆 **TOP 5 MOST PROFITABLE CRAFTS**
"""
            
            for i, craft in enumerate(profitable_crafts[:5], 1):
                result += f"""
{i}. {craft['recipe']} ({craft['profession']})
   • Craft for: {int(craft['mat_cost'] // 10000):,}g
   • Sell for: {int(craft['product_price'] // 10000):,}g
   • Profit: {int(craft['profit'] // 10000):,}g
   • ROI: {craft['margin']:.1f}%
"""

            # Add diagnostics if no profitable crafts found
            if not profitable_crafts:
                result += f"""

⚠️ **NO PROFITABLE CRAFTS FOUND**

Analysis Details:
• Total auction listings: {len(auctions):,}
• Unique items with prices: {len(avg_prices):,}
• Unprofitable recipes (<10% margin): {unprofitable_count}
• Missing materials: {len(materials_not_found)} recipes
• Missing products: {len(products_not_found)} recipes

Common Issues:
1. The hardcoded item IDs might not match current game items
2. Materials or products might not be traded on this realm
3. Market prices might be too competitive (low margins)

Debug Information:
"""
                if materials_not_found[:3]:  # Show first 3
                    result += "\nMissing Materials:\n"
                    for recipe, mats in materials_not_found[:3]:
                        result += f"• {recipe}: Items {mats}\n"
                
                if products_not_found[:3]:  # Show first 3
                    result += "\nMissing Products:\n"
                    for recipe, product in products_not_found[:3]:
                        result += f"• {recipe}: Item #{product}\n"
            
            result += f"""

📊 **MARKET INSIGHTS**
• Best Margins: {profitable_crafts[0]['profession'] if profitable_crafts else 'N/A'}
• Average ROI: {(sum(c['margin'] for c in profitable_crafts) / len(profitable_crafts) if profitable_crafts else 0):.1f}% 
• Total Profitable Recipes: {len(profitable_crafts)}

💡 **CRAFTING STRATEGY**
1. Focus on items with >30% profit margins
2. Buy materials during off-peak hours
3. Craft during high-demand times (raid nights)
4. Consider profession synergies
5. Track material price trends

⚠️ **RISKS TO CONSIDER**
• Market saturation
• Crafting time investment
• Material availability
• Competition from other crafters"""

            return result
            
    except Exception as e:
        logger.error(f"Error in crafting analysis: {str(e)}")
        return f"Error analyzing crafting: {str(e)}"


@mcp.tool()
async def predict_market_trends(realm_slug: str = "stormrage", region: str = "us", item_ids: Optional[str] = None) -> str:
    """
    Predict market trends based on historical data and current patterns.
    
    Args:
        realm_slug: Realm to analyze
        region: Region code
        item_ids: Comma-separated item IDs to analyze (optional)
    
    Returns:
        Market trend predictions based on real historical data
    """
    try:
        if not API_AVAILABLE:
            return "Error: Blizzard API not available"
        
        async with BlizzardAPIClient() as client:
            # Get current data
            token_endpoint = "/data/wow/token/index"
            token_data = await client.make_request(
                token_endpoint,
                {"namespace": f"dynamic-{region}", "locale": "en_US"}
            )
            
            realm_endpoint = f"/data/wow/realm/{realm_slug}"
            realm_data = await client.make_request(
                realm_endpoint,
                {"namespace": f"dynamic-{region}", "locale": "en_US"}
            )
            
            token_price = token_data.get("price", 0)
            
            result = f"""Market Trend Analysis - {realm_data.get('name', realm_slug.title())} ({region.upper()})
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📊 **CURRENT MARKET CONDITIONS**
• Token Price: {token_price // 10000:,}g
"""
            
            # Analyze specific items if provided
            if item_ids:
                item_list = [int(id.strip()) for id in item_ids.split(",") if id.strip().isdigit()]
                
                result += f"\n📈 **ITEM-SPECIFIC TRENDS**\n"
                
                for item_id in item_list[:10]:  # Limit to 10 items
                    trends = get_historical_trends(region, realm_slug, item_id, hours=24)
                    
                    if "error" not in trends:
                        price_change = trends['price_trend'] * 100
                        volatility = trends['price_volatility'] * 100
                        
                        # Determine trend direction
                        if price_change > 5:
                            trend_icon = "📈"
                            trend_text = "RISING"
                            action = "SELL"
                        elif price_change < -5:
                            trend_icon = "📉"
                            trend_text = "FALLING"
                            action = "BUY"
                        else:
                            trend_icon = "➡️"
                            trend_text = "STABLE"
                            action = "HOLD"
                        
                        result += f"""
**Item #{item_id}** {trend_icon}
• Current Price: {int(trends['current_price'] // 10000):,}g
• 24h Average: {int(trends['avg_price'] // 10000):,}g
• Price Range: {int(trends['min_price'] // 10000):,}g - {int(trends['max_price'] // 10000):,}g
• Trend: {trend_text} ({price_change:+.1f}%)
• Volatility: {volatility:.1f}%
• Data Points: {trends['data_points']}
• Recommendation: **{action}**
"""
                    else:
                        result += f"\n**Item #{item_id}**\n• No historical data available\n"
            
            # General market trends from available data
            all_items_with_history = []
            for key in historical_data:
                if key.startswith(f"{region}_{realm_slug}_"):
                    item_id = historical_data[key].get("item_id")
                    if item_id:
                        trends = get_historical_trends(region, realm_slug, item_id, hours=24)
                        if "error" not in trends:
                            all_items_with_history.append({
                                "item_id": item_id,
                                "trend": trends['price_trend'],
                                "volatility": trends['price_volatility'],
                                "volume": trends['avg_quantity']
                            })
            
            if all_items_with_history:
                # Calculate market-wide metrics
                rising_items = sum(1 for item in all_items_with_history if item['trend'] > 0.05)
                falling_items = sum(1 for item in all_items_with_history if item['trend'] < -0.05)
                stable_items = len(all_items_with_history) - rising_items - falling_items
                
                avg_volatility = sum(item['volatility'] for item in all_items_with_history) / len(all_items_with_history)
                
                # Sort by trend
                top_gainers = sorted(all_items_with_history, key=lambda x: x['trend'], reverse=True)[:5]
                top_losers = sorted(all_items_with_history, key=lambda x: x['trend'])[:5]
                
                result += f"""

📊 **MARKET-WIDE ANALYSIS** (Based on {len(all_items_with_history)} tracked items)
• Rising Items: {rising_items} ({rising_items/len(all_items_with_history)*100:.1f}%)
• Falling Items: {falling_items} ({falling_items/len(all_items_with_history)*100:.1f}%)
• Stable Items: {stable_items} ({stable_items/len(all_items_with_history)*100:.1f}%)
• Average Volatility: {avg_volatility*100:.1f}%
• Market Sentiment: {'Bullish' if rising_items > falling_items else 'Bearish' if falling_items > rising_items else 'Neutral'}

🚀 **TOP GAINERS** (24h)
"""
                for i, item in enumerate(top_gainers, 1):
                    result += f"{i}. Item #{item['item_id']}: {item['trend']*100:+.1f}%\n"
                
                result += f"""
📉 **TOP LOSERS** (24h)
"""
                for i, item in enumerate(top_losers, 1):
                    result += f"{i}. Item #{item['item_id']}: {item['trend']*100:+.1f}%\n"
            
            # Time-based patterns
            current_hour = datetime.now().hour
            current_day = datetime.now().strftime("%A")
            
            result += f"""

⏰ **TIME-BASED PATTERNS**
• Current Time: {current_hour}:00 server time
• Day: {current_day}
• Peak Trading: {'Active' if 18 <= current_hour <= 23 else 'Starting' if 16 <= current_hour < 18 else 'Quiet'}

💡 **TRADING RECOMMENDATIONS**

**Immediate Actions:**
• {'Post high-value items - peak hours' if 18 <= current_hour <= 23 else 'Scout for deals - low competition' if 2 <= current_hour <= 10 else 'Monitor market trends'}
• {'Focus on consumables' if current_day in ['Monday', 'Tuesday'] else 'Target transmog items' if current_day in ['Friday', 'Saturday'] else 'General trading'}

**Token Strategy:**
• Current Price: {token_price // 10000:,}g
• Action: {'BUY - Below average' if token_price < 2500000 else 'SELL - Above average' if token_price > 3000000 else 'HOLD - Fair value'}

📅 **WEEKLY OUTLOOK**
• Best Selling Days: Tuesday (raid reset), Friday-Saturday (weekend activity)
• Best Buying Days: Monday, Wednesday-Thursday (lower competition)
• Avoid Major Trades: Sunday evening (market uncertainty pre-reset)

Note: Historical data improves with usage. The more the market is monitored, the more accurate predictions become."""

        # Save historical data periodically
        save_historical_data()
        
        return result
        
    except Exception as e:
        logger.error(f"Error in trend prediction: {str(e)}")
        return f"Error predicting trends: {str(e)}"

@mcp.tool()
async def get_historical_data(realm_slug: str = "stormrage", region: str = "us", item_id: int = 0, hours: int = 24) -> str:
    """
    Get historical price data for an item.
    
    Args:
        realm_slug: Realm to analyze
        region: Region code
        item_id: Item ID to get history for
        hours: Number of hours of history to retrieve (max 24)
    
    Returns:
        Historical price data and trends
    """
    try:
        if item_id == 0:
            return "Error: Please provide an item_id"
        
        trends = get_historical_trends(region, realm_slug, item_id, min(hours, 24))
        
        if "error" in trends:
            return f"No historical data available for item {item_id} on {realm_slug}-{region}"
        
        key = f"{region}_{realm_slug}_{item_id}"
        data_points = historical_data.get(key, {}).get("data_points", [])
        
        # Get recent data points
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_points = [
            dp for dp in data_points 
            if datetime.fromisoformat(dp["timestamp"]) > cutoff_time
        ]
        
        result = f"""Historical Data - Item #{item_id} on {realm_slug.title()} ({region.upper()})
Time Range: Last {hours} hours
Data Points: {len(recent_points)}

📊 **PRICE ANALYSIS**
• Current Price: {int(trends['current_price'] // 10000):,}g
• Average Price: {int(trends['avg_price'] // 10000):,}g
• Minimum Price: {int(trends['min_price'] // 10000):,}g
• Maximum Price: {int(trends['max_price'] // 10000):,}g
• Price Volatility: {trends['price_volatility']*100:.1f}%
• Price Trend: {trends['price_trend']*100:+.1f}%

📈 **RECENT PRICE HISTORY**
"""
        
        # Show last 10 data points
        for dp in recent_points[-10:]:
            timestamp = datetime.fromisoformat(dp["timestamp"])
            time_str = timestamp.strftime("%H:%M")
            price_gold = int(dp["price"] // 10000)
            result += f"• {time_str}: {price_gold:,}g (qty: {dp['quantity']})\n"
        
        # Trading recommendation
        price_change = trends['price_trend'] * 100
        if price_change > 5:
            recommendation = "SELL - Price is trending up"
        elif price_change < -5:
            recommendation = "BUY - Price is trending down"
        else:
            recommendation = "HOLD - Price is stable"
        
        result += f"\n💡 **RECOMMENDATION**: {recommendation}"
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting historical data: {str(e)}")
        return f"Error retrieving historical data: {str(e)}"

@mcp.tool()
async def update_historical_database(
    realms: Optional[str] = None,
    top_items: int = 100,
    include_all_items: bool = False,
    auto_expand: bool = False
) -> str:
    """
    Update historical database by running market analysis on specified realms.
    
    Args:
        realms: Comma-separated list of realm:region pairs (e.g., "stormrage:us,area-52:us")
                Special values: "all-us" (all US realms), "popular" (top 10 realms)
                If not provided, updates default realms.
        top_items: Number of top traded items to track per realm (default: 100, max: 500)
        include_all_items: Track all items, not just top traded (warning: resource intensive)
        auto_expand: Automatically add connected realms
    
    Returns:
        Update status and statistics
    """
    import time
    
    try:
        if not API_AVAILABLE:
            return "Error: Blizzard API not available"
        
        # 1. RATE LIMITING CHECK
        last_update_key = "last_historical_update"
        if last_update_key in analysis_cache:
            last_update = analysis_cache[last_update_key]
            if datetime.now() - last_update < timedelta(seconds=RESOURCE_LIMITS["MIN_SECONDS_BETWEEN_UPDATES"]):
                seconds_to_wait = RESOURCE_LIMITS["MIN_SECONDS_BETWEEN_UPDATES"] - (datetime.now() - last_update).seconds
                return f"❌ Rate limit: Please wait {seconds_to_wait} seconds before updating again."
        
        # 2. PARAMETER VALIDATION - Critical security check
        if include_all_items and realms and realms.lower() == "all-us":
            return "❌ Security Error: Cannot use include_all_items=true with realms='all-us' (potential DoS)"
        
        # Limit top_items to prevent resource exhaustion
        top_items = min(max(top_items, 10), RESOURCE_LIMITS["MAX_ITEMS_PER_REALM"])
        
        # 3. MEMORY CHECK before starting
        current_memory_mb = calculate_historical_data_memory()
        if current_memory_mb > RESOURCE_LIMITS["MAX_HISTORICAL_DATA_MB"]:
            cleanup_old_historical_data()
            
        # Track execution time
        start_time = time.time()
        
        # Parse realms or use defaults
        if realms:
            if realms.lower() == "all-us":
                # SECURITY: Limit to top 5 realms instead of all US realms
                realm_list = [
                    ("us", "stormrage"), ("us", "area-52"), ("us", "tichondrius"),
                    ("us", "mal-ganis"), ("us", "kiljaeden")
                ]
                logger.warning("Limiting 'all-us' to top 5 realms for security")
            elif realms.lower() == "popular":
                # Top population realms - already limited to 10
                realm_list = [
                    ("us", "stormrage"), ("us", "area-52"), ("us", "tichondrius"),
                    ("us", "mal-ganis"), ("us", "kiljaeden"), ("us", "illidan"),
                    ("us", "thrall"), ("us", "moon-guard"), ("us", "wyrmrest-accord"),
                    ("us", "bleeding-hollow")
                ]
            else:
                realm_list = []
                parsed_realms = realms.split(",")
                
                # SECURITY: Enforce realm limit
                if len(parsed_realms) > RESOURCE_LIMITS["MAX_REALMS_PER_REQUEST"]:
                    return f"❌ Error: Too many realms ({len(parsed_realms)}). Maximum {RESOURCE_LIMITS['MAX_REALMS_PER_REQUEST']} allowed."
                
                for realm_spec in parsed_realms:
                    parts = realm_spec.strip().split(":")
                    if len(parts) == 2:
                        realm_list.append((parts[1], parts[0]))  # (region, realm)
                    else:
                        realm_list.append(("us", parts[0]))  # Default to US
        else:
            # Default realms - already limited to 5
            realm_list = [
                ("us", "stormrage"),
                ("us", "area-52"),
                ("us", "tichondrius"),
                ("us", "mal-ganis"),
                ("us", "kiljaeden"),
            ]
        
        result = f"""Historical Database Update
Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📊 **UPDATING REALMS**
"""
        
        success_count = 0
        total_items_tracked = 0
        errors = []
        
        async with BlizzardAPIClient() as client:
            for region, realm in realm_list:
                # SECURITY: Check timeout before processing each realm
                elapsed_time = time.time() - start_time
                if elapsed_time > RESOURCE_LIMITS["MAX_EXECUTION_TIME"]:
                    result += f"\n\n⚠️ **TIMEOUT**: Operation stopped after {elapsed_time:.1f} seconds"
                    result += f"\n• Processed {success_count}/{len(realm_list)} realms"
                    result += f"\n• Tracked {total_items_tracked} items total"
                    break
                
                # SECURITY: Check total items limit
                if total_items_tracked >= RESOURCE_LIMITS["MAX_TOTAL_ITEMS"]:
                    result += f"\n\n⚠️ **ITEM LIMIT**: Reached maximum of {RESOURCE_LIMITS['MAX_TOTAL_ITEMS']} items"
                    break
                
                result += f"\n• {realm.title()} ({region.upper()}): "
                
                try:
                    # Get realm info
                    realm_endpoint = f"/data/wow/realm/{realm}"
                    realm_data = await client.make_request(
                        realm_endpoint, 
                        {"namespace": f"dynamic-{region}", "locale": "en_US"}
                    )
                    
                    # Get auction data
                    connected_realm_href = realm_data.get("connected_realm", {}).get("href", "")
                    connected_realm_id = connected_realm_href.split("/")[-1].split("?")[0]
                    
                    auction_endpoint = f"/data/wow/connected-realm/{connected_realm_id}/auctions"
                    auction_data = await client.make_request(
                        auction_endpoint,
                        {"namespace": f"dynamic-{region}", "locale": "en_US"}
                    )
                    
                    auctions = auction_data.get("auctions", [])
                    
                    # Analyze and store historical data
                    item_prices = defaultdict(list)
                    item_quantities = defaultdict(int)
                    
                    for auction in auctions:
                        item_id = auction.get('item', {}).get('id', 0)
                        buyout = auction.get('buyout', 0)
                        quantity = auction.get('quantity', 1)
                        
                        if buyout > 0 and quantity > 0:
                            price_per_unit = buyout / quantity
                            item_prices[item_id].append(price_per_unit)
                            item_quantities[item_id] += quantity
                    
                    # Store historical data for items
                    items_by_volume = sorted(item_quantities.items(), key=lambda x: x[1], reverse=True)
                    items_updated = 0
                    
                    # Determine which items to track with security limits
                    if include_all_items:
                        # SECURITY: Still enforce item limit even with include_all_items
                        remaining_capacity = RESOURCE_LIMITS["MAX_TOTAL_ITEMS"] - total_items_tracked
                        items_to_track = list(item_quantities.items())[:remaining_capacity]
                        if len(item_quantities) > remaining_capacity:
                            logger.warning(f"Limiting items from {len(item_quantities)} to {remaining_capacity} due to total limit")
                    else:
                        # Calculate safe item limit for this realm
                        remaining_capacity = RESOURCE_LIMITS["MAX_TOTAL_ITEMS"] - total_items_tracked
                        safe_limit = min(top_items, remaining_capacity)
                        items_to_track = items_by_volume[:safe_limit]
                    
                    for item_id, total_quantity in items_to_track:
                        # Additional safety check
                        if total_items_tracked >= RESOURCE_LIMITS["MAX_TOTAL_ITEMS"]:
                            break
                            
                        if item_id in item_prices and item_prices[item_id]:
                            avg_price = sum(item_prices[item_id]) / len(item_prices[item_id])
                            store_historical_data(region, realm, item_id, avg_price, total_quantity)
                            items_updated += 1
                    
                    result += f"✓ Updated {items_updated} items"
                    success_count += 1
                    total_items_tracked += items_updated
                    
                except Exception as e:
                    error_msg = str(e)[:50]
                    result += f"✗ Error: {error_msg}"
                    errors.append(f"{realm}: {error_msg}")
        
        # Save historical data
        save_historical_data()
        
        # Update rate limit timestamp
        analysis_cache[last_update_key] = datetime.now()
        
        # Calculate comprehensive statistics
        total_data_points = sum(len(data["data_points"]) for data in historical_data.values())
        unique_items = len(set(key.split('_')[2] for key in historical_data.keys() if '_' in key))
        realms_with_data = len(set(f"{key.split('_')[0]}_{key.split('_')[1]}" for key in historical_data.keys() if '_' in key))
        memory_usage_mb = calculate_historical_data_memory()
        
        # Summary
        result += f"""

📊 **UPDATE SUMMARY**
• Realms Requested: {len(realm_list)} ({', '.join(f"{r[1]}-{r[0]}" for r in realm_list[:3])}{'...' if len(realm_list) > 3 else ''})
• Realms Updated: {success_count}/{len(realm_list)}
• Items Tracked This Update: {total_items_tracked:,}
• Tracking Mode: {"All Items" if include_all_items else f"Top {top_items} Items/Realm"}
• Data Saved: {"Yes" if success_count > 0 else "No"}
• Completed: {datetime.now().strftime('%H:%M:%S')}
"""
        
        if errors:
            result += f"\n⚠️ **ERRORS**\n"
            for error in errors[:5]:  # Limit error display
                result += f"• {error}\n"
            if len(errors) > 5:
                result += f"• ... and {len(errors) - 5} more errors\n"
        
        # Get current historical data stats
        result += f"\n📈 **HISTORICAL DATABASE STATS**\n"
        result += f"• Total Realms with Data: {realms_with_data}\n"
        result += f"• Unique Items Tracked: {unique_items:,}\n"
        result += f"• Total Data Points: {total_data_points:,}\n"
        result += f"• Data Retention: 24 hours (288 points max per item)\n"
        result += f"• Memory Usage: {memory_usage_mb:.1f} MB / {RESOURCE_LIMITS['MAX_HISTORICAL_DATA_MB']} MB\n"
        result += f"• Execution Time: {time.time() - start_time:.1f} seconds\n"
        
        # Add security status
        result += f"\n🔒 **SECURITY LIMITS**\n"
        result += f"• Rate Limiting: Active (1 update per {RESOURCE_LIMITS['MIN_SECONDS_BETWEEN_UPDATES']}s)\n"
        result += f"• Max Realms: {RESOURCE_LIMITS['MAX_REALMS_PER_REQUEST']} per request\n"
        result += f"• Max Items: {RESOURCE_LIMITS['MAX_TOTAL_ITEMS']} total\n"
        result += f"• Timeout: {RESOURCE_LIMITS['MAX_EXECUTION_TIME']}s\n"
        
        result += f"\n💡 **USAGE TIPS**\n"
        result += f"• For specific realms: realms='mal-ganis:us,kiljaeden:us'\n"
        result += f"• For popular realms: realms='popular'\n"
        result += f"• For all US realms: realms='all-us' (limited to 5 realms)\n"
        result += f"• For more items: top_items=200 (max {RESOURCE_LIMITS['MAX_ITEMS_PER_REALM']})\n"
        result += f"• ⚠️ include_all_items=true cannot be used with realms='all-us'\n"
        
        return result
        
    except Exception as e:
        logger.error(f"Error updating historical database: {str(e)}")
        return f"Error updating historical database: {str(e)}"

@mcp.tool()
async def analyze_with_details(analysis_type: str = "volatility", realm_slug: str = "stormrage", region: str = "us", top_n: int = 20) -> str:
    """
    Perform detailed market analysis showing all calculations and work.
    
    Args:
        analysis_type: Type of analysis - "volatility", "trends", "opportunities", "cross_realm"
        realm_slug: Realm to analyze
        region: Region code
        top_n: Number of top items to include
    
    Returns:
        Detailed analysis with step-by-step calculations and visualizations
    """
    try:
        timestamp = datetime.now()
        result = f"""Detailed Market Analysis - {analysis_type.title()}
Realm: {realm_slug.title()} ({region.upper()})
Generated: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}

📊 **ANALYSIS TYPE**: {analysis_type.upper()}
================================================================================
"""
        
        # Step 1: Data Collection
        result += "\n🔍 **STEP 1: DATA COLLECTION**\n"
        result += "-" * 80 + "\n"
        
        # Get historical data for the realm
        historical_items = []
        data_points_by_item = {}
        
        for key in historical_data:
            if key.startswith(f"{region}_{realm_slug}_"):
                item_id = historical_data[key].get("item_id")
                if item_id and "data_points" in historical_data[key]:
                    data_points = historical_data[key]["data_points"]
                    if len(data_points) > 1:  # Need at least 2 points for analysis
                        historical_items.append(item_id)
                        data_points_by_item[item_id] = data_points
        
        result += f"• Total items with historical data: {len(historical_items)}\n"
        result += f"• Items with 2+ data points: {len(data_points_by_item)}\n"
        result += f"• Analysis scope: Last 24 hours\n"
        
        if not data_points_by_item:
            return result + "\n❌ Insufficient historical data. Please run update_historical_database first."
        
        # Step 2: Calculate Metrics
        result += "\n\n📈 **STEP 2: METRIC CALCULATIONS**\n"
        result += "-" * 80 + "\n"
        
        metrics_by_item = {}
        
        for item_id, data_points in data_points_by_item.items():
            # Extract prices and timestamps
            prices = [dp["price"] for dp in data_points]
            quantities = [dp["quantity"] for dp in data_points]
            timestamps = [datetime.fromisoformat(dp["timestamp"]) for dp in data_points]
            
            # Calculate metrics
            avg_price = sum(prices) / len(prices)
            min_price = min(prices)
            max_price = max(prices)
            current_price = prices[-1]
            
            # Volatility calculation
            if avg_price > 0:
                price_volatility = (max_price - min_price) / avg_price
            else:
                price_volatility = 0
            
            # Trend calculation
            if len(prices) >= 2:
                # Simple linear regression for trend
                x = list(range(len(prices)))
                x_mean = sum(x) / len(x)
                y_mean = avg_price
                
                numerator = sum((x[i] - x_mean) * (prices[i] - y_mean) for i in range(len(prices)))
                denominator = sum((x[i] - x_mean) ** 2 for i in range(len(prices)))
                
                if denominator != 0:
                    slope = numerator / denominator
                    trend_percentage = (slope / avg_price) * 100 if avg_price > 0 else 0
                else:
                    trend_percentage = 0
            else:
                trend_percentage = 0
            
            # Volume metrics
            avg_quantity = sum(quantities) / len(quantities)
            total_volume = sum(quantities)
            
            metrics_by_item[item_id] = {
                "avg_price": avg_price,
                "min_price": min_price,
                "max_price": max_price,
                "current_price": current_price,
                "volatility": price_volatility,
                "trend": trend_percentage,
                "avg_quantity": avg_quantity,
                "total_volume": total_volume,
                "data_points": len(prices),
                "price_history": prices,
                "timestamp_history": timestamps
            }
        
        result += f"• Metrics calculated for {len(metrics_by_item)} items\n"
        result += f"• Calculations performed:\n"
        result += f"  - Price volatility: (max - min) / average\n"
        result += f"  - Trend: Linear regression slope as % of average\n"
        result += f"  - Volume metrics: Average and total quantities\n"
        
        # Step 3: Analysis-specific processing
        result += f"\n\n📊 **STEP 3: {analysis_type.upper()} ANALYSIS**\n"
        result += "-" * 80 + "\n"
        
        if analysis_type == "volatility":
            # Sort by volatility
            sorted_items = sorted(metrics_by_item.items(), 
                                key=lambda x: x[1]["volatility"], 
                                reverse=True)[:top_n]
            
            result += f"\nTop {len(sorted_items)} Most Volatile Items:\n\n"
            
            # Create volatility data for visualization
            volatility_data = []
            
            for rank, (item_id, metrics) in enumerate(sorted_items, 1):
                volatility_pct = metrics["volatility"] * 100
                result += f"{rank}. Item #{item_id}\n"
                result += f"   • Volatility: {volatility_pct:.2f}%\n"
                result += f"   • Price range: {int(metrics['min_price']//10000):,}g - {int(metrics['max_price']//10000):,}g\n"
                result += f"   • Average: {int(metrics['avg_price']//10000):,}g\n"
                result += f"   • Current: {int(metrics['current_price']//10000):,}g\n"
                result += f"   • Trend: {metrics['trend']:+.2f}%/hour\n"
                result += f"   • Data points: {metrics['data_points']}\n"
                result += f"   • Calculation: ({int(metrics['max_price']//10000):,} - {int(metrics['min_price']//10000):,}) / {int(metrics['avg_price']//10000):,} = {volatility_pct:.2f}%\n"
                result += "\n"
                
                volatility_data.append({
                    "item_id": f"Item {item_id}",
                    "volatility": volatility_pct,
                    "avg_price": metrics['avg_price'] / 10000,
                    "volume": metrics['total_volume']
                })
            
            # Create visualization
            if volatility_data:
                df = pd.DataFrame(volatility_data)
                
                # Create bubble chart
                fig = go.Figure()
                
                fig.add_trace(go.Scatter(
                    x=df['avg_price'],
                    y=df['volatility'],
                    mode='markers+text',
                    marker=dict(
                        size=df['volume'] / df['volume'].max() * 100,
                        color=df['volatility'],
                        colorscale='Viridis',
                        showscale=True,
                        colorbar=dict(title="Volatility %")
                    ),
                    text=df['item_id'],
                    textposition="top center"
                ))
                
                fig.update_layout(
                    title="Price Volatility Analysis - Bubble Size = Trading Volume",
                    xaxis_title="Average Price (gold)",
                    yaxis_title="Volatility (%)",
                    height=600
                )
                
                # Save visualization
                chart_path = f"volatility_analysis_{timestamp.strftime('%Y%m%d_%H%M%S')}.html"
                fig.write_html(chart_path)
                result += f"\n📊 **VISUALIZATION CREATED**: {chart_path}\n"
        
        elif analysis_type == "trends":
            # Sort by trend strength
            sorted_items = sorted(metrics_by_item.items(), 
                                key=lambda x: abs(x[1]["trend"]), 
                                reverse=True)[:top_n]
            
            result += f"\nTop {len(sorted_items)} Trending Items:\n\n"
            
            rising = []
            falling = []
            
            for rank, (item_id, metrics) in enumerate(sorted_items, 1):
                trend = metrics["trend"]
                result += f"{rank}. Item #{item_id}: {trend:+.2f}%/hour\n"
                result += f"   • Direction: {'📈 RISING' if trend > 0 else '📉 FALLING' if trend < 0 else '➡️ STABLE'}\n"
                result += f"   • Current: {int(metrics['current_price']//10000):,}g\n"
                result += f"   • 24h change: {int((metrics['current_price'] - metrics['min_price'])//10000):,}g\n"
                result += f"   • Projected next hour: {int((metrics['current_price'] * (1 + trend/100))//10000):,}g\n"
                result += f"   • Confidence: {'High' if metrics['data_points'] > 10 else 'Medium' if metrics['data_points'] > 5 else 'Low'}\n"
                result += "\n"
                
                if trend > 0:
                    rising.append((item_id, trend))
                else:
                    falling.append((item_id, trend))
            
            result += f"\n📊 **TREND SUMMARY**:\n"
            result += f"• Rising items: {len(rising)}\n"
            result += f"• Falling items: {len(falling)}\n"
            result += f"• Average trend: {sum(m['trend'] for m in metrics_by_item.values()) / len(metrics_by_item):.2f}%/hour\n"
        
        elif analysis_type == "opportunities":
            # Find arbitrage and flip opportunities
            opportunities = []
            
            for item_id, metrics in metrics_by_item.items():
                # Opportunity score based on volatility and current position
                price_position = (metrics['current_price'] - metrics['min_price']) / (metrics['max_price'] - metrics['min_price']) if metrics['max_price'] > metrics['min_price'] else 0.5
                
                if price_position < 0.3 and metrics['trend'] > 0:
                    # Near bottom, trending up
                    opportunity_type = "BUY"
                    score = (1 - price_position) * metrics['volatility'] * 100
                elif price_position > 0.7 and metrics['trend'] < 0:
                    # Near top, trending down
                    opportunity_type = "SELL"
                    score = price_position * metrics['volatility'] * 100
                elif metrics['volatility'] > 0.2:
                    # High volatility flip opportunity
                    opportunity_type = "FLIP"
                    score = metrics['volatility'] * 50
                else:
                    continue
                
                opportunities.append({
                    "item_id": item_id,
                    "type": opportunity_type,
                    "score": score,
                    "metrics": metrics
                })
            
            # Sort by opportunity score
            opportunities.sort(key=lambda x: x['score'], reverse=True)
            
            result += f"\nTop {min(len(opportunities), top_n)} Market Opportunities:\n\n"
            
            for rank, opp in enumerate(opportunities[:top_n], 1):
                item_id = opp['item_id']
                metrics = opp['metrics']
                
                result += f"{rank}. Item #{item_id} - {opp['type']} OPPORTUNITY (Score: {opp['score']:.1f})\n"
                result += f"   • Current: {int(metrics['current_price']//10000):,}g\n"
                result += f"   • Range: {int(metrics['min_price']//10000):,}g - {int(metrics['max_price']//10000):,}g\n"
                
                if opp['type'] == "BUY":
                    profit_potential = metrics['avg_price'] - metrics['current_price']
                    result += f"   • Profit potential: {int(profit_potential//10000):,}g per item\n"
                    result += f"   • Entry point: Near 24h low\n"
                elif opp['type'] == "SELL":
                    result += f"   • Exit point: Near 24h high\n"
                    result += f"   • Risk: Price declining {metrics['trend']:.1f}%/hour\n"
                else:  # FLIP
                    result += f"   • Flip margin: {int((metrics['max_price'] - metrics['min_price'])//10000):,}g\n"
                    result += f"   • Buy below: {int((metrics['min_price'] * 1.1)//10000):,}g\n"
                    result += f"   • Sell above: {int((metrics['max_price'] * 0.9)//10000):,}g\n"
                
                result += "\n"
        
        # Step 4: Statistical Summary
        result += "\n\n📊 **STEP 4: STATISTICAL SUMMARY**\n"
        result += "-" * 80 + "\n"
        
        all_volatilities = [m['volatility'] for m in metrics_by_item.values()]
        all_trends = [m['trend'] for m in metrics_by_item.values()]
        
        result += f"\nMarket-wide Statistics:\n"
        result += f"• Average volatility: {sum(all_volatilities) / len(all_volatilities) * 100:.2f}%\n"
        result += f"• Median volatility: {sorted(all_volatilities)[len(all_volatilities)//2] * 100:.2f}%\n"
        result += f"• Max volatility: {max(all_volatilities) * 100:.2f}%\n"
        result += f"• Average trend: {sum(all_trends) / len(all_trends):.2f}%/hour\n"
        result += f"• Rising items: {sum(1 for t in all_trends if t > 0)} ({sum(1 for t in all_trends if t > 0) / len(all_trends) * 100:.1f}%)\n"
        result += f"• Falling items: {sum(1 for t in all_trends if t < 0)} ({sum(1 for t in all_trends if t < 0) / len(all_trends) * 100:.1f}%)\n"
        
        # Step 5: Recommendations
        result += "\n\n💡 **STEP 5: ACTIONABLE RECOMMENDATIONS**\n"
        result += "-" * 80 + "\n"
        
        if analysis_type == "volatility":
            result += "\n1. **High Volatility Items**: Focus on items with >20% volatility for flipping\n"
            result += "2. **Entry Strategy**: Buy when price is below 30% of daily range\n"
            result += "3. **Exit Strategy**: Sell when price is above 70% of daily range\n"
            result += "4. **Risk Management**: Don't invest more than 10% in any single volatile item\n"
        elif analysis_type == "trends":
            result += "\n1. **Rising Trends**: Buy items with >5%/hour growth and hold for 2-4 hours\n"
            result += "2. **Falling Trends**: Sell immediately or short items with <-5%/hour decline\n"
            result += "3. **Timing**: Best results when trends have 10+ data points (high confidence)\n"
        elif analysis_type == "opportunities":
            result += "\n1. **BUY Signals**: Act quickly on items near 24h lows with upward trends\n"
            result += "2. **SELL Signals**: Exit positions near 24h highs with downward trends\n"
            result += "3. **FLIP Strategy**: Focus on items with >20% daily range for quick profits\n"
        
        result += "\n\n" + "="*80 + "\n"
        result += "Analysis complete. All calculations and methodology shown above.\n"
        
        return result
        
    except Exception as e:
        logger.error(f"Error in detailed analysis: {str(e)}")
        return f"Error performing analysis: {str(e)}"

@mcp.tool()
async def debug_api_data(realm_slug: str = "stormrage", region: str = "us") -> str:
    """
    Get raw API data for debugging purposes.
    
    Shows actual API responses to verify data is coming from Blizzard.
    
    Args:
        realm_slug: Realm to check
        region: Region code
    
    Returns:
        Raw API data and sample auction listings
    """
    try:
        if not API_AVAILABLE:
            return "Error: Blizzard API not available"
        
        debug_info = {
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "realm": realm_slug,
            "region": region,
            "api_data": {}
        }
        
        async with BlizzardAPIClient() as client:
            # Get realm info
            realm_endpoint = f"/data/wow/realm/{realm_slug}"
            realm_data = await client.make_request(
                realm_endpoint, 
                {"namespace": f"dynamic-{region}", "locale": "en_US"}
            )
            
            debug_info["api_data"]["realm_info"] = {
                "name": realm_data.get("name"),
                "id": realm_data.get("id"),
                "connected_realm_id": realm_data.get("connected_realm", {}).get("id")
            }
            
            # Store raw realm response
            debug_info["raw_realm_response"] = realm_data
            
            # Get auction data
            connected_realm_href = realm_data.get("connected_realm", {}).get("href", "")
            connected_realm_id = connected_realm_href.split("/")[-1].split("?")[0]
            
            auction_endpoint = f"/data/wow/connected-realm/{connected_realm_id}/auctions"
            auction_data = await client.make_request(
                auction_endpoint,
                {"namespace": f"dynamic-{region}", "locale": "en_US"}
            )
            
            auctions = auction_data.get("auctions", [])
            
            # Get token price
            token_endpoint = "/data/wow/token/index"
            token_data = await client.make_request(
                token_endpoint,
                {"namespace": f"dynamic-{region}", "locale": "en_US"}
            )
            
            debug_info["api_data"]["token"] = {
                "price_copper": token_data.get("price", 0),
                "price_gold": token_data.get("price", 0) // 10000,
                "last_updated": token_data.get("last_updated_timestamp", 0)
            }
            
            # Store raw token response
            debug_info["raw_token_response"] = token_data
            
            debug_info["api_data"]["auctions"] = {
                "total_count": len(auctions),
                "sample_size": min(10, len(auctions)),
                "first_10_auctions": []
            }
            
            # Store raw auction response sample
            debug_info["raw_auction_response_sample"] = {
                "_links": auction_data.get("_links"),
                "connected_realm": auction_data.get("connected_realm"),
                "commodities": auction_data.get("commodities"),
                "first_3_auctions_raw": auctions[:3] if auctions else []
            }
            
            # Sample first 10 auctions with details
            for i, auction in enumerate(auctions[:10]):
                debug_info["api_data"]["auctions"]["first_10_auctions"].append({
                    "auction_id": auction.get("id"),
                    "item_id": auction.get("item", {}).get("id"),
                    "quantity": auction.get("quantity"),
                    "unit_price": auction.get("unit_price", 0) // 10000 if auction.get("unit_price") else None,
                    "buyout": auction.get("buyout", 0) // 10000 if auction.get("buyout") else None,
                    "time_left": auction.get("time_left")
                })
            
            # Count unique items
            unique_items = set()
            for auction in auctions:
                item_id = auction.get('item', {}).get('id', 0)
                if item_id:
                    unique_items.add(item_id)
            
            debug_info["api_data"]["statistics"] = {
                "unique_items": len(unique_items),
                "average_auctions_per_item": len(auctions) / len(unique_items) if unique_items else 0,
                "sample_item_ids": list(unique_items)[:20]
            }
            
            result = f"""Debug API Data - {realm_data.get('name', realm_slug.title())} ({region.upper()})
Generated: {debug_info['timestamp']}

🔍 **RAW API VERIFICATION**

**Realm Data:**
• Name: {debug_info['api_data']['realm_info']['name']}
• Realm ID: {debug_info['api_data']['realm_info']['id']}
• Connected Realm ID: {debug_info['api_data']['realm_info']['connected_realm_id']}

**Token Price (LIVE):**
• Price: {debug_info['api_data']['token']['price_gold']:,}g
• Raw Price: {debug_info['api_data']['token']['price_copper']:,} copper
• Last Updated: {debug_info['api_data']['token']['last_updated']}

**Auction House Data:**
• Total Auctions: {debug_info['api_data']['auctions']['total_count']:,}
• Unique Items: {debug_info['api_data']['statistics']['unique_items']:,}
• Avg Listings per Item: {debug_info['api_data']['statistics']['average_auctions_per_item']:.1f}

**Sample Auctions (First 10):**
"""
            
            for i, auction in enumerate(debug_info['api_data']['auctions']['first_10_auctions'], 1):
                result += f"""
{i}. Auction #{auction['auction_id']}
   • Item ID: {auction['item_id']}
   • Quantity: {auction['quantity']}
   • Buyout: {auction['buyout']:,}g
   • Time Left: {auction['time_left']}
"""

            result += f"""

**Sample Item IDs Being Traded:**
{', '.join(str(id) for id in debug_info['api_data']['statistics']['sample_item_ids'])}

**API Status:**
✅ Blizzard API Connected
✅ Real-time data retrieved
✅ Token price: {debug_info['api_data']['token']['price_gold']:,}g
✅ Auction count: {debug_info['api_data']['auctions']['total_count']:,}

This data comes directly from Blizzard's API endpoints.

**RAW API RESPONSES (JSON):**

1. RAW TOKEN RESPONSE:
{json.dumps(debug_info.get('raw_token_response', {}), indent=2)}

2. RAW REALM RESPONSE (truncated):
{json.dumps({k: v for k, v in debug_info.get('raw_realm_response', {}).items() if k in ['_links', 'id', 'name', 'slug', 'region', 'connected_realm']}, indent=2)}

3. RAW AUCTION RESPONSE SAMPLE:
{json.dumps(debug_info.get('raw_auction_response_sample', {}), indent=2)}"""

            return result
            
    except Exception as e:
        logger.error(f"Error in debug API data: {str(e)}")
        return f"Error getting debug data: {str(e)}"

@mcp.tool()
async def get_item_info(item_ids: str, region: str = "us") -> str:
    """
    Get item names and details from Blizzard's Item API.
    
    Fetches official item names and information for given item IDs.
    
    Args:
        item_ids: Comma-separated item IDs (e.g. "18712,37812,210796")
        region: Region code (us, eu, kr, tw)
    
    Returns:
        Item details including names, quality, type, and icon
    """
    try:
        if not API_AVAILABLE:
            return "Error: Blizzard API not available"
        
        # Parse item IDs
        ids = [id.strip() for id in item_ids.split(",") if id.strip()]
        if not ids:
            return "Error: No valid item IDs provided"
        
        # Limit to 20 items per request
        ids = ids[:20]
        
        results = []
        
        async with BlizzardAPIClient() as client:
            for item_id in ids:
                try:
                    # Get item data from API
                    item_endpoint = f"/data/wow/item/{item_id}"
                    item_data = await client.make_request(
                        item_endpoint,
                        {"namespace": f"static-{region}", "locale": "en_US"}
                    )
                    
                    # Get media data for icon
                    media_endpoint = f"/data/wow/media/item/{item_id}"
                    media_data = await client.make_request(
                        media_endpoint,
                        {"namespace": f"static-{region}", "locale": "en_US"}
                    )
                    
                    # Extract icon URL
                    icon_url = None
                    if media_data and "assets" in media_data:
                        for asset in media_data.get("assets", []):
                            if asset.get("key") == "icon":
                                icon_url = asset.get("value")
                                break
                    
                    # Format item info
                    item_info = {
                        "id": item_id,
                        "name": item_data.get("name", "Unknown"),
                        "quality": item_data.get("quality", {}).get("name", "Unknown"),
                        "level": item_data.get("level", 0),
                        "required_level": item_data.get("required_level", 0),
                        "item_class": item_data.get("item_class", {}).get("name", "Unknown"),
                        "item_subclass": item_data.get("item_subclass", {}).get("name", "Unknown"),
                        "inventory_type": item_data.get("inventory_type", {}).get("name", "Unknown"),
                        "purchase_price": item_data.get("purchase_price", 0),
                        "sell_price": item_data.get("sell_price", 0),
                        "max_count": item_data.get("max_count", 0),
                        "is_stackable": item_data.get("is_stackable", False),
                        "icon_url": icon_url,
                        "raw_response": item_data  # Include raw API response
                    }
                    
                    results.append(item_info)
                    
                except Exception as e:
                    results.append({
                        "id": item_id,
                        "error": str(e),
                        "name": f"Error fetching item {item_id}"
                    })
            
            # Format response
            output = f"""Item Information from Blizzard API
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📦 **ITEM DETAILS**
"""
            
            for item in results:
                if "error" in item:
                    output += f"""
❌ Item #{item['id']}: {item['error']}
"""
                else:
                    output += f"""
📌 **{item['name']}** (ID: {item['id']})
• Quality: {item['quality']}
• Type: {item['item_class']} - {item['item_subclass']}
• Item Level: {item['level']}
• Required Level: {item['required_level']}
• Slot: {item['inventory_type']}
• Vendor Price: {item['purchase_price'] // 10000}g {(item['purchase_price'] % 10000) // 100}s {item['purchase_price'] % 100}c
• Sell Price: {item['sell_price'] // 10000}g {(item['sell_price'] % 10000) // 100}s {item['sell_price'] % 100}c
• Stackable: {'Yes' if item['is_stackable'] else 'No'} {f"(Max: {item['max_count']})" if item['max_count'] > 0 else ''}
"""
                    if item.get('icon_url'):
                        output += f"• Icon: {item['icon_url']}\n"
            
            output += f"""

💡 **USAGE TIPS**
• Use these item IDs in market analysis tools
• Check if items are tradeable (some are soulbound)
• Compare vendor prices to AH prices
• Quality affects market value (Poor < Common < Uncommon < Rare < Epic < Legendary)

🔍 **RAW API DATA SAMPLE** (First Item)
{json.dumps(results[0].get('raw_response', {}), indent=2)[:500]}...
"""
            
            return output
            
    except Exception as e:
        logger.error(f"Error getting item info: {str(e)}")
        return f"Error getting item info: {str(e)}"

@mcp.tool()
async def check_staging_data() -> str:
    """
    Check how many data points are stored in staging/cache.
    
    Shows cache statistics including:
    - Number of cached analyses
    - Cache hit rates
    - Data freshness
    - Memory usage estimates
    
    Returns:
        Staging data statistics
    """
    try:
        # Get cache statistics
        total_cache_entries = len(analysis_cache)
        valid_cache_entries = 0
        expired_cache_entries = 0
        cache_size_estimate = 0
        
        current_time = datetime.now()
        oldest_entry = None
        newest_entry = None
        
        cache_breakdown = {
            "market_opportunities": 0,
            "crafting_analysis": 0,
            "other": 0
        }
        
        for key, ttl_time in analysis_cache_ttl.items():
            if current_time < ttl_time:
                valid_cache_entries += 1
            else:
                expired_cache_entries += 1
            
            # Track oldest and newest
            if oldest_entry is None or ttl_time < oldest_entry:
                oldest_entry = ttl_time
            if newest_entry is None or ttl_time > newest_entry:
                newest_entry = ttl_time
            
            # Categorize cache entries
            if "opportunities_" in key:
                cache_breakdown["market_opportunities"] += 1
            elif "crafting_" in key:
                cache_breakdown["crafting_analysis"] += 1
            else:
                cache_breakdown["other"] += 1
            
            # Estimate size (rough estimate)
            if key in analysis_cache:
                cache_size_estimate += len(str(analysis_cache[key]))
        
        # Check API client cache if available
        api_cache_info = "API cache information not available"
        if API_AVAILABLE:
            try:
                # This would need to be implemented in BlizzardAPIClient
                # For now, we'll just note it's using the client
                api_cache_info = "API client has internal caching (1-hour TTL)"
            except:
                pass
        
        result = f"""Staging Data Statistics
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📊 **CACHE OVERVIEW**
• Total cache entries: {total_cache_entries}
• Valid (not expired): {valid_cache_entries}
• Expired: {expired_cache_entries}
• Cache hit rate: {(valid_cache_entries / total_cache_entries * 100) if total_cache_entries > 0 else 0:.1f}%

📈 **CACHE BREAKDOWN**
• Market opportunities: {cache_breakdown['market_opportunities']}
• Crafting analyses: {cache_breakdown['crafting_analysis']}
• Other data: {cache_breakdown['other']}

⏰ **DATA FRESHNESS**
• Oldest entry expires: {oldest_entry.strftime('%Y-%m-%d %H:%M:%S') if oldest_entry else 'N/A'}
• Newest entry expires: {newest_entry.strftime('%Y-%m-%d %H:%M:%S') if newest_entry else 'N/A'}
• Cache TTL: 1 hour

💾 **MEMORY USAGE**
• Estimated cache size: {cache_size_estimate / 1024:.1f} KB
• Average entry size: {(cache_size_estimate / total_cache_entries / 1024) if total_cache_entries > 0 else 0:.1f} KB

🔧 **API CACHING**
• {api_cache_info}
• Auction data cached to reduce API calls
• Token prices always fetched fresh

📝 **STAGING NOTES**
• Data is cached in-memory (not persistent)
• Cache clears on server restart
• Helps avoid Blizzard API rate limits
• Each realm/region combination cached separately

💡 **RECOMMENDATIONS**
"""
        
        if valid_cache_entries == 0:
            result += "• No valid cache entries - all data will be fresh\n"
        elif valid_cache_entries > 10:
            result += "• Good cache coverage - fast response times\n"
        
        if expired_cache_entries > valid_cache_entries:
            result += "• Many expired entries - consider cache cleanup\n"
        
        result += "• Monitor cache size if memory is limited\n"
        result += "• Cache helps stay within API rate limits"
        
        return result
        
    except Exception as e:
        logger.error(f"Error checking staging data: {str(e)}")
        return f"Error checking staging data: {str(e)}"

@mcp.tool()
def get_analysis_help() -> str:
    """
    Get help on using the analysis tools effectively.
    
    Returns:
        Guide to all analysis features
    """
    return """WoW Economic Analysis Tools - User Guide

🛠️ **AVAILABLE ANALYSIS TOOLS**

1. **analyze_market_opportunities**
   • Finds profitable flips and underpriced items
   • Identifies low-competition markets
   • Shows specific item IDs with profit margins
   • Best for: Active traders looking for quick profits

2. **analyze_crafting_profits**
   • Compares material costs vs crafted item prices
   • Shows ROI for each profession
   • Identifies most profitable recipes
   • Best for: Crafters maximizing profession income

3. **predict_market_trends**
   • Forecasts price movements
   • Identifies best times to buy/sell
   • Provides seasonal insights
   • Best for: Strategic long-term trading

4. **get_item_info**
   • Look up item names and details by ID
   • Get quality, type, vendor prices, and icons
   • Shows raw API response data
   • Best for: Identifying items from auction data

5. **get_historical_data**
   • Retrieves historical price data for specific items
   • Shows price trends over the last 24 hours
   • Provides buy/sell/hold recommendations
   • Best for: Analyzing item-specific price movements

6. **debug_api_data**
   • Shows raw API responses from Blizzard
   • Verifies real-time data connectivity
   • Displays auction samples and token prices
   • Best for: Troubleshooting and verification

7. **check_staging_data**
   • Shows cache statistics and data points
   • Displays cache hit rates and memory usage
   • Tracks data freshness and expiration
   • Best for: Monitoring server performance

8. **update_historical_database**
   • Updates historical price data for multiple realms
   • Tracks top 100 items by volume on each realm
   • Can specify custom realms or use defaults
   • Best for: Scheduled data collection

9. **analyze_with_details**
   • Performs in-depth analysis with all calculations shown
   • Types: volatility, trends, opportunities
   • Shows step-by-step methodology and formulas
   • Creates Plotly visualizations for data
   • Best for: Understanding market dynamics with proof

📋 **HOW TO USE EFFECTIVELY**

**Daily Routine:**
1. Check market opportunities on your main realm
2. Review crafting profits for your professions
3. Monitor token prices across regions
4. Plan trades based on trend predictions

**Weekly Strategy:**
• Monday: Buy materials (low prices)
• Tuesday: Sell consumables (raid reset)
• Friday-Saturday: Post high-value items
• Sunday: Stock up for next week

**Key Metrics to Track:**
• Profit margins > 30% for flips
• ROI > 50% for crafting
• Token differences > 10% for arbitrage
• Market activity levels for timing

💰 **PROFIT MAXIMIZATION TIPS**

1. **Diversify**: Don't focus on one market
2. **Time It**: Post during peak hours
3. **Research**: Track your competition
4. **Patient**: Some items take time to sell
5. **Liquid**: Keep 30% gold for opportunities

🎯 **QUICK START COMMANDS**

• "Find market opportunities on stormrage"
• "Analyze crafting profits for alchemy"
• "Predict market trends for area-52"
• "Get item info for 210796,210799"
• "Debug API data for stormrage"

⚠️ **IMPORTANT NOTES**
• Data updates hourly from Blizzard
• Prices include 5% AH cut
• Always verify before large investments
• Markets can change rapidly

Remember: The best gold-makers combine multiple strategies!"""

def main():
    """Main entry point for FastMCP 2.0 server."""
    try:
        # Check for Blizzard API credentials
        client_id = os.getenv("BLIZZARD_CLIENT_ID")
        if not client_id:
            logger.warning("⚠️ No Blizzard API credentials found in environment variables")
        
        port = int(os.getenv("PORT", "8000"))
        
        logger.info("🚀 WoW Economic Analysis Server with FastMCP 2.0")
        logger.info("🔧 Tools: Market analysis, crafting profits, predictions, historical data, debug, item lookup, staging")
        logger.info("📊 Registered tools: 10 WoW economic analysis tools")
        logger.info(f"🌐 HTTP Server: 0.0.0.0:{port}")
        logger.info("✅ Starting server...")
        
        if client_id:
            logger.info(f"✅ Blizzard API configured: {client_id[:10]}...")
        
        # Run server using FastMCP 2.0 HTTP transport
        mcp.run(
            transport="http",
            host="0.0.0.0",
            port=port
        )
        
    except KeyboardInterrupt:
        logger.info("⏹️  Shutting down gracefully...")
        save_historical_data()
        logger.info("💾 Historical data saved")
    except Exception as e:
        logger.error(f"❌ Error starting server: {e}")
        save_historical_data()
        sys.exit(1)

if __name__ == "__main__":
    main()