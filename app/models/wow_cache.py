"""
WoW Data Caching Models for Staging System
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()

class WoWDataCache(Base):
    """
    Universal cache table for all WoW API data
    """
    __tablename__ = "wow_data_cache"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    data_type = Column(String(50), nullable=False)  # 'auction', 'guild', 'realm', 'character'
    cache_key = Column(String(200), nullable=False)  # realm-slug, guild-realm-name, etc.
    region = Column(String(10), nullable=False, default='us')  # us, eu, kr, tw, cn
    game_version = Column(String(20), default='retail')  # 'retail' or 'classic'
    data = Column(JSON, nullable=False)  # The actual API response
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)  # Optional expiration
    is_valid = Column(Boolean, default=True)  # Mark as invalid if outdated
    api_source = Column(String(50), default='blizzard')  # Track data source
    
    # Composite indexes for fast lookups
    __table_args__ = (
        Index('idx_cache_lookup', 'data_type', 'cache_key', 'region', 'game_version'),
        Index('idx_cache_timestamp', 'timestamp'),
        Index('idx_cache_expires', 'expires_at'),
        Index('idx_cache_valid', 'is_valid'),
    )

class RealmStatus(Base):
    """
    Track realm population and status over time
    """
    __tablename__ = "realm_status"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    realm_slug = Column(String(100), nullable=False)
    realm_name = Column(String(100), nullable=False)
    region = Column(String(10), nullable=False)
    population = Column(String(20))  # Low, Medium, High, Full
    timezone = Column(String(50))
    realm_type = Column(String(20))  # PvP, PvE, RP, etc.
    connected_realms = Column(JSON)  # List of connected realm slugs
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_realm_lookup', 'realm_slug', 'region'),
        Index('idx_realm_updated', 'last_updated'),
    )

class AuctionSnapshot(Base):
    """
    Store periodic auction house snapshots
    """
    __tablename__ = "auction_snapshots"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    realm_slug = Column(String(100), nullable=False)
    connected_realm_id = Column(String(50), nullable=False)
    region = Column(String(10), nullable=False)
    snapshot_time = Column(DateTime, nullable=False, default=datetime.utcnow)
    auction_count = Column(Integer, default=0)
    total_value = Column(Integer, default=0)  # Total buyout value in copper
    average_value = Column(Integer, default=0)  # Average auction value
    data_hash = Column(String(64))  # Hash of auction data for deduplication
    raw_data = Column(JSON)  # Store raw auction data
    
    __table_args__ = (
        Index('idx_auction_realm', 'realm_slug', 'snapshot_time'),
        Index('idx_auction_time', 'snapshot_time'),
        Index('idx_auction_hash', 'data_hash'),
    )

class GuildCache(Base):
    """
    Cache guild information with member data
    """
    __tablename__ = "guild_cache"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    guild_name = Column(String(100), nullable=False)
    realm_slug = Column(String(100), nullable=False)
    region = Column(String(10), nullable=False)
    member_count = Column(Integer, default=0)
    achievement_points = Column(Integer, default=0)
    average_item_level = Column(Integer, default=0)
    guild_level = Column(Integer, default=0)
    faction = Column(String(20))  # Alliance, Horde
    guild_data = Column(JSON)  # Full guild information
    roster_data = Column(JSON)  # Member roster
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_guild_lookup', 'guild_name', 'realm_slug', 'region'),
        Index('idx_guild_updated', 'last_updated'),
    )

class TokenPriceHistory(Base):
    """
    Track WoW Token price changes over time
    """
    __tablename__ = "token_price_history"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    region = Column(String(10), nullable=False)
    price = Column(Integer, nullable=False)  # Price in copper
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_updated_timestamp = Column(Integer)  # From API
    
    __table_args__ = (
        Index('idx_token_region_time', 'region', 'timestamp'),
    )

class DataCollectionLog(Base):
    """
    Track data collection attempts and success rates
    """
    __tablename__ = "data_collection_log"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    collection_type = Column(String(50), nullable=False)  # 'auction', 'guild', etc.
    target = Column(String(200), nullable=False)  # realm, guild name, etc.
    region = Column(String(10), nullable=False)
    status = Column(String(20), nullable=False)  # 'success', 'failed', 'partial'
    error_message = Column(Text)
    records_collected = Column(Integer, default=0)
    execution_time = Column(Integer)  # Milliseconds
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_collection_type_time', 'collection_type', 'timestamp'),
        Index('idx_collection_status', 'status'),
    )