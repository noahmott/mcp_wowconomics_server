"""
Member database models and schemas
"""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field

from .database import Base


class Member(Base):
    """Member database model"""
    __tablename__ = "members"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guild_id = Column(UUID(as_uuid=True), ForeignKey("guilds.id"), nullable=False)
    
    # Character information
    character_name = Column(String(50), nullable=False)
    character_class = Column(String(20))
    character_spec = Column(String(30))
    character_race = Column(String(30))
    level = Column(Integer, default=1)
    
    # Guild-specific information
    guild_rank = Column(String(50))
    guild_rank_id = Column(Integer)
    
    # Activity tracking
    last_seen = Column(DateTime)
    last_login = Column(DateTime)
    achievement_points = Column(Integer, default=0)
    
    # Performance metrics
    item_level = Column(Integer, default=0)
    
    # Metadata
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Raw API data storage
    raw_data = Column(JSONB)
    equipment_data = Column(JSONB)
    achievement_data = Column(JSONB)
    mythic_plus_data = Column(JSONB)
    
    # Relationships
    guild = relationship("Guild", back_populates="members")
    raid_performances = relationship("RaidPerformance", back_populates="member", cascade="all, delete-orphan")
    
    # Indexes for efficient lookups
    __table_args__ = (
        Index('idx_member_guild_name', 'guild_id', 'character_name'),
        Index('idx_member_last_seen', 'last_seen'),
        Index('idx_member_active', 'is_active'),
        Index('idx_member_class', 'character_class'),
    )


# Pydantic schemas
class MemberBase(BaseModel):
    """Base member schema"""
    character_name: str = Field(..., max_length=50)
    character_class: Optional[str] = Field(None, max_length=20)
    character_spec: Optional[str] = Field(None, max_length=30)
    character_race: Optional[str] = Field(None, max_length=30)
    level: Optional[int] = Field(1, ge=1, le=80)
    guild_rank: Optional[str] = Field(None, max_length=50)
    guild_rank_id: Optional[int] = Field(None, ge=0)
    achievement_points: Optional[int] = Field(0, ge=0)
    item_level: Optional[int] = Field(0, ge=0)


class MemberCreate(MemberBase):
    """Schema for creating a member"""
    guild_id: uuid.UUID


class MemberUpdate(BaseModel):
    """Schema for updating a member"""
    character_class: Optional[str] = Field(None, max_length=20)
    character_spec: Optional[str] = Field(None, max_length=30)
    character_race: Optional[str] = Field(None, max_length=30)
    level: Optional[int] = Field(None, ge=1, le=80)
    guild_rank: Optional[str] = Field(None, max_length=50)
    guild_rank_id: Optional[int] = Field(None, ge=0)
    achievement_points: Optional[int] = Field(None, ge=0)
    item_level: Optional[int] = Field(None, ge=0)
    last_seen: Optional[datetime] = None
    last_login: Optional[datetime] = None
    is_active: Optional[bool] = None


class MemberResponse(MemberBase):
    """Schema for member responses"""
    id: uuid.UUID
    guild_id: uuid.UUID
    first_seen: datetime
    last_updated: datetime
    last_seen: Optional[datetime]
    last_login: Optional[datetime]
    is_active: bool
    
    class Config:
        from_attributes = True


class MemberPerformanceResponse(BaseModel):
    """Schema for member performance data"""
    member_info: Dict[str, Any]
    performance_metrics: Dict[str, Any]
    equipment_summary: Dict[str, Any]
    recent_achievements: list
    mythic_plus_score: Optional[float] = None
    
    class Config:
        from_attributes = True