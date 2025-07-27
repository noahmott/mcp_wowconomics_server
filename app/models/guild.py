"""
Guild database models and schemas
"""

import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from .db_types import JSONB
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field

from .database import Base


class Guild(Base):
    """Guild database model"""
    __tablename__ = "guilds"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    realm = Column(String(50), nullable=False)
    name = Column(String(100), nullable=False)
    faction = Column(String(20))  # Alliance/Horde
    game_version = Column(String(20), default='retail')  # 'retail' or 'classic'
    level = Column(Integer, default=0)
    member_count = Column(Integer, default=0)
    achievement_points = Column(Integer, default=0)
    
    # Metadata
    created_date = Column(DateTime)
    last_updated = Column(DateTime, default=datetime.utcnow)
    last_crawled = Column(DateTime)
    is_active = Column(Boolean, default=True)
    
    # Raw API data storage
    raw_data = Column(JSONB)
    
    # Relationships
    members = relationship("Member", back_populates="guild", cascade="all, delete-orphan")
    raid_progress = relationship("RaidProgress", back_populates="guild", cascade="all, delete-orphan")
    
    # Composite indexes for efficient lookups
    __table_args__ = (
        Index('idx_guild_realm_name', 'realm', 'name'),
        Index('idx_guild_updated', 'last_updated'),
        Index('idx_guild_active', 'is_active'),
        Index('idx_guild_version', 'game_version'),
    )


# Pydantic schemas
class GuildBase(BaseModel):
    """Base guild schema"""
    realm: str = Field(..., max_length=50)
    name: str = Field(..., max_length=100)
    faction: Optional[str] = Field(None, max_length=20)
    level: Optional[int] = Field(0, ge=0)
    member_count: Optional[int] = Field(0, ge=0)
    achievement_points: Optional[int] = Field(0, ge=0)


class GuildCreate(GuildBase):
    """Schema for creating a guild"""
    pass


class GuildUpdate(BaseModel):
    """Schema for updating a guild"""
    faction: Optional[str] = Field(None, max_length=20)
    level: Optional[int] = Field(None, ge=0)
    member_count: Optional[int] = Field(None, ge=0)
    achievement_points: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class GuildResponse(GuildBase):
    """Schema for guild responses"""
    id: uuid.UUID
    created_date: Optional[datetime]
    last_updated: datetime
    last_crawled: Optional[datetime]
    is_active: bool
    
    class Config:
        from_attributes = True


class GuildAnalysisResponse(BaseModel):
    """Schema for guild analysis responses"""
    guild_info: dict
    member_data: List[dict]
    analysis_results: dict
    visualization_urls: List[str]
    
    class Config:
        from_attributes = True