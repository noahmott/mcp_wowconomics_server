#!/usr/bin/env python3
"""
Scheduled update script for Heroku Scheduler
Captures hourly economy snapshots for configured realms
"""

import asyncio
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import required modules
import json
from app.scheduler.capture_snapshots import capture_economy_snapshot
from app.core.service_manager import get_service_manager

# Configuration - realms to capture snapshots for
REALMS_TO_CAPTURE = [
    "area-52",
    "stormrage", 
    "illidan",
    "tichondrius",
    "mal'ganis",
    "zul'jin",
    "thrall",
    "lightbringer",
    "moonguard",
    "wyrmrest-accord"
]

async def main():
    """Main function to run the scheduled capture"""
    print(f"\n[{datetime.now()}] Starting scheduled economy snapshot capture...")
    print(f"Capturing snapshots for {len(REALMS_TO_CAPTURE)} realms")
    
    try:
        # Initialize services first
        service_mgr = await get_service_manager()
        redis_client = service_mgr.redis_client
        
        if not redis_client:
            print("ERROR: Redis not available")
            return
        
        # Use Redis lock to prevent concurrent executions
        lock_key = "economy_snapshot:scheduler_lock"
        lock_value = f"scheduler_{datetime.now().timestamp()}"
        
        # Try to acquire lock with 5 minute expiry
        lock_acquired = await redis_client.set(
            lock_key, 
            lock_value, 
            nx=True,  # Only set if not exists
            ex=300    # 5 minute expiry
        )
        
        if not lock_acquired:
            print(f"Another scheduler instance is running, skipping...")
            return
        
        print(f"Lock acquired, proceeding with snapshot capture...")
        
        # Call the function directly (it's not an MCP tool anymore)
        result = await capture_economy_snapshot(
            realms=REALMS_TO_CAPTURE,
            region="us",
            game_version="retail",
            force_update=False
        )
        
        if result.get("success"):
            print(f"\nSUCCESS! Captured economy snapshots:")
            print(f"  - Snapshots created: {result.get('snapshots_created', 0)}")
            print(f"  - Snapshots skipped: {result.get('snapshots_skipped', 0)}")
            
            # Show details
            realm_results = result.get('realm_results', {})
            if realm_results:
                print("\nRealm details:")
                for realm, status in realm_results.items():
                    if status.get('status') == 'success':
                        print(f"  [OK] {realm}: {status.get('unique_items')} items")
                    elif status.get('status') == 'skipped':
                        print(f"  [-] {realm}: Skipped (recent snapshot exists)")
                    else:
                        print(f"  [X] {realm}: {status.get('reason', 'Error')}")
        else:
            print(f"\nERROR: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"\nERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        
        # Try to log error to Redis if possible
        try:
            if 'redis_client' in locals() and redis_client:
                error_key = f"economy_snapshot:scheduler_error:{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                error_data = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "traceback": traceback.format_exc()
                }
                await redis_client.setex(error_key, 86400, json.dumps(error_data))  # Keep for 24 hours
                print(f"Error logged to Redis: {error_key}")
        except:
            pass
        
        sys.exit(1)
    
    # Release the lock
    if 'redis_client' in locals() and redis_client and 'lock_key' in locals():
        await redis_client.delete(lock_key)
        print(f"Lock released")
    
    print(f"\n[{datetime.now()}] Scheduled update completed")

if __name__ == "__main__":
    asyncio.run(main())