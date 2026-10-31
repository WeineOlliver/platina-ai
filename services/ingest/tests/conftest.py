import asyncio
import asyncpg
import pytest
from urllib.parse import urlparse
from src.config import settings


def is_database_available() -> bool:
    try:
        url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        parsed = urlparse(url)
        user = parsed.username or "platina"
        password = parsed.password or "change_me"
        database = parsed.path.lstrip("/") or "platina_rag"
        host = parsed.hostname or "localhost"
        port = parsed.port or 5432

        async def _check():
            conn = await asyncpg.connect(
                user=user,
                password=password,
                database=database,
                host=host,
                port=port,
                timeout=1.5,
            )
            await conn.close()
            return True

        return asyncio.run(_check())
    except Exception:
        return False


_DB_AVAILABLE = is_database_available()


@pytest.fixture(autouse=True)
def skip_if_no_db(request):
    if request.node.get_closest_marker("integration"):
        if not _DB_AVAILABLE:
            pytest.skip("PostgreSQL database not available (integration test requires active Postgres)")
