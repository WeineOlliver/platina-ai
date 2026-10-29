import pytest
from decimal import Decimal
from sqlalchemy import text, select, inspect
from sqlalchemy.exc import IntegrityError
from src.database import get_db_session
from src.models.chunk import GuideChunkModel
from src.models.player import PlayerTrophyModel, PlayerGameModel, PlayerModel
from src.models.catalog import GameModel, TrophyModel


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_catalog_models_attributes():
    """Verify that GameModel, TrophyModel, GuideChunkModel, and PlayerTrophyModel have expected attributes."""
    # GameModel attributes
    for attr in [
        "id",
        "title",
        "np_communication_id",
        "aliases",
        "difficulty",
        "hours",
        "playthroughs",
        "metadata_source",
        "trophies",
    ]:
        assert hasattr(GameModel, attr), f"GameModel must have '{attr}' attribute"

    # TrophyModel attributes
    for attr in [
        "id",
        "game_id",
        "psn_trophy_id",
        "name",
        "type",
        "description",
        "dlc",
        "location",
        "missable",
        "missable_sources",
        "aliases",
        "game",
    ]:
        assert hasattr(TrophyModel, attr), f"TrophyModel must have '{attr}' attribute"

    # GuideChunkModel catalog FKs
    assert hasattr(GuideChunkModel, "game_id"), "GuideChunkModel must have 'game_id' attribute"
    assert hasattr(GuideChunkModel, "trophy_id"), "GuideChunkModel must have 'trophy_id' attribute"

    # PlayerTrophyModel catalog FK and legacy columns
    assert hasattr(PlayerTrophyModel, "trophy_id"), "PlayerTrophyModel must have 'trophy_id' attribute"
    for legacy_col in [
        "id",
        "player_game_id",
        "trophy_name",
        "trophy_type",
        "trophy_category",
        "is_missable",
        "is_unlocked",
        "unlocked_at",
        "chapter_or_location",
    ]:
        assert hasattr(PlayerTrophyModel, legacy_col), f"PlayerTrophyModel must keep legacy column '{legacy_col}'"


@pytest.mark.anyio
async def test_catalog_database_schema():
    """Verify tables and columns exist in PostgreSQL database."""
    async with get_db_session() as session:
        # Check games table columns
        res = await session.execute(
            text(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'games';
                """
            )
        )
        game_cols = {row[0]: row[1] for row in res.fetchall()}
        assert "id" in game_cols
        assert "title" in game_cols
        assert "np_communication_id" in game_cols
        assert "aliases" in game_cols
        assert "difficulty" in game_cols
        assert "hours" in game_cols
        assert "playthroughs" in game_cols
        assert "metadata_source" in game_cols

        # Check trophies table columns
        res = await session.execute(
            text(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'trophies';
                """
            )
        )
        trophy_cols = {row[0]: row[1] for row in res.fetchall()}
        assert "id" in trophy_cols
        assert "game_id" in trophy_cols
        assert "psn_trophy_id" in trophy_cols
        assert "name" in trophy_cols
        assert "type" in trophy_cols
        assert "description" in trophy_cols
        assert "dlc" in trophy_cols
        assert "location" in trophy_cols
        assert "missable" in trophy_cols
        assert "missable_sources" in trophy_cols
        assert "aliases" in trophy_cols

        # Check guide_chunks new columns
        res = await session.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'guide_chunks' AND column_name IN ('game_id', 'trophy_id');
                """
            )
        )
        guide_chunk_cols = {row[0] for row in res.fetchall()}
        assert "game_id" in guide_chunk_cols
        assert "trophy_id" in guide_chunk_cols

        # Check player_trophies new column
        res = await session.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'player_trophies' AND column_name = 'trophy_id';
                """
            )
        )
        player_trophies_cols = {row[0] for row in res.fetchall()}
        assert "trophy_id" in player_trophies_cols


@pytest.mark.anyio
async def test_catalog_crud_and_relationships():
    """Verify ORM insert, relationships, and foreign key cascades."""
    test_game_id = "test-game-witcher-3"
    test_trophy_id = "test-witcher-3-card-collector"
    test_chunk_id = "test-chunk-schema-1"

    async with get_db_session() as session:
        # Cleanup if needed
        await session.execute(text("DELETE FROM guide_chunks WHERE id = :id"), {"id": test_chunk_id})
        await session.execute(text("DELETE FROM trophies WHERE id = :id"), {"id": test_trophy_id})
        await session.execute(text("DELETE FROM games WHERE id = :id"), {"id": test_game_id})

        # 1. Create Game
        game = GameModel(
            id=test_game_id,
            title="The Witcher 3: Wild Hunt",
            np_communication_id="NPWR00001_00",
            aliases=["Witcher 3", "TW3"],
            difficulty=Decimal("4.5"),
            hours=150,
            playthroughs=1,
            metadata_source="psnprofiles",
        )
        session.add(game)
        await session.flush()

        # 2. Create Trophy
        trophy = TrophyModel(
            id=test_trophy_id,
            game_id=test_game_id,
            psn_trophy_id=10,
            name="Card Collector",
            type="bronze",
            description="Acquire all gwent cards available in the base version of the game.",
            dlc=None,
            location="Velen / Novigrad / Skellige",
            missable=True,
            missable_sources=["psnprofiles", "powerpyx"],
            aliases=["Gwent Collector", "Collect All Cards"],
        )
        session.add(trophy)
        await session.flush()

        # 3. Create GuideChunk linked to game and trophy
        chunk = GuideChunkModel(
            id=test_chunk_id,
            game="The Witcher 3: Wild Hunt",
            game_id=test_game_id,
            trophy_id=test_trophy_id,
            title="Card Collector - Missable Guide",
            content="Make sure to play the Baron before he hangs himself.",
            is_missable=True,
            embedding=[0.0] * 384,
        )
        session.add(chunk)
        await session.flush()

        # 4. Verify query with relationship
        stmt = select(TrophyModel).where(TrophyModel.id == test_trophy_id)
        res = await session.execute(stmt)
        loaded_trophy = res.scalar_one()
        assert loaded_trophy.game.title == "The Witcher 3: Wild Hunt"
        assert loaded_trophy.missable is True
        assert "Gwent Collector" in loaded_trophy.aliases

        # 5. Verify UNIQUE(game_id, name)
        duplicate_trophy = TrophyModel(
            id="test-witcher-3-card-collector-duplicate",
            game_id=test_game_id,
            name="Card Collector",
            type="silver",
        )
        session.add(duplicate_trophy)
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()

    # Cleanup in fresh session
    async with get_db_session() as session:
        await session.execute(text("DELETE FROM guide_chunks WHERE id = :id"), {"id": test_chunk_id})
        await session.execute(text("DELETE FROM trophies WHERE id = :id"), {"id": test_trophy_id})
        await session.execute(text("DELETE FROM games WHERE id = :id"), {"id": test_game_id})
