"""
Standalone capture function for Heroku scheduler
This doesn't require MCP initialization
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

from ..api.blizzard_client import BlizzardAPIClient
from ..services.auction_aggregator import AuctionAggregatorService
from ..utils.namespace_utils import get_connected_realm_id
from ..core.service_manager import get_service_manager

logger = logging.getLogger(__name__)
auction_aggregator = AuctionAggregatorService()


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
        service_mgr = await get_service_manager()
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
                            # Decode bytes to string if necessary
                            if isinstance(last_update, bytes):
                                last_update = last_update.decode('utf-8')
                            last_time = datetime.fromisoformat(last_update)
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
                    
                    # Update last snapshot time (define the variable here)
                    last_snapshot_time_key = f"{snapshot_key}:last_update"
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