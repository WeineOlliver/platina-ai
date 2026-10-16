from fastapi.testclient import TestClient
from src.main import create_app

client = TestClient(create_app())


def test_health_check_returns_200():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "platina-ingest"
    assert "timestamp" in data
