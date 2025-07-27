"""
Activity Logger for MCP Server

Tracks all client connections, requests, responses, and server activities in Redis.
"""
import json
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import redis.asyncio as aioredis
import logging

logger = logging.getLogger(__name__)


@dataclass
class ClientSession:
    """Client session information"""
    session_id: str
    client_info: Dict[str, Any]
    created_at: str
    last_activity: str
    request_count: int
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None


@dataclass
class ActivityLog:
    """Activity log entry"""
    log_id: str
    session_id: str
    activity_type: str  # 'connection', 'request', 'response', 'error', 'disconnect'
    timestamp: str
    tool_name: Optional[str] = None
    request_data: Optional[Dict[str, Any]] = None
    response_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    duration_ms: Optional[float] = None
    reasoning: Optional[str] = None  # If exposed by client
    metadata: Optional[Dict[str, Any]] = None


class ActivityLogger:
    """Comprehensive activity logging for MCP server"""
    
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self.key_prefixes = {
            'activity': 'wow:activity',
            'sessions': 'wow:sessions',
            'stats': 'wow:stats:activity',
            'daily': 'wow:daily'
        }
        self.log_retention_days = 30
        self.session_timeout = 3600  # 1 hour
    
    async def start_session(self, session_id: str, client_info: Dict[str, Any], 
                          user_agent: Optional[str] = None, 
                          ip_address: Optional[str] = None) -> ClientSession:
        """Start a new client session"""
        try:
            now = datetime.now(timezone.utc).isoformat()
            
            session = ClientSession(
                session_id=session_id,
                client_info=client_info,
                created_at=now,
                last_activity=now,
                request_count=0,
                user_agent=user_agent,
                ip_address=ip_address
            )
            
            # Store session in Redis with TTL
            session_key = f"{self.key_prefixes['sessions']}:{session_id}"
            await self.redis.setex(
                session_key, 
                self.session_timeout, 
                json.dumps(asdict(session), default=str)
            )
            
            # Log connection activity
            await self.log_activity(
                session_id=session_id,
                activity_type='connection',
                metadata={
                    'client_name': client_info.get('name', 'Unknown'),
                    'client_version': client_info.get('version', 'Unknown'),
                    'user_agent': user_agent,
                    'ip_address': ip_address
                }
            )
            
            # Update daily stats
            await self._update_daily_stats('connections')
            
            logger.info(f"Started session {session_id} for client {client_info.get('name', 'Unknown')}")
            return session
            
        except Exception as e:
            logger.error(f"Error starting session {session_id}: {str(e)}")
            raise
    
    async def log_request(self, session_id: str, tool_name: str, 
                         request_data: Dict[str, Any],
                         reasoning: Optional[str] = None) -> str:
        """Log an incoming MCP request"""
        try:
            log_id = str(uuid.uuid4())
            
            activity = ActivityLog(
                log_id=log_id,
                session_id=session_id,
                activity_type='request',
                timestamp=datetime.now(timezone.utc).isoformat(),
                tool_name=tool_name,
                request_data=request_data,
                reasoning=reasoning
            )
            
            # Store activity log
            activity_key = f"{self.key_prefixes['activity']}:{log_id}"
            ttl = self.log_retention_days * 24 * 3600  # Convert to seconds
            await self.redis.setex(
                activity_key,
                ttl,
                json.dumps(asdict(activity), default=str)
            )
            
            # Update session activity
            await self._update_session_activity(session_id)
            
            # Update daily stats
            await self._update_daily_stats('requests')
            await self._update_daily_stats(f'tool:{tool_name}')
            
            logger.debug(f"Logged request {log_id} for tool {tool_name}")
            return log_id
            
        except Exception as e:
            logger.error(f"Error logging request: {str(e)}")
            return ""
    
    async def log_response(self, log_id: str, response_data: Dict[str, Any], 
                          duration_ms: float, success: bool = True) -> None:
        """Log MCP response"""
        try:
            if not log_id:
                return
                
            # Get existing activity log
            activity_key = f"{self.key_prefixes['activity']}:{log_id}"
            existing_data = await self.redis.get(activity_key)
            
            if existing_data:
                activity_dict = json.loads(existing_data.decode('utf-8'))
                
                # Update with response information
                activity_dict['response_data'] = response_data
                activity_dict['duration_ms'] = duration_ms
                activity_dict['activity_type'] = 'response'
                
                # Store updated activity
                ttl = await self.redis.ttl(activity_key)
                await self.redis.setex(
                    activity_key,
                    ttl if ttl > 0 else self.log_retention_days * 24 * 3600,
                    json.dumps(activity_dict, default=str)
                )
                
                # Update daily stats
                if success:
                    await self._update_daily_stats('successful_responses')
                else:
                    await self._update_daily_stats('failed_responses')
                
                logger.debug(f"Logged response for {log_id} (duration: {duration_ms}ms)")
            
        except Exception as e:
            logger.error(f"Error logging response: {str(e)}")
    
    async def log_error(self, session_id: str, error_message: str, 
                       tool_name: Optional[str] = None,
                       metadata: Optional[Dict[str, Any]] = None) -> None:
        """Log an error"""
        try:
            log_id = str(uuid.uuid4())
            
            activity = ActivityLog(
                log_id=log_id,
                session_id=session_id,
                activity_type='error',
                timestamp=datetime.now(timezone.utc).isoformat(),
                tool_name=tool_name,
                error_message=error_message,
                metadata=metadata
            )
            
            # Store error log
            activity_key = f"{self.key_prefixes['activity']}:{log_id}"
            ttl = self.log_retention_days * 24 * 3600
            await self.redis.setex(
                activity_key,
                ttl,
                json.dumps(asdict(activity), default=str)
            )
            
            # Update daily stats
            await self._update_daily_stats('errors')
            if tool_name:
                await self._update_daily_stats(f'tool_errors:{tool_name}')
            
            logger.warning(f"Logged error for session {session_id}: {error_message}")
            
        except Exception as e:
            logger.error(f"Error logging error: {str(e)}")
    
    async def end_session(self, session_id: str) -> None:
        """End a client session"""
        try:
            # Log disconnection
            await self.log_activity(
                session_id=session_id,
                activity_type='disconnect'
            )
            
            # Remove session (let it expire naturally for analytics)
            logger.info(f"Ended session {session_id}")
            
        except Exception as e:
            logger.error(f"Error ending session {session_id}: {str(e)}")
    
    async def log_activity(self, session_id: str, activity_type: str, 
                          tool_name: Optional[str] = None,
                          metadata: Optional[Dict[str, Any]] = None) -> str:
        """Log general activity"""
        try:
            log_id = str(uuid.uuid4())
            
            activity = ActivityLog(
                log_id=log_id,
                session_id=session_id,
                activity_type=activity_type,
                timestamp=datetime.now(timezone.utc).isoformat(),
                tool_name=tool_name,
                metadata=metadata
            )
            
            # Store activity log
            activity_key = f"{self.key_prefixes['activity']}:{log_id}"
            ttl = self.log_retention_days * 24 * 3600
            await self.redis.setex(
                activity_key,
                ttl,
                json.dumps(asdict(activity), default=str)
            )
            
            return log_id
            
        except Exception as e:
            logger.error(f"Error logging activity: {str(e)}")
            return ""
    
    async def get_session_stats(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a specific session"""
        try:
            session_key = f"{self.key_prefixes['sessions']}:{session_id}"
            session_data = await self.redis.get(session_key)
            
            if session_data:
                return json.loads(session_data.decode('utf-8'))
            return None
            
        except Exception as e:
            logger.error(f"Error getting session stats: {str(e)}")
            return None
    
    async def get_daily_stats(self, date: Optional[str] = None) -> Dict[str, int]:
        """Get daily activity statistics"""
        try:
            if not date:
                date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            
            stats = {}
            pattern = f"{self.key_prefixes['daily']}:{date}:*"
            
            async for key in self.redis.scan_iter(match=pattern):
                key_str = key.decode('utf-8')
                stat_name = key_str.split(':', -1)[-1]
                value = await self.redis.get(key)
                stats[stat_name] = int(value.decode('utf-8')) if value else 0
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting daily stats: {str(e)}")
            return {}
    
    async def _update_session_activity(self, session_id: str) -> None:
        """Update session last activity and request count"""
        try:
            session_key = f"{self.key_prefixes['sessions']}:{session_id}"
            session_data = await self.redis.get(session_key)
            
            if session_data:
                session_dict = json.loads(session_data.decode('utf-8'))
                session_dict['last_activity'] = datetime.now(timezone.utc).isoformat()
                session_dict['request_count'] = session_dict.get('request_count', 0) + 1
                
                # Extend TTL
                await self.redis.setex(
                    session_key,
                    self.session_timeout,
                    json.dumps(session_dict, default=str)
                )
                
        except Exception as e:
            logger.error(f"Error updating session activity: {str(e)}")
    
    async def _update_daily_stats(self, stat_name: str) -> None:
        """Update daily statistics counter"""
        try:
            date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            stat_key = f"{self.key_prefixes['daily']}:{date}:{stat_name}"
            
            # Increment counter
            await self.redis.incr(stat_key)
            
            # Set expiry for 32 days (a bit longer than retention)
            await self.redis.expire(stat_key, 32 * 24 * 3600)
            
        except Exception as e:
            logger.error(f"Error updating daily stats: {str(e)}")


# Global activity logger instance
_activity_logger: Optional[ActivityLogger] = None


async def get_activity_logger(redis_client: aioredis.Redis) -> ActivityLogger:
    """Get or create activity logger instance"""
    global _activity_logger
    if _activity_logger is None:
        _activity_logger = ActivityLogger(redis_client)
    return _activity_logger


async def initialize_activity_logger(redis_client: aioredis.Redis) -> ActivityLogger:
    """Initialize the activity logger"""
    logger.info("Initializing activity logger")
    return await get_activity_logger(redis_client)