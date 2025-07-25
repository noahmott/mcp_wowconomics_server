"""
Database migration to create comprehensive auction snapshot tables
This properly captures aggregate market data, not just individual price points
"""

import asyncio
import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def create_auction_snapshot_tables():
    """Create auction snapshot tables for proper market analysis"""
    
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
            print("🗃️ Creating comprehensive auction snapshot tables...")
            
            # Create auction_market_snapshots table for aggregate data
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS auction_market_snapshots (
                    id VARCHAR PRIMARY KEY,
                    timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    region VARCHAR(10) NOT NULL,
                    realm_slug VARCHAR(100) NOT NULL,
                    connected_realm_id VARCHAR(50),
                    item_id INTEGER NOT NULL,
                    -- Aggregate market data
                    total_quantity INTEGER NOT NULL,
                    auction_count INTEGER NOT NULL,
                    unique_sellers INTEGER,
                    -- Price statistics
                    min_price NUMERIC(20,2),
                    max_price NUMERIC(20,2),
                    avg_price NUMERIC(20,2),
                    median_price NUMERIC(20,2),
                    std_dev_price NUMERIC(20,2),
                    -- Market concentration
                    top_seller_quantity INTEGER,
                    top_seller_percentage NUMERIC(5,2),
                    -- Additional metrics
                    total_market_value NUMERIC(20,2),
                    price_per_unit_mode NUMERIC(20,2),
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
                );
            """))
            
            # Create comprehensive indexes
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_snapshot_lookup 
                ON auction_market_snapshots (region, realm_slug, item_id, timestamp DESC);
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_snapshot_item_quantity 
                ON auction_market_snapshots (item_id, total_quantity DESC);
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_snapshot_timestamp 
                ON auction_market_snapshots (timestamp DESC);
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_snapshot_realm_time 
                ON auction_market_snapshots (realm_slug, timestamp DESC);
            """))
            
            # Create price distribution table
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS auction_price_distributions (
                    id VARCHAR PRIMARY KEY,
                    snapshot_id VARCHAR REFERENCES auction_market_snapshots(id),
                    price_point NUMERIC(20,2) NOT NULL,
                    quantity_at_price INTEGER NOT NULL,
                    sellers_at_price INTEGER,
                    percentage_of_market NUMERIC(5,2),
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
                );
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_price_dist_snapshot 
                ON auction_price_distributions (snapshot_id);
            """))
            
            # Create market velocity table
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS market_velocity (
                    id VARCHAR PRIMARY KEY,
                    region VARCHAR(10) NOT NULL,
                    realm_slug VARCHAR(100) NOT NULL,
                    item_id INTEGER NOT NULL,
                    measurement_date DATE NOT NULL,
                    -- Velocity metrics
                    listings_added INTEGER DEFAULT 0,
                    listings_removed INTEGER DEFAULT 0,
                    estimated_sales INTEGER DEFAULT 0,
                    quantity_turnover INTEGER DEFAULT 0,
                    -- Price movement
                    price_changes INTEGER DEFAULT 0,
                    avg_price_start NUMERIC(20,2),
                    avg_price_end NUMERIC(20,2),
                    price_volatility NUMERIC(10,4),
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
                    UNIQUE(region, realm_slug, item_id, measurement_date)
                );
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_velocity_lookup 
                ON market_velocity (region, realm_slug, item_id, measurement_date DESC);
            """))
            
            # Create functions for analysis
            await conn.execute(text("""
                CREATE OR REPLACE FUNCTION get_items_by_quantity(
                    p_region VARCHAR,
                    p_realm VARCHAR,
                    p_hours INTEGER DEFAULT 24,
                    p_limit INTEGER DEFAULT 50
                )
                RETURNS TABLE(
                    item_id INTEGER,
                    avg_quantity NUMERIC,
                    avg_price NUMERIC,
                    total_auctions BIGINT,
                    snapshots_count BIGINT,
                    quantity_trend NUMERIC
                ) AS $$
                BEGIN
                    RETURN QUERY
                    WITH recent_data AS (
                        SELECT 
                            ams.item_id,
                            ams.total_quantity,
                            ams.avg_price,
                            ams.auction_count,
                            ams.timestamp,
                            LAG(ams.total_quantity) OVER (PARTITION BY ams.item_id ORDER BY ams.timestamp) as prev_quantity
                        FROM auction_market_snapshots ams
                        WHERE ams.region = p_region
                            AND ams.realm_slug = p_realm
                            AND ams.timestamp > NOW() - INTERVAL '1 hour' * p_hours
                    )
                    SELECT 
                        rd.item_id,
                        AVG(rd.total_quantity)::NUMERIC as avg_quantity,
                        AVG(rd.avg_price)::NUMERIC as avg_price,
                        SUM(rd.auction_count)::BIGINT as total_auctions,
                        COUNT(*)::BIGINT as snapshots_count,
                        CASE 
                            WHEN COUNT(rd.prev_quantity) > 0 THEN 
                                (AVG(rd.total_quantity) - AVG(rd.prev_quantity)) / NULLIF(AVG(rd.prev_quantity), 0)
                            ELSE 0
                        END::NUMERIC as quantity_trend
                    FROM recent_data rd
                    GROUP BY rd.item_id
                    ORDER BY avg_quantity DESC
                    LIMIT p_limit;
                END;
                $$ LANGUAGE plpgsql;
            """))
            
            await conn.execute(text("""
                CREATE OR REPLACE FUNCTION get_market_depth(
                    p_region VARCHAR,
                    p_realm VARCHAR,
                    p_item_id INTEGER
                )
                RETURNS TABLE(
                    price_point NUMERIC,
                    total_quantity BIGINT,
                    seller_count BIGINT,
                    market_share NUMERIC,
                    cumulative_quantity BIGINT
                ) AS $$
                BEGIN
                    RETURN QUERY
                    WITH latest_snapshot AS (
                        SELECT id
                        FROM auction_market_snapshots
                        WHERE region = p_region
                            AND realm_slug = p_realm
                            AND item_id = p_item_id
                        ORDER BY timestamp DESC
                        LIMIT 1
                    )
                    SELECT 
                        apd.price_point,
                        SUM(apd.quantity_at_price)::BIGINT as total_quantity,
                        SUM(apd.sellers_at_price)::BIGINT as seller_count,
                        apd.percentage_of_market,
                        SUM(SUM(apd.quantity_at_price)) OVER (ORDER BY apd.price_point)::BIGINT as cumulative_quantity
                    FROM auction_price_distributions apd
                    WHERE apd.snapshot_id = (SELECT id FROM latest_snapshot)
                    GROUP BY apd.price_point, apd.percentage_of_market
                    ORDER BY apd.price_point;
                END;
                $$ LANGUAGE plpgsql;
            """))
            
            print("✅ Auction snapshot tables created successfully!")
            
            # Create data retention policy
            await conn.execute(text("""
                CREATE OR REPLACE FUNCTION cleanup_old_auction_data()
                RETURNS INTEGER AS $$
                DECLARE
                    rows_deleted INTEGER;
                    total_deleted INTEGER := 0;
                BEGIN
                    -- Keep detailed snapshots for 7 days
                    DELETE FROM auction_price_distributions 
                    WHERE created_at < NOW() - INTERVAL '7 days';
                    GET DIAGNOSTICS rows_deleted = ROW_COUNT;
                    total_deleted := total_deleted + rows_deleted;
                    
                    -- Keep aggregate snapshots for 30 days
                    DELETE FROM auction_market_snapshots 
                    WHERE timestamp < NOW() - INTERVAL '30 days';
                    GET DIAGNOSTICS rows_deleted = ROW_COUNT;
                    total_deleted := total_deleted + rows_deleted;
                    
                    RETURN total_deleted;
                END;
                $$ LANGUAGE plpgsql;
            """))
            
            print("✅ Analysis functions created!")
            print("🎯 Auction snapshot system ready for comprehensive market analysis!")
            
        return True
        
    except Exception as e:
        print(f"❌ Error creating auction snapshot tables: {str(e)}")
        return False
    
    finally:
        await engine.dispose()

if __name__ == "__main__":
    success = asyncio.run(create_auction_snapshot_tables())
    if success:
        print("\\n🚀 Auction snapshot migration completed successfully!")
        print("💡 Your system now captures complete market aggregate data.")
    else:
        print("\\n❌ Auction snapshot migration failed!")
        sys.exit(1)