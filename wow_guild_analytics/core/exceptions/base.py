"""
Base Exception Classes

Core exception hierarchy for the application.
"""

from typing import Optional, Dict, Any


class WoWGuildError(Exception):
    """Base exception for all application errors."""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        self.message = message
        self.details = details or {}
        self.original_exception = original_exception
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "details": self.details
        }


class APIError(WoWGuildError):
    """API-related errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        endpoint: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, details)
        self.status_code = status_code
        self.endpoint = endpoint

        # Add to details
        self.details["status_code"] = status_code
        self.details["endpoint"] = endpoint


class ValidationError(WoWGuildError):
    """Data validation errors."""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, details)
        self.field = field
        self.value = value

        # Add to details
        self.details["field"] = field
        self.details["value"] = value


class NotFoundError(WoWGuildError):
    """Resource not found errors."""

    def __init__(
        self,
        resource: str,
        identifier: Any,
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"{resource} not found: {identifier}"
        super().__init__(message, details)
        self.resource = resource
        self.identifier = identifier

        # Add to details
        self.details["resource"] = resource
        self.details["identifier"] = str(identifier)


class ConfigurationError(WoWGuildError):
    """Configuration-related errors."""

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, details)
        self.config_key = config_key

        # Add to details
        self.details["config_key"] = config_key


class ServiceError(WoWGuildError):
    """Service-level errors."""

    def __init__(
        self,
        message: str,
        service_name: Optional[str] = None,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, details)
        self.service_name = service_name
        self.operation = operation

        # Add to details
        self.details["service_name"] = service_name
        self.details["operation"] = operation
