import pytest
from httpx import AsyncClient, ASGITransport
from src.main import create_app
from src.schemas.search import SearchQueryRequest, SearchResultItem

SAMPLE_SEARCH_GUIDE = """# Guia de Teste - Platina Hardening

## Troféu: Masterminds
Requer completar todos os 3 Atos do Golpe do Juízo Final (The Doomsday Heist) em ordem, com a mesma equipe, sem perder nenhuma vida.

## Troféu Perdível: Lança de Gransax
Arma lendária necessária para a platina. Fica na lança gigante cravada em Leyndell. Deve ser pega antes de derrotar Maliketh em Farum Azula, pois a capital se tornará em cinzas.

## Troféu: Primeiro Passo
Troféu concedido ao iniciar a jornada e derrotar o primeiro inimigo tutorial do jogo.
"""


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def async_client():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture(autouse=True)
async def setup_test_guide(async_client):
    """Seed the database with known chunks for search testing."""
    await async_client.post(
        "/api/v1/ingest/reindex",
        json={
            "game": "SearchTestGame",
            "source_url": "https://example.com/search-test",
            "content": SAMPLE_SEARCH_GUIDE,
        },
    )


@pytest.mark.anyio
async def test_search_schema_supports_min_similarity():
    """Verify that SearchQueryRequest supports min_similarity with default 0.65."""
    req_default = SearchQueryRequest(query="teste")
    assert req_default.min_similarity == 0.65

    req_custom = SearchQueryRequest(query="teste", min_similarity=0.85)
    assert req_custom.min_similarity == 0.85


@pytest.mark.anyio
async def test_exact_keyword_matching_bm25_surfaces_term_when_cosine_lower(async_client):
    """
    Exact keyword search:
    BM25 full-text match must surface the exact keyword chunk 'Masterminds'
    even when vector cosine similarity is lower for a short single-keyword query.
    """
    response = await async_client.post(
        "/api/v1/ingest/search",
        json={
            "query": "Masterminds",
            "game": "SearchTestGame",
            "limit": 3,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_results"] > 0
    top_hit = data["results"][0]
    assert "Masterminds" in top_hit["title"]
    assert top_hit["similarity_score"] >= 0.65
    assert "is_missable" in top_hit


@pytest.mark.anyio
async def test_semantic_matching_surfaces_relevant_chunk(async_client):
    """
    Semantic search:
    Vector cosine similarity retrieves relevant chunk when querying conceptually.
    """
    response = await async_client.post(
        "/api/v1/ingest/search",
        json={
            "query": "Lança de Gransax Leyndell missable Maliketh cinzas",
            "game": "SearchTestGame",
            "limit": 3,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_results"] > 0
    top_hit = data["results"][0]
    assert "Gransax" in top_hit["title"]
    assert top_hit["is_missable"] is True
    assert top_hit["similarity_score"] >= 0.65


@pytest.mark.anyio
async def test_cutoff_filtering_drops_completely_unrelated_queries(async_client):
    """
    Threshold cutoff:
    Completely unrelated queries having no semantic or keyword match must return empty results.
    """
    response = await async_client.post(
        "/api/v1/ingest/search",
        json={
            "query": "receita de bolo de chocolate fofinho com cobertura de brigadeiro",
            "game": "SearchTestGame",
            "limit": 3,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_results"] == 0
    assert data["results"] == []


@pytest.mark.anyio
async def test_custom_min_similarity_threshold_filtering(async_client):
    """
    Assert that setting an ultra-high min_similarity cutoff (e.g. 0.99)
    drops candidates that would otherwise pass with default 0.65.
    """
    # 1. Normal search with default min_similarity (0.65) passes
    res_normal = await async_client.post(
        "/api/v1/ingest/search",
        json={
            "query": "Masterminds",
            "game": "SearchTestGame",
            "min_similarity": 0.65,
        },
    )
    assert res_normal.status_code == 200
    assert res_normal.json()["total_results"] > 0

    # 2. Search with extreme min_similarity (0.999) drops results
    res_strict = await async_client.post(
        "/api/v1/ingest/search",
        json={
            "query": "Masterminds",
            "game": "SearchTestGame",
            "min_similarity": 0.999,
        },
    )
    assert res_strict.status_code == 200
    assert res_strict.json()["total_results"] == 0
    assert res_strict.json()["results"] == []
