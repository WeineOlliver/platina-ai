import pytest
from decimal import Decimal
from sqlalchemy import select, text
from src.database import get_db_session
from src.models.catalog import GameModel, TrophyModel
from src.catalog.importer import (
    parse_trophies_html,
    parse_guide_html,
    import_catalog,
)


SYNTHETIC_TROPHIES_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Synthetic Adventure Trophies • PSNProfiles.com</title>
</head>
<body>
    <div class="title-bar">
        <div class="title flex v-align center">Synthetic Adventure Trophies</div>
    </div>

    <!-- Base Game -->
    <div class="box">
        <table class="zebra">
            <tr>
                <td style="padding: 10px 10px 10px 0; width: 100%;">
                    <span class="title">Base Game</span>
                </td>
            </tr>
        </table>
        <table class="zebra">
            <tr></tr>
            <tr>
                <td>
                    <a href="/trophy/10001-synthetic-adventure/1-master-adventurer">
                        <img src="/lib/img/icons/40-platinum.png" title="Platinum"/>
                    </a>
                </td>
                <td style="width: 100%;">
                    <a class="title" href="/trophy/10001-synthetic-adventure/1-master-adventurer">Master Adventurer</a>
                    <br/>
                    Collect all trophies in the game.
                </td>
                <td>
                    <span class="separator left">
                        <img src="/lib/img/icons/40-platinum.png" title="Platinum"/>
                    </span>
                </td>
            </tr>
            <tr>
                <td>
                    <a href="/trophy/10001-synthetic-adventure/2-first-steps">
                        <img src="/lib/img/icons/40-bronze.png" title="Bronze"/>
                    </a>
                </td>
                <td style="width: 100%;">
                    <a class="title" href="/trophy/10001-synthetic-adventure/2-first-steps">First Steps</a>
                    <br/>
                    Complete the tutorial quest.
                </td>
                <td>
                    <span class="separator left">
                        <img src="/lib/img/icons/40-bronze.png" title="Bronze"/>
                    </span>
                </td>
            </tr>
            <tr>
                <td>
                    <a href="/trophy/10001-synthetic-adventure/3-missable-relic">
                        <img src="/lib/img/icons/40-silver.png" title="Silver"/>
                    </a>
                </td>
                <td style="width: 100%;">
                    <a class="title" href="/trophy/10001-synthetic-adventure/3-missable-relic">Missable Relic</a>
                    <br/>
                    Find the ancient relic before leaving the starting island.
                </td>
                <td>
                    <span class="separator left">
                        <img src="/lib/img/icons/40-silver.png" title="Silver"/>
                    </span>
                </td>
            </tr>
        </table>
    </div>

    <!-- Hearts of Stone DLC -->
    <div class="box">
        <table class="zebra">
            <tr>
                <td style="width: 100%;">
                    <span class="title">Hearts of Stone</span>
                </td>
            </tr>
        </table>
        <table class="zebra">
            <tr></tr>
            <tr>
                <td>
                    <a href="/trophy/10001-synthetic-adventure/4-stone-heart">
                        <img src="/lib/img/icons/40-bronze.png" title="Bronze"/>
                    </a>
                </td>
                <td style="width: 100%;">
                    <a class="title" href="/trophy/10001-synthetic-adventure/4-stone-heart">Stone Heart</a>
                    <br/>
                    Defeat the cursed prince.
                </td>
                <td>
                    <span class="separator left">
                        <img src="/lib/img/icons/40-bronze.png" title="Bronze"/>
                    </span>
                </td>
            </tr>
        </table>
    </div>

    <!-- Blood and Wine DLC -->
    <div class="box">
        <table class="zebra">
            <tr>
                <td style="width: 100%;">
                    <span class="title">Blood and Wine</span>
                </td>
            </tr>
        </table>
        <table class="zebra">
            <tr></tr>
            <tr>
                <td>
                    <a href="/trophy/10001-synthetic-adventure/5-wine-country">
                        <img src="/lib/img/icons/40-bronze.png" title="Bronze"/>
                    </a>
                </td>
                <td style="width: 100%;">
                    <a class="title" href="/trophy/10001-synthetic-adventure/5-wine-country">Wine Country</a>
                    <br/>
                    Arrive in the southern kingdom.
                </td>
                <td>
                    <span class="separator left">
                        <img src="/lib/img/icons/40-bronze.png" title="Bronze"/>
                    </span>
                </td>
            </tr>
        </table>
    </div>
</body>
</html>
"""

SYNTHETIC_GUIDE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Synthetic Adventure Trophy Guide • PSNProfiles.com</title>
</head>
<body>
    <div class="section-holder" id="SectionContainer1">
        <div class="box light guide overview">
            <div class="overview-info">
                <span class="tag">
                    <span class="typo-top">7/10</span>
                    <br/>
                    <span class="typo-bottom">Difficulty</span>
                </span>
                <span class="tag">
                    <span class="typo-top">2</span>
                    <br/>
                    <span class="typo-bottom">Playthroughs</span>
                </span>
                <span class="tag">
                    <span class="typo-top">110</span>
                    <br/>
                    <span class="typo-bottom">Hours</span>
                </span>
            </div>
            <table class="invisible tags">
                <tr>
                    <td>
                        <span class="tag Status">Story</span>
                    </td>
                    <td>
                        <nobr><a href="#2-first-steps">First Steps</a></nobr>
                    </td>
                </tr>
                <tr>
                    <td>
                        <span class="tag Status">Missable</span>
                    </td>
                    <td>
                        <nobr><a href="#3-missable-relic">Missable Relic</a></nobr>
                    </td>
                </tr>
            </table>
        </div>
    </div>

    <!-- Individual trophy section for Missable Relic -->
    <div class="section-holder" id="SectionContainer2">
        <div class="box section-holder" id="MissableRelic">
            <table class="zebra">
                <tr>
                    <td>
                        <a class="title" href="/trophy/10001-synthetic-adventure/3-missable-relic">Missable Relic</a>
                    </td>
                </tr>
            </table>
            <div class="section-tags">
                <span class="tag">Missable</span>
                <span class="tag">Collectable</span>
            </div>
        </div>
    </div>
</body>
</html>
"""


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_parse_trophies_html():
    """Verify parsing of Base Game, DLCs, and trophy rows from synthetic HTML."""
    parsed = parse_trophies_html(SYNTHETIC_TROPHIES_HTML)
    assert parsed["title"] == "Synthetic Adventure"
    trophies = parsed["trophies"]
    assert len(trophies) == 5

    # Base Game trophies (dlc is None)
    base_trophies = [t for t in trophies if t["dlc"] is None]
    assert len(base_trophies) == 3
    t1 = next(t for t in base_trophies if t["name"] == "Master Adventurer")
    assert t1["type"] == "platinum"
    assert t1["description"] == "Collect all trophies in the game."
    assert t1["psnprofiles_trophy_id"] == 1

    t2 = next(t for t in base_trophies if t["name"] == "First Steps")
    assert t2["type"] == "bronze"
    assert t2["description"] == "Complete the tutorial quest."
    assert t2["psnprofiles_trophy_id"] == 2

    t3 = next(t for t in base_trophies if t["name"] == "Missable Relic")
    assert t3["type"] == "silver"
    assert t3["description"] == "Find the ancient relic before leaving the starting island."
    assert t3["psnprofiles_trophy_id"] == 3

    # Hearts of Stone DLC
    hos = [t for t in trophies if t["dlc"] == "Hearts of Stone"]
    assert len(hos) == 1
    assert hos[0]["name"] == "Stone Heart"
    assert hos[0]["type"] == "bronze"

    # Blood and Wine DLC
    baw = [t for t in trophies if t["dlc"] == "Blood and Wine"]
    assert len(baw) == 1
    assert baw[0]["name"] == "Wine Country"
    assert baw[0]["type"] == "bronze"


def test_parse_guide_html():
    """Verify parsing overview metadata and missables from synthetic guide HTML."""
    overview = parse_guide_html(SYNTHETIC_GUIDE_HTML)
    assert overview["difficulty"] == Decimal("7")
    assert overview["hours"] == 110
    assert overview["playthroughs"] == 2
    assert "Missable Relic" in overview["missable_trophies"]
    assert "First Steps" not in overview["missable_trophies"]


@pytest.mark.anyio
@pytest.mark.integration
async def test_import_catalog_idempotent(tmp_path):
    """Verify full catalog import and idempotent upsert into database."""
    game_id = "test-synthetic-adventure"

    trophies_file = tmp_path / "trophies.html"
    trophies_file.write_text(SYNTHETIC_TROPHIES_HTML, encoding="utf-8")

    guide_file = tmp_path / "guide.html"
    guide_file.write_text(SYNTHETIC_GUIDE_HTML, encoding="utf-8")

    # Clean up before testing
    async with get_db_session() as session:
        await session.execute(text("DELETE FROM trophies WHERE game_id = :gid"), {"gid": game_id})
        await session.execute(text("DELETE FROM games WHERE id = :gid"), {"gid": game_id})

    # 1. First import
    res1 = await import_catalog(game_id, str(trophies_file), str(guide_file))
    assert res1["imported_trophies"] == 5
    assert res1["unlocated_trophies"] == 5

    async with get_db_session() as session:
        # Check game
        stmt_game = select(GameModel).where(GameModel.id == game_id)
        game = (await session.execute(stmt_game)).scalar_one()
        assert game.title == "Synthetic Adventure"
        assert game.difficulty == Decimal("7")
        assert game.hours == 110
        assert game.playthroughs == 2
        assert game.metadata_source == "psnprofiles"

        # Check trophies
        stmt_trophies = select(TrophyModel).where(TrophyModel.game_id == game_id).order_by(TrophyModel.psnprofiles_trophy_id)
        trophies = (await session.execute(stmt_trophies)).scalars().all()
        assert len(trophies) == 5

        relic = next(t for t in trophies if t.name == "Missable Relic")
        assert relic.missable is True
        assert "psnprofiles" in relic.missable_sources
        assert relic.location is None

        master = next(t for t in trophies if t.name == "Master Adventurer")
        assert master.missable is False
        assert master.dlc is None

        hos_t = next(t for t in trophies if t.name == "Stone Heart")
        assert hos_t.dlc == "Hearts of Stone"

        baw_t = next(t for t in trophies if t.name == "Wine Country")
        assert baw_t.dlc == "Blood and Wine"

    # 2. Re-import (Idempotency check)
    res2 = await import_catalog(game_id, str(trophies_file), str(guide_file))
    assert res2["imported_trophies"] == 5

    async with get_db_session() as session:
        count = (await session.execute(text("SELECT count(*) FROM trophies WHERE game_id = :gid"), {"gid": game_id})).scalar()
        assert count == 5

    # Clean up after test
    async with get_db_session() as session:
        await session.execute(text("DELETE FROM trophies WHERE game_id = :gid"), {"gid": game_id})
        await session.execute(text("DELETE FROM games WHERE id = :gid"), {"gid": game_id})


def test_normalize_catalog_name():
    # Insight: Ensures apostrophes, curly quotes and ellipses unify across sources
    from src.catalog.importer import normalize_catalog_name

    assert normalize_catalog_name("When It's Many Against One…") == "when it s many against one"
    assert normalize_catalog_name("When It’s Many Against One...") == "when it s many against one"
    assert normalize_catalog_name("Crow’s Perch") == "crow s perch"
    assert normalize_catalog_name("Crow's Perch") == "crow s perch"
