"""
WoW Data Staging Service - Intelligent Caching with API Fallbacks
"""

import asyncio
import json
import hashlib
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func

from ..models.wow_cache import (
    WoWDataCache, RealmStatus, AuctionSnapshot, 
    GuildCache, TokenPriceHistory, DataCollectionLog
)
from ..api.blizzard_client import BlizzardAPIClient, BlizzardAPIError
from ..utils.namespace_utils import get_dynamic_namespace, get_static_namespace

logger = logging.getLogger(__name__)

class WoWDataStagingService:
    """
    Intelligent data staging service for WoW API data
    """
    
    def __init__(self, db_session: AsyncSession, redis_client: aioredis.Redis):
        self.db = db_session
        self.redis = redis_client
        self.api_client = None  # Will be initialized when needed
        self.game_version = os.getenv("WOW_VERSION", "classic").lower()  # 'retail' or 'classic'
        
        # Cache TTL settings (in seconds)
        self.cache_ttl = {
            'auction': 3600,      # 1 hour (matches Blizzard's update frequency)
            'guild': 3600 * 6,    # 6 hours
            'realm': 3600 * 24,   # 24 hours
            'character': 3600 * 2, # 2 hours
            'token': 1800,        # 30 minutes
        }
    
    async def get_data(self, data_type: str, cache_key: str, region: str = 'us', 
                      force_refresh: bool = False, game_version: str = None) -> Optional[Dict[str, Any]]:
        """
        Get data with intelligent fallback strategy:
        1. Redis cache (fastest)
        2. PostgreSQL cache (persistent)
        3. Live API (when possible)
        4. Synthetic data (educational examples)
        """
        
        # Use provided game_version or default to instance's game_version
        version = game_version or self.game_version
        
        # Step 1: Try Redis cache first (unless force refresh)
        if not force_refresh:
            redis_key = f"{data_type}:{region}:{cache_key}:{version}"
            cached_data = await self.redis.get(redis_key)
            if cached_data:
                logger.debug(f"Cache hit (Redis): {redis_key}")
                return json.loads(cached_data)
        
        # Step 2: Try PostgreSQL cache
        if not force_refresh:
            db_data = await self._get_from_database(data_type, cache_key, region, version)
            if db_data:
                logger.debug(f"Cache hit (PostgreSQL): {data_type}:{cache_key}")
                # Refresh Redis cache
                await self._cache_to_redis(data_type, cache_key, region, db_data, version)
                return db_data
        
        # Step 3: Try live API
        try:
            if not self.api_client:
                self.api_client = BlizzardAPIClient()
                await self.api_client.__aenter__()
            
            live_data = await self._fetch_from_api(data_type, cache_key, region)
            if live_data:
                logger.info(f"Live API success: {data_type}:{cache_key}")
                # Cache in both systems
                await self._cache_data(data_type, cache_key, region, live_data, version)
                return live_data
                
        except Exception as e:
            logger.warning(f"Live API failed for {data_type}:{cache_key}: {str(e)}")
            await self._log_collection_attempt(data_type, cache_key, region, 'failed', str(e))
        
        # Step 4: Generate synthetic/example data
        logger.info(f"Generating example data for {data_type}:{cache_key}")
        synthetic_data = await self._generate_example_data(data_type, cache_key, region)
        return synthetic_data
    
    async def _get_from_database(self, data_type: str, cache_key: str, region: str, game_version: str) -> Optional[Dict[str, Any]]:
        """Retrieve data from PostgreSQL cache"""
        try:
            # Check if data is still valid (not expired)
            now = datetime.utcnow()
            
            stmt = select(WoWDataCache).where(
                and_(
                    WoWDataCache.data_type == data_type,
                    WoWDataCache.cache_key == cache_key,
                    WoWDataCache.region == region,
                    WoWDataCache.game_version == game_version,
                    WoWDataCache.is_valid == True,
                    # Either no expiration or not expired
                    (WoWDataCache.expires_at.is_(None)) | (WoWDataCache.expires_at > now)
                )
            ).order_by(desc(WoWDataCache.timestamp)).limit(1)
            
            result = await self.db.execute(stmt)
            cache_entry = result.scalar_one_or_none()
            
            if cache_entry:
                return {
                    'data': cache_entry.data,
                    'timestamp': cache_entry.timestamp,
                    'age_hours': (now - cache_entry.timestamp).total_seconds() / 3600
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Database cache error: {str(e)}")
            return None
    
    async def _cache_data(self, data_type: str, cache_key: str, region: str, data: Dict[str, Any], game_version: str):
        """Cache data in both Redis and PostgreSQL"""
        try:
            # Cache in Redis
            await self._cache_to_redis(data_type, cache_key, region, data, game_version)
            
            # Cache in PostgreSQL
            await self._cache_to_database(data_type, cache_key, region, data, game_version)
            
        except Exception as e:
            logger.error(f"Caching error: {str(e)}")
    
    async def _cache_to_redis(self, data_type: str, cache_key: str, region: str, data: Dict[str, Any], game_version: str):
        """Cache data in Redis with TTL"""
        redis_key = f"{data_type}:{region}:{cache_key}:{game_version}"
        ttl = self.cache_ttl.get(data_type, 3600)
        
        await self.redis.setex(redis_key, ttl, json.dumps(data, default=str))
        logger.debug(f"Cached to Redis: {redis_key} (TTL: {ttl}s)")
    
    async def _cache_to_database(self, data_type: str, cache_key: str, region: str, data: Dict[str, Any], game_version: str):
        """Cache data in PostgreSQL with expiration"""
        try:
            # Calculate expiration time
            ttl = self.cache_ttl.get(data_type, 3600)
            expires_at = datetime.utcnow() + timedelta(seconds=ttl)
            
            # Create cache entry
            cache_entry = WoWDataCache(
                data_type=data_type,
                cache_key=cache_key,
                region=region,
                game_version=game_version,
                data=data.get('data', data),  # Handle nested data structure
                expires_at=expires_at,
                api_source='blizzard'
            )
            
            self.db.add(cache_entry)
            await self.db.commit()
            
            logger.debug(f"Cached to PostgreSQL: {data_type}:{cache_key}")
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"PostgreSQL caching error: {str(e)}")
    
    async def _fetch_from_api(self, data_type: str, cache_key: str, region: str) -> Optional[Dict[str, Any]]:
        """Fetch data from live Blizzard API"""
        
        # Determine namespace based on data type and game version
        if data_type in ['realm', 'token', 'auction']:
            data_namespace = get_dynamic_namespace(region, self.game_version)
        else:
            data_namespace = get_static_namespace(region, self.game_version)
        
        if data_type == 'realm':
            if cache_key == 'index':
                endpoint = "/data/wow/realm/index"
                params = {"namespace": data_namespace, "locale": "en_US"}
                return await self.api_client.make_request(endpoint, params)
            else:
                endpoint = f"/data/wow/realm/{cache_key}"
                params = {"namespace": data_namespace, "locale": "en_US"}
                return await self.api_client.make_request(endpoint, params)
        
        elif data_type == 'token':
            endpoint = "/data/wow/token/index"
            params = {"namespace": data_namespace, "locale": "en_US"}
            return await self.api_client.make_request(endpoint, params)
        
        elif data_type == 'guild':
            # cache_key format: "realm-slug:guild-name"
            realm_slug, guild_name = cache_key.split(':', 1)
            return await self.api_client.get_comprehensive_guild_data(realm_slug, guild_name)
        
        elif data_type == 'auction':
            # cache_key format: "realm-slug" or "connected-realm-id"
            realm_data = await self._get_realm_info(cache_key, region)
            if realm_data:
                connected_realm_href = realm_data.get("connected_realm", {}).get("href", "")
                if connected_realm_href:
                    connected_realm_id = connected_realm_href.split("/")[-1]
                    endpoint = f"/data/wow/connected-realm/{connected_realm_id}/auctions"
                    params = {"namespace": data_namespace, "locale": "en_US"}
                    return await self.api_client.make_request(endpoint, params)
        
        return None
    
    async def _get_realm_info(self, realm_slug: str, region: str) -> Optional[Dict[str, Any]]:
        """Helper to get realm information"""
        try:
            endpoint = f"/data/wow/realm/{realm_slug}"
            params = {"namespace": data_namespace, "locale": "en_US"}
            return await self.api_client.make_request(endpoint, params)
        except Exception:
            return None
    
    async def _generate_example_data(self, data_type: str, cache_key: str, region: str) -> Dict[str, Any]:
        """Generate realistic example data for demonstration"""
        
        if data_type == 'auction':
            return {
                'data': {
                    'auctions': [
                        {
                            'id': 12345,
                            'item': {'id': 171276},
                            'buyout': 1500000,  # 150g
                            'quantity': 1,
                            'time_left': 'LONG'
                        }
                    ] * 5000  # Simulate 5000 auctions
                },
                'realm': cache_key,
                'synthetic': True,
                'message': 'Example data - API currently restricted'
            }
        
        elif data_type == 'guild':
            realm_slug, guild_name = cache_key.split(':', 1)
            return {
                'data': {
                    'guild_info': {
                        'name': guild_name,
                        'realm': {'slug': realm_slug},
                        'member_count': 125,
                        'achievement_points': 15420
                    },
                    'members_data': [
                        {
                            'name': f'Player{i}',
                            'level': 80,
                            'character_class': {'name': 'Warrior'},
                            'guild_rank': 1 if i < 5 else 2,
                            'equipment_summary': {'average_item_level': 580 + (i % 20)}
                        } for i in range(20)
                    ]
                },
                'synthetic': True,
                'message': 'Example guild data - API currently restricted'
            }
        
        elif data_type == 'realm':
            return {
                'data': {
                    'name': cache_key.title().replace('-', ' '),
                    'slug': cache_key,
                    'population': {'name': 'High'},
                    'type': {'name': 'Normal'},
                    'timezone': 'America/New_York'
                },
                'synthetic': True,
                'message': 'Example realm data - API currently restricted'
            }
        
        elif data_type == 'token':
            return {
                'data': {
                    'price': 2500000,  # 250g
                    'last_updated_timestamp': int(datetime.now().timestamp())
                },
                'synthetic': True,
                'message': 'Example token price - API currently restricted'
            }
        
        return {
            'data': {},
            'synthetic': True,
            'message': f'No example data available for {data_type}'
        }
    
    async def _log_collection_attempt(self, collection_type: str, target: str, region: str, 
                                    status: str, error_message: str = None, records_collected: int = 0):
        """Log data collection attempts for monitoring"""
        try:
            log_entry = DataCollectionLog(
                collection_type=collection_type,
                target=target,
                region=region,
                status=status,
                error_message=error_message,
                records_collected=records_collected,
                timestamp=datetime.utcnow()
            )
            
            self.db.add(log_entry)
            await self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to log collection attempt: {str(e)}")
            await self.db.rollback()
    
    async def seed_data(self, data_types: List[str], targets: List[str], region: str = 'us') -> Dict[str, Any]:
        """
        Manually seed data when API is accessible
        """
        results = {
            'success': [],
            'failed': [],
            'total_records': 0
        }
        
        for data_type in data_types:
            for target in targets:
                try:
                    cache_key = target
                    if data_type == 'guild' and ':' not in target:
                        # Default to common realm if not specified
                        cache_key = f"stormrage:{target}"
                    
                    # Force refresh to get live data
                    data = await self.get_data(data_type, cache_key, region, force_refresh=True)
                    
                    if data and not data.get('synthetic'):
                        results['success'].append(f"{data_type}:{cache_key}")
                        records = 1
                        if data_type == 'auction':
                            records = len(data.get('data', {}).get('auctions', []))
                        results['total_records'] += records
                        
                        await self._log_collection_attempt(data_type, cache_key, region, 'success', records_collected=records)
                    else:
                        results['failed'].append(f"{data_type}:{cache_key} - API restriction")
                        await self._log_collection_attempt(data_type, cache_key, region, 'failed', 'API restriction')
                        
                except Exception as e:
                    error_msg = str(e)
                    results['failed'].append(f"{data_type}:{cache_key} - {error_msg}")
                    await self._log_collection_attempt(data_type, cache_key, region, 'failed', error_msg)
                
                # Rate limiting - be respectful
                await asyncio.sleep(0.5)
        
        return results
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about cached data"""
        try:
            # Count cached items by type
            stmt = select(
                WoWDataCache.data_type,
                func.count(WoWDataCache.id).label('count'),
                func.max(WoWDataCache.timestamp).label('latest')
            ).where(WoWDataCache.is_valid == True).group_by(WoWDataCache.data_type)
            
            result = await self.db.execute(stmt)
            cache_stats = result.all()
            
            stats = {
                'cache_entries': {row.data_type: row.count for row in cache_stats},
                'latest_updates': {row.data_type: row.latest for row in cache_stats},
                'total_cached_items': sum(row.count for row in cache_stats)
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get cache stats: {str(e)}")
            return {'error': str(e)}
    
    async def cleanup_expired_cache(self) -> int:
        """Remove expired cache entries"""
        try:
            now = datetime.utcnow()
            
            # Mark expired entries as invalid
            stmt = select(WoWDataCache).where(
                and_(
                    WoWDataCache.expires_at < now,
                    WoWDataCache.is_valid == True
                )
            )
            
            result = await self.db.execute(stmt)
            expired_entries = result.scalars().all()
            
            count = 0
            for entry in expired_entries:
                entry.is_valid = False
                count += 1
            
            await self.db.commit()
            logger.info(f"Marked {count} cache entries as expired")
            
            return count
            
        except Exception as e:
            logger.error(f"Failed to cleanup cache: {str(e)}")
            await self.db.rollback()
            return 0