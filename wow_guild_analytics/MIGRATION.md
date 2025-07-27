# Migration Guide: Moving to Modular Architecture

This guide helps you migrate from the existing monolithic structure to the new modular architecture.

## Overview

The migration is designed to be gradual and non-breaking. The existing FastMCP integration remains untouched while internal components are refactored.

## Migration Steps

### Step 1: Install Dependencies

Add new dependencies to `requirements.txt`:
```
dependency-injector>=4.41.0
pydantic-settings>=2.0.0
```

### Step 2: Initialize Modular System

In your application startup (e.g., `app/main.py`), add:

```python
from wow_guild_analytics.startup import startup, shutdown

# In your lifespan context manager
async def lifespan(app: FastAPI):
    # Initialize modular system
    await startup()
    
    # Your existing initialization...
    
    yield
    
    # Shutdown modular system
    await shutdown()
```

### Step 3: Migrate Components Gradually

#### Cache Migration

**Before (Direct Redis usage):**
```python
import redis
r = redis.Redis()
r.set("key", "value")
```

**After (Using Cache Protocol):**
```python
from wow_guild_analytics.core.container import get_container

container = get_container()
cache = container.cache()
await cache.set("key", "value")
```

#### Blizzard API Migration

**Before:**
```python
from app.api.blizzard_client import BlizzardAPIClient

async with BlizzardAPIClient() as client:
    data = await client.get_guild_info("realm", "guild")
```

**After (Option 1 - Using Adapter):**
```python
from wow_guild_analytics.adapters import LegacyBlizzardClientAdapter

async with LegacyBlizzardClientAdapter() as client:
    data = await client.get_guild_info("realm", "guild")
```

**After (Option 2 - Using New Client):**
```python
from wow_guild_analytics.infrastructure.api.blizzard import IntegratedBlizzardClient
from wow_guild_analytics.core.config import ConfigLoader

settings = ConfigLoader.load_config()
client = IntegratedBlizzardClient(settings)

async with client:
    data = await client.get_guild("realm", "guild")
```

#### Database Migration

**Before:**
```python
from app.models import db_session
from app.models.guild import Guild

with db_session() as session:
    guild = session.query(Guild).first()
```

**After:**
```python
from wow_guild_analytics.infrastructure.database import get_db_session
from wow_guild_analytics.domain.guild.models import Guild

async with get_db_session() as session:
    result = await session.execute(select(Guild))
    guild = result.scalar_one_or_none()
```

### Step 4: Update MCP Server

The MCP server is automatically migrated when you run:

```python
from wow_guild_analytics.startup import migrate_existing_server

await migrate_existing_server()
```

This patches the existing `WoWGuildMCPServer` to use modular components internally.

### Step 5: Test Everything

Run the comprehensive test suite:

```bash
# Unit tests
pytest wow_guild_analytics/tests/unit

# Integration tests
cd wow_guild_analytics/tests
./run_docker_tests.sh
```

## Configuration Migration

### Environment Variables

Update your `.env` file:

```env
# Old format
BLIZZARD_CLIENT_ID=xxx
BLIZZARD_CLIENT_SECRET=xxx

# New format (same variables work)
BLIZZARD_CLIENT_ID=xxx
BLIZZARD_CLIENT_SECRET=xxx

# Optional new settings
API_RATE_LIMIT=100
CACHE_DEFAULT_TTL=300
```

### Database Models

The new models are compatible with existing database schema. No migration needed.

## Rollback Plan

If issues arise, you can rollback by:

1. Remove the startup/shutdown calls
2. Continue using original imports
3. The adapter layer ensures compatibility

## Common Issues

### Import Errors

**Problem:** `ImportError: cannot import name 'X' from 'app.Y'`

**Solution:** Update imports to use new paths:
```python
# Old
from app.api.blizzard_client import BlizzardAPIClient

# New
from wow_guild_analytics.adapters import LegacyBlizzardClientAdapter as BlizzardAPIClient
```

### Async/Await Issues

**Problem:** `RuntimeError: This event loop is already running`

**Solution:** Ensure all database and cache operations use async/await:
```python
# Old
value = cache.get("key")

# New  
value = await cache.get("key")
```

### Configuration Not Found

**Problem:** `ConfigurationError: Setting not found`

**Solution:** Check environment variables and config files are properly set.

## Performance Considerations

The modular architecture includes several performance improvements:

1. **Connection Pooling**: Database and Redis connections are pooled
2. **Caching**: API responses are cached with configurable TTLs
3. **Rate Limiting**: Prevents API throttling
4. **Async Operations**: All I/O is async for better concurrency

## Monitoring

Add monitoring for the new components:

```python
from wow_guild_analytics.core.container import get_container

container = get_container()

# Get statistics
cache_stats = await container.cache().get_stats()
rate_limit_stats = container.blizzard_client().get_rate_limit_stats()
```

## Support

For migration support:
1. Check the test examples in `wow_guild_analytics/tests/`
2. Review adapter implementations in `wow_guild_analytics/adapters/`
3. Enable debug logging: `LOG_LEVEL=DEBUG`