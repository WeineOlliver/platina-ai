from fastapi import APIRouter, HTTPException, Query
from src.services.player import player_progress_service
from src.schemas.player import PlayerProgressResponse

router = APIRouter(prefix="/api/v1/players", tags=["Player Progress"])


@router.get("/{psn_id}/progress", response_model=PlayerProgressResponse)
async def get_player_progress(
    psn_id: str,
    game: str = Query(..., min_length=2, description="Nome do jogo para consultar o progresso"),
):
    """
    Retorna o progresso atual do jogador no jogo, destacando troféus pendentes e missables.
    Usado como ferramenta (Tool) para Agentes de IA.
    """
    progress = await player_progress_service.get_progress(psn_id, game)
    if not progress:
        raise HTTPException(
            status_code=404,
            detail=f"Nenhum registro de troféus encontrado para o jogador '{psn_id}' no jogo '{game}'."
        )
    return progress
