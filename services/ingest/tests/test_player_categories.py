import pytest
from sqlalchemy import text, select
from src.database import get_db_session
from src.models.player import PlayerTrophyModel, PlayerGameModel, PlayerModel


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_player_trophy_model_has_category_attribute():
    """Assert that PlayerTrophyModel has trophy_category mapped."""
    assert hasattr(
        PlayerTrophyModel, "trophy_category"
    ), "PlayerTrophyModel must map 'trophy_category' column."


@pytest.mark.anyio
async def test_player_trophy_model_has_trophy_id_attribute():
    """Assert that PlayerTrophyModel has canonical trophy_id mapped."""
    assert hasattr(
        PlayerTrophyModel, "trophy_id"
    ), "PlayerTrophyModel must map 'trophy_id' column."


@pytest.mark.anyio
async def test_trophy_category_column_exists_in_database():
    """Assert that trophy_category column exists on player_trophies table in PostgreSQL."""
    async with get_db_session() as session:
        result = await session.execute(
            text(
                """
                SELECT column_name, data_type, column_default
                FROM information_schema.columns
                WHERE table_name = 'player_trophies' AND column_name = 'trophy_category';
                """
            )
        )
        row = result.fetchone()
        assert row is not None, "Column 'trophy_category' must exist in 'player_trophies' table."
        assert row[0] == "trophy_category"
        assert row[1] == "character varying"


@pytest.mark.anyio
async def test_insert_and_query_trophy_with_category():
    """Assert inserting and querying a trophy with a specific trophy_category succeeds."""
    player_id = "test_cat_player_001"
    game_id = "test_cat_game_001"
    trophy_id_custom = "test_cat_trophy_custom"
    trophy_id_default = "test_cat_trophy_default"

    async with get_db_session() as session:
        # Cleanup any leftover test data
        await session.execute(text("DELETE FROM player_trophies WHERE id IN (:t1, :t2)"), {"t1": trophy_id_custom, "t2": trophy_id_default})
        await session.execute(text("DELETE FROM player_games WHERE id = :gid"), {"gid": game_id})
        await session.execute(text("DELETE FROM players WHERE id = :pid"), {"pid": player_id})

        # Create prerequisite player and game
        player = PlayerModel(id=player_id, psn_id="TestCatPSN", email="cat@test.com")
        session.add(player)
        await session.flush()

        game = PlayerGameModel(id=game_id, player_id=player_id, game_title="Test Adventure", platform="PS5")
        session.add(game)
        await session.flush()

        # Insert trophy with explicit category
        trophy_custom = PlayerTrophyModel(
            id=trophy_id_custom,
            player_game_id=game_id,
            trophy_name="Fast Explorer",
            trophy_type="bronze",
            trophy_category="quick_cleanup",
        )
        session.add(trophy_custom)

        # Insert trophy with default category
        trophy_default = PlayerTrophyModel(
            id=trophy_id_default,
            player_game_id=game_id,
            trophy_name="Standard Story Trophy",
            trophy_type="silver",
        )
        session.add(trophy_default)
        await session.flush()

        # Query custom category trophy via ORM
        stmt_custom = select(PlayerTrophyModel).where(PlayerTrophyModel.id == trophy_id_custom)
        res_custom = await session.execute(stmt_custom)
        fetched_custom = res_custom.scalar_one_or_none()
        assert fetched_custom is not None
        assert fetched_custom.trophy_category == "quick_cleanup"

        # Query default category trophy via ORM
        stmt_default = select(PlayerTrophyModel).where(PlayerTrophyModel.id == trophy_id_default)
        res_default = await session.execute(stmt_default)
        fetched_default = res_default.scalar_one_or_none()
        assert fetched_default is not None
        assert fetched_default.trophy_category == "standard"

        # Query filtering by trophy_category
        stmt_filter = (
            select(PlayerTrophyModel)
            .where(PlayerTrophyModel.player_game_id == game_id)
            .where(PlayerTrophyModel.trophy_category == "quick_cleanup")
        )
        res_filter = await session.execute(stmt_filter)
        results = res_filter.scalars().all()
        assert len(results) == 1
        assert results[0].trophy_name == "Fast Explorer"

        # Cleanup
        await session.execute(text("DELETE FROM player_trophies WHERE id IN (:t1, :t2)"), {"t1": trophy_id_custom, "t2": trophy_id_default})
        await session.execute(text("DELETE FROM player_games WHERE id = :gid"), {"gid": game_id})
        await session.execute(text("DELETE FROM players WHERE id = :pid"), {"pid": player_id})
