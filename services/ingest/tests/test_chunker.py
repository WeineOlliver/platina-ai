import pytest
from httpx import AsyncClient, ASGITransport
from src.main import create_app

SAMPLE_GUIDE = """# Guia de Platina - Bloodborne

Este é o guia completo para conquistar o troféu de platina em Bloodborne.

## Troféu: Padre Gascoigne
Derrote o chefe Padre Gascoigne no cemitério de Central Yharnam. Não há como perder este troféu, pois faz parte da história obrigatória.

## Troféu Perdível: Amigo dos Corvos (Eileen the Crow)
Atenção: Este troféu é missable (perdível)! Se você avançar para a Lua Vermelha sem completar os encontros anteriores com Eileen, ela desaparecerá ou se tornará hostil permanentemente.

## Passo 1: Exploração Inicial
Colete todas as armas iniciais antes de avançar para a Grande Catedral.
"""


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def async_client():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.mark.anyio
async def test_chunker_splits_by_markdown_headings(async_client):
    response = await async_client.post(
        "/api/v1/ingest/parse",
        json={
            "game": "Bloodborne",
            "source_url": "https://powerpyx.com/bloodborne",
            "content": SAMPLE_GUIDE,
        },
    )

    assert response.status_code == 200
    chunks = response.json()
    assert len(chunks) == 4

    # Verify first section
    assert chunks[0]["title"] == "Guia de Platina - Bloodborne"
    assert chunks[0]["is_missable"] is False

    # Verify missable flag detection
    missable_chunk = next(c for c in chunks if "Eileen" in c["title"])
    assert missable_chunk["is_missable"] is True
    assert "perdível" in missable_chunk["content"].lower() or "missable" in missable_chunk["title"].lower()

    # Verify metadata
    assert chunks[0]["metadata"]["source_url"] == "https://powerpyx.com/bloodborne"
    assert "chunk_index" in chunks[0]["metadata"]


@pytest.mark.anyio
async def test_chunker_rejects_empty_payload(async_client):
    response = await async_client.post(
        "/api/v1/ingest/parse",
        json={
            "game": "Bloodborne",
            "content": "Short",
        },
    )
    assert response.status_code == 422  # Pydantic validation error (min_length=50)


@pytest.mark.anyio
async def test_index_guide_stores_in_pgvector(async_client):
    response = await async_client.post(
        "/api/v1/ingest/index",
        json={
            "game": "Bloodborne",
            "source_url": "https://powerpyx.com/bloodborne",
            "content": SAMPLE_GUIDE,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["inserted_count"] == 4
    assert data["game"] == "Bloodborne"


@pytest.mark.anyio
async def test_semantic_search_retrieves_relevant_chunk(async_client):
    # Search specifically for Eileen the Crow
    response = await async_client.post(
        "/api/v1/ingest/search",
        json={
            "query": "Eileen the Crow corvos perdível",
            "game": "Bloodborne",
            "limit": 2,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_results"] > 0
    top_result = data["results"][0]
    assert "Eileen" in top_result["title"]
    assert top_result["is_missable"] is True
    assert top_result["similarity_score"] > 0.0


@pytest.mark.anyio
async def test_semantic_search_hybrid_missable_filter(async_client):
    response = await async_client.post(
        "/api/v1/ingest/search",
        json={
            "query": "troféus",
            "game": "Bloodborne",
            "missable_only": True,
            "limit": 5,
        },
    )
    assert response.status_code == 200
    data = response.json()
    for item in data["results"]:
        assert item["is_missable"] is True
