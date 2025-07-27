"""
Redis-based WoW Data Staging Service
Replaces SQLite/PostgreSQL with Redis for all staging operations
"""

import asyncio
import json
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union
import redis.asyncio as aioredis

from ..api.blizzard_client import BlizzardAPIClient, BlizzardAPIError
from ..utils.namespace_utils import get_dynamic_namespace, get_static_namespace

logger = logging.getLogger(__name__)


class RedisDataStagingService:
    """
    Redis-only data staging service for WoW API data
    """
    
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self.api_client = None  # Will be initialized when needed
        self.game_version = "retail"  # Default to retail
        
        # Cache TTL settings (in seconds)
        self.cache_ttl = {
            'auction': 3600,        # 1 hour
            'guild': 3600 * 6,      # 6 hours
            'realm': 3600 * 24,     # 24 hours
            'character': 3600 * 2,  # 2 hours
            'token': 1800,          # 30 minutes
            'guild_roster': 3600,   # 1 hour
            'guild_info': 3600 * 6, # 6 hours
        }
        
        # Key prefixes for organization
        self.key_prefixes = {
            'cache': 'wow:cache',
            'meta': 'wow:meta',
            'stats': 'wow:stats',
            'log': 'wow:log',
            'index': 'wow:index'
        }
    
    def _make_cache_key(self, data_type: str, cache_key: str, region: str = 'us', 
                       game_version: Optional[str] = None) -> str:
        """Generate Redis key for caching"""
        version = game_version or self.game_version
        return f"{self.key_prefixes['cache']}:{data_type}:{region}:{version}:{cache_key}"
    
    def _make_meta_key(self, data_type: str, cache_key: str, region: str = 'us',
                      game_version: Optional[str] = None) -> str:
        """Generate Redis key for metadata"""
        version = game_version or self.game_version
        return f"{self.key_prefixes['meta']}:{data_type}:{region}:{version}:{cache_key}"
    
    async def get_data(self, data_type: str, cache_key: str, region: str = 'us', 
                      force_refresh: bool = False, game_version: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get data with Redis caching and API fallback
        """
        version = game_version or self.game_version
        
        # Step 1: Try Redis cache (unless force refresh)
        if not force_refresh:
            redis_key = self._make_cache_key(data_type, cache_key, region, version)
            cached_data = await self.redis.get(redis_key)
            
            if cached_data:
                logger.debug(f"Cache hit: {redis_key}")
                
                # Get metadata
                meta_key = self._make_meta_key(data_type, cache_key, region, version)
                metadata = await self.redis.hgetall(meta_key)
                
                data = json.loads(cached_data)
                data['_metadata'] = {
                    'cached_at': metadata.get(b'cached_at', b'').decode('utf-8'),
                    'source': metadata.get(b'source', b'api').decode('utf-8'),
                    'ttl': await self.redis.ttl(redis_key)
                }
                
                # Update stats
                await self._increment_stat('cache_hits', data_type)
                
                return data
        
        # Step 2: Try live API
        try:
            if not self.api_client:
                self.api_client = BlizzardAPIClient(game_version=version)
                await self.api_client.__aenter__()
            
            live_data = await self._fetch_from_api(data_type, cache_key, region)
            if live_data:
                logger.info(f"Live API success: {data_type}:{cache_key}")
                
                # Cache the data
                await self._cache_data(data_type, cache_key, region, live_data, version)
                
                # Update stats
                await self._increment_stat('api_calls', data_type)
                
                return live_data
                
        except Exception as e:
            logger.warning(f"Live API failed for {data_type}:{cache_key}: {str(e)}")
            await self._log_error(data_type, cache_key, region, str(e))
            
            # Update stats
            await self._increment_stat('api_errors', data_type)
        
        # Step 3: Generate synthetic/example data for testing
        logger.info(f"Generating example data for {data_type}:{cache_key}")
        synthetic_data = await self._generate_example_data(data_type, cache_key, region)
        
        # Cache synthetic data with shorter TTL
        await self._cache_data(data_type, cache_key, region, synthetic_data, version, 
                             ttl_override=300)  # 5 minutes for synthetic data
        
        return synthetic_data
    
    async def _cache_data(self, data_type: str, cache_key: str, region: str, 
                         data: Dict[str, Any], game_version: str, ttl_override: Optional[int] = None):
        """Cache data in Redis with metadata"""
        try:
            # Main data key
            redis_key = self._make_cache_key(data_type, cache_key, region, game_version)
            ttl = ttl_override or self.cache_ttl.get(data_type, 3600)
            
            # Store the data
            await self.redis.setex(redis_key, ttl, json.dumps(data, default=str))
            
            # Store metadata
            meta_key = self._make_meta_key(data_type, cache_key, region, game_version)
            metadata = {
                'cached_at': datetime.utcnow().isoformat(),
                'source': 'synthetic' if data.get('synthetic') else 'api',
                'data_type': data_type,
                'cache_key': cache_key,
                'region': region,
                'game_version': game_version,
                'ttl': ttl
            }
            await self.redis.hset(meta_key, mapping=metadata)
            await self.redis.expire(meta_key, ttl)
            
            # Update index
            index_key = f"{self.key_prefixes['index']}:{data_type}:{region}:{game_version}"
            await self.redis.sadd(index_key, cache_key)
            
            logger.debug(f"Cached to Redis: {redis_key} (TTL: {ttl}s)")
            
        except Exception as e:
            logger.error(f"Redis caching error: {str(e)}")
    
    async def _fetch_from_api(self, data_type: str, cache_key: str, region: str) -> Optional[Dict[str, Any]]:
        """Fetch data from live Blizzard API"""
        
        if data_type == 'guild':
            # cache_key format: "realm-slug:guild-name"
            parts = cache_key.split(':', 1)
            if len(parts) == 2:
                realm_slug, guild_name = parts
                return await self.api_client.get_comprehensive_guild_data(realm_slug, guild_name)
        
        elif data_type == 'guild_roster':
            # cache_key format: "realm-slug:guild-name"
            parts = cache_key.split(':', 1)
            if len(parts) == 2:
                realm_slug, guild_name = parts
                return await self.api_client.get_guild_roster(realm_slug, guild_name)
        
        elif data_type == 'guild_info':
            # cache_key format: "realm-slug:guild-name"
            parts = cache_key.split(':', 1)
            if len(parts) == 2:
                realm_slug, guild_name = parts
                return await self.api_client.get_guild_info(realm_slug, guild_name)
        
        elif data_type == 'character':
            # cache_key format: "realm-slug:character-name"
            parts = cache_key.split(':', 1)
            if len(parts) == 2:
                realm_slug, character_name = parts
                return await self.api_client.get_character_profile(realm_slug, character_name)
        
        elif data_type == 'realm':
            if cache_key == 'index':
                endpoint = "/data/wow/realm/index"
                return await self.api_client.make_request(endpoint)
            else:
                endpoint = f"/data/wow/realm/{cache_key}"
                return await self.api_client.make_request(endpoint)
        
        elif data_type == 'token':
            endpoint = "/data/wow/token/index"
            return await self.api_client.make_request(endpoint)
        
        return None
    
    async def _generate_example_data(self, data_type: str, cache_key: str, region: str) -> Dict[str, Any]:
        """Generate realistic example data for demonstration"""
        
        if data_type in ['guild', 'guild_info']:
            parts = cache_key.split(':', 1)
            realm_slug = parts[0] if parts else 'unknown-realm'
            guild_name = parts[1] if len(parts) > 1 else 'Unknown Guild'
            
            return {
                'guild_info': {
                    'name': guild_name,
                    'realm': {'slug': realm_slug, 'name': realm_slug.title().replace('-', ' ')},
                    'faction': {'type': 'HORDE', 'name': 'Horde'},
                    'member_count': 125,
                    'achievement_points': 15420,
                    'created_timestamp': int((datetime.utcnow() - timedelta(days=365)).timestamp() * 1000)
                },
                'members_data': [
                    {
                        'name': f'Player{i}',
                        'level': 70,
                        'character_class': {
                            'id': (i % 12) + 1,
                            'name': ['Warrior', 'Paladin', 'Hunter', 'Rogue', 'Priest', 'Death Knight',
                                    'Shaman', 'Mage', 'Warlock', 'Monk', 'Druid', 'Demon Hunter'][i % 12]
                        },
                        'guild_rank': 1 if i < 3 else 2 if i < 10 else 3,
                        'equipment_summary': {'average_item_level': 440 + (i % 20)}
                    } for i in range(20)
                ],
                'synthetic': True,
                'message': 'Example guild data for testing'
            }
        
        elif data_type == 'guild_roster':
            parts = cache_key.split(':', 1)
            guild_name = parts[1] if len(parts) > 1 else 'Unknown Guild'
            
            return {
                'guild': {'name': guild_name},
                'members': [
                    {
                        'character': {
                            'name': f'Player{i}',
                            'id': 1000 + i,
                            'realm': {'slug': parts[0] if parts else 'unknown-realm'},
                            'level': 70,
                            'playable_class': {'id': (i % 12) + 1}
                        },
                        'rank': 1 if i < 3 else 2 if i < 10 else 3
                    } for i in range(50)
                ],
                'synthetic': True
            }
        
        elif data_type == 'character':
            parts = cache_key.split(':', 1)
            character_name = parts[1] if len(parts) > 1 else 'Unknown'
            
            return {
                'name': character_name,
                'level': 70,
                'achievement_points': 12500,
                'character_class': {'name': 'Warrior'},
                'active_spec': {'name': 'Protection'},
                'equipment_summary': {'average_item_level': 450},
                'synthetic': True
            }
        
        elif data_type == 'realm':
            return {
                'name': cache_key.title().replace('-', ' '),
                'slug': cache_key,
                'population': {'type': 'HIGH', 'name': 'High'},
                'type': {'type': 'NORMAL', 'name': 'Normal'},
                'timezone': 'America/New_York',
                'synthetic': True
            }
        
        elif data_type == 'token':
            return {
                'price': 250000,  # 25g in copper
                'last_updated_timestamp': int(datetime.utcnow().timestamp() * 1000),
                'synthetic': True
            }
        
        return {
            'error': 'Unknown data type',
            'synthetic': True,
            'data_type': data_type
        }
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about cached data"""
        try:
            stats = {}
            
            # Get all stats keys
            stats_pattern = f"{self.key_prefixes['stats']}:*"
            stats_keys = []
            async for key in self.redis.scan_iter(match=stats_pattern):
                stats_keys.append(key)
            
            # Get stat values
            for key in stats_keys:
                key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                stat_name = key_str.split(':')[-1]
                value = await self.redis.get(key)
                stats[stat_name] = int(value) if value else 0
            
            # Count cached items by type
            cache_counts = {}
            for data_type in ['guild', 'character', 'realm', 'token', 'guild_roster', 'guild_info']:
                pattern = f"{self.key_prefixes['cache']}:{data_type}:*"
                count = 0
                async for _ in self.redis.scan_iter(match=pattern):
                    count += 1
                cache_counts[data_type] = count
            
            # Get Redis info
            info = await self.redis.info()
            
            return {
                'cache_counts': cache_counts,
                'total_cached_items': sum(cache_counts.values()),
                'stats': stats,
                'redis_info': {
                    'used_memory_human': info.get('used_memory_human', 'N/A'),
                    'connected_clients': info.get('connected_clients', 0),
                    'total_commands_processed': info.get('total_commands_processed', 0)
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get cache stats: {str(e)}")
            return {'error': str(e)}
    
    async def clear_cache(self, data_type: Optional[str] = None, 
                         region: Optional[str] = None) -> int:
        """Clear cache entries"""
        try:
            if data_type and region:
                pattern = f"{self.key_prefixes['cache']}:{data_type}:{region}:*"
            elif data_type:
                pattern = f"{self.key_prefixes['cache']}:{data_type}:*"
            else:
                pattern = f"{self.key_prefixes['cache']}:*"
            
            count = 0
            keys_to_delete = []
            
            async for key in self.redis.scan_iter(match=pattern):
                keys_to_delete.append(key)
                count += 1
                
                # Delete in batches
                if len(keys_to_delete) >= 100:
                    await self.redis.delete(*keys_to_delete)
                    keys_to_delete = []
            
            # Delete remaining keys
            if keys_to_delete:
                await self.redis.delete(*keys_to_delete)
            
            logger.info(f"Cleared {count} cache entries")
            return count
            
        except Exception as e:
            logger.error(f"Failed to clear cache: {str(e)}")
            return 0
    
    async def _increment_stat(self, stat_name: str, data_type: str):
        """Increment a statistics counter"""
        try:
            key = f"{self.key_prefixes['stats']}:{stat_name}:{data_type}"
            await self.redis.incr(key)
            
            # Set expiration to 7 days
            await self.redis.expire(key, 7 * 24 * 3600)
        except Exception as e:
            logger.error(f"Failed to increment stat {stat_name}: {str(e)}")
    
    async def _log_error(self, data_type: str, cache_key: str, region: str, error: str):
        """Log errors to Redis"""
        try:
            log_key = f"{self.key_prefixes['log']}:errors:{datetime.utcnow().strftime('%Y%m%d')}"
            log_entry = {
                'timestamp': datetime.utcnow().isoformat(),
                'data_type': data_type,
                'cache_key': cache_key,
                'region': region,
                'error': error
            }
            
            await self.redis.lpush(log_key, json.dumps(log_entry))
            await self.redis.ltrim(log_key, 0, 999)  # Keep last 1000 errors
            await self.redis.expire(log_key, 7 * 24 * 3600)  # 7 days
            
        except Exception as e:
            logger.error(f"Failed to log error: {str(e)}")
    
    async def close(self):
        """Close connections"""
        if self.api_client:
            await self.api_client.__aexit__(None, None, None)