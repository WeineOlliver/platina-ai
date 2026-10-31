from fastapi import APIRouter, HTTPException, Query
from src.services.player import player_progress_service
from src.schemas.player import PlayerProgressResponse

router = APIRouter(prefix="/api/v1/players", tags=["Player Progress"])


@router.get("/me/progress", response_model=PlayerProgressResponse)
@router.get("/progress", response_model=PlayerProgressResponse)
@router.get("/{psn_id}/progress", response_model=PlayerProgressResponse)
async def get_player_progress(
    game: str = Query(..., min_length=2, description="Game title to query trophy progress"),
    psn_id: str = "me",
):
    """
    Returns current trophy progress for the project owner, highlighting pending and missable trophies.
    Used as an Agent Tool. Only the project owner's profile is tracked.
    """
    progress = await player_progress_service.get_progress(psn_id, game)
    if not progress:
        raise HTTPException(
            status_code=404,
            detail=f"No trophy progress found for game '{game}' on project owner profile."
        )
    return progress
