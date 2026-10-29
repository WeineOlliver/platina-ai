import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text, select
from src.database import get_db_session
from src.models.player import PlayerGameModel, PlayerTrophyModel
from src.services.player import player_progress_service
from src.main import create_app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def async_client():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.mark.anyio
async def test_witcher3_player_game_canonical_total():
    """Verify that player_games record for Witcher 3 has total_trophies=79 and unlocked_trophies=0."""
    async with get_db_session() as session:
        stmt = select(PlayerGameModel).where(PlayerGameModel.id == "pg_witcher3_01")
        result = await session.execute(stmt)
        game = result.scalar_one_or_none()

        assert game is not None, "pg_witcher3_01 must exist in player_games"
        assert game.game_title == "The Witcher 3: Wild Hunt"
        assert game.platform == "PS5"
        assert game.total_trophies == 79
        assert game.unlocked_trophies == 0
        assert game.platinum_status == "in_progress"


@pytest.mark.anyio
async def test_witcher3_all_player_trophies_have_canonical_trophy_id():
    """Verify that all 79 player_trophies for pg_witcher3_01 have trophy_id populated and is_unlocked=False."""
    async with get_db_session() as session:
        stmt = (
            select(PlayerTrophyModel)
            .where(PlayerTrophyModel.player_game_id == "pg_witcher3_01")
            .order_by(PlayerTrophyModel.trophy_name)
        )
        result = await session.execute(stmt)
        trophies = result.scalars().all()

        assert len(trophies) == 79, f"Expected 79 trophies for Witcher 3, found {len(trophies)}"

        for t in trophies:
            assert t.trophy_id is not None, f"Trophy '{t.trophy_name}' has null trophy_id"
            assert t.trophy_id.startswith("the-witcher-3-wild-hunt-"), (
                f"Unexpected trophy_id '{t.trophy_id}' for '{t.trophy_name}'"
            )
            assert t.is_unlocked is False, f"Trophy '{t.trophy_name}' should not be unlocked"
            assert t.unlocked_at is None, f"Trophy '{t.trophy_name}' should have null unlocked_at"

        # Verify that all 10 canonical missables are flagged
        missables = [t for t in trophies if t.is_missable]
        assert len(missables) == 10, f"Expected 10 missable trophies, found {len(missables)}"


@pytest.mark.anyio
async def test_witcher3_player_progress_service():
    """Verify player_progress_service returns 0 unlocked and 79 pending for Witcher 3."""
    progress = await player_progress_service.get_progress("olliverW9", "The Witcher 3: Wild Hunt")

    assert progress is not None
    assert progress.psn_id == "olliverW9"
    assert progress.game == "The Witcher 3: Wild Hunt"
    assert progress.total_trophies == 79
    assert progress.unlocked_count == 0
    assert progress.pending_count == 79
    assert progress.completion_percentage == 0.0
    assert progress.pending_missables_count == 10
    assert len(progress.pending_missables) == 10

    # Ensure every trophy item in pending missables has trophy_id populated
    for item in progress.pending_missables:
        assert item.trophy_id is not None
        assert item.trophy_id.startswith("the-witcher-3-wild-hunt-")
        assert item.is_missable is True


@pytest.mark.anyio
async def test_witcher3_player_progress_api_endpoint(async_client):
    """Verify /api/v1/players/{psn_id}/progress endpoint reflects canonical catalog values."""
    response = await async_client.get(
        "/api/v1/players/olliverW9/progress",
        params={"game": "The Witcher 3: Wild Hunt"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["psn_id"] == "olliverW9"
    assert data["game"] == "The Witcher 3: Wild Hunt"
    assert data["total_trophies"] == 79
    assert data["unlocked_count"] == 0
    assert data["pending_count"] == 79
    assert data["completion_percentage"] == 0.0
    assert data["pending_missables_count"] == 10
    assert len(data["pending_missable_trophies"]) == 10

    for item in data["pending_missable_trophies"]:
        assert item["trophy_id"] is not None
        assert item["trophy_id"].startswith("the-witcher-3-wild-hunt-")
