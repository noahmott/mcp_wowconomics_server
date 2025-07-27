# PEP 8 Compliance Guidelines

## Overview
This document outlines the PEP 8 coding standards for the WoW Guild Analytics project.

## Code Style Guidelines

### 1. Module and Package Naming
All modules and packages should follow PEP 8 naming conventions:
- Use lowercase with underscores (snake_case)
- Examples: `blizzard_client.py`, `guild_analysis.py`

### 2. Import Organization
Imports should be organized as follows:
```python
# Standard library
import os
import logging
from typing import Dict, Any, Optional

# Third-party
from fastmcp import FastMCP
import httpx

# Local imports
from .utils import cache
from .api import blizzard_client
```

### 3. Class and Function Naming
- Classes: CapWords convention (`BlizzardAPIClient`, `GuildAnalysisWorkflow`)
- Functions: lowercase_with_underscores (`get_guild_info`, `analyze_guild_performance`)
- Constants: UPPER_CASE_WITH_UNDERSCORES

### 4. Line Length
- Maximum line length: 88 characters (Black default)
- Break long lines using appropriate techniques:
```python
# For long strings
long_url = (
    f"/profile/wow/character/{realm_slug}/"
    f"{character_slug}/equipment"
)

# For method calls
result = await self.very_long_method_name(
    parameter1=value1,
    parameter2=value2,
    parameter3=value3
)
```

### 5. Type Hints
Use type hints for function arguments and return values:
```python
async def get_guild_info(
    self, 
    realm: str, 
    guild_name: str
) -> Dict[str, Any]:
    """Get guild information."""
```

### 6. Docstrings
All public methods should have proper docstrings:
```python
def get_character_profile(self, realm: str, name: str) -> Dict[str, Any]:
    """
    Get character profile data.
    
    Args:
        realm: The realm slug
        name: Character name
        
    Returns:
        Character profile data
    """
```

## Automated Tools

### 1. Install and configure flake8:
```bash
pip install flake8
flake8 app/ --max-line-length=88
```

### 2. Use black formatter:
```bash
pip install black
black app/
```

### 3. Add pre-commit hooks:
```yaml
# .pre-commit-config.yaml
repos:
- repo: https://github.com/psf/black
  rev: 23.1.0
  hooks:
  - id: black
- repo: https://github.com/pycqa/flake8
  rev: 6.0.0
  hooks:
  - id: flake8
    args: [--max-line-length=88]
```

## Best Practices

1. **Consistent Formatting**: Use Black for automatic formatting
2. **Type Safety**: Add type hints to all function signatures
3. **Documentation**: Write clear docstrings for all public functions
4. **Import Order**: Follow the standard library → third-party → local pattern
5. **Error Handling**: Avoid bare except clauses; be specific about exceptions

## Project-Specific Conventions

- All MCP tool functions should be decorated with `@mcp.tool()` and `@with_supabase_logging`
- Use async/await for all I/O operations
- Cache keys should follow the pattern: `prefix:identifier`
- All API errors should be properly logged before raising