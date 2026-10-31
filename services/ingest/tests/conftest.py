import pytest
import socket
from urllib.parse import urlparse
from src.config import settings


def is_database_available() -> bool:
    try:
        url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        parsed = urlparse(url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 5432
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


_DB_AVAILABLE = is_database_available()


@pytest.fixture(autouse=True)
def skip_if_no_db(request):
    if request.node.get_closest_marker("integration"):
        if not _DB_AVAILABLE:
            pytest.skip("PostgreSQL database not available (integration test requires active Postgres)")
