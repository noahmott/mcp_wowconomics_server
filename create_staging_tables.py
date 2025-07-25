"""
Database migration script to create WoW data staging tables
"""

import asyncio
import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def create_staging_tables():
    """Create all staging tables for WoW data caching"""
    
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
            print("🗃️ Creating WoW data staging tables...")
            
            # Create wow_data_cache table
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS wow_data_cache (
                    id VARCHAR PRIMARY KEY,
                    data_type VARCHAR(50) NOT NULL,
                    cache_key VARCHAR(200) NOT NULL,
                    region VARCHAR(10) NOT NULL DEFAULT 'us',
                    data JSONB NOT NULL,
                    timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc'),
                    expires_at TIMESTAMP WITHOUT TIME ZONE,
                    is_valid BOOLEAN DEFAULT TRUE,
                    api_source VARCHAR(50) DEFAULT 'blizzard'
                );
            """))
            
            # Create indexes for wow_data_cache
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_cache_lookup 
                ON wow_data_cache (data_type, cache_key, region);
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_cache_timestamp 
                ON wow_data_cache (timestamp);
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_cache_expires 
                ON wow_data_cache (expires_at);
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_cache_valid 
                ON wow_data_cache (is_valid);
            """))
            
            # Create realm_status table
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS realm_status (
                    id VARCHAR PRIMARY KEY,
                    realm_slug VARCHAR(100) NOT NULL,
                    realm_name VARCHAR(100) NOT NULL,
                    region VARCHAR(10) NOT NULL,
                    population VARCHAR(20),
                    timezone VARCHAR(50),
                    realm_type VARCHAR(20),
                    connected_realms JSONB,
                    last_updated TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
                );
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_realm_lookup 
                ON realm_status (realm_slug, region);
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_realm_updated 
                ON realm_status (last_updated);
            """))
            
            # Create auction_snapshots table
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS auction_snapshots (
                    id VARCHAR PRIMARY KEY,
                    realm_slug VARCHAR(100) NOT NULL,
                    connected_realm_id VARCHAR(50) NOT NULL,
                    region VARCHAR(10) NOT NULL,
                    snapshot_time TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc'),
                    auction_count INTEGER DEFAULT 0,
                    total_value BIGINT DEFAULT 0,
                    average_value INTEGER DEFAULT 0,
                    data_hash VARCHAR(64),
                    raw_data JSONB
                );
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_auction_realm 
                ON auction_snapshots (realm_slug, snapshot_time);
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_auction_time 
                ON auction_snapshots (snapshot_time);
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_auction_hash 
                ON auction_snapshots (data_hash);
            """))
            
            # Create guild_cache table
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS guild_cache (
                    id VARCHAR PRIMARY KEY,
                    guild_name VARCHAR(100) NOT NULL,
                    realm_slug VARCHAR(100) NOT NULL,
                    region VARCHAR(10) NOT NULL,
                    member_count INTEGER DEFAULT 0,
                    achievement_points INTEGER DEFAULT 0,
                    average_item_level INTEGER DEFAULT 0,
                    guild_level INTEGER DEFAULT 0,
                    faction VARCHAR(20),
                    guild_data JSONB,
                    roster_data JSONB,
                    last_updated TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
                );
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_guild_lookup 
                ON guild_cache (guild_name, realm_slug, region);
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_guild_updated 
                ON guild_cache (last_updated);
            """))
            
            # Create token_price_history table
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS token_price_history (
                    id VARCHAR PRIMARY KEY,
                    region VARCHAR(10) NOT NULL,
                    price INTEGER NOT NULL,
                    timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc'),
                    last_updated_timestamp INTEGER
                );
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_token_region_time 
                ON token_price_history (region, timestamp);
            """))
            
            # Create data_collection_log table
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS data_collection_log (
                    id VARCHAR PRIMARY KEY,
                    collection_type VARCHAR(50) NOT NULL,
                    target VARCHAR(200) NOT NULL,
                    region VARCHAR(10) NOT NULL,
                    status VARCHAR(20) NOT NULL,
                    error_message TEXT,
                    records_collected INTEGER DEFAULT 0,
                    execution_time INTEGER,
                    timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
                );
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_collection_type_time 
                ON data_collection_log (collection_type, timestamp);
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_collection_status 
                ON data_collection_log (status);
            """))
            
            print("✅ All staging tables created successfully!")
            
            # Insert some example data for demonstration
            print("📝 Inserting example data...")
            
            import uuid
            import json
            from datetime import datetime
            
            # Example realm data
            await conn.execute(text("""
                INSERT INTO wow_data_cache (id, data_type, cache_key, region, data, api_source)
                VALUES (:id, 'realm', 'stormrage', 'us', :data, 'example')
                ON CONFLICT (id) DO NOTHING
            """), {
                'id': str(uuid.uuid4()),
                'data': json.dumps({
                    'name': 'Stormrage',
                    'slug': 'stormrage',
                    'population': {'name': 'High'},
                    'type': {'name': 'Normal'},
                    'timezone': 'America/New_York'
                })
            })
            
            # Example auction data
            await conn.execute(text("""
                INSERT INTO wow_data_cache (id, data_type, cache_key, region, data, api_source)
                VALUES (:id, 'auction', 'stormrage', 'us', :data, 'example')
                ON CONFLICT (id) DO NOTHING
            """), {
                'id': str(uuid.uuid4()),
                'data': json.dumps({
                    'auctions': [
                        {
                            'id': 12345 + i,
                            'item': {'id': 171276 + (i % 100)},
                            'buyout': 1000000 + (i * 50000),
                            'quantity': 1,
                            'time_left': 'LONG'
                        } for i in range(100)
                    ]
                })
            })
            
            # Example token data
            await conn.execute(text("""
                INSERT INTO wow_data_cache (id, data_type, cache_key, region, data, api_source)
                VALUES (:id, 'token', 'current', 'us', :data, 'example')
                ON CONFLICT (id) DO NOTHING
            """), {
                'id': str(uuid.uuid4()),
                'data': json.dumps({
                    'price': 2500000,  # 250g
                    'last_updated_timestamp': int(datetime.now().timestamp())
                })
            })
            
            print("✅ Example data inserted successfully!")
            print("🎯 Staging system is ready for use!")
            
        return True
        
    except Exception as e:
        print(f"❌ Error creating staging tables: {str(e)}")
        return False
    
    finally:
        await engine.dispose()

if __name__ == "__main__":
    success = asyncio.run(create_staging_tables())
    if success:
        print("\\n🚀 Database migration completed successfully!")
        print("💡 You can now use the enhanced MCP server with data staging.")
    else:
        print("\\n❌ Database migration failed!")
        sys.exit(1)