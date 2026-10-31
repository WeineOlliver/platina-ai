import pytest
from httpx import AsyncClient, ASGITransport
from src.main import create_app
from src.schemas.search import SearchQueryRequest
from src.services.search import vector_search_service

pytestmark = [pytest.mark.integration, pytest.mark.requires_witcher_catalog]


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def async_client():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.mark.anyio
async def test_get_trophy_guide_exact_stopword_d10(async_client):
    """
    D10 Stopword test: 'What Was That?' is composed of stopwords but must resolve
    directly in catalog retrieval without vector search and return ordered guide chunks.
    """
    response = await async_client.get(
        "/api/v1/catalog/trophy-guide",
        params={"game": "The Witcher 3: Wild Hunt", "trophy": "What Was That?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "found"
    assert data["trophy"]["name"] == "What Was That?"
    assert data["linked_chunks_count"] >= 1
    assert data["has_guide"] is True
    assert len(data["chunks"]) >= 1
    # Verify chunks have title and content
    assert "What Was That?" in data["chunks"][0]["title"]


@pytest.mark.anyio
async def test_get_trophy_guide_fuzzy_suggestion(async_client):
    """
    When exact match or alias is not found, return fuzzy candidate suggestions.
    """
    response = await async_client.get(
        "/api/v1/catalog/trophy-guide",
        params={"game": "the-witcher-3-wild-hunt", "trophy": "What That"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("suggestions", "not_found")
    assert any("What Was That?" in s for s in data["suggestions"])


@pytest.mark.anyio
async def test_get_trophy_guide_dlc_without_guide_n01(async_client):
    """
    N01 Coverage-based abstention: Blood and Wine trophies exist in catalog,
    but have 0 linked chunks. Endpoint must report linked_chunks_count=0 and has_guide=False.
    """
    response = await async_client.get(
        "/api/v1/catalog/trophy-guide",
        params={"game": "the-witcher-3-wild-hunt", "trophy": "David and Golyat"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "found"
    assert data["trophy"]["dlc"] == "Blood and Wine"
    assert data["linked_chunks_count"] == 0
    assert data["has_guide"] is False
    assert len(data["chunks"]) == 0


@pytest.mark.anyio
async def test_get_trophy_guide_unindexed_game(async_client):
    """
    Unindexed game must return 404 status code.
    """
    response = await async_client.get(
        "/api/v1/catalog/trophy-guide",
        params={"game": "Hollow Knight Silksong", "trophy": "Any Trophy"},
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_get_catalog_trophies_filters(async_client):
    """
    Tests GET /api/v1/catalog/trophies filtering by dlc, missable, location, and type.
    """
    # 1. Filter by DLC 'Blood and Wine'
    resp_dlc = await async_client.get(
        "/api/v1/catalog/trophies",
        params={"game": "the-witcher-3-wild-hunt", "dlc": "Blood and Wine"},
    )
    assert resp_dlc.status_code == 200
    data_dlc = resp_dlc.json()
    assert data_dlc["total"] == 13
    assert data_dlc["has_guide"] is False
    assert all(t["dlc"] == "Blood and Wine" for t in data_dlc["trophies"])

    # 2. Filter Base Game
    resp_base = await async_client.get(
        "/api/v1/catalog/trophies",
        params={"game": "the-witcher-3-wild-hunt", "dlc": "Base Game"},
    )
    assert resp_base.status_code == 200
    data_base = resp_base.json()
    assert data_base["total"] == 53
    assert all(t["dlc"] is None for t in data_base["trophies"])

    # 3. Filter Missable
    resp_miss = await async_client.get(
        "/api/v1/catalog/trophies",
        params={"game": "the-witcher-3-wild-hunt", "missable": "true"},
    )
    assert resp_miss.status_code == 200
    data_miss = resp_miss.json()
    assert data_miss["total"] >= 10
    assert all(t["missable"] is True for t in data_miss["trophies"])

    # 4. Filter Novigrad location
    resp_loc = await async_client.get(
        "/api/v1/catalog/trophies",
        params={"game": "the-witcher-3-wild-hunt", "location": "Novigrad", "missable": "true"},
    )
    assert resp_loc.status_code == 200
    names = [t["name"] for t in resp_loc.json()["trophies"]]
    assert "The Doppler Effect" in names
    assert "Gwent Master" in names


@pytest.mark.anyio
async def test_get_catalog_overview(async_client):
    """
    Tests GET /api/v1/catalog/overview returns difficulty, hours, playthroughs, and counts.
    """
    response = await async_client.get(
        "/api/v1/catalog/overview",
        params={"game": "The Witcher 3: Wild Hunt"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["game_id"] == "the-witcher-3-wild-hunt"
    assert data["total_trophies"] == 79
    assert data["by_type"]["bronze"] > 0
    assert data["by_type"]["silver"] > 0
    assert data["by_type"]["gold"] > 0
    assert data["by_type"]["platinum"] == 1
    dlc_names = [d["name"] for d in data["by_dlc"]]
    assert "Base Game" in dlc_names
    assert "Hearts of Stone" in dlc_names
    assert "Blood and Wine" in dlc_names


@pytest.mark.anyio
async def test_search_filters_by_canonical_game_id(async_client):
    """
    Tests that VectorSearchService resolves game to canonical game_id for filtering.
    """
    req = SearchQueryRequest(
        query="Card Collector Gwent",
        game="The Witcher 3: Wild Hunt",
        limit=3,
        min_similarity=0.0,
    )
    res = await vector_search_service.search(req)
    assert res.total_results > 0
    for item in res.results:
        assert "witcher" in item.game.lower()
