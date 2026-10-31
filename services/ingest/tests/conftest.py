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


def is_witcher3_catalog_seeded() -> bool:
    if not _DB_AVAILABLE:
        return False
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
            count = await conn.fetchval(
                "SELECT count(*) FROM games WHERE id = $1", "the-witcher-3-wild-hunt"
            )
            await conn.close()
            return bool(count and count > 0)

        return asyncio.run(_check())
    except Exception:
        return False


_WITCHER_SEEDED = is_witcher3_catalog_seeded()


@pytest.fixture(autouse=True)
def skip_if_no_db(request):
    if request.node.get_closest_marker("integration"):
        if not _DB_AVAILABLE:
            pytest.skip("PostgreSQL database not available (integration test requires active Postgres)")


@pytest.fixture(autouse=True)
def skip_if_no_witcher_catalog(request):
    if request.node.get_closest_marker("requires_witcher_catalog"):
        if not _WITCHER_SEEDED:
            pytest.skip("The Witcher 3 canonical catalog not seeded in database")
