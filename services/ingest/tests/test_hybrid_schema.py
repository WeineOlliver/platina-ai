import pytest
from sqlalchemy import text, select, func
from src.database import get_db_session
from src.models.chunk import GuideChunkModel


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_tsv_column_exists_in_guide_chunks():
    """Assert that the tsv column exists on the GuideChunkModel and database table."""
    assert hasattr(GuideChunkModel, "tsv"), "GuideChunkModel must have 'tsv' attribute mapped."

    async with get_db_session() as session:
        result = await session.execute(
            text(
                """
                SELECT column_name, data_type, is_generated
                FROM information_schema.columns
                WHERE table_name = 'guide_chunks' AND column_name = 'tsv';
                """
            )
        )
        row = result.fetchone()
        assert row is not None, "Column 'tsv' must exist in 'guide_chunks' table."
        assert row[0] == "tsv"
        assert row[1] == "tsvector"


@pytest.mark.anyio
async def test_query_tsv_with_to_tsquery():
    """Assert that a query against guide_chunks.tsv @@ to_tsquery('portuguese', ...) returns matching chunks."""
    test_chunk_id = "test_fts_chunk_001"
    game_title = "Demon's Souls Remake"
    trophy_title = "Troféu Perdível: Anel do Guerreiro Lendário"
    trophy_content = "Este troféu requer derrotar o chefe sem ser atingido pela espada mágica."

    async with get_db_session() as session:
        # Clean up any leftover test data
        await session.execute(text("DELETE FROM guide_chunks WHERE id = :id"), {"id": test_chunk_id})

        # Insert test chunk via raw SQL (bypassing embedding requirement for schema check)
        await session.execute(
            text(
                """
                INSERT INTO guide_chunks (id, game, title, content, is_missable, embedding)
                VALUES (:id, :game, :title, :content, :is_missable, array_fill(0::real, ARRAY[1536]));
                """
            ),
            {
                "id": test_chunk_id,
                "game": game_title,
                "title": trophy_title,
                "content": trophy_content,
                "is_missable": True,
            },
        )

        # 1. Query using GuideChunkModel with tsv @@ to_tsquery
        stmt = (
            select(GuideChunkModel)
            .where(GuideChunkModel.id == test_chunk_id)
            .where(GuideChunkModel.tsv.op("@@")(func.to_tsquery("portuguese", "guerreiro")))
        )
        res = await session.execute(stmt)
        matched_chunk = res.scalar_one_or_none()

        assert matched_chunk is not None, "Full-text search query on GuideChunkModel.tsv must return the matching chunk"
        assert matched_chunk.id == test_chunk_id
        assert matched_chunk.title == trophy_title

        # 2. Query using direct SQL to assert the raw SQL expression
        sql_stmt = text(
            """
            SELECT id, title
            FROM guide_chunks
            WHERE id = :id AND tsv @@ to_tsquery('portuguese', 'espada');
            """
        )
        sql_res = await session.execute(sql_stmt, {"id": test_chunk_id})
        sql_row = sql_res.fetchone()
        assert sql_row is not None
        assert sql_row[0] == test_chunk_id

        # Clean up test data
        await session.execute(text("DELETE FROM guide_chunks WHERE id = :id"), {"id": test_chunk_id})
