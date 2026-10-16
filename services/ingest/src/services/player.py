from typing import Optional, List, Dict, Any
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from src.database import get_db_session
from src.models.player import PlayerModel, PlayerGameModel, PlayerTrophyModel


class PlayerProgressService:
    """
    Queries player progress and trophy state across games for Agent tool use.
    """

    async def get_player_game_progress(self, psn_id: str, game_title: str) -> Optional[Dict[str, Any]]:
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
            pending_missables = [t for t in pending if t.is_missable]

            return {
                "psn_id": psn_id,
                "game": game_record.game_title,
                "platform": game_record.platform,
                "total_trophies": len(game_record.trophies),
                "unlocked_count": len(unlocked),
                "completion_percentage": round((len(unlocked) / len(game_record.trophies) * 100), 1) if game_record.trophies else 0,
                "pending_count": len(pending),
                "pending_missables_count": len(pending_missables),
                "pending_missable_trophies": [
                    {
                        "trophy_name": t.trophy_name,
                        "chapter_or_location": t.chapter_or_location,
                        "trophy_type": t.trophy_type,
                    }
                    for t in pending_missables
                ],
                "recently_unlocked": [
                    {
                        "trophy_name": t.trophy_name,
                        "unlocked_at": t.unlocked_at.isoformat() if t.unlocked_at else None,
                    }
                    for t in unlocked[-3:]
                ],
            }


player_progress_service = PlayerProgressService()
