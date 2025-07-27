#!/bin/sh

echo "Starting WoW Guild MCP Server with Redis..."
echo "==========================================="
echo "Redis URL: ${REDIS_URL}"
echo "Port: ${PORT}"
echo "WoW Version: ${WOW_VERSION}"
echo "==========================================="

# Start the application
exec python -m app.main_redis