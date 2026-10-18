import pytest
from httpx import AsyncClient, ASGITransport, Response
from unittest.mock import patch, AsyncMock
from src.main import create_app
from src.database import get_db_session
from src.models.chunk import GuideChunkModel
from sqlalchemy import delete
from src.services.scraper import TrophyGuideScraper, scraper


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def async_client():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture(autouse=True)
async def cleanup_test_game():
    test_games = ["The Witcher 3: Wild Hunt", "Test Scraped Game"]
    async with get_db_session() as session:
        for g in test_games:
            await session.execute(delete(GuideChunkModel).where(GuideChunkModel.game.ilike(g)))
    yield
    async with get_db_session() as session:
        for g in test_games:
            await session.execute(delete(GuideChunkModel).where(GuideChunkModel.game.ilike(g)))


@pytest.mark.anyio
async def test_scraper_fallback_structured_roadmap():
    scraper_instance = TrophyGuideScraper()
    markdown, canonical_url = await scraper_instance.fetch_guide("The Witcher 3: Wild Hunt")

    assert "the-witcher-3-wild-hunt" in canonical_url
    assert "Roadmap Overview" in markdown
    assert "Tempo" in markdown
    assert "Dificuldade" in markdown
    assert "Passos da Platina" in markdown
    assert "Card Collector" in markdown
    assert "Full Crew" in markdown
    assert "Assassin of Kings" in markdown
    assert "Humpty Dumpty" in markdown
    assert "That Is the Evilest Thing" in markdown
    assert "Brawler" in markdown
    assert "Fist of the South Star" in markdown


@pytest.mark.anyio
async def test_scraper_fetches_source_url_with_html_parsing():
    html_sample = """
    <html>
      <head><title>Mock Guide</title></head>
      <body>
        <h1>Mock Guide Header</h1>
        <p>Overview of the game roadmap.</p>
        <h2>Perdível: Secret Trophy</h2>
        <p>Atenção: este troféu é missable se você avançar sem salvar.</p>
      </body>
    </html>
    """
    mock_response = AsyncMock(spec=Response)
    mock_response.status_code = 200
    mock_response.text = html_sample
    mock_response.url = "https://powerpyx.com/mock-guide"

    with patch("httpx.AsyncClient.get", return_value=mock_response):
        scraper_instance = TrophyGuideScraper()
        markdown, url = await scraper_instance.fetch_guide("Mock Game", source_url="https://powerpyx.com/mock-guide")

        assert url == "https://powerpyx.com/mock-guide"
        assert "# Mock Guide Header" in markdown
        assert "## Perdível: Secret Trophy" in markdown
        assert "Atenção: este troféu é missable" in markdown


@pytest.mark.anyio
async def test_fetch_and_index_new_game_and_idempotent_skip(async_client):
    game_name = "The Witcher 3: Wild Hunt"

    # 1. First call: game is not indexed yet -> should scrape, chunk, embed, index
    response1 = await async_client.post(
        "/api/v1/ingest/fetch-and-index",
        json={"game": game_name},
    )
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["status"] == "indexed"
    assert data1["game"] == game_name
    assert data1["chunks_indexed"] >= 4
    assert "the-witcher-3-wild-hunt" in data1["source_url"]

    # 2. Second call: game is already indexed -> should return already_indexed with chunk count
    response2 = await async_client.post(
        "/api/v1/ingest/fetch-and-index",
        json={"game": game_name},
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["status"] == "already_indexed"
    assert data2["chunks_indexed"] == data1["chunks_indexed"]
