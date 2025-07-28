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

# Import and run the capture function
from app.mcp_server_fastmcp import capture_economy_snapshot, get_or_initialize_services

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
        await get_or_initialize_services()
        
        # Import the tool after initialization
        from app.mcp_server_fastmcp import capture_economy_snapshot
        
        # Get the actual function from the tool
        if hasattr(capture_economy_snapshot, 'fn'):
            # It's a FastMCP tool
            capture_fn = capture_economy_snapshot.fn
        else:
            # It's a regular function
            capture_fn = capture_economy_snapshot
        
        # Call the function
        result = await capture_fn(
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
                        print(f"  ✓ {realm}: {status.get('unique_items')} items")
                    elif status.get('status') == 'skipped':
                        print(f"  - {realm}: Skipped (recent snapshot exists)")
                    else:
                        print(f"  ✗ {realm}: {status.get('reason', 'Error')}")
        else:
            print(f"\nERROR: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"\nERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print(f"\n[{datetime.now()}] Scheduled update completed")

if __name__ == "__main__":
    asyncio.run(main())