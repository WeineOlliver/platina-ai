from pydantic import BaseModel, Field
from typing import Optional, List, Any


class RecentlyUnlockedItem(BaseModel):
    trophy_name: str
    unlocked_at: Optional[str] = None


class PlayerTrophyProgressItem(BaseModel):
    trophy_name: str
    trophy_type: str = "bronze"
    trophy_category: str = "standard"
    chapter_or_location: Optional[str] = None
    is_missable: bool = False


class PlayerProgressResponse(BaseModel):
    psn_id: str
    game: str
    platform: str = "PS5"
    total_trophies: int = 0
    unlocked_count: int = 0
    completion_percentage: float = 0.0
    pending_count: int = 0
    pending_missables_count: int = 0
    pending_missable_trophies: List[PlayerTrophyProgressItem] = Field(default_factory=list)
    recently_unlocked: List[RecentlyUnlockedItem] = Field(default_factory=list)
    unearned_trophies_summary: List[str] = Field(default_factory=list)
    quick_cleanup_trophies: List[PlayerTrophyProgressItem] = Field(default_factory=list)
    heavy_grind_trophies: List[PlayerTrophyProgressItem] = Field(default_factory=list)
    natural_grind_trophies: List[PlayerTrophyProgressItem] = Field(default_factory=list)
    pending_missables: List[PlayerTrophyProgressItem] = Field(default_factory=list)

    def __getitem__(self, item: str) -> Any:
        # ponytail: allow dictionary-style subscripting for backward-compatibility with untyped callers
        return getattr(self, item)
