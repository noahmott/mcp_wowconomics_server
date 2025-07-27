#!/bin/bash

# Script to configure RedisInsight database connection via API
echo "Waiting for RedisInsight to be ready..."
sleep 10

# Wait for RedisInsight API to be available
until curl -s http://localhost:5540/api/health > /dev/null; do
    echo "Waiting for RedisInsight API..."
    sleep 2
done

echo "RedisInsight API is ready. Adding database connection..."

# Add Redis database connection via API
curl -X POST http://localhost:5540/api/instance \
  -H "Content-Type: application/json" \
  -d '{
    "host": "redis",
    "port": 6379,
    "name": "WoW Guild Cache",
    "connectionType": "STANDALONE",
    "timeout": 30000
  }'

echo "Database connection added successfully!"