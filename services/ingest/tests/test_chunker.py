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
@pytest.mark.integration
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
@pytest.mark.integration
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
@pytest.mark.integration
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


@pytest.mark.anyio
@pytest.mark.integration
async def test_reindex_purges_stale_chunks_and_updates(async_client):
    updated_guide = """# Guia Atualizado - Bloodborne

## Troféu: Padre Gascoigne (Estratégia Otimizada)
Use a caixa de música para atordoar Gascoigne três vezes antes de sua transformação em fera.
"""
    response = await async_client.post(
        "/api/v1/ingest/reindex",
        json={
            "game": "Bloodborne",
            "source_url": "https://powerpyx.com/bloodborne-v2",
            "content": updated_guide,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "reindexed"
    assert data["game"] == "Bloodborne"
    assert data["deleted_count"] >= 1
    assert data["reindexed_count"] == 2


def test_build_context_prefix_format():
    # Insight: Context prefix format must strictly be '<game title> › <DLC ou Base Game> › <section title>'
    from src.services.chunker import build_context_prefix

    prefix_base = build_context_prefix("The Witcher 3: Wild Hunt", "Full Crew (Part 1)", "Defend Kaer Morhen")
    assert prefix_base == "The Witcher 3: Wild Hunt › Base Game › Full Crew (Part 1)"

    prefix_hos = build_context_prefix(
        "The Witcher 3: Wild Hunt",
        "When It's Many Against One…",
        "Provoke all Iris von Everec’s Nightmares",
    )
    assert prefix_hos == "The Witcher 3: Wild Hunt › Hearts of Stone › When It's Many Against One…"

    prefix_baw = build_context_prefix(
        "The Witcher 3: Wild Hunt",
        "Grandmaster",
        "Find all Grandmaster diagrams in Toussaint. Blood and Wine DLC.",
    )
    assert prefix_baw == "The Witcher 3: Wild Hunt › Blood and Wine › Grandmaster"


def test_psnprofiles_neighboring_sections_no_text_bleed():
    # Insight: Ensures neighboring PSNProfiles trophy sections do not bleed text into each other
    from src.services.scraper import TrophyGuideScraper
    from src.services.chunker import TrophyGuideChunker
    from src.schemas.chunk import IngestGuideRequest

    fixture_html = """
    <div id="SectionContainer16" class="section-holder">
        <div id="Kingmaker" class="box section-holder">
            <table class="zebra">
                <tr><td style="width: 100%;"><a class="title">Kingmaker</a><br />Complete subplot choosing Skellige ruler.</td></tr>
            </table>
        </div>
        <div>
            <div class="fr-view box light guide no-top-border">
                Kingmaker is a subplot in Skellige deciding the new monarch. Complete The King is Dead to proceed.
                <h1>Kingmaker Video Guide</h1>
                <div>Video link for Kingmaker</div>
            </div>
        </div>
    </div>
    <div id="SectionContainer17" class="section-holder">
        <div id="Assassin-of-Kings" class="box section-holder">
            <table class="zebra">
                <tr><td style="width: 100%;"><a class="title">Assassin of Kings</a><br />Take part in the conspiracy against King Radovid.</td></tr>
            </table>
        </div>
        <div>
            <div class="fr-view box light guide no-top-border">
                Assassin of Kings takes place in Novigrad with Redania Most Wanted and Dijkstra.
                <h1>Assassin of Kings Video Guide</h1>
                <div>Video link for Assassin of Kings</div>
            </div>
        </div>
    </div>
    """

    scraper = TrophyGuideScraper()
    markdown = scraper._html_to_markdown(fixture_html)

    chunker = TrophyGuideChunker()
    req = IngestGuideRequest(game="The Witcher 3: Wild Hunt", source_url="https://psnprofiles.com", content=markdown)
    chunks = chunker.chunk_guide(req)

    assert len(chunks) >= 2
    for c in chunks:
        has_km = "skellige" in c.content.lower() or "kingmaker" in c.title.lower()
        has_ak = "novigrad" in c.content.lower() or "assassin" in c.title.lower() or "radovid" in c.content.lower()
        assert not (has_km and has_ak), f"Chunk '{c.title}' mixed text from both neighboring sections!"
