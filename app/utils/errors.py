"""
Error handling utilities and custom exceptions
"""

import logging
import traceback
from enum import Enum
from typing import Optional, Dict, Any
from functools import wraps
import asyncio

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Error type enumeration"""
    API_RATE_LIMIT = "api_rate_limit"
    API_AUTHENTICATION = "api_authentication"
    DATA_NOT_FOUND = "data_not_found"
    NETWORK_ERROR = "network_error"
    PROCESSING_ERROR = "processing_error"
    DATABASE_ERROR = "database_error"
    VALIDATION_ERROR = "validation_error"
    TIMEOUT_ERROR = "timeout_error"
    UNKNOWN_ERROR = "unknown_error"


class WoWGuildError(Exception):
    """Base exception for WoW Guild application"""
    
    def __init__(
        self, 
        error_type: ErrorType, 
        message: str, 
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        self.error_type = error_type
        self.message = message
        self.details = details or {}
        self.original_exception = original_exception
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for serialization"""
        return {
            "error_type": self.error_type.value,
            "message": self.message,
            "details": self.details,
            "traceback": traceback.format_exc() if self.original_exception else None
        }
    
    @classmethod
    def from_exception(cls, exc: Exception, error_type: ErrorType = ErrorType.UNKNOWN_ERROR) -> 'WoWGuildError':
        """Create WoWGuildError from generic exception"""
        return cls(
            error_type=error_type,
            message=str(exc),
            original_exception=exc
        )


class APIError(WoWGuildError):
    """API-related errors"""
    
    def __init__(self, message: str, status_code: Optional[int] = None, endpoint: Optional[str] = None):
        super().__init__(
            error_type=ErrorType.API_RATE_LIMIT if status_code == 429 else ErrorType.NETWORK_ERROR,
            message=message,
            details={"status_code": status_code, "endpoint": endpoint}
        )
        self.status_code = status_code
        self.endpoint = endpoint


class ValidationError(WoWGuildError):
    """Data validation errors"""
    
    def __init__(self, message: str, field: Optional[str] = None, value: Optional[Any] = None):
        super().__init__(
            error_type=ErrorType.VALIDATION_ERROR,
            message=message,
            details={"field": field, "value": value}
        )
        self.field = field
        self.value = value


class DataNotFoundError(WoWGuildError):
    """Data not found errors"""
    
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            error_type=ErrorType.DATA_NOT_FOUND,
            message=f"{resource} not found: {identifier}",
            details={"resource": resource, "identifier": identifier}
        )
        self.resource = resource
        self.identifier = identifier


def error_handler(error_type: ErrorType = ErrorType.UNKNOWN_ERROR, reraise: bool = False):
    """Decorator for handling and logging errors"""
    
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except WoWGuildError:
                # Re-raise our custom errors
                if reraise:
                    raise
                logger.error(f"Error in {func.__name__}: {traceback.format_exc()}")
                return None
            except Exception as e:
                logger.error(f"Unexpected error in {func.__name__}: {str(e)}")
                logger.error(traceback.format_exc())
                
                if reraise:
                    raise WoWGuildError.from_exception(e, error_type)
                return None
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except WoWGuildError:
                if reraise:
                    raise
                logger.error(f"Error in {func.__name__}: {traceback.format_exc()}")
                return None
            except Exception as e:
                logger.error(f"Unexpected error in {func.__name__}: {str(e)}")
                logger.error(traceback.format_exc())
                
                if reraise:
                    raise WoWGuildError.from_exception(e, error_type)
                return None
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def get_error_suggestion(error_type: ErrorType) -> list[str]:
    """Get user-friendly suggestions based on error type"""
    suggestions = {
        ErrorType.API_RATE_LIMIT: [
            "You've hit the API rate limit. Please wait a few minutes before trying again.",
            "Consider reducing the frequency of requests.",
            "The system will automatically retry after the cooldown period."
        ],
        ErrorType.API_AUTHENTICATION: [
            "API authentication failed. Please check your credentials.",
            "Ensure your Blizzard API keys are valid and properly configured.",
            "Contact an administrator if the issue persists."
        ],
        ErrorType.DATA_NOT_FOUND: [
            "Check if the realm name is spelled correctly (e.g., 'stormrage', 'area-52').",
            "Verify that the guild name is accurate and exists on the specified realm.",
            "Make sure the character name is correct and the character exists.",
            "Some data may not be publicly available or the character may be inactive."
        ],
        ErrorType.NETWORK_ERROR: [
            "There was a network connectivity issue. Please try again.",
            "Check your internet connection.",
            "The Blizzard API servers may be temporarily unavailable."
        ],
        ErrorType.PROCESSING_ERROR: [
            "An error occurred while processing your request.",
            "Please try again with different parameters.",
            "If the issue persists, contact support."
        ],
        ErrorType.DATABASE_ERROR: [
            "A database error occurred. Please try again.",
            "If the issue persists, contact an administrator.",
            "Your request may have been partially processed."
        ],
        ErrorType.VALIDATION_ERROR: [
            "The provided data is invalid. Please check your input.",
            "Make sure all required fields are filled correctly.",
            "Check the format of realm and character names."
        ],
        ErrorType.TIMEOUT_ERROR: [
            "The request timed out. This usually happens with large guilds.",
            "Please try again - the data may be cached now.",
            "Consider using more specific queries to reduce processing time."
        ],
        ErrorType.UNKNOWN_ERROR: [
            "An unexpected error occurred. Please try again.",
            "If the issue persists, please contact support.",
            "Try using different parameters or simplifying your request."
        ]
    }
    
    return suggestions.get(error_type, suggestions[ErrorType.UNKNOWN_ERROR])


class ErrorReporting:
    """Error reporting and analytics"""
    
    def __init__(self):
        self.error_counts = {}
        self.recent_errors = []
        self.max_recent_errors = 100
    
    def report_error(self, error: WoWGuildError, context: Optional[Dict[str, Any]] = None):
        """Report an error for analytics"""
        error_key = f"{error.error_type.value}:{error.message[:50]}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        
        error_record = {
            "timestamp": logger.time.time(),
            "error_type": error.error_type.value,
            "message": error.message,
            "details": error.details,
            "context": context or {}
        }
        
        self.recent_errors.append(error_record)
        
        # Keep only recent errors
        if len(self.recent_errors) > self.max_recent_errors:
            self.recent_errors = self.recent_errors[-self.max_recent_errors:]
        
        logger.error(f"Error reported: {error.error_type.value} - {error.message}")
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics"""
        return {
            "total_errors": len(self.recent_errors),
            "error_counts": self.error_counts.copy(),
            "recent_errors": self.recent_errors[-10:],  # Last 10 errors
            "most_common_errors": sorted(
                self.error_counts.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:5]
        }


# Global error reporter instance
error_reporter = ErrorReporting()


def format_error_for_user(error: WoWGuildError) -> str:
    """Format error message for end users"""
    base_message = f"❌ **Error:** {error.message}"
    
    suggestions = get_error_suggestion(error.error_type)
    if suggestions:
        suggestion_text = "\n💡 **Suggestions:**\n" + "\n".join(f"• {s}" for s in suggestions[:3])
        return base_message + "\n" + suggestion_text
    
    return base_message


