"""
Blizzard API Models

Pydantic models for Blizzard API responses.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class Realm(BaseModel):
    """Realm model."""
    id: int
    name: str
    slug: str

    class Config:
        orm_mode = True


class Faction(BaseModel):
    """Faction model."""
    type: str
    name: str


class PlayableClass(BaseModel):
    """Playable class model."""
    id: int
    name: str


class PlayableRace(BaseModel):
    """Playable race model."""
    id: int
    name: str


class Character(BaseModel):
    """Basic character model."""
    id: Optional[int] = None
    name: str
    realm: Realm
    level: int
    playable_class: Optional[PlayableClass] = Field(None, alias="class")
    playable_race: Optional[PlayableRace] = Field(None, alias="race")

    class Config:
        allow_population_by_field_name = True


class GuildMember(BaseModel):
    """Guild member model."""
    character: Character
    rank: int


class GuildProfile(BaseModel):
    """Guild profile model."""
    id: Optional[int] = None
    name: str
    faction: Faction
    achievement_points: int
    member_count: int
    realm: Realm
    created_timestamp: Optional[int] = None

    class Config:
        orm_mode = True


class CharacterProfile(BaseModel):
    """Character profile model."""
    id: int
    name: str
    gender: Dict[str, Any]
    faction: Faction
    race: PlayableRace
    character_class: PlayableClass
    active_spec: Optional[Dict[str, Any]] = None
    realm: Realm
    guild: Optional[Dict[str, Any]] = None
    level: int
    experience: int
    achievement_points: int
    last_login_timestamp: Optional[int] = None
    average_item_level: Optional[int] = None
    equipped_item_level: Optional[int] = None

    class Config:
        orm_mode = True


class EquippedItem(BaseModel):
    """Equipped item model."""
    item: Dict[str, Any]
    slot: Dict[str, Any]
    quantity: int = 1
    context: Optional[int] = None
    bonus_list: Optional[List[int]] = None
    quality: Optional[Dict[str, Any]] = None
    name: Optional[str] = None
    level: Optional[Dict[str, Any]] = None
    stats: Optional[List[Dict[str, Any]]] = None
    enchantments: Optional[List[Dict[str, Any]]] = None
    sockets: Optional[List[Dict[str, Any]]] = None


class CharacterEquipment(BaseModel):
    """Character equipment model."""
    equipped_items: List[EquippedItem]
    equipped_item_level: int

    class Config:
        orm_mode = True


class MythicKeystoneRun(BaseModel):
    """Mythic keystone run model."""
    completed_timestamp: int
    duration: int
    keystone_level: int
    keystone_affixes: List[Dict[str, Any]]
    members: List[Dict[str, Any]]
    dungeon: Dict[str, Any]
    is_completed_within_time: bool
    mythic_rating: Optional[Dict[str, Any]] = None


class MythicPlusProfile(BaseModel):
    """Mythic+ profile model."""
    current_period: Optional[Dict[str, Any]] = None
    seasons: Optional[List[Dict[str, Any]]] = None
    character: Character
    current_mythic_rating: Optional[Dict[str, Any]] = None

    class Config:
        orm_mode = True


class RaidEncounter(BaseModel):
    """Raid encounter model."""
    encounter: Dict[str, Any]
    completed_count: int
    last_kill_timestamp: Optional[int] = None


class RaidInstance(BaseModel):
    """Raid instance model."""
    instance: Dict[str, Any]
    modes: List[Dict[str, Any]]


class RaidProgression(BaseModel):
    """Raid progression model."""
    character: Character
    expansions: List[Dict[str, Any]]

    class Config:
        orm_mode = True


class Auction(BaseModel):
    """Auction model."""
    id: int
    item: Dict[str, Any]
    quantity: int
    unit_price: Optional[int] = None
    bid: Optional[int] = None
    buyout: Optional[int] = None
    time_left: str


class AuctionData(BaseModel):
    """Auction house data model."""
    auctions: List[Auction]
    commodities: Optional[Dict[str, Any]] = None

    class Config:
        orm_mode = True


class TokenPrice(BaseModel):
    """WoW Token price model."""
    last_updated_timestamp: int
    price: int

    class Config:
        orm_mode = True
