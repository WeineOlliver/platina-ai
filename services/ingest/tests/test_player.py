import pytest
from httpx import AsyncClient, ASGITransport
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


@pytest.mark.anyio
async def test_get_player_progress_not_found(async_client):
    response = await async_client.get(
        "/api/v1/players/NonExistentUser/progress",
        params={"game": "Bloodborne"},
    )
    assert response.status_code == 404
