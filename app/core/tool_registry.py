"""
Tool registry for managing MCP tools across modules
"""

import logging
from typing import Dict, Callable, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ToolInfo:
    """Information about a registered tool"""
    name: str
    function: Callable
    module: str
    category: str
    description: str = ""


class ToolRegistry:
    """Registry for all MCP tools"""
    
    def __init__(self):
        self._tools: Dict[str, ToolInfo] = {}
        self._categories: Dict[str, list] = {}
    
    def register(self, name: str, category: str, module: str, description: str = ""):
        """Decorator to register a tool"""
        def decorator(func: Callable) -> Callable:
            tool_info = ToolInfo(
                name=name,
                function=func,
                module=module,
                category=category,
                description=description or func.__doc__ or ""
            )
            
            self._tools[name] = tool_info
            
            if category not in self._categories:
                self._categories[category] = []
            self._categories[category].append(name)
            
            logger.debug(f"Registered tool: {name} in category: {category}")
            return func
        
        return decorator
    
    def get_tool(self, name: str) -> Optional[ToolInfo]:
        """Get a tool by name"""
        return self._tools.get(name)
    
    def get_tools_by_category(self, category: str) -> List[str]:
        """Get all tools in a category"""
        return self._categories.get(category, [])
    
    def get_all_tools(self) -> Dict[str, ToolInfo]:
        """Get all registered tools"""
        return self._tools.copy()
    
    def get_categories(self) -> List[str]:
        """Get all categories"""
        return list(self._categories.keys())


# Global tool registry instance
tool_registry = ToolRegistry()