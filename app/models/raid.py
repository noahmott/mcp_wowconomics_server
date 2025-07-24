"""
Raid progression database models and schemas
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Float, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field
from enum import Enum

from .database import Base


class DifficultyEnum(str, Enum):
    """Raid difficulty levels"""
    NORMAL = "normal"
    HEROIC = "heroic"
    MYTHIC = "mythic"
    LFR = "lfr"


class RaidProgress(Base):
    """Raid progression tracking for guilds"""
    __tablename__ = "raid_progress"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guild_id = Column(UUID(as_uuid=True), ForeignKey("guilds.id"), nullable=False)
    
    # Raid information
    raid_name = Column(String(100), nullable=False)
    raid_slug = Column(String(50), nullable=False)
    difficulty = Column(String(20), nullable=False)
    
    # Progress tracking
    total_bosses = Column(Integer, default=0)
    bosses_killed = Column(Integer, default=0)
    progress_percentage = Column(Float, default=0.0)
    
    # Timing
    first_kill_date = Column(DateTime)
    last_kill_date = Column(DateTime)
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    # Metadata
    is_current_tier = Column(Boolean, default=True)
    raw_data = Column(JSONB)
    
    # Relationships
    guild = relationship("Guild", back_populates="raid_progress")
    performances = relationship("RaidPerformance", back_populates="raid_progress", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_raid_guild_name_diff', 'guild_id', 'raid_slug', 'difficulty'),
        Index('idx_raid_current_tier', 'is_current_tier'),
        Index('idx_raid_updated', 'last_updated'),
    )


class RaidPerformance(Base):
    """Individual member performance in raids"""
    __tablename__ = "raid_performances"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    member_id = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False)
    raid_progress_id = Column(UUID(as_uuid=True), ForeignKey("raid_progress.id"), nullable=False)
    
    # Performance metrics
    boss_name = Column(String(100))
    encounter_id = Column(Integer)
    damage_done = Column(Integer, default=0)
    healing_done = Column(Integer, default=0)
    damage_taken = Column(Integer, default=0)
    deaths = Column(Integer, default=0)
    
    # Parse data
    parse_percentile = Column(Float)  # Warcraft Logs percentile
    dps = Column(Float, default=0.0)
    hps = Column(Float, default=0.0)
    
    # Metadata
    encounter_date = Column(DateTime)
    log_id = Column(String(50))  # Warcraft Logs ID
    fight_id = Column(Integer)
    duration_ms = Column(Integer)
    
    # Raw performance data
    raw_data = Column(JSONB)
    
    # Relationships
    member = relationship("Member", back_populates="raid_performances")
    raid_progress = relationship("RaidProgress", back_populates="performances")
    
    # Indexes
    __table_args__ = (
        Index('idx_perf_member_raid', 'member_id', 'raid_progress_id'),
        Index('idx_perf_encounter_date', 'encounter_date'),
        Index('idx_perf_boss', 'boss_name'),
    )


# Pydantic schemas
class RaidProgressBase(BaseModel):
    """Base raid progress schema"""
    raid_name: str = Field(..., max_length=100)
    raid_slug: str = Field(..., max_length=50)
    difficulty: DifficultyEnum
    total_bosses: Optional[int] = Field(0, ge=0)
    bosses_killed: Optional[int] = Field(0, ge=0)
    progress_percentage: Optional[float] = Field(0.0, ge=0.0, le=100.0)


class RaidProgressCreate(RaidProgressBase):
    """Schema for creating raid progress"""
    guild_id: uuid.UUID


class RaidProgressUpdate(BaseModel):
    """Schema for updating raid progress"""
    total_bosses: Optional[int] = Field(None, ge=0)
    bosses_killed: Optional[int] = Field(None, ge=0)
    progress_percentage: Optional[float] = Field(None, ge=0.0, le=100.0)
    first_kill_date: Optional[datetime] = None
    last_kill_date: Optional[datetime] = None
    is_current_tier: Optional[bool] = None


class RaidProgressResponse(RaidProgressBase):
    """Schema for raid progress responses"""
    id: uuid.UUID
    guild_id: uuid.UUID
    first_kill_date: Optional[datetime]
    last_kill_date: Optional[datetime]
    last_updated: datetime
    is_current_tier: bool
    
    class Config:
        from_attributes = True


class RaidPerformanceBase(BaseModel):
    """Base raid performance schema"""
    boss_name: Optional[str] = Field(None, max_length=100)
    encounter_id: Optional[int] = None
    damage_done: Optional[int] = Field(0, ge=0)
    healing_done: Optional[int] = Field(0, ge=0)
    damage_taken: Optional[int] = Field(0, ge=0)
    deaths: Optional[int] = Field(0, ge=0)
    parse_percentile: Optional[float] = Field(None, ge=0.0, le=100.0)
    dps: Optional[float] = Field(0.0, ge=0.0)
    hps: Optional[float] = Field(0.0, ge=0.0)


class RaidPerformanceCreate(RaidPerformanceBase):
    """Schema for creating raid performance"""
    member_id: uuid.UUID
    raid_progress_id: uuid.UUID


class RaidPerformanceResponse(RaidPerformanceBase):
    """Schema for raid performance responses"""
    id: uuid.UUID
    member_id: uuid.UUID
    raid_progress_id: uuid.UUID
    encounter_date: Optional[datetime]
    log_id: Optional[str]
    fight_id: Optional[int]
    duration_ms: Optional[int]
    
    class Config:
        from_attributes = True


class RaidAnalysisResponse(BaseModel):
    """Schema for comprehensive raid analysis"""
    guild_progress: List[RaidProgressResponse]
    top_performers: Dict[str, List[Dict[str, Any]]]
    progress_trends: Dict[str, Any]
    upcoming_encounters: List[Dict[str, Any]]
    performance_insights: List[str]
    
    class Config:
        from_attributes = True