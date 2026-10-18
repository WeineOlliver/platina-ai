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


@pytest.mark.anyio
async def test_discover_subpages_matching_and_filtering():
    scraper_instance = TrophyGuideScraper()
    base_url = "https://www.powerpyx.com/the-witcher-3-wild-hunt-trophy-guide-roadmap/"
    html_content = """
    <html>
      <body>
        <a href="https://www.powerpyx.com/the-witcher-3-wild-hunt-trophy-guide-roadmap/">Main Guide</a>
        <a href="/all-gwent-cards-guide/">All Gwent Cards Guide</a>
        <a href="/gwent/locations/">Gwent Locations</a>
        <a href="/collectibles/places-of-power/">Collectibles Guide</a>
        <a href="/weapons/mastercrafted-gear/">Weapons Guide</a>
        <a href="/hearts-of-stone-dlc-trophy-guide/">DLC Trophy Guide</a>
        <!-- Noise to filter -->
        <a href="/tag/witcher-3/">Tag Page</a>
        <a href="/category/ps4-guides/">Category Page</a>
        <a href="#comments">Comments</a>
        <a href="/the-witcher-3-gwent/#respond">Leave a reply</a>
        <a href="https://twitter.com/PowerPyx">Twitter</a>
        <a href="https://facebook.com/PowerPyx">Facebook</a>
        <!-- Duplicates and excess -->
        <a href="/all-gwent-cards-guide/">All Gwent Cards Duplicate</a>
    """ + "".join(f'<a href="/all-extra-{i}-guide/">Extra {i}</a>\n' for i in range(20)) + """
      </body>
    </html>
    """
    subpages = scraper_instance.discover_subpages(html_content, base_url)

    # Must contain matched patterns
    assert "https://www.powerpyx.com/all-gwent-cards-guide/" in subpages
    assert "https://www.powerpyx.com/gwent/locations/" in subpages
    assert "https://www.powerpyx.com/collectibles/places-of-power/" in subpages
    assert "https://www.powerpyx.com/weapons/mastercrafted-gear/" in subpages
    assert "https://www.powerpyx.com/hearts-of-stone-dlc-trophy-guide/" in subpages

    # Must filter noise
    assert not any("/tag/" in u for u in subpages)
    assert not any("/category/" in u for u in subpages)
    assert not any("twitter.com" in u for u in subpages)
    assert not any("facebook.com" in u for u in subpages)
    assert not any("#comments" in u or "#respond" in u for u in subpages)
    assert base_url not in subpages

    # Must deduplicate and cap at 15
    assert len(subpages) <= 15
    assert len(subpages) == len(set(subpages))


@pytest.mark.anyio
async def test_fetch_game_guide_with_subpages_parallel_fetching():
    scraper_instance = TrophyGuideScraper()
    base_url = "https://www.powerpyx.com/mock-game-trophy-guide-roadmap/"

    main_html = """
    <html>
      <head><title>Mock Game Trophy Guide</title></head>
      <body>
        <h1>Mock Game Trophy Guide</h1>
        <p>Main roadmap content.</p>
        <a href="/all-collectibles-guide/">All Collectibles</a>
        <a href="/weapons/ultimate-arms/">Ultimate Weapons</a>
      </body>
    </html>
    """

    sub1_html = """
    <html>
      <head><title>Mock Game - All Collectibles Guide</title></head>
      <body>
        <h1>All Collectibles Guide</h1>
        <p>Details about hidden items.</p>
      </body>
    </html>
    """

    sub2_html = """
    <html>
      <head><title>Mock Game - Weapons Guide</title></head>
      <body>
        <h1>Weapons Guide</h1>
        <p>Details about ultimate weapons.</p>
      </body>
    </html>
    """

    async def mock_get(url, *args, **kwargs):
        url_str = str(url)
        resp = AsyncMock(spec=Response)
        resp.status_code = 200
        if "all-collectibles-guide" in url_str:
            resp.text = sub1_html
            resp.url = "https://www.powerpyx.com/all-collectibles-guide/"
        elif "weapons" in url_str:
            resp.text = sub2_html
            resp.url = "https://www.powerpyx.com/weapons/ultimate-arms/"
        else:
            resp.text = main_html
            resp.url = base_url
        return resp

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        pages = await scraper_instance.fetch_game_guide_with_subpages("Mock Game", source_url=base_url)

        assert len(pages) == 3
        urls = [p[2] for p in pages]
        assert base_url in urls
        assert "https://www.powerpyx.com/all-collectibles-guide/" in urls
        assert "https://www.powerpyx.com/weapons/ultimate-arms/" in urls

        # Verify page title and markdown content
        titles = [p[0] for p in pages]
        assert any("Collectibles" in t for t in titles)
        assert any("Weapons" in t for t in titles)


@pytest.mark.anyio
async def test_fetch_game_guide_witcher_3_subpages_gwent_requirements():
    scraper_instance = TrophyGuideScraper()
    pages = await scraper_instance.fetch_game_guide_with_subpages("The Witcher 3: Wild Hunt")

    assert len(pages) >= 2
    gwent_page = next((p for p in pages if "gwent" in p[2].lower() or "gwent" in p[0].lower()), None)
    assert gwent_page is not None, "Gwent subpage must be present for The Witcher 3"

    title, markdown, url = gwent_page
    assert "Dandelion in Vegelbud Masquerade" in markdown
    assert "Zoltan/Baron in Velen" in markdown
    assert "High Stakes tournament in Passiflora" in markdown
    assert "White Orchard innkeeper" in markdown


@pytest.mark.anyio
async def test_fetch_and_index_force_reindex(async_client):
    game_name = "The Witcher 3: Wild Hunt"

    # 1. First indexing
    resp1 = await async_client.post(
        "/api/v1/ingest/fetch-and-index",
        json={"game": game_name},
    )
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["status"] == "indexed"
    initial_chunks = data1["chunks_indexed"]

    # 2. Subsequent call without force_reindex returns already_indexed
    resp2 = await async_client.post(
        "/api/v1/ingest/fetch-and-index",
        json={"game": game_name, "force_reindex": False},
    )
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "already_indexed"

    # 3. Subsequent call with force_reindex=True re-indexes
    resp3 = await async_client.post(
        "/api/v1/ingest/fetch-and-index",
        json={"game": game_name, "force_reindex": True},
    )
    assert resp3.status_code == 200
    data3 = resp3.json()
    assert data3["status"] == "indexed"
    assert data3["chunks_indexed"] >= initial_chunks
