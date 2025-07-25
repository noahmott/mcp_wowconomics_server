"""
Database migration script to create member history tables
"""

import asyncio
import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def create_member_history_tables():
    """Create member history tables for tracking guild member changes over time"""
    
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
            print("🗃️ Creating member history tables...")
            
            # Create member_history table
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS member_history (
                    id VARCHAR PRIMARY KEY,
                    member_id UUID NOT NULL,
                    guild_id UUID NOT NULL,
                    character_name VARCHAR(50) NOT NULL,
                    character_class VARCHAR(20),
                    character_spec VARCHAR(30),
                    level INTEGER,
                    guild_rank VARCHAR(50),
                    guild_rank_id INTEGER,
                    item_level INTEGER,
                    achievement_points INTEGER,
                    last_login TIMESTAMP WITHOUT TIME ZONE,
                    snapshot_date DATE NOT NULL,
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
                    UNIQUE(member_id, snapshot_date)
                );
            """))
            
            # Create indexes for efficient queries
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_member_history_member_id 
                ON member_history (member_id, snapshot_date DESC);
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_member_history_guild_id 
                ON member_history (guild_id, snapshot_date DESC);
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_member_history_snapshot 
                ON member_history (snapshot_date DESC);
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_member_history_character 
                ON member_history (character_name, snapshot_date DESC);
            """))
            
            # Create guild_history table for guild-level metrics
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS guild_history (
                    id VARCHAR PRIMARY KEY,
                    guild_id UUID NOT NULL,
                    guild_name VARCHAR(100) NOT NULL,
                    realm_slug VARCHAR(100) NOT NULL,
                    member_count INTEGER DEFAULT 0,
                    average_item_level NUMERIC(10,2),
                    total_achievement_points INTEGER DEFAULT 0,
                    active_members INTEGER DEFAULT 0,
                    inactive_members INTEGER DEFAULT 0,
                    snapshot_date DATE NOT NULL,
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
                    UNIQUE(guild_id, snapshot_date)
                );
            """))
            
            # Create indexes for guild_history
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_guild_history_guild_id 
                ON guild_history (guild_id, snapshot_date DESC);
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_guild_history_snapshot 
                ON guild_history (snapshot_date DESC);
            """))
            
            # Create member_activity_log table for tracking joins/leaves
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS member_activity_log (
                    id VARCHAR PRIMARY KEY,
                    member_id UUID NOT NULL,
                    guild_id UUID NOT NULL,
                    character_name VARCHAR(50) NOT NULL,
                    activity_type VARCHAR(20) NOT NULL, -- 'joined', 'left', 'promoted', 'demoted'
                    old_value VARCHAR(100),
                    new_value VARCHAR(100),
                    detected_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
                );
            """))
            
            # Create indexes for activity log
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_activity_log_member 
                ON member_activity_log (member_id, detected_at DESC);
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_activity_log_guild 
                ON member_activity_log (guild_id, detected_at DESC);
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_activity_log_type 
                ON member_activity_log (activity_type, detected_at DESC);
            """))
            
            print("✅ All member history tables created successfully!")
            
            # Create a function to snapshot current members
            await conn.execute(text("""
                CREATE OR REPLACE FUNCTION snapshot_guild_members(target_guild_id UUID)
                RETURNS INTEGER AS $$
                DECLARE
                    rows_inserted INTEGER;
                BEGIN
                    -- Insert member snapshots for today
                    INSERT INTO member_history (
                        id, member_id, guild_id, character_name, character_class,
                        character_spec, level, guild_rank, guild_rank_id,
                        item_level, achievement_points, last_login, snapshot_date
                    )
                    SELECT 
                        gen_random_uuid()::text,
                        id, guild_id, character_name, character_class,
                        character_spec, level, guild_rank, guild_rank_id,
                        item_level, achievement_points, last_login, CURRENT_DATE
                    FROM members
                    WHERE guild_id = target_guild_id
                    ON CONFLICT (member_id, snapshot_date) DO UPDATE SET
                        character_class = EXCLUDED.character_class,
                        character_spec = EXCLUDED.character_spec,
                        level = EXCLUDED.level,
                        guild_rank = EXCLUDED.guild_rank,
                        guild_rank_id = EXCLUDED.guild_rank_id,
                        item_level = EXCLUDED.item_level,
                        achievement_points = EXCLUDED.achievement_points,
                        last_login = EXCLUDED.last_login;
                    
                    GET DIAGNOSTICS rows_inserted = ROW_COUNT;
                    RETURN rows_inserted;
                END;
                $$ LANGUAGE plpgsql;
            """))
            
            print("✅ Snapshot function created!")
            print("🎯 Member history system is ready for use!")
            
        return True
        
    except Exception as e:
        print(f"❌ Error creating member history tables: {str(e)}")
        return False
    
    finally:
        await engine.dispose()

if __name__ == "__main__":
    success = asyncio.run(create_member_history_tables())
    if success:
        print("\\n🚀 Member history migration completed successfully!")
        print("💡 Your database now supports historical member tracking.")
    else:
        print("\\n❌ Member history migration failed!")
        sys.exit(1)