"""
contracts.py - Typed Pydantic models for pipeline v2 and artifact contracts.
These models define the shape of JSON artifacts in:
- data/<game_id>/parsed/*.json (TrophyListParsed, GuideParsed)
- data/<game_id>/linked/game.json (LinkedGame)
"""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from src.pipeline.normalize import generate_trophy_id, normalize_name

# ---------------------------------------------------------
# 1. Catalog / Trophy List Contracts
# ---------------------------------------------------------


class TrophyParsed(BaseModel):
    """Individual trophy item parsed from catalog (e.g. PSNProfiles trophy list)."""

    name: str
    type: str  # bronze, silver, gold, platinum
    description: str
    group: str = "Base Game"  # "Base Game" or DLC name (e.g. Hearts of Stone, Blood and Wine)
    psnprofiles_trophy_id: Optional[int] = None


class TrophyListParsed(BaseModel):
    """Artifact of parsing a catalog trophy list source."""

    game_title: str
    np_communication_id: Optional[str] = None
    trophies: List[TrophyParsed] = Field(default_factory=list)


# ---------------------------------------------------------
# 2. Guide Contracts
# ---------------------------------------------------------


class GuideOverview(BaseModel):
    """High-level roadmap metrics extracted from a guide."""

    difficulty: Optional[str] = None
    hours: Optional[str] = None
    playthroughs: Optional[str] = None


class GuideMissable(BaseModel):
    """Missable trophy reference extracted from a guide."""

    trophy_name: str


GuideSectionKind = Literal["trophy", "roadmap", "collectible_group", "general"]


class GuideSection(BaseModel):
    """Granular structural section of a parsed guide."""

    order: int
    kind: GuideSectionKind
    title: str
    trophy_name: Optional[str] = None
    text: str
    parent_title: Optional[str] = None


class GuideParsed(BaseModel):
    """Artifact of parsing a guide or supplement source."""

    source_id: str
    overview: GuideOverview = Field(default_factory=GuideOverview)
    missables: List[GuideMissable] = Field(default_factory=list)
    locations: Dict[str, List[str]] = Field(default_factory=dict)  # {location: [trophy_name]}
    sections: List[GuideSection] = Field(default_factory=list)


# ---------------------------------------------------------
# 3. Linked Game Contracts
# ---------------------------------------------------------


class GameInfo(BaseModel):
    """Game metadata container."""

    id: str
    title: str
    np_communication_id: Optional[str] = None


class LinkedTrophy(BaseModel):
    """Consolidated trophy entity with deterministic id and multi-source enrichment."""

    trophy_id: str  # slug(game_id + nome normalizado)
    name: str
    type: str
    description: str
    group: str = "Base Game"
    psnprofiles_trophy_id: Optional[int] = None
    np_communication_id: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)  # Stored for future localized names
    missable_sources: List[str] = Field(default_factory=list)  # List of source IDs claiming missable


class LinkedSection(BaseModel):
    """Guide section resolved against canonical trophy catalog."""

    order: int
    kind: GuideSectionKind
    title: str
    trophy_name: Optional[str] = None
    trophy_id: Optional[str] = None  # Populated when kind == 'trophy' and link succeeded
    text: str
    parent_title: Optional[str] = None
    source_id: str


class LinkedConflict(BaseModel):
    """Recorded factual divergence between sources (e.g. missable classification mismatch)."""

    fact: str
    details: Dict[str, Any] = Field(default_factory=dict)


class LinkedUnlinked(BaseModel):
    """Section of kind 'trophy' that failed to match any catalog trophy."""

    section: GuideSection
    source_id: str
    reason: str


class LinkedGame(BaseModel):
    """Final unified linked game artifact produced by link stage."""

    game: GameInfo
    trophies: List[LinkedTrophy] = Field(default_factory=list)
    sections: List[LinkedSection] = Field(default_factory=list)
    conflicts: List[LinkedConflict] = Field(default_factory=list)
    unlinked: List[LinkedUnlinked] = Field(default_factory=list)


def compute_trophy_id(game_id: str, trophy_name: str) -> str:
    """Convenience alias for deterministic trophy_id generation."""
    return generate_trophy_id(game_id, trophy_name)
