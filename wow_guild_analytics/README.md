# WoW Guild Analytics - Modular Architecture

This directory contains the new modular architecture for the WoW Guild Analytics system. The architecture has been designed following Domain-Driven Design (DDD) principles and modern Python best practices.

## Architecture Overview

The modular architecture is organized into the following layers:

### Core Layer (`core/`)
- **Protocols**: Python Protocol definitions for dependency inversion
- **Models**: Base model classes with common functionality
- **Config**: Configuration management with Pydantic
- **Container**: Dependency injection container
- **Exceptions**: Custom exception hierarchy

### Infrastructure Layer (`infrastructure/`)
- **API**: External API clients (Blizzard API)
- **Cache**: Cache implementations (Redis, Memory)
- **Database**: Database connection and repositories
- **Auth**: Authentication services
- **Middleware**: Rate limiting and other middleware

### Domain Layer (`domain/`)
- **Guild**: Guild-related models and logic
- **Character**: Character-related models and logic
- **Market**: Market/auction house models and logic
- **Raid**: Raid-related models and logic

### Application Layer (`application/`)
- **Services**: Business logic and use cases
- **Workflows**: Complex multi-step operations

### Presentation Layer (`presentation/`)
- **MCP**: Model Context Protocol server
- **API**: REST API endpoints (if needed)

### Adapters Layer (`adapters/`)
- **Legacy adapters**: Backward compatibility with existing code

## Key Features

### 1. Protocol-Based Design
All major components are defined using Python Protocols, enabling:
- Loose coupling between layers
- Easy testing with mock implementations
- Clear interface definitions

### 2. Dependency Injection
The system uses `dependency-injector` for managing dependencies:
- Centralized configuration
- Easy swapping of implementations
- Testability

### 3. Backward Compatibility
The `LegacyBlizzardClientAdapter` ensures existing code continues to work:
- No changes required to FastMCP integration
- Gradual migration path
- Full API compatibility

### 4. Advanced Caching
Multi-level caching with namespace support:
- Redis for distributed caching
- Memory cache for single-instance deployments
- Automatic cache key generation
- TTL management

### 5. Rate Limiting
Sophisticated rate limiting for external APIs:
- Token bucket algorithm
- Per-realm rate limiting
- Burst handling
- Request queuing

## Migration Guide

### Using the New Architecture

1. **Initialize the system**:
```python
from wow_guild_analytics.startup import startup

# Initialize all components
await startup()
```

2. **Use services through dependency injection**:
```python
from wow_guild_analytics.core.container import get_container

container = get_container()
cache = container.cache()
```

3. **Migrate existing code gradually**:
```python
# Old code continues to work
from app.api.blizzard_client import BlizzardAPIClient

# New code uses modular components
from wow_guild_analytics.adapters import LegacyBlizzardClientAdapter
```

### Testing

Run integration tests to verify the system:

```bash
# Run Docker integration tests
cd wow_guild_analytics/tests
./run_docker_tests.sh  # Linux/Mac
# or
./run_docker_tests.ps1  # Windows
```

### Configuration

The system uses environment variables and configuration files:

1. **Environment Variables**:
   - `BLIZZARD_CLIENT_ID`
   - `BLIZZARD_CLIENT_SECRET`
   - `DATABASE_URL`
   - `REDIS_URL`

2. **Configuration Files**:
   - `config/settings.yaml` (optional)
   - `.env` file (for local development)

## Benefits

1. **Maintainability**: Clear separation of concerns
2. **Testability**: Easy to test individual components
3. **Scalability**: Can scale individual services
4. **Flexibility**: Easy to swap implementations
5. **Type Safety**: Full type hints throughout

## Future Enhancements

- GraphQL API layer
- Event-driven architecture with message queues
- Microservices deployment
- Advanced monitoring and observability
- Machine learning integration for predictions