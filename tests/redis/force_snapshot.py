"""Force a new economy snapshot to test the encoding fix"""

import asyncio
import os
from dotenv import load_dotenv
import sys

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

# Import after adding to path
from app.mcp_server_fastmcp import get_or_initialize_services
from app.api.blizzard_client import BlizzardAPIClient
from datetime import datetime, timezone
import json
import redis.asyncio as aioredis

async def force_snapshot():
    """Force a new snapshot for testing"""
    print("Forcing new economy snapshot...")
    
    # Initialize services
    await get_or_initialize_services()
    
    # Get Redis client
    redis_url = os.getenv("REDIS_URL")
    if redis_url.startswith("rediss://"):
        redis_client = await aioredis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=False,
            max_connections=50,
            ssl_cert_reqs=None
        )
    else:
        redis_client = await aioredis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=False,
            max_connections=50
        )
    
    # Test simple storage first
    print("\nTesting simple Redis storage...")
    test_key = "test:encoding"
    test_data = {"test": True, "timestamp": datetime.now(timezone.utc).isoformat()}
    
    # Store with proper encoding
    await redis_client.setex(
        test_key,
        60,  # 60 seconds TTL
        json.dumps(test_data).encode()  # Encode to bytes
    )
    print(f"Stored test data: {test_data}")
    
    # Retrieve and decode
    retrieved = await redis_client.get(test_key)
    if retrieved:
        decoded = json.loads(retrieved.decode())
        print(f"Retrieved and decoded: {decoded}")
    
    # Now test with a mini snapshot
    print("\nCreating mini economy snapshot...")
    realm = "area-52"
    snapshot_key = f"economy_snapshot:retail:us:{realm}:test"
    
    mini_snapshot = {
        "realm": realm,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "test": True,
        "items": {
            "168487": {"avg_price": 1500, "quantity": 100}
        }
    }
    
    # Store latest snapshot
    await redis_client.setex(
        f"{snapshot_key}:latest",
        300,  # 5 minutes
        json.dumps(mini_snapshot).encode()
    )
    print(f"Stored test snapshot for {realm}")
    
    # Verify it's stored
    exists = await redis_client.exists(f"{snapshot_key}:latest")
    print(f"Snapshot exists: {exists}")
    
    # Clean up
    await redis_client.delete(test_key)
    await redis_client.aclose()
    
    print("\nTest completed!")

if __name__ == "__main__":
    asyncio.run(force_snapshot())