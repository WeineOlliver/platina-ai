from fastapi.testclient import TestClient
from src.main import create_app

client = TestClient(create_app())

SAMPLE_GUIDE = """# Guia de Platina - Bloodborne

Este é o guia completo para conquistar o troféu de platina em Bloodborne.

## Troféu: Padre Gascoigne
Derrote o chefe Padre Gascoigne no cemitério de Central Yharnam. Não há como perder este troféu, pois faz parte da história obrigatória.

## Troféu Perdível: Amigo dos Corvos (Eileen the Crow)
Atenção: Este troféu é missable (perdível)! Se você avançar para a Lua Vermelha sem completar os encontros anteriores com Eileen, ela desaparecerá ou se tornará hostil permanentemente.

## Passo 1: Exploração Inicial
Colete todas as armas iniciais antes de avançar para a Grande Catedral.
"""


def test_chunker_splits_by_markdown_headings():
    response = client.post(
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


def test_chunker_rejects_empty_payload():
    response = client.post(
        "/api/v1/ingest/parse",
        json={
            "game": "Bloodborne",
            "content": "Short",
        },
    )
    assert response.status_code == 422  # Pydantic validation error (min_length=50)


def test_index_guide_stores_in_pgvector():
    response = client.post(
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
