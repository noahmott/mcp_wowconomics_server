"""
Database migration to create market history tables for persistent storage
"""

import asyncio
import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def create_market_history_tables():
    """Create market history tables for persistent time series data"""
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not found in environment variables")
        return False
    
    # Convert postgres:// to postgresql+asyncpg:// for async
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    
    engine = create_async_engine(database_url, echo=True)
    
    try:
        async with engine.begin() as conn:
            print("🗃️ Creating market history tables...")
            
            # Create market_history table for time series data
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS market_history (
                    id VARCHAR PRIMARY KEY,
                    region VARCHAR(10) NOT NULL,
                    realm_slug VARCHAR(100) NOT NULL,
                    item_id INTEGER NOT NULL,
                    price NUMERIC(20,2) NOT NULL,
                    quantity INTEGER NOT NULL,
                    timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
                );
            """))
            
            # Create indexes separately
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_market_lookup 
                ON market_history (region, realm_slug, item_id, timestamp DESC);
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_market_timestamp 
                ON market_history (timestamp DESC);
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_market_item 
                ON market_history (item_id, timestamp DESC);
            """))
            
            # Create item_metadata table for item information
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS item_metadata (
                    item_id INTEGER PRIMARY KEY,
                    item_name VARCHAR(200),
                    item_type VARCHAR(50),
                    item_subtype VARCHAR(50),
                    item_quality INTEGER,
                    last_updated TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
                );
            """))
            
            # Create market_snapshots table for tracking update runs
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS market_snapshots (
                    id VARCHAR PRIMARY KEY,
                    snapshot_time TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    realms_updated INTEGER DEFAULT 0,
                    items_tracked INTEGER DEFAULT 0,
                    success BOOLEAN DEFAULT TRUE,
                    error_message TEXT,
                    execution_time_seconds NUMERIC(10,2),
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
                );
            """))
            
            # Create indexes for efficient queries
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_snapshots_time 
                ON market_snapshots (snapshot_time DESC);
            """))
            
            # Create a function to get recent price trends
            await conn.execute(text("""
                CREATE OR REPLACE FUNCTION get_price_trends(
                    p_region VARCHAR,
                    p_realm VARCHAR,
                    p_item_id INTEGER,
                    p_hours INTEGER DEFAULT 24
                )
                RETURNS TABLE(
                    avg_price NUMERIC,
                    min_price NUMERIC,
                    max_price NUMERIC,
                    price_volatility NUMERIC,
                    data_points INTEGER,
                    oldest_timestamp TIMESTAMP,
                    newest_timestamp TIMESTAMP
                ) AS $$
                BEGIN
                    RETURN QUERY
                    SELECT 
                        AVG(price) as avg_price,
                        MIN(price) as min_price,
                        MAX(price) as max_price,
                        CASE 
                            WHEN AVG(price) > 0 THEN (MAX(price) - MIN(price)) / AVG(price)
                            ELSE 0
                        END as price_volatility,
                        COUNT(*)::INTEGER as data_points,
                        MIN(timestamp) as oldest_timestamp,
                        MAX(timestamp) as newest_timestamp
                    FROM market_history
                    WHERE region = p_region
                        AND realm_slug = p_realm
                        AND item_id = p_item_id
                        AND timestamp > NOW() - INTERVAL '1 hour' * p_hours;
                END;
                $$ LANGUAGE plpgsql;
            """))
            
            print("✅ Market history tables created successfully!")
            
            # Create data retention policy (keep 7 days of data)
            await conn.execute(text("""
                CREATE OR REPLACE FUNCTION cleanup_old_market_data()
                RETURNS INTEGER AS $$
                DECLARE
                    rows_deleted INTEGER;
                BEGIN
                    DELETE FROM market_history 
                    WHERE timestamp < NOW() - INTERVAL '7 days';
                    
                    GET DIAGNOSTICS rows_deleted = ROW_COUNT;
                    RETURN rows_deleted;
                END;
                $$ LANGUAGE plpgsql;
            """))
            
            print("✅ Data retention policy created (7 days)!")
            print("🎯 Market history system is ready for persistent storage!")
            
        return True
        
    except Exception as e:
        print(f"❌ Error creating market history tables: {str(e)}")
        return False
    
    finally:
        await engine.dispose()

if __name__ == "__main__":
    success = asyncio.run(create_market_history_tables())
    if success:
        print("\\n🚀 Market history migration completed successfully!")
        print("💡 Your time series data will now persist across restarts.")
    else:
        print("\\n❌ Market history migration failed!")
        sys.exit(1)