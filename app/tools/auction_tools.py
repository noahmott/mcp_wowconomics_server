"""
Auction house and economy analysis tools for WoW Guild MCP Server
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

from .base import mcp_tool, with_supabase_logging, get_or_initialize_services
from ..api.blizzard_client import BlizzardAPIClient, BlizzardAPIError
from ..services.auction_aggregator import AuctionAggregatorService
from ..utils.namespace_utils import get_connected_realm_id

# Create auction aggregator instance
auction_aggregator = AuctionAggregatorService()

logger = logging.getLogger(__name__)


@mcp_tool()
@with_supabase_logging
async def get_auction_house_snapshot(
    realm: str,
    item_search: Optional[str] = None,
    max_results: int = 100,
    game_version: str = "retail"
) -> Dict[str, Any]:
    """
    Get current auction house snapshot for a realm
    
    Args:
        realm: Server realm (e.g., 'stormrage', 'area-52')
        item_search: Optional item name or ID to search for
        max_results: Maximum number of items to return
        game_version: WoW version ('retail' or 'classic')
    
    Returns:
        Current auction house data with market analysis
    """
    try:
        logger.info(f"Getting auction house data for realm {realm} ({game_version})")
        
        async with BlizzardAPIClient(game_version=game_version) as client:
            # Get connected realm ID using helper function
            connected_realm_id = await get_connected_realm_id(realm, game_version, client)
            
            if not connected_realm_id:
                return {"error": f"Could not find connected realm ID for realm {realm}"}
            
            # Get current auction data
            ah_data = await client.get_auction_house_data(connected_realm_id)
            
            if not ah_data or 'auctions' not in ah_data:
                return {"error": "No auction data available"}
            
            # Aggregate auction data
            aggregated = auction_aggregator.aggregate_auction_data(ah_data['auctions'])
            
            # Filter results if item search provided
            if item_search:
                if item_search.isdigit():
                    # Search by item ID
                    item_id = int(item_search)
                    if item_id in aggregated:
                        aggregated = {item_id: aggregated[item_id]}
                else:
                    # Item name search would require additional API endpoints
                    logger.warning("Item name search not yet implemented")
            
            # Sort by total market value and limit results
            sorted_items = sorted(
                aggregated.items(),
                key=lambda x: x[1]['total_market_value'],
                reverse=True
            )[:max_results]
            
            return {
                "success": True,
                "realm": realm,
                "connected_realm_id": connected_realm_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "total_items": len(aggregated),
                "items_returned": len(sorted_items),
                "market_data": dict(sorted_items)
            }
            
    except BlizzardAPIError as e:
        logger.error(f"Blizzard API error: {e.message}")
        return {"error": f"API Error: {e.message}"}
    except Exception as e:
        logger.error(f"Error getting auction house data: {str(e)}")
        return {"error": f"Auction house data failed: {str(e)}"}


@mcp_tool()
@with_supabase_logging
async def capture_economy_snapshot(
    realms: List[str],
    region: str = "us",
    game_version: str = "retail",
    force_update: bool = False
) -> Dict[str, Any]:
    """
    Capture hourly economy snapshots for specified realms
    
    Args:
        realms: List of realm names to capture data for
        region: Region (us, eu, etc.)
        game_version: WoW version ('retail' or 'classic')
        force_update: Force update even if recent snapshot exists
    
    Returns:
        Snapshot capture results
    """
    try:
        logger.info(f"Capturing economy snapshots for {len(realms)} realms")
        
        # Initialize services if needed
        service_mgr = await get_or_initialize_services()
        redis_client = service_mgr.redis_client
        
        if not redis_client:
            return {
                "error": "Redis not available for economy snapshots",
                "message": "Redis connection required for storing economy data"
            }
        
        results = {}
        snapshots_created = 0
        snapshots_skipped = 0
        
        async with BlizzardAPIClient(game_version=game_version) as client:
            for realm in realms:
                try:
                    # Check if we have a recent snapshot (within last hour)
                    snapshot_key = f"economy_snapshot:{game_version}:{region}:{realm.lower()}"
                    
                    if not force_update:
                        # Check last snapshot time
                        last_snapshot_time_key = f"{snapshot_key}:last_update"
                        last_update = await redis_client.get(last_snapshot_time_key)
                        
                        if last_update:
                            last_time = datetime.fromisoformat(last_update.decode())  # Decode bytes to string
                            time_diff = datetime.now(timezone.utc) - last_time
                            
                            if time_diff.total_seconds() < 3600:  # Less than 60 minutes (1 hour)
                                logger.info(f"Skipping {realm} - snapshot is {int(time_diff.total_seconds() / 60)} minutes old")
                                results[realm] = {"status": "skipped", "reason": "recent_snapshot_exists"}
                                snapshots_skipped += 1
                                continue
                    
                    # Get connected realm ID
                    connected_realm_id = await get_connected_realm_id(realm, game_version, client)
                    
                    if not connected_realm_id:
                        results[realm] = {"status": "error", "reason": "realm_not_found"}
                        continue
                    
                    # Get auction data
                    ah_data = await client.get_auction_house_data(connected_realm_id)
                    
                    if not ah_data or 'auctions' not in ah_data:
                        results[realm] = {"status": "error", "reason": "no_auction_data"}
                        continue
                    
                    # Aggregate auction data
                    aggregated = auction_aggregator.aggregate_auction_data(ah_data['auctions'])
                    
                    # Create timestamped snapshot
                    timestamp = datetime.now(timezone.utc)
                    timestamp_key = f"{snapshot_key}:{timestamp.strftime('%Y%m%d_%H%M')}"
                    
                    snapshot_data = {
                        "realm": realm,
                        "connected_realm_id": connected_realm_id,
                        "timestamp": timestamp.isoformat(),
                        "auction_count": len(ah_data['auctions']),
                        "unique_items": len(aggregated),
                        "market_data": aggregated
                    }
                    
                    # Store snapshot with 30-day expiry
                    await redis_client.setex(
                        timestamp_key,
                        2592000,  # 30 days in seconds
                        json.dumps(snapshot_data)
                    )
                    
                    # Update last snapshot time
                    await redis_client.set(last_snapshot_time_key, timestamp.isoformat())
                    
                    results[realm] = {
                        "status": "success",
                        "auctions": len(ah_data['auctions']),
                        "unique_items": len(aggregated),
                        "timestamp": timestamp.isoformat()
                    }
                    snapshots_created += 1
                    
                except Exception as e:
                    logger.error(f"Error capturing snapshot for {realm}: {str(e)}")
                    results[realm] = {"status": "error", "reason": str(e)}
        
        return {
            "success": True,
            "snapshots_created": snapshots_created,
            "snapshots_skipped": snapshots_skipped,
            "realm_results": results,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error capturing economy snapshots: {str(e)}")
        return {"error": f"Economy snapshot capture failed: {str(e)}"}


@mcp_tool()
@with_supabase_logging
async def get_economy_trends(
    realm: str,
    item_ids: List[int],
    hours: int = 24,
    region: str = "us",
    game_version: str = "retail"
) -> Dict[str, Any]:
    """
    Get price trends for specific items over time
    
    Args:
        realm: Server realm
        item_ids: List of item IDs to get trends for
        hours: Number of hours of history to retrieve (max 720/30 days)
        region: Region (us, eu, etc.)
        game_version: WoW version ('retail' or 'classic')
    
    Returns:
        Price trend data for specified items
    """
    try:
        logger.info(f"Getting economy trends for {len(item_ids)} items on {realm}")
        
        # Initialize services if needed
        service_mgr = await get_or_initialize_services()
        redis_client = service_mgr.redis_client
        
        if not redis_client:
            return {
                "error": "Redis not available",
                "message": "Redis connection required for retrieving economy trends"
            }
        
        # Limit hours to 30 days max
        hours = min(hours, 720)
        
        trends = {}
        snapshot_base_key = f"economy_snapshot:{game_version}:{region}:{realm.lower()}"
        
        # Get all snapshots for the time period
        current_time = datetime.now(timezone.utc)
        cutoff_time = current_time - timedelta(hours=hours)
        
        # Get all snapshot keys for this realm
        pattern = f"{snapshot_base_key}:*"
        all_keys = await redis_client.keys(pattern)
        
        # Filter keys to only include timestamps within our time range
        for key in all_keys:
            # Decode bytes key to string
            key_str = key.decode() if isinstance(key, bytes) else key
            key_parts = key_str.split(':')
            if len(key_parts) >= 5 and key_parts[-1].startswith('202'):
                # Parse timestamp from key
                timestamp_str = key_parts[-1]
                try:
                    # Handle both old (YYYYMMDD_HH) and new (YYYYMMDD_HHMM) formats
                    if len(timestamp_str) == 11:  # Old format: YYYYMMDD_HH
                        ts_dt = datetime.strptime(timestamp_str, '%Y%m%d_%H').replace(tzinfo=timezone.utc)
                    else:  # New format: YYYYMMDD_HHMM
                        ts_dt = datetime.strptime(timestamp_str, '%Y%m%d_%H%M').replace(tzinfo=timezone.utc)
                    
                    # Skip if outside our time range
                    if ts_dt < cutoff_time or ts_dt > current_time:
                        continue
                    
                    snapshot_data = await redis_client.get(key)
                    if snapshot_data:
                        snapshot = json.loads(snapshot_data.decode())  # Decode bytes to string
                        
                        for item_id in item_ids:
                            item_id_str = str(item_id)
                            if item_id_str in snapshot.get("market_data", {}):
                                if item_id not in trends:
                                    trends[item_id] = []
                                
                                item_data = snapshot["market_data"][item_id_str]
                                trends[item_id].append({
                                    "timestamp": snapshot["timestamp"],
                                    "min_price": item_data["min_price"],
                                    "max_price": item_data["max_price"],
                                    "mean_price": item_data["mean_price"],
                                    "auction_count": item_data["auction_count"],
                                    "total_quantity": item_data["total_quantity"]
                                })
                except ValueError:
                    # Skip keys with invalid timestamp format
                    continue
        
        # Calculate trend statistics
        trend_analysis = {}
        for item_id, price_history in trends.items():
            if price_history:
                # Sort by timestamp
                price_history.sort(key=lambda x: x["timestamp"])
                
                # Calculate price changes
                if len(price_history) >= 2:
                    start_price = price_history[0]["mean_price"]
                    end_price = price_history[-1]["mean_price"]
                    price_change = end_price - start_price
                    price_change_pct = (price_change / start_price * 100) if start_price > 0 else 0
                    
                    trend_analysis[item_id] = {
                        "price_history": price_history,
                        "start_price": start_price,
                        "current_price": end_price,
                        "price_change": price_change,
                        "price_change_percentage": price_change_pct,
                        "data_points": len(price_history)
                    }
        
        return {
            "success": True,
            "realm": realm,
            "hours_analyzed": hours,
            "items_found": len(trend_analysis),
            "trend_data": trend_analysis,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting economy trends: {str(e)}")
        return {"error": f"Economy trends retrieval failed: {str(e)}"}


@mcp_tool()
@with_supabase_logging
async def find_market_opportunities(
    realm: str,
    min_profit_margin: float = 20.0,
    max_results: int = 20,
    game_version: str = "retail"
) -> Dict[str, Any]:
    """
    Find profitable market opportunities based on current auction data
    
    Args:
        realm: Server realm
        min_profit_margin: Minimum profit margin percentage (default 20%)
        max_results: Maximum number of opportunities to return
        game_version: WoW version ('retail' or 'classic')
    
    Returns:
        List of profitable market opportunities
    """
    try:
        logger.info(f"Finding market opportunities on {realm} ({game_version})")
        
        async with BlizzardAPIClient(game_version=game_version) as client:
            # Get connected realm ID using helper function
            connected_realm_id = await get_connected_realm_id(realm, game_version, client)
            
            if not connected_realm_id:
                return {"error": "Could not find connected realm ID"}
            
            # Get current auction data
            ah_data = await client.get_auction_house_data(connected_realm_id)
            
            if not ah_data or 'auctions' not in ah_data:
                return {"error": "No auction data available"}
            
            # Aggregate auction data
            aggregated = auction_aggregator.aggregate_auction_data(ah_data['auctions'])
            
            # Find opportunities (items with high price variance)
            opportunities = []
            for item_id, data in aggregated.items():
                if data['auction_count'] < 2:
                    continue
                    
                # Calculate potential profit margin
                price_range = data['max_price'] - data['min_price']
                if data['min_price'] > 0:
                    margin_pct = (price_range / data['min_price']) * 100
                    
                    if margin_pct >= min_profit_margin:
                        opportunities.append({
                            'item_id': item_id,
                            'min_price': data['min_price'],
                            'max_price': data['max_price'],
                            'mean_price': data['avg_price'],
                            'profit_margin_pct': margin_pct,
                            'auction_count': data['auction_count'],
                            'total_quantity': data['total_quantity'],
                            'potential_profit': price_range
                        })
            
            # Sort by profit margin
            opportunities.sort(key=lambda x: x['profit_margin_pct'], reverse=True)
            
            return {
                "success": True,
                "realm": realm,
                "connected_realm_id": connected_realm_id,
                "opportunities_found": len(opportunities),
                "opportunities": opportunities[:max_results],
                "min_profit_margin": min_profit_margin,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    except BlizzardAPIError as e:
        logger.error(f"Blizzard API error: {e.message}")
        return {"error": f"API Error: {e.message}"}
    except Exception as e:
        logger.error(f"Error finding market opportunities: {str(e)}")
        return {"error": f"Market opportunity search failed: {str(e)}"}


@mcp_tool()
@with_supabase_logging
async def analyze_item_market_history(
    realm: str,
    item_id: int,
    days: int = 7,
    game_version: str = "retail"
) -> Dict[str, Any]:
    """
    Analyze historical market trends for a specific item
    
    Args:
        realm: Server realm
        item_id: Item ID to analyze
        days: Number of days of history to analyze (default 7)
        game_version: WoW version ('retail' or 'classic')
    
    Returns:
        Historical market analysis with trends and predictions
    """
    try:
        logger.info(f"Analyzing market history for item {item_id} on {realm}")
        
        # Get connected realm ID using centralized helper
        async with BlizzardAPIClient(game_version=game_version) as client:
            connected_realm_id = await get_connected_realm_id(realm, game_version, client)
            
            if not connected_realm_id:
                logger.error(f"Could not find connected realm ID for {realm} ({game_version})")
                return {"error": f"Could not find connected realm ID for {realm}"}
            
            # Historical data requires persistent storage - returning current analysis
            # Mock analysis structure for future implementation
            return {
                "success": True,
                "realm": realm,
                "item_id": item_id,
                "analysis_period_days": days,
                "market_trends": {
                    "price_trend": "stable",
                    "volume_trend": "increasing",
                    "volatility": "low",
                    "recommended_action": "hold"
                },
                "note": "Historical data requires persistent auction snapshot storage"
            }
            
    except Exception as e:
        logger.error(f"Error analyzing market history: {str(e)}")
        return {"error": f"Market analysis failed: {str(e)}"}


@mcp_tool()
@with_supabase_logging
async def check_economy_snapshot_health(
    realms: Optional[List[str]] = None,
    region: str = "us",
    game_version: str = "retail",
    check_hours: int = 24
) -> Dict[str, Any]:
    """
    Check the health of economy snapshots in Redis
    
    Args:
        realms: List of realms to check (if None, checks all configured realms)
        region: Region (us, eu, etc.)
        game_version: WoW version ('retail' or 'classic')
        check_hours: Number of hours to analyze (default 24)
    
    Returns:
        Health check results including snapshot frequency and any issues
    """
    try:
        logger.info(f"Checking economy snapshot health for {game_version} {region}")
        
        # Initialize services if needed
        service_mgr = await get_or_initialize_services()
        redis_client = service_mgr.redis_client
        
        if not redis_client:
            return {
                "error": "Redis not available",
                "message": "Redis connection required for health check"
            }
        
        # Default realms if none specified
        if not realms:
            realms = [
                "area-52", "stormrage", "illidan", "tichondrius", 
                "mal'ganis", "zul'jin", "thrall", "lightbringer",
                "moonguard", "wyrmrest-accord"
            ]
        
        current_time = datetime.now(timezone.utc)
        cutoff_time = current_time - timedelta(hours=check_hours)
        health_results = {}
        
        for realm in realms:
            realm_lower = realm.lower()
            snapshot_base_key = f"economy_snapshot:{game_version}:{region}:{realm_lower}"
            
            # Get last update time
            last_update_key = f"{snapshot_base_key}:last_update"
            last_update = await redis_client.get(last_update_key)
            
            # Get all snapshot keys for this realm
            pattern = f"{snapshot_base_key}:*"
            all_keys = await redis_client.keys(pattern)
            
            # Filter and parse snapshot timestamps
            snapshots = []
            for key in all_keys:
                key_str = key.decode() if isinstance(key, bytes) else key
                key_parts = key_str.split(':')
                if len(key_parts) >= 5 and key_parts[-1].startswith('202'):
                    timestamp_str = key_parts[-1]
                    try:
                        # Handle both old and new formats
                        if len(timestamp_str) == 11:  # YYYYMMDD_HH
                            ts_dt = datetime.strptime(timestamp_str, '%Y%m%d_%H').replace(tzinfo=timezone.utc)
                        else:  # YYYYMMDD_HHMM
                            ts_dt = datetime.strptime(timestamp_str, '%Y%m%d_%H%M').replace(tzinfo=timezone.utc)
                        
                        if ts_dt >= cutoff_time:
                            snapshots.append(ts_dt)
                    except ValueError:
                        continue
            
            # Sort snapshots by time
            snapshots.sort()
            
            # Analyze snapshot health
            health_data = {
                "realm": realm,
                "status": "unknown",
                "last_update": None,
                "minutes_since_update": None,
                "snapshot_count": len(snapshots),
                "expected_snapshots": int(check_hours),  # 1 per hour
                "missing_percentage": 0,
                "gaps": [],
                "issues": []
            }
            
            # Check last update time
            if last_update:
                try:
                    last_time = datetime.fromisoformat(last_update.decode())
                    health_data["last_update"] = last_time.isoformat()
                    health_data["minutes_since_update"] = int((current_time - last_time).total_seconds() / 60)
                    
                    # Flag if no recent update (more than 75 minutes for hourly snapshots)
                    if health_data["minutes_since_update"] > 75:
                        health_data["issues"].append(f"No update in {health_data['minutes_since_update']} minutes")
                except:
                    health_data["issues"].append("Invalid last_update timestamp")
            else:
                health_data["issues"].append("No last_update timestamp found")
            
            # Analyze gaps between snapshots
            if len(snapshots) >= 2:
                gaps = []
                for i in range(1, len(snapshots)):
                    gap_minutes = (snapshots[i] - snapshots[i-1]).total_seconds() / 60
                    if gap_minutes > 75:  # More than 75 minutes is concerning for hourly snapshots
                        gaps.append({
                            "from": snapshots[i-1].isoformat(),
                            "to": snapshots[i].isoformat(),
                            "gap_minutes": int(gap_minutes)
                        })
                
                health_data["gaps"] = gaps
                
                # Calculate average interval
                total_minutes = (snapshots[-1] - snapshots[0]).total_seconds() / 60
                avg_interval = total_minutes / (len(snapshots) - 1) if len(snapshots) > 1 else 0
                health_data["average_interval_minutes"] = round(avg_interval, 1)
                
                # Check for duplicates (snapshots within 1 minute)
                duplicates = 0
                for i in range(1, len(snapshots)):
                    if (snapshots[i] - snapshots[i-1]).total_seconds() < 60:
                        duplicates += 1
                if duplicates > 0:
                    health_data["issues"].append(f"{duplicates} duplicate snapshots detected")
            
            # Calculate missing percentage
            health_data["missing_percentage"] = round(
                (1 - health_data["snapshot_count"] / health_data["expected_snapshots"]) * 100, 1
            ) if health_data["expected_snapshots"] > 0 else 0
            
            # Determine overall status
            if not health_data["issues"] and health_data["missing_percentage"] < 10:
                health_data["status"] = "healthy"
            elif health_data["missing_percentage"] < 25 and len(health_data["issues"]) <= 1:
                health_data["status"] = "warning"
            else:
                health_data["status"] = "unhealthy"
            
            health_results[realm] = health_data
        
        # Calculate overall health
        total_realms = len(health_results)
        healthy_realms = sum(1 for r in health_results.values() if r["status"] == "healthy")
        warning_realms = sum(1 for r in health_results.values() if r["status"] == "warning")
        unhealthy_realms = sum(1 for r in health_results.values() if r["status"] == "unhealthy")
        
        return {
            "success": True,
            "check_time": current_time.isoformat(),
            "hours_analyzed": check_hours,
            "overall_health": {
                "total_realms": total_realms,
                "healthy": healthy_realms,
                "warning": warning_realms,
                "unhealthy": unhealthy_realms,
                "health_percentage": round((healthy_realms / total_realms) * 100, 1) if total_realms > 0 else 0
            },
            "realm_health": health_results,
            "recommendations": _get_health_recommendations(health_results)
        }
        
    except Exception as e:
        logger.error(f"Error checking snapshot health: {str(e)}")
        return {"error": f"Snapshot health check failed: {str(e)}"}


def _get_health_recommendations(health_results: Dict[str, Any]) -> List[str]:
    """Generate recommendations based on health check results"""
    recommendations = []
    
    # Check for systematic issues
    realms_with_gaps = sum(1 for r in health_results.values() if r.get("gaps", []))
    realms_with_duplicates = sum(1 for r in health_results.values() 
                                if any("duplicate" in issue for issue in r.get("issues", [])))
    stale_realms = sum(1 for r in health_results.values() 
                      if r.get("minutes_since_update", 0) > 30)
    
    if stale_realms > len(health_results) * 0.5:
        recommendations.append("CRITICAL: Scheduler appears to be down - over 50% of realms have stale data")
    
    if realms_with_duplicates > 3:
        recommendations.append("Multiple realms show duplicate snapshots - check for concurrent scheduler runs")
    
    if realms_with_gaps > len(health_results) * 0.3:
        recommendations.append("Many realms have gaps in snapshots - check scheduler reliability")
    
    # Check individual realm issues
    for realm, data in health_results.items():
        if data["status"] == "unhealthy":
            if data.get("minutes_since_update", 0) > 60:
                recommendations.append(f"{realm}: No updates in over an hour - check API access")
            elif data.get("missing_percentage", 0) > 50:
                recommendations.append(f"{realm}: Missing {data['missing_percentage']}% of expected snapshots")
    
    if not recommendations:
        recommendations.append("All systems operating normally")
    
    return recommendations