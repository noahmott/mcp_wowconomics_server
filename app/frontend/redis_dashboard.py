"""
Redis Dashboard Frontend

Provides a web interface to view Redis data, activity logs, and server statistics.
"""
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import aioredis
from ..services.redis_staging import RedisDataStagingService


router = APIRouter(prefix="/dashboard", tags=["dashboard"])
templates = Jinja2Templates(directory="app/frontend/templates")


async def get_redis_client() -> aioredis.Redis:
    """Get Redis client"""
    redis_url = "redis://localhost:6379"
    return await aioredis.from_url(redis_url)


class RedisDashboard:
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self.key_prefixes = {
            'cache': 'wow:cache',
            'meta': 'wow:meta',
            'stats': 'wow:stats',
            'log': 'wow:log',
            'activity': 'wow:activity',
            'sessions': 'wow:sessions',
            'index': 'wow:index'
        }
    
    async def get_overview_stats(self) -> Dict[str, Any]:
        """Get Redis overview statistics"""
        try:
            info = await self.redis.info()
            
            # Count keys by type
            key_counts = {}
            for prefix_name, prefix in self.key_prefixes.items():
                count = 0
                async for _ in self.redis.scan_iter(match=f"{prefix}:*"):
                    count += 1
                key_counts[prefix_name] = count
            
            # Get basic stats
            total_keys = await self.redis.dbsize()
            memory_usage = info.get('used_memory_human', 'N/A')
            uptime = info.get('uptime_in_seconds', 0)
            
            return {
                'total_keys': total_keys,
                'memory_usage': memory_usage,
                'uptime_seconds': uptime,
                'uptime_formatted': str(timedelta(seconds=uptime)),
                'key_breakdown': key_counts,
                'redis_version': info.get('redis_version', 'Unknown'),
                'connected_clients': info.get('connected_clients', 0),
                'commands_processed': info.get('total_commands_processed', 0)
            }
        except Exception as e:
            return {'error': str(e)}
    
    async def get_cache_data(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get cached data entries"""
        try:
            cache_entries = []
            count = 0
            
            async for key in self.redis.scan_iter(match=f"{self.key_prefixes['cache']}:*"):
                if count >= limit:
                    break
                
                key_str = key.decode('utf-8')
                ttl = await self.redis.ttl(key)
                
                # Parse key components
                parts = key_str.split(':')
                if len(parts) >= 4:
                    data_type = parts[2]
                    region = parts[3] if len(parts) > 3 else 'unknown'
                    version = parts[4] if len(parts) > 4 else 'unknown'
                    cache_key = ':'.join(parts[5:]) if len(parts) > 5 else 'unknown'
                    
                    # Get metadata
                    meta_key = f"{self.key_prefixes['meta']}:{':'.join(parts[2:])}"
                    metadata = await self.redis.hgetall(meta_key)
                    
                    cache_entries.append({
                        'key': key_str,
                        'data_type': data_type,
                        'region': region,
                        'version': version,
                        'cache_key': cache_key,
                        'ttl_seconds': ttl if ttl > 0 else None,
                        'expires_in': f"{ttl // 60}m {ttl % 60}s" if ttl > 0 else "Expired",
                        'cached_at': metadata.get(b'cached_at', b'').decode('utf-8') if metadata else '',
                        'source': metadata.get(b'source', b'unknown').decode('utf-8') if metadata else ''
                    })
                    count += 1
            
            return sorted(cache_entries, key=lambda x: x.get('cached_at', ''), reverse=True)
        except Exception as e:
            return [{'error': str(e)}]
    
    async def get_activity_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent activity logs"""
        try:
            logs = []
            count = 0
            
            # Get activity logs sorted by timestamp
            async for key in self.redis.scan_iter(match=f"{self.key_prefixes['activity']}:*"):
                if count >= limit:
                    break
                
                data = await self.redis.get(key)
                if data:
                    try:
                        log_entry = json.loads(data.decode('utf-8'))
                        logs.append(log_entry)
                        count += 1
                    except json.JSONDecodeError:
                        continue
            
            return sorted(logs, key=lambda x: x.get('timestamp', ''), reverse=True)
        except Exception as e:
            return [{'error': str(e)}]
    
    async def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Get active MCP sessions"""
        try:
            sessions = []
            
            async for key in self.redis.scan_iter(match=f"{self.key_prefixes['sessions']}:*"):
                data = await self.redis.get(key)
                if data:
                    try:
                        session_data = json.loads(data.decode('utf-8'))
                        ttl = await self.redis.ttl(key)
                        session_data['ttl_seconds'] = ttl
                        sessions.append(session_data)
                    except json.JSONDecodeError:
                        continue
            
            return sorted(sessions, key=lambda x: x.get('created_at', ''), reverse=True)
        except Exception as e:
            return [{'error': str(e)}]
    
    async def search_keys(self, pattern: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search Redis keys by pattern"""
        try:
            results = []
            count = 0
            
            async for key in self.redis.scan_iter(match=f"*{pattern}*"):
                if count >= limit:
                    break
                
                key_str = key.decode('utf-8')
                key_type = await self.redis.type(key)
                ttl = await self.redis.ttl(key)
                
                results.append({
                    'key': key_str,
                    'type': key_type.decode('utf-8'),
                    'ttl': ttl if ttl > 0 else None
                })
                count += 1
            
            return results
        except Exception as e:
            return [{'error': str(e)}]


@router.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request, redis: aioredis.Redis = Depends(get_redis_client)):
    """Dashboard home page"""
    dashboard = RedisDashboard(redis)
    stats = await dashboard.get_overview_stats()
    await redis.close()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "stats": stats
    })


@router.get("/api/stats")
async def get_stats(redis: aioredis.Redis = Depends(get_redis_client)):
    """Get Redis statistics API"""
    dashboard = RedisDashboard(redis)
    stats = await dashboard.get_overview_stats()
    await redis.close()
    return JSONResponse(stats)


@router.get("/api/cache")
async def get_cache_data(limit: int = 50, redis: aioredis.Redis = Depends(get_redis_client)):
    """Get cache data API"""
    dashboard = RedisDashboard(redis)
    cache_data = await dashboard.get_cache_data(limit)
    await redis.close()
    return JSONResponse(cache_data)


@router.get("/api/activity")
async def get_activity_logs(limit: int = 100, redis: aioredis.Redis = Depends(get_redis_client)):
    """Get activity logs API"""
    dashboard = RedisDashboard(redis)
    logs = await dashboard.get_activity_logs(limit)
    await redis.close()
    return JSONResponse(logs)


@router.get("/api/sessions")
async def get_active_sessions(redis: aioredis.Redis = Depends(get_redis_client)):
    """Get active sessions API"""
    dashboard = RedisDashboard(redis)
    sessions = await dashboard.get_active_sessions()
    await redis.close()
    return JSONResponse(sessions)


@router.get("/api/search")
async def search_redis_keys(pattern: str, limit: int = 50, redis: aioredis.Redis = Depends(get_redis_client)):
    """Search Redis keys API"""
    if not pattern or len(pattern) < 2:
        raise HTTPException(status_code=400, detail="Pattern must be at least 2 characters")
    
    dashboard = RedisDashboard(redis)
    results = await dashboard.search_keys(pattern, limit)
    await redis.close()
    return JSONResponse(results)


@router.get("/cache", response_class=HTMLResponse)
async def cache_page(request: Request, redis: aioredis.Redis = Depends(get_redis_client)):
    """Cache data page"""
    dashboard = RedisDashboard(redis)
    cache_data = await dashboard.get_cache_data()
    await redis.close()
    
    return templates.TemplateResponse("cache.html", {
        "request": request,
        "cache_data": cache_data
    })


@router.get("/activity", response_class=HTMLResponse)
async def activity_page(request: Request, redis: aioredis.Redis = Depends(get_redis_client)):
    """Activity logs page"""
    dashboard = RedisDashboard(redis)
    logs = await dashboard.get_activity_logs()
    await redis.close()
    
    return templates.TemplateResponse("activity.html", {
        "request": request,
        "logs": logs
    })


@router.get("/sessions", response_class=HTMLResponse)
async def sessions_page(request: Request, redis: aioredis.Redis = Depends(get_redis_client)):
    """Active sessions page"""
    dashboard = RedisDashboard(redis)
    sessions = await dashboard.get_active_sessions()
    await redis.close()
    
    return templates.TemplateResponse("sessions.html", {
        "request": request,
        "sessions": sessions
    })