#!/usr/bin/env python3
"""
Scheduled update script for Heroku Scheduler
Captures hourly economy snapshots for configured realms
"""

import asyncio
import os
import sys
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the capture function from the main server
from app.mcp_server_fastmcp import capture_economy_snapshot, get_or_initialize_services

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

async def run_scheduled_update():
    """Run the scheduled economy snapshot capture"""
    try:
        logger.info("Starting scheduled economy snapshot capture...")
        logger.info(f"Capturing snapshots for {len(REALMS_TO_CAPTURE)} realms")
        
        # Initialize services (Redis connection, etc.)
        await get_or_initialize_services()
        
        # Capture economy snapshots
        result = await capture_economy_snapshot(
            realms=REALMS_TO_CAPTURE,
            region="us",
            game_version="retail",
            force_update=False  # Only update if needed (respects hourly cache)
        )
        
        if result.get("success"):
            logger.info(f"Successfully captured snapshots:")
            logger.info(f"  - Snapshots created: {result['snapshots_created']}")
            logger.info(f"  - Snapshots skipped: {result['snapshots_skipped']}")
            
            # Log details for each realm
            realm_results = result.get('realm_results', {})
            for realm, status in realm_results.items():
                if status.get('status') == 'success':
                    logger.info(f"  ✓ {realm}: {status.get('unique_items')} items, {status.get('auctions')} auctions")
                elif status.get('status') == 'skipped':
                    logger.info(f"  - {realm}: Skipped (recent snapshot exists)")
                else:
                    logger.warning(f"  ✗ {realm}: {status.get('reason', 'Unknown error')}")
        else:
            logger.error(f"Failed to capture snapshots: {result.get('error')}")
            
    except Exception as e:
        logger.error(f"Error during scheduled update: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    logger.info("Scheduled update completed")

if __name__ == "__main__":
    # Run the async function
    asyncio.run(run_scheduled_update())