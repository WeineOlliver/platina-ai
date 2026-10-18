from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from src.database import get_db_session
from src.models.player import PlayerModel, PlayerGameModel, PlayerTrophyModel
from src.schemas.player import PlayerProgressResponse, PlayerTrophyProgressItem, RecentlyUnlockedItem


class PlayerProgressService:
    """
    Queries player progress and trophy state across games for Agent tool use.
    """

    async def get_progress(self, psn_id: str, game_title: str) -> Optional[PlayerProgressResponse]:
        async with get_db_session() as session:
            stmt = (
                select(PlayerGameModel)
                .join(PlayerModel, PlayerModel.id == PlayerGameModel.player_id)
                .where(
                    PlayerModel.psn_id.ilike(psn_id.strip()),
                    PlayerGameModel.game_title.ilike(f"%{game_title.strip()}%"),
                )
                .options(selectinload(PlayerGameModel.trophies))
            )
            result = await session.execute(stmt)
            game_record = result.scalars().first()

            if not game_record:
                return None

            unlocked = [t for t in game_record.trophies if t.is_unlocked]
            pending = [t for t in game_record.trophies if not t.is_unlocked]

            def to_item(t: PlayerTrophyModel) -> PlayerTrophyProgressItem:
                category = getattr(t, "trophy_category", "standard") or "standard"
                return PlayerTrophyProgressItem(
                    trophy_name=t.trophy_name,
                    trophy_type=t.trophy_type,
                    trophy_category=category,
                    chapter_or_location=t.chapter_or_location,
                    is_missable=bool(t.is_missable),
                )

            pending_items = [to_item(t) for t in pending]
            pending_missables = [t for t in pending_items if t.is_missable or t.trophy_category == "missable"]
            quick_cleanup = [t for t in pending_items if t.trophy_category == "quick_cleanup"]
            heavy_grind = [t for t in pending_items if t.trophy_category == "heavy_grind"]
            natural_grind = [t for t in pending_items if t.trophy_category == "natural_grind"]

            total_count = len(game_record.trophies)
            unlocked_count = len(unlocked)
            completion_pct = round((unlocked_count / total_count * 100), 1) if total_count else 0.0

            recently_unlocked_items = [
                RecentlyUnlockedItem(
                    trophy_name=t.trophy_name,
                    unlocked_at=t.unlocked_at.isoformat() if t.unlocked_at else None,
                )
                for t in unlocked[-3:]
            ]

            unearned_summary = [
                f"{t.trophy_name} ({t.trophy_type}): {t.chapter_or_location or 'Troféu pendente'}"
                for t in pending[:15]
            ]

            return PlayerProgressResponse(
                psn_id=psn_id,
                game=game_record.game_title,
                platform=game_record.platform or "PS5",
                total_trophies=total_count,
                unlocked_count=unlocked_count,
                completion_percentage=completion_pct,
                pending_count=len(pending),
                pending_missables_count=len(pending_missables),
                pending_missable_trophies=pending_missables,
                quick_cleanup_trophies=quick_cleanup,
                heavy_grind_trophies=heavy_grind,
                natural_grind_trophies=natural_grind,
                pending_missables=pending_missables,
                unearned_trophies_summary=unearned_summary,
                recently_unlocked=recently_unlocked_items,
            )

    async def get_player_game_progress(self, psn_id: str, game_title: str) -> Optional[PlayerProgressResponse]:
        return await self.get_progress(psn_id, game_title)


player_progress_service = PlayerProgressService()
