import pytest
from httpx import AsyncClient, ASGITransport
from src.main import create_app
from src.config import settings


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_fetch_and_index_returns_404_when_disabled():
    """Verify that /api/v1/ingest/fetch-and-index returns 404 when ON_DEMAND_INGESTION is False (default)."""
    assert settings.ON_DEMAND_INGESTION is False

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/ingest/fetch-and-index",
            json={"game": "The Witcher 3: Wild Hunt"},
        )
        assert response.status_code == 404
        assert "disabled" in response.json()["detail"].lower()
