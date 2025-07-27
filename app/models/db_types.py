"""
Database type compatibility layer
"""

import os
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB as PostgresJSONB

# Check if we're using PostgreSQL or SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Use JSONB for PostgreSQL, JSON for SQLite
if "postgresql" in DATABASE_URL or "postgres" in DATABASE_URL:
    JSONB = PostgresJSONB
else:
    # SQLite doesn't support JSONB, use JSON instead
    JSONB = JSON