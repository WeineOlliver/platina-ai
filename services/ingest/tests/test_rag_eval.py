import pytest
from httpx import AsyncClient, ASGITransport
from src.main import create_app

SAMPLE_EVAL_GUIDE = """## Guia Completo de Troféus - Elden Ring
Este é o sumário e introdução aos requisitos da platina.

## Troféu Perdível: Espada de Ranni (Dark Moon Greatsword)
Atenção crítica: Este troféu é perdível (missable). A questline de Ranni deve ser avançada antes de queimar a Térvore (Erdtree) com a Chama dos Gigantes em Forge of the Giants. Se você derrotar Maliketh antes de entregar o Anel do Juramento Escuro, Ranni desaparecerá e você não conseguirá o final Age of Stars nem a arma lendária.

## Troféu: Godrick, o Enxertado
Derrote Godrick, o Enxertado no Castelo Tempesvéu (Stormveil Castle). Troféu obrigatório da história principal que não pode ser perdido.

## Troféu Perdível: Lança de Gransax (Bolt of Gransax)
Missable extremo! Esta arma lendária fica na lança gigante cravada em Leyndell, Capital Real. Ela DEVE ser coletada antes de derrotar Maliketh em Farum Azula. Após Farum Azula, a capital vira a Capital das Cinzas e a lança fica inacessível para sempre no seu playthrough atual.
"""

EVAL_BENCHMARK_CASES = [
    {
        "description": "Busca semântica por troféu perdível com aviso de ponto de não retorno",
        "query": "Lança de Gransax Bolt of Gransax Leyndell missable",
        "expected_trophy": "Lança de Gransax",
        "expected_missable": True,
        "expected_keyword": "maliketh",
    },
    {
        "description": "Busca semântica por questline de Ranni e final Age of Stars",
        "query": "Ranni Dark Moon Greatsword Térvore missable",
        "expected_trophy": "Ranni",
        "expected_missable": True,
        "expected_keyword": "térvore",
    },
    {
        "description": "Busca por troféu de chefe obrigatório da história",
        "query": "Godrick Enxertado Castelo Tempesvéu Stormveil",
        "expected_trophy": "Godrick",
        "expected_missable": False,
        "expected_keyword": "castelo",
    },
]


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def async_client():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.mark.anyio
async def test_rag_evaluation_benchmark_precision_and_recall(async_client):
    """
    RAG Benchmark Suite:
    Indexes a golden sample trophy guide and asserts retrieval precision,
    relevance scoring, and accurate heuristic classification.
    """
    # 1. Index the evaluation guide
    index_res = await async_client.post(
        "/api/v1/ingest/index",
        json={
            "game": "Elden Ring",
            "source_url": "https://powerpyx.com/elden-ring",
            "content": SAMPLE_EVAL_GUIDE,
        },
    )
    assert index_res.status_code == 200
    assert index_res.json()["inserted_count"] == 4

    passed_benchmarks = 0

    # 2. Evaluate each benchmark scenario
    for case in EVAL_BENCHMARK_CASES:
        search_res = await async_client.post(
            "/api/v1/ingest/search",
            json={
                "query": case["query"],
                "game": "Elden Ring",
                "limit": 2,
            },
        )
        assert search_res.status_code == 200
        data = search_res.json()
        assert data["total_results"] > 0

        top_hit = data["results"][0]

        # Metric 1: Keyword/Trophy Precision (Top-1 hit matches intended entity)
        assert case["expected_trophy"].lower() in top_hit["title"].lower(), (
            f"Failed on case: {case['description']}. Expected '{case['expected_trophy']}' in '{top_hit['title']}'"
        )

        # Metric 2: Ground Truth Missable Classification Accuracy
        assert top_hit["is_missable"] == case["expected_missable"], (
            f"Missable flag mismatch for: {top_hit['title']}"
        )

        # Metric 3: Contextual Relevance (Must contain critical operational instruction)
        assert case["expected_keyword"].lower() in top_hit["content"].lower()

        # Metric 4: Minimum similarity score threshold
        assert top_hit["similarity_score"] >= 0.5, f"Low similarity score: {top_hit['similarity_score']}"

        passed_benchmarks += 1

    # Ensure 100% pass rate on retrieval benchmark
    assert passed_benchmarks == len(EVAL_BENCHMARK_CASES)
