#!/usr/bin/env python3
"""
Script to completely wipe Redis cache
WARNING: This will delete ALL data in Redis!
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
import redis.asyncio as aioredis

# Load environment variables
load_dotenv()

async def wipe_redis():
    """Completely wipe all data from Redis"""
    redis_url = os.getenv("REDIS_URL")
    
    if not redis_url:
        print("ERROR: REDIS_URL not found in environment variables")
        return
    
    print("WARNING: This will DELETE ALL DATA from Redis!")
    print("This includes:")
    print("  - All economy snapshots")
    print("  - All cached data")
    print("  - All temporary keys")
    print("")
    
    # Get confirmation
    confirm = input("Type 'DELETE ALL' to confirm: ")
    if confirm != "DELETE ALL":
        print("Cancelled.")
        return
    
    print(f"\nConnecting to Redis...")
    
    # Connect to Redis
    if redis_url.startswith("rediss://"):
        redis_client = await aioredis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
            ssl_cert_reqs=None
        )
    else:
        redis_client = await aioredis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50
        )
    
    print("Connected to Redis successfully!")
    
    try:
        # Get memory info before
        info = await redis_client.info("memory")
        used_memory_before = info.get("used_memory_human", "Unknown")
        print(f"\nMemory used before: {used_memory_before}")
        
        # Count keys before deletion
        all_keys = await redis_client.keys("*")
        total_keys = len(all_keys)
        print(f"Total keys to delete: {total_keys}")
        
        if total_keys > 0:
            # Show sample of keys
            print("\nSample of keys to be deleted:")
            for key in all_keys[:10]:
                print(f"  - {key}")
            if total_keys > 10:
                print(f"  ... and {total_keys - 10} more keys")
            
            print("\nDeleting all keys...")
            
            # Delete all keys
            deleted = 0
            batch_size = 1000
            for i in range(0, total_keys, batch_size):
                batch = all_keys[i:i+batch_size]
                if batch:
                    await redis_client.delete(*batch)
                    deleted += len(batch)
                    print(f"  Deleted {deleted}/{total_keys} keys...")
            
            print(f"\nSuccessfully deleted {deleted} keys!")
        else:
            print("\nNo keys found in Redis.")
            
        # Always flush to ensure complete cleanup
        await redis_client.flushdb()
        print("Database flushed completely.")
        
        # Get memory info after
        info = await redis_client.info("memory")
        used_memory_after = info.get("used_memory_human", "Unknown")
        max_memory = info.get("maxmemory_human", "Unknown")
        
        print(f"\nMemory used after: {used_memory_after}")
        print(f"Max memory limit: {max_memory}")
        
        # Also show some other useful stats
        print(f"\nRedis Info:")
        print(f"  Total connections received: {info.get('total_connections_received', 'Unknown')}")
        print(f"  Connected clients: {info.get('connected_clients', 'Unknown')}")
        
    except Exception as e:
        print(f"\nERROR: {type(e).__name__}: {e}")
        raise
    
    finally:
        await redis_client.aclose()
        print("\nRedis connection closed.")

if __name__ == "__main__":
    asyncio.run(wipe_redis())