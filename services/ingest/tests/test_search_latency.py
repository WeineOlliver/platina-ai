import pytest
from httpx import AsyncClient, ASGITransport
from src.main import create_app
from src.schemas.search import SearchResponse, SearchQueryRequest
from src.services.search import vector_search_service


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def async_client():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.mark.anyio
async def test_search_response_schema_latency_fields():
    """Verify that SearchResponse model includes retrieval_latency_ms and reranker_latency_ms with default 0.0."""
    res = SearchResponse(query="teste", total_results=0, results=[])
    assert hasattr(res, "retrieval_latency_ms")
    assert hasattr(res, "reranker_latency_ms")
    assert isinstance(res.retrieval_latency_ms, float)
    assert isinstance(res.reranker_latency_ms, float)
    assert res.retrieval_latency_ms == 0.0
    assert res.reranker_latency_ms == 0.0


@pytest.mark.anyio
async def test_search_endpoint_returns_latency_metrics(async_client):
    """
    Search endpoint must return retrieval_latency_ms and reranker_latency_ms >= 0.0.
    """
    response = await async_client.post(
        "/api/v1/ingest/search",
        json={
            "query": "trofeu teste de latencia",
            "limit": 3,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "retrieval_latency_ms" in data
    assert "reranker_latency_ms" in data
    assert isinstance(data["retrieval_latency_ms"], (int, float))
    assert isinstance(data["reranker_latency_ms"], (int, float))
    assert data["retrieval_latency_ms"] >= 0.0
    assert data["reranker_latency_ms"] >= 0.0


@pytest.mark.anyio
async def test_vector_search_service_computes_latency_metrics():
    """
    Direct service invocation returns SearchResponse with populated latency metrics >= 0.0.
    """
    req = SearchQueryRequest(query="busca direta por latencia", limit=2)
    response = await vector_search_service.search(req)
    assert isinstance(response, SearchResponse)
    assert response.retrieval_latency_ms >= 0.0
    assert response.reranker_latency_ms >= 0.0
