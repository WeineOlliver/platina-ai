import pytest
from sqlalchemy import select
from src.database import get_db_session
from src.models.catalog import TrophyModel
from src.schemas.chunk import DocumentChunk
from src.services.entity_linker import (
    normalize_for_matching,
    link_chunk_to_trophy,
    link_chunks_to_trophies,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_normalize_for_matching():
    # Basic casing and spacing
    assert normalize_for_matching("  Card Collector  ") == "card collector"

    # Part suffix removal
    assert normalize_for_matching("Power Overwhelming (Part 1)") == "power overwhelming"
    assert normalize_for_matching("Pest Control (Part 3 of 4)") == "pest control"
    assert normalize_for_matching("Kingmaker - Part 2") == "kingmaker"
    assert normalize_for_matching("Getting all Missable Trophies (Part 2)") == "getting all missable trophies"

    # Guide noise suffixes removal
    assert normalize_for_matching("What Was That? Video Guide") == "what was that"
    assert normalize_for_matching("Shrieker Trophy Video Guide") == "shrieker"
    assert normalize_for_matching("Munchkin Video Guide (works after patch 1.30)") == "munchkin"
    assert normalize_for_matching("The Witcher 3: Wild Hunt Trophy Guide") == "the witcher 3 wild hunt"

    # Punctuation, curly quotes, and ellipses
    assert normalize_for_matching("When It's Many Against One…") == "when its many against one"
    assert normalize_for_matching("When It’s Many Against One") == "when its many against one"
    assert normalize_for_matching("Can't Touch This!") == "cant touch this"
    assert normalize_for_matching("Rad Steez, Bro!") == "rad steez bro"
    assert normalize_for_matching("Moo-rderer") == "moo rderer"


@pytest.mark.anyio
async def test_link_chunk_to_trophy_database():
    game_id = "the-witcher-3-wild-hunt"
    async with get_db_session() as session:
        # Match Base Game trophy with Part suffix
        trophy_power = await link_chunk_to_trophy("Power Overwhelming (Part 1)", game_id, session)
        assert trophy_power is not None
        assert trophy_power.name == "Power Overwhelming"
        assert trophy_power.dlc is None

        # Match trophy with Video Guide suffix and question mark
        trophy_wwt = await link_chunk_to_trophy("What Was That? Video Guide", game_id, session)
        assert trophy_wwt is not None
        assert trophy_wwt.name == "What Was That?"

        # Match DLC trophy with ellipsis
        trophy_hos = await link_chunk_to_trophy("When It's Many Against One…", game_id, session)
        assert trophy_hos is not None
        assert trophy_hos.name == "When It's Many Against One…"
        assert trophy_hos.dlc == "Hearts of Stone"

        # Non-trophy section should not link
        non_trophy = await link_chunk_to_trophy("General Roadmap & Stage 1 Overview", game_id, session)
        assert non_trophy is None


@pytest.mark.anyio
async def test_link_chunk_to_trophy_with_alias():
    game_id = "the-witcher-3-wild-hunt"
    async with get_db_session() as session:
        # Fetch an existing trophy and add a temporary alias
        stmt = select(TrophyModel).where(
            TrophyModel.game_id == game_id,
            TrophyModel.name == "Kaer Morhen Trained"
        )
        res = await session.execute(stmt)
        trophy = res.scalar_one_or_none()
        assert trophy is not None

        original_aliases = list(trophy.aliases or [])
        try:
            trophy.aliases = original_aliases + ["Witcher Training Master"]
            await session.flush()

            # Attempt to link using the alias title
            matched = await link_chunk_to_trophy("Witcher Training Master (Part 1)", game_id, session)
            assert matched is not None
            assert matched.name == "Kaer Morhen Trained"
            assert matched.id == trophy.id
        finally:
            trophy.aliases = original_aliases
            await session.flush()


@pytest.mark.anyio
async def test_link_chunks_to_trophies_batch_and_summary():
    game_id = "the-witcher-3-wild-hunt"
    chunks = [
        DocumentChunk(
            chunk_id="chk-1",
            game="The Witcher 3: Wild Hunt",
            title="Power Overwhelming (Part 1)",
            content="Find all Places of Power simultaneously active.",
        ),
        DocumentChunk(
            chunk_id="chk-2",
            game="The Witcher 3: Wild Hunt",
            title="When It's Many Against One… Video Guide",
            content="Taunt all iris nightmare copies at once.",
        ),
        DocumentChunk(
            chunk_id="chk-3",
            game="The Witcher 3: Wild Hunt",
            title="Roadmap & Stage Overview",
            content="General introduction to the trophy roadmap.",
        ),
    ]

    async with get_db_session() as session:
        summary = await link_chunks_to_trophies(chunks, game_id, session)

        assert summary["linked_count"] == 2
        assert summary["unlinked_count"] == 1
        assert "Roadmap & Stage Overview" in summary["unlinked_titles"]

        # Chunk 1: Base game trophy
        assert chunks[0].trophy_id == "the-witcher-3-wild-hunt-power-overwhelming"
        assert chunks[0].context_prefix == "The Witcher 3: Wild Hunt › Base Game › Power Overwhelming (Part 1)"

        # Chunk 2: Hearts of Stone DLC trophy
        assert chunks[1].trophy_id == "the-witcher-3-wild-hunt-when-its-many-against-one"
        assert chunks[1].context_prefix == "The Witcher 3: Wild Hunt › Hearts of Stone › When It's Many Against One… Video Guide"

        # Chunk 3: Unlinked
        assert chunks[2].trophy_id is None
        assert "Base Game" in chunks[2].context_prefix
