"""
WoW Guild Analytics - Modular Architecture

A comprehensive World of Warcraft guild and economic analysis system.
"""

__version__ = "2.0.0"
__author__ = "WoW Guild Analytics Team"

# Public API exports
from .core.config import Settings
from .core.exceptions import WoWGuildError

__all__ = [
    "Settings",
    "WoWGuildError",
]
