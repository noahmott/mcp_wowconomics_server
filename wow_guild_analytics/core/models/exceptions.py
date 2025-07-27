"""
Model-related Exceptions

Custom exceptions for model validation and operations.
"""

from typing import Dict, Any, Optional


class ModelValidationError(Exception):
    """Raised when model validation fails."""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        errors: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.field = field
        self.value = value
        self.errors = errors or {}
        super().__init__(self.message)

    def __str__(self) -> str:
        """String representation."""
        if self.field:
            return f"Validation error on field '{self.field}': {self.message}"
        return self.message
