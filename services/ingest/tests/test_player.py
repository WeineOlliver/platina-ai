import pytest
from httpx import AsyncClient, ASGITransport
from src.main import create_app
from src.schemas.player import PlayerProgressResponse, PlayerTrophyProgressItem
from src.services.player import player_progress_service


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def async_client():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.mark.anyio
async def test_get_player_progress_success(async_client):
    response = await async_client.get(
        "/api/v1/players/OlliverHunter/progress",
        params={"game": "Bloodborne"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["psn_id"] == "OlliverHunter"
    assert data["game"] == "Bloodborne"
    assert data["total_trophies"] == 6
    assert data["unlocked_count"] == 3
    assert data["pending_count"] == 3
    assert data["pending_missables_count"] == 2

    # Verify that Eileen is flagged as pending missable
    missable_names = [t["trophy_name"] for t in data["pending_missable_trophies"]]
    assert any("Eileen" in name for name in missable_names)

    # Verify bucket fields are present in response
    assert "quick_cleanup_trophies" in data
    assert "heavy_grind_trophies" in data
    assert "natural_grind_trophies" in data
    assert "pending_missables" in data
    assert len(data["pending_missables"]) == 2
    assert any("Eileen" in t["trophy_name"] for t in data["pending_missables"])
    assert all(t["trophy_category"] == "standard" for t in data["pending_missables"])


@pytest.mark.anyio
async def test_get_player_progress_not_found(async_client):
    response = await async_client.get(
        "/api/v1/players/NonExistentUser/progress",
        params={"game": "Bloodborne"},
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_get_player_progress_gta_categorized_buckets(async_client):
    response = await async_client.get(
        "/api/v1/players/olliverW9/progress",
        params={"game": "Grand Theft Auto V"},
    )
    assert response.status_code == 200
    data = response.json()

    # Validate against Pydantic schema
    progress_obj = PlayerProgressResponse(**data)
    assert progress_obj.psn_id == "olliverW9"
    assert progress_obj.game == "Grand Theft Auto V"
    assert progress_obj.pending_missables_count == 0
    assert len(progress_obj.pending_missables) == 0

    expected_quick_cleanup = {
        "Vinewood Visionary",
        "Majestic",
        "Humans of Los Santos",
        "Animal Lover",
        "Ensemble Piece",
        "Cult Movie",
        "Location Scout",
        "Method Actor",
        "Cryptozoologist",
    }
    actual_quick_cleanup = {t.trophy_name for t in progress_obj.quick_cleanup_trophies}
    assert expected_quick_cleanup.issubset(actual_quick_cleanup)
    assert all(t.trophy_category == "quick_cleanup" for t in progress_obj.quick_cleanup_trophies)

    expected_heavy_grind = {
        "Live a Little",
        "Mastermind",
        "Masterminds",
        "Elitist",
    }
    actual_heavy_grind = {t.trophy_name for t in progress_obj.heavy_grind_trophies}
    assert expected_heavy_grind.issubset(actual_heavy_grind)
    assert all(t.trophy_category == "heavy_grind" for t in progress_obj.heavy_grind_trophies)


@pytest.mark.anyio
async def test_player_progress_service_get_progress_direct():
    result = await player_progress_service.get_progress("olliverW9", "Grand Theft Auto V")
    assert result is not None
    assert isinstance(result, PlayerProgressResponse)
    assert len(result.quick_cleanup_trophies) == 9
    assert len(result.heavy_grind_trophies) == 4
    assert len(result.pending_missables) == 0


@pytest.mark.anyio
async def test_get_player_progress_witcher_3(async_client):
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
    assert data["pending_missables_count"] == 10
    assert isinstance(data["pending_missable_trophies"], list)
    assert len(data["pending_missable_trophies"]) == 10

