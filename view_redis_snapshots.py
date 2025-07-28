"""Script to view stored economy snapshots in Redis"""

import asyncio
import json
import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import redis.asyncio as aioredis

# Load environment variables
load_dotenv()

async def view_snapshots():
    """View economy snapshots stored in Redis"""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    print(f"Connecting to Redis at: {redis_url[:50]}...")
    
    try:
        # Initialize Redis
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
        
        # Test connection
        await redis_client.ping()
        print("Connected to Redis successfully\n")
        
        # Find all economy snapshot keys
        print("Finding economy snapshot keys...")
        snapshot_keys = []
        latest_keys = []
        timestamp_keys = []
        last_update_keys = []
        
        async for key in redis_client.scan_iter(match="economy_snapshot:*"):
            key_str = key.decode() if isinstance(key, bytes) else key
            snapshot_keys.append(key_str)
            
            if key_str.endswith(":latest"):
                latest_keys.append(key_str)
            elif key_str.endswith(":last_update"):
                last_update_keys.append(key_str)
            elif "_" in key_str.split(":")[-1]:  # Timestamp format YYYYMMDD_HH
                timestamp_keys.append(key_str)
        
        print(f"\nTotal snapshot keys found: {len(snapshot_keys)}")
        print(f"  - Latest snapshots: {len(latest_keys)}")
        print(f"  - Timestamped snapshots: {len(timestamp_keys)}")
        print(f"  - Last update markers: {len(last_update_keys)}")
        
        # Show latest snapshots
        if latest_keys:
            print("\n=== LATEST SNAPSHOTS ===")
            for key in sorted(latest_keys)[:10]:  # Show first 10
                try:
                    data = await redis_client.get(key)
                    if data:
                        snapshot = json.loads(data.decode())
                        realm = snapshot.get('realm', 'unknown')
                        timestamp = snapshot.get('timestamp', 'unknown')
                        unique_items = snapshot.get('unique_items', 0)
                        total_auctions = snapshot.get('total_auctions', 0)
                        
                        # Parse timestamp
                        if timestamp != 'unknown':
                            ts = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            age = datetime.now(timezone.utc) - ts
                            age_str = f"{int(age.total_seconds() / 3600):.1f} hours ago"
                        else:
                            age_str = "unknown"
                        
                        print(f"\nRealm: {realm}")
                        print(f"  Key: {key}")
                        print(f"  Timestamp: {timestamp} ({age_str})")
                        print(f"  Unique items: {unique_items}")
                        print(f"  Total auctions: {total_auctions}")
                        
                        # Show TTL
                        ttl = await redis_client.ttl(key)
                        print(f"  TTL: {ttl} seconds ({ttl/3600:.1f} hours)")
                except Exception as e:
                    print(f"\nError reading {key}: {e}")
        
        # Show timestamped snapshots
        if timestamp_keys:
            print("\n=== TIMESTAMPED SNAPSHOTS (Historical) ===")
            # Group by realm
            by_realm = {}
            for key in timestamp_keys:
                parts = key.split(':')
                if len(parts) >= 4:
                    realm = parts[3]
                    if realm not in by_realm:
                        by_realm[realm] = []
                    by_realm[realm].append(key)
            
            for realm, keys in sorted(by_realm.items()):
                print(f"\n{realm}: {len(keys)} snapshots")
                # Show latest 3 for each realm
                for key in sorted(keys)[-3:]:
                    timestamp_part = key.split(':')[-1]
                    ttl = await redis_client.ttl(key)
                    print(f"  - {timestamp_part} (TTL: {ttl/86400:.1f} days)")
        
        # Show last update times
        if last_update_keys:
            print("\n=== LAST UPDATE TIMES ===")
            for key in sorted(last_update_keys):
                try:
                    last_update = await redis_client.get(key)
                    if last_update:
                        last_time = datetime.fromisoformat(last_update.decode())
                        age = datetime.now(timezone.utc) - last_time
                        realm = key.split(':')[3]
                        print(f"{realm}: {int(age.total_seconds() / 60)} minutes ago")
                except Exception as e:
                    print(f"Error reading {key}: {e}")
        
        # Check for guild roster cache
        print("\n=== GUILD ROSTER CACHE ===")
        roster_keys = []
        async for key in redis_client.scan_iter(match="guild_roster:*"):
            roster_keys.append(key.decode() if isinstance(key, bytes) else key)
        
        print(f"Guild roster keys found: {len(roster_keys)}")
        for key in sorted(roster_keys)[:5]:  # Show first 5
            ttl = await redis_client.ttl(key)
            print(f"  - {key} (TTL: {ttl/86400:.1f} days)")
        
        await redis_client.aclose()
        print("\nDone!")
        
    except Exception as e:
        print(f"\nError: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(view_snapshots())