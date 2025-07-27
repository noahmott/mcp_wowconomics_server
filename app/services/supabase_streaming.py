"""
Supabase Streaming Service

Streams activity logs and real-time events to Supabase while keeping guild data in Redis for performance.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

import redis.asyncio as aioredis

from .supabase_client import (
    SupabaseRealTimeClient, 
    ActivityLogEntry,
    get_supabase_client
)

logger = logging.getLogger(__name__)


class SupabaseStreamingService:
    """Service to stream activity logs and events to Supabase while keeping guild data in Redis"""
    
    def __init__(self, redis_client: aioredis.Redis, supabase_client: SupabaseRealTimeClient = None):
        self.redis = redis_client
        self.supabase_client = supabase_client
        self.streaming_active = False
        self.stream_tasks = []
        
        # Only monitor activity logs and sessions for Supabase streaming
        # Guild data stays in Redis for performance
        self.key_patterns = {
            'activity': 'wow:activity:*',
            'sessions': 'wow:sessions:*',
            'daily_stats': 'wow:daily:*'
        }
    
    async def initialize(self) -> None:
        """Initialize the streaming service"""
        try:
            if not self.supabase_client:
                self.supabase_client = await get_supabase_client()
            
            logger.info("Supabase streaming service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize streaming service: {e}")
            raise
    
    async def start_streaming(self) -> None:
        """Start streaming activity logs and events to Supabase"""
        try:
            if self.streaming_active:
                logger.warning("Streaming already active")
                return
            
            self.streaming_active = True
            
            # Start monitoring tasks for activity logs and sessions only
            # Guild data remains in Redis for fast access
            activity_task = asyncio.create_task(self._monitor_activity_logs())
            sessions_task = asyncio.create_task(self._monitor_sessions())
            stats_task = asyncio.create_task(self._monitor_daily_stats())
            
            self.stream_tasks = [activity_task, sessions_task, stats_task]
            
            logger.info("Supabase streaming started (activity logs and sessions only)")
            
        except Exception as e:
            logger.error(f"Error starting streaming: {e}")
            self.streaming_active = False
            raise
    
    async def stop_streaming(self) -> None:
        """Stop streaming Redis data to Supabase"""
        try:
            self.streaming_active = False
            
            # Cancel all streaming tasks
            for task in self.stream_tasks:
                if not task.done():
                    task.cancel()
            
            # Wait for tasks to complete
            if self.stream_tasks:
                await asyncio.gather(*self.stream_tasks, return_exceptions=True)
            
            self.stream_tasks = []
            logger.info("Supabase streaming stopped")
            
        except Exception as e:
            logger.error(f"Error stopping streaming: {e}")
    
    async def stream_activity_log_entry(self, log_id: str, log_data: Dict[str, Any]) -> bool:
        """Stream a single activity log entry to Supabase"""
        try:
            if not self.supabase_client:
                await self.initialize()
            
            # Convert Redis log data to Supabase format
            activity_entry = ActivityLogEntry(
                id=log_data.get('log_id', log_id),
                session_id=log_data.get('session_id', ''),
                activity_type=log_data.get('activity_type', ''),
                timestamp=log_data.get('timestamp', datetime.now(timezone.utc).isoformat()),
                tool_name=log_data.get('tool_name'),
                request_data=log_data.get('request_data'),
                response_data=log_data.get('response_data'),
                error_message=log_data.get('error_message'),
                duration_ms=log_data.get('duration_ms'),
                reasoning=log_data.get('reasoning'),
                metadata=log_data.get('metadata')
            )
            
            # Stream to Supabase
            success = await self.supabase_client.stream_activity_log(activity_entry)
            
            if success:
                # Also broadcast the update
                await self.supabase_client.broadcast_activity_update({
                    'type': 'new_activity',
                    'data': activity_entry.__dict__
                })
            
            return success
            
        except Exception as e:
            logger.error(f"Error streaming activity log entry: {e}")
            return False
    
    async def stream_session_event(self, session_id: str, session_data: Dict[str, Any]) -> bool:
        """Stream session events to Supabase for real-time monitoring"""
        try:
            if not self.supabase_client:
                await self.initialize()
            
            # Create a simplified session event for Supabase
            session_event = {
                'session_id': session_id,
                'client_info': session_data.get('client_info', {}),
                'created_at': session_data.get('created_at', ''),
                'last_activity': session_data.get('last_activity', ''),
                'request_count': session_data.get('request_count', 0),
                'user_agent': session_data.get('user_agent'),
                'ip_address': session_data.get('ip_address'),
                'event_type': 'session_update',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            # Broadcast session update via real-time channel
            success = await self.supabase_client.broadcast_activity_update({
                'type': 'session_event',
                'data': session_event
            })
            
            return success
            
        except Exception as e:
            logger.error(f"Error streaming session event: {e}")
            return False
    
    async def stream_stats_event(self, stat_key: str, stat_value: int) -> bool:
        """Stream daily stats events to Supabase for monitoring"""
        try:
            if not self.supabase_client:
                await self.initialize()
            
            # Parse stat key: wow:daily:{date}:{stat_name}
            key_parts = stat_key.split(':')
            if len(key_parts) >= 4:
                date = key_parts[2]
                stat_name = key_parts[3]
                
                stats_event = {
                    'date': date,
                    'stat_name': stat_name,
                    'value': stat_value,
                    'event_type': 'stats_update',
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                
                # Broadcast stats update
                success = await self.supabase_client.broadcast_activity_update({
                    'type': 'stats_event',
                    'data': stats_event
                })
                
                return success
            
            return False
            
        except Exception as e:
            logger.error(f"Error streaming stats event: {e}")
            return False
    
    async def _monitor_activity_logs(self) -> None:
        """Monitor Redis for new activity logs"""
        try:
            processed_keys = set()
            
            while self.streaming_active:
                try:
                    # Scan for activity log keys
                    async for key in self.redis.scan_iter(match=self.key_patterns['activity']):
                        key_str = key.decode('utf-8')
                        
                        # Skip already processed keys
                        if key_str in processed_keys:
                            continue
                        
                        # Get the activity log data
                        data = await self.redis.get(key)
                        if data:
                            try:
                                log_data = json.loads(data.decode('utf-8'))
                                await self.stream_activity_log_entry(key_str, log_data)
                                processed_keys.add(key_str)
                                
                            except json.JSONDecodeError:
                                logger.warning(f"Invalid JSON in activity log: {key_str}")
                                continue
                    
                    # Clean up processed keys periodically (keep last 1000)
                    if len(processed_keys) > 1000:
                        # Remove oldest 200 keys
                        old_keys = list(processed_keys)[:200]
                        processed_keys -= set(old_keys)
                    
                    # Wait before next scan
                    await asyncio.sleep(5)
                    
                except Exception as e:
                    logger.error(f"Error in activity log monitoring: {e}")
                    await asyncio.sleep(10)
                    
        except asyncio.CancelledError:
            logger.info("Activity log monitoring task cancelled")
        except Exception as e:
            logger.error(f"Activity log monitoring task failed: {e}")
    
    async def _monitor_sessions(self) -> None:
        """Monitor Redis for session changes"""
        try:
            processed_keys = set()
            
            while self.streaming_active:
                try:
                    # Scan for session keys
                    async for key in self.redis.scan_iter(match=self.key_patterns['sessions']):
                        key_str = key.decode('utf-8')
                        
                        # Skip already processed keys
                        if key_str in processed_keys:
                            continue
                        
                        # Get the session data
                        data = await self.redis.get(key)
                        if data:
                            try:
                                session_data = json.loads(data.decode('utf-8'))
                                session_id = key_str.split(':')[-1]
                                await self.stream_session_event(session_id, session_data)
                                processed_keys.add(key_str)
                                
                            except json.JSONDecodeError:
                                logger.warning(f"Invalid JSON in session data: {key_str}")
                                continue
                    
                    # Clean up processed keys periodically
                    if len(processed_keys) > 500:
                        old_keys = list(processed_keys)[:100]
                        processed_keys -= set(old_keys)
                    
                    # Wait before next scan
                    await asyncio.sleep(15)
                    
                except Exception as e:
                    logger.error(f"Error in session monitoring: {e}")
                    await asyncio.sleep(20)
                    
        except asyncio.CancelledError:
            logger.info("Session monitoring task cancelled")
        except Exception as e:
            logger.error(f"Session monitoring task failed: {e}")
    
    async def _monitor_daily_stats(self) -> None:
        """Monitor Redis for daily stats changes"""
        try:
            last_stats = {}
            
            while self.streaming_active:
                try:
                    # Scan for daily stats keys
                    async for key in self.redis.scan_iter(match=self.key_patterns['daily_stats']):
                        key_str = key.decode('utf-8')
                        
                        # Get current value
                        value = await self.redis.get(key)
                        if value:
                            try:
                                current_value = int(value.decode('utf-8'))
                                
                                # Check if value changed
                                if key_str not in last_stats or last_stats[key_str] != current_value:
                                    await self.stream_stats_event(key_str, current_value)
                                    last_stats[key_str] = current_value
                                    
                            except (ValueError, UnicodeDecodeError):
                                logger.warning(f"Invalid value in stats key: {key_str}")
                                continue
                    
                    # Wait before next scan
                    await asyncio.sleep(30)
                    
                except Exception as e:
                    logger.error(f"Error in daily stats monitoring: {e}")
                    await asyncio.sleep(45)
                    
        except asyncio.CancelledError:
            logger.info("Daily stats monitoring task cancelled")
        except Exception as e:
            logger.error(f"Daily stats monitoring task failed: {e}")


# Global streaming service instance
_streaming_service: Optional[SupabaseStreamingService] = None


async def get_streaming_service(redis_client: aioredis.Redis) -> SupabaseStreamingService:
    """Get or create streaming service instance"""
    global _streaming_service
    if _streaming_service is None:
        _streaming_service = SupabaseStreamingService(redis_client)
        await _streaming_service.initialize()
    return _streaming_service


async def initialize_streaming_service(redis_client: aioredis.Redis) -> SupabaseStreamingService:
    """Initialize the streaming service"""
    logger.info("Initializing Supabase streaming service")
    service = await get_streaming_service(redis_client)
    await service.start_streaming()
    return service