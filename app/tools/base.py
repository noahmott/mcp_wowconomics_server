"""
Base functionality for MCP tools including decorators and shared utilities
"""

import functools
import time
import logging
from typing import Any, Dict, Callable
from datetime import datetime, timezone
import uuid

logger = logging.getLogger(__name__)

# Global service references
mcp = None
redis_client = None
activity_logger = None
supabase_client = None
streaming_service = None


def set_mcp_instance(mcp_instance):
    """Set the global MCP instance for tools to use"""
    global mcp
    mcp = mcp_instance


def set_service_instances(redis=None, activity=None, supabase=None, streaming=None):
    """Set global service instances for tools to use"""
    global redis_client, activity_logger, supabase_client, streaming_service
    if redis:
        redis_client = redis
    if activity:
        activity_logger = activity
    if supabase:
        supabase_client = supabase
    if streaming:
        streaming_service = streaming


def mcp_tool(*args, **kwargs):
    """Wrapper for mcp.tool() decorator that uses the global mcp instance"""
    def decorator(func):
        if mcp is None:
            raise RuntimeError("MCP instance not set. Call set_mcp_instance() first.")
        return mcp.tool(*args, **kwargs)(func)
    
    if args and callable(args[0]):
        return decorator(args[0])
    return decorator


def with_error_handling(func: Callable) -> Callable:
    """Decorator to add standard error handling to tool functions"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)
            return {"error": f"Tool execution failed: {str(e)}"}
    return wrapper


def with_supabase_logging(func: Callable) -> Callable:
    """Decorator to add Supabase activity logging to MCP tools"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        error_message = None
        response_data = None
        
        request_data = {}
        import inspect
        sig = inspect.signature(func)
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()
        
        for param_name, param_value in bound_args.arguments.items():
            if param_name not in ['self', 'cls']:
                request_data[param_name] = param_value
        
        try:
            result = await func(*args, **kwargs)
            response_data = result
            
            await log_to_supabase(
                tool_name=func.__name__,
                request_data=request_data,
                response_data=response_data,
                duration_ms=(time.time() - start_time) * 1000
            )
            
            return result
            
        except Exception as e:
            error_message = str(e)
            
            await log_to_supabase(
                tool_name=func.__name__,
                request_data=request_data,
                error_message=error_message,
                duration_ms=(time.time() - start_time) * 1000
            )
            
            raise
    
    return wrapper


async def log_to_supabase(tool_name: str, request_data: Dict[str, Any], 
                         response_data: Dict[str, Any] = None, 
                         error_message: str = None,
                         duration_ms: float = None):
    """Log activity to Supabase (imported from main module)"""
    try:
        if not supabase_client:
            logger.debug("Supabase client not available - skipping log")
            return
        
        from ..services.supabase_client import ActivityLogEntry
        
        # Create activity log entry
        log_entry = ActivityLogEntry(
            id=str(uuid.uuid4()),
            session_id="fastmcp-direct",
            activity_type="tool_call" if not error_message else "tool_error",
            timestamp=datetime.now(timezone.utc).isoformat(),
            tool_name=tool_name,
            request_data=request_data,
            response_data=response_data,
            error_message=error_message,
            duration_ms=duration_ms,
            metadata={
                "source": "fastmcp",
                "direct_logging": True
            }
        )
        
        # Stream to Supabase
        success = await supabase_client.stream_activity_log(log_entry)
        if success:
            logger.debug(f"Successfully logged {tool_name} to Supabase")
        else:
            logger.warning(f"Failed to log {tool_name} to Supabase - no error thrown")
        
    except Exception as e:
        logger.error(f"Failed to log to Supabase: {e}")
        pass


async def get_or_initialize_services():
    """Get or initialize required services"""
    from ..core.service_manager import get_service_manager
    
    service_mgr = await get_service_manager()
    
    global redis_client, activity_logger, supabase_client, streaming_service
    redis_client = service_mgr.redis_client
    activity_logger = service_mgr.activity_logger
    supabase_client = service_mgr.supabase_client
    streaming_service = service_mgr.streaming_service
    
    return service_mgr