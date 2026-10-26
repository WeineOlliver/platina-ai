import pytest
from httpx import AsyncClient, ASGITransport, Response
from unittest.mock import patch, AsyncMock
from src.main import create_app
from src.database import get_db_session
from src.models.chunk import GuideChunkModel
from sqlalchemy import delete, select
from src.services.scraper import TrophyGuideScraper, scraper


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def async_client():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture(autouse=True)
async def cleanup_test_game():
    async with get_db_session() as session:
        await session.execute(delete(GuideChunkModel).where(GuideChunkModel.game.ilike("Test%")))
    yield
    async with get_db_session() as session:
        await session.execute(delete(GuideChunkModel).where(GuideChunkModel.game.ilike("Test%")))


@pytest.mark.anyio
async def test_cleanup_fixture_preserves_witcher_chunks():
    async with get_db_session() as session:
        witcher_chunk = GuideChunkModel(
            id="chunk_test_w3_preserved",
            game="The Witcher 3: Wild Hunt",
            title="Preserved Witcher Chunk",
            content="This chunk must not be deleted by test fixtures.",
            source_url="https://test.powerpyx.com/witcher-chunk",
            embedding=[0.0] * 1536,
            is_missable=False,
        )
        test_chunk = GuideChunkModel(
            id="chunk_test_scraped_temp",
            game="Test Scraped Game",
            title="Temporary Test Chunk",
            content="This chunk should be deleted by test cleanup.",
            source_url="https://test.powerpyx.com/test-chunk",
            embedding=[0.0] * 1536,
            is_missable=False,
        )
        session.add(witcher_chunk)
        session.add(test_chunk)
        await session.commit()

    async with get_db_session() as session:
        await session.execute(delete(GuideChunkModel).where(GuideChunkModel.game.ilike("Test%")))
        await session.commit()

    async with get_db_session() as session:
        w_res = await session.execute(select(GuideChunkModel).where(GuideChunkModel.game == "The Witcher 3: Wild Hunt"))
        witcher_survived = w_res.scalars().all()
        assert len(witcher_survived) >= 1
        assert any(c.title == "Preserved Witcher Chunk" for c in witcher_survived)

        t_res = await session.execute(select(GuideChunkModel).where(GuideChunkModel.game == "Test Scraped Game"))
        assert len(t_res.scalars().all()) == 0

        await session.execute(
            delete(GuideChunkModel).where(
                GuideChunkModel.game == "The Witcher 3: Wild Hunt",
                GuideChunkModel.title == "Preserved Witcher Chunk",
            )
        )
        await session.commit()


@pytest.mark.anyio
async def test_scraper_fallback_structured_roadmap():
    scraper_instance = TrophyGuideScraper()
    markdown, canonical_url = await scraper_instance.fetch_guide("Test Scraped Game")

    assert "test-scraped-game" in canonical_url
    assert "Roadmap Overview" in markdown
    assert "Tempo" in markdown
    assert "Dificuldade" in markdown
    assert "Passos da Platina" in markdown


@pytest.mark.anyio
async def test_scraper_fetches_source_url_with_html_parsing():
    html_sample = """
    <html>
      <head><title>Mock Guide</title></head>
      <body>
        <h1>Mock Guide Header</h1>
        <p>Overview of the game roadmap.</p>
        <h2>Perdível: Secret Trophy</h2>
        <p>Atenção: este troféu é missable se você avançar sem salvar.</p>
      </body>
    </html>
    """
    mock_response = AsyncMock(spec=Response)
    mock_response.status_code = 200
    mock_response.text = html_sample
    mock_response.url = "https://powerpyx.com/mock-guide"

    with patch("httpx.AsyncClient.get", return_value=mock_response):
        scraper_instance = TrophyGuideScraper()
        markdown, url = await scraper_instance.fetch_guide("Mock Game", source_url="https://powerpyx.com/mock-guide")

        assert url == "https://powerpyx.com/mock-guide"
        assert "# Mock Guide Header" in markdown
        assert "## Perdível: Secret Trophy" in markdown
        assert "Atenção: este troféu é missable" in markdown


@pytest.mark.anyio
async def test_fetch_and_index_new_game_and_idempotent_skip(async_client):
    game_name = "Test Scraped Game"

    # 1. First call: game is not indexed yet -> should scrape, chunk, embed, index
    response1 = await async_client.post(
        "/api/v1/ingest/fetch-and-index",
        json={"game": game_name},
    )
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["status"] == "indexed"
    assert data1["game"] == game_name
    assert data1["chunks_indexed"] >= 1
    assert "test-scraped-game" in data1["source_url"]

    # 2. Second call: game is already indexed -> should return already_indexed with chunk count
    response2 = await async_client.post(
        "/api/v1/ingest/fetch-and-index",
        json={"game": game_name},
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["status"] == "already_indexed"
    assert data2["chunks_indexed"] == data1["chunks_indexed"]


@pytest.mark.anyio
async def test_discover_subpages_matching_and_filtering():
    scraper_instance = TrophyGuideScraper()
    base_url = "https://www.powerpyx.com/the-witcher-3-wild-hunt-trophy-guide-roadmap/"
    html_content = """
    <html>
      <body>
        <a href="https://www.powerpyx.com/the-witcher-3-wild-hunt-trophy-guide-roadmap/">Main Guide</a>
        <a href="/all-gwent-cards-guide/">All Gwent Cards Guide</a>
        <a href="/gwent/locations/">Gwent Locations</a>
        <a href="/collectibles/places-of-power/">Collectibles Guide</a>
        <a href="/weapons/mastercrafted-gear/">Weapons Guide</a>
        <a href="/hearts-of-stone-dlc-trophy-guide/">DLC Trophy Guide</a>
        <!-- Noise to filter -->
        <a href="/tag/witcher-3/">Tag Page</a>
        <a href="/category/ps4-guides/">Category Page</a>
        <a href="#comments">Comments</a>
        <a href="/the-witcher-3-gwent/#respond">Leave a reply</a>
        <a href="https://twitter.com/PowerPyx">Twitter</a>
        <a href="https://facebook.com/PowerPyx">Facebook</a>
        <!-- Duplicates and excess -->
        <a href="/all-gwent-cards-guide/">All Gwent Cards Duplicate</a>
    """ + "".join(f'<a href="/all-extra-{i}-guide/">Extra {i}</a>\n' for i in range(20)) + """
      </body>
    </html>
    """
    subpages = scraper_instance.discover_subpages(html_content, base_url)

    # Must contain matched patterns
    assert "https://www.powerpyx.com/all-gwent-cards-guide/" in subpages
    assert "https://www.powerpyx.com/gwent/locations/" in subpages
    assert "https://www.powerpyx.com/collectibles/places-of-power/" in subpages
    assert "https://www.powerpyx.com/weapons/mastercrafted-gear/" in subpages
    assert "https://www.powerpyx.com/hearts-of-stone-dlc-trophy-guide/" in subpages

    # Must filter noise
    assert not any("/tag/" in u for u in subpages)
    assert not any("/category/" in u for u in subpages)
    assert not any("twitter.com" in u for u in subpages)
    assert not any("facebook.com" in u for u in subpages)
    assert not any("#comments" in u or "#respond" in u for u in subpages)
    assert base_url not in subpages

    # Must deduplicate and cap at 15
    assert len(subpages) <= 15
    assert len(subpages) == len(set(subpages))


@pytest.mark.anyio
async def test_fetch_game_guide_with_subpages_parallel_fetching():
    scraper_instance = TrophyGuideScraper()
    base_url = "https://www.powerpyx.com/mock-game-trophy-guide-roadmap/"

    main_html = """
    <html>
      <head><title>Mock Game Trophy Guide</title></head>
      <body>
        <h1>Mock Game Trophy Guide</h1>
        <p>Main roadmap content.</p>
        <a href="/all-collectibles-guide/">All Collectibles</a>
        <a href="/weapons/ultimate-arms/">Ultimate Weapons</a>
      </body>
    </html>
    """

    sub1_html = """
    <html>
      <head><title>Mock Game - All Collectibles Guide</title></head>
      <body>
        <h1>All Collectibles Guide</h1>
        <p>Details about hidden items.</p>
      </body>
    </html>
    """

    sub2_html = """
    <html>
      <head><title>Mock Game - Weapons Guide</title></head>
      <body>
        <h1>Weapons Guide</h1>
        <p>Details about ultimate weapons.</p>
      </body>
    </html>
    """

    async def mock_get(url, *args, **kwargs):
        url_str = str(url)
        resp = AsyncMock(spec=Response)
        resp.status_code = 200
        if "all-collectibles-guide" in url_str:
            resp.text = sub1_html
            resp.url = "https://www.powerpyx.com/all-collectibles-guide/"
        elif "weapons" in url_str:
            resp.text = sub2_html
            resp.url = "https://www.powerpyx.com/weapons/ultimate-arms/"
        else:
            resp.text = main_html
            resp.url = base_url
        return resp

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        pages = await scraper_instance.fetch_game_guide_with_subpages("Mock Game", source_url=base_url)

        assert len(pages) == 3
        urls = [p[2] for p in pages]
        assert base_url in urls
        assert "https://www.powerpyx.com/all-collectibles-guide/" in urls
        assert "https://www.powerpyx.com/weapons/ultimate-arms/" in urls

        # Verify page title and markdown content
        titles = [p[0] for p in pages]
        assert any("Collectibles" in t for t in titles)
        assert any("Weapons" in t for t in titles)


@pytest.mark.anyio
async def test_fetch_game_guide_subpages_generic_fallback():
    scraper_instance = TrophyGuideScraper()
    pages = await scraper_instance.fetch_game_guide_with_subpages("Test Scraped Game")

    assert len(pages) == 1
    title, markdown, url, html = pages[0]
    assert "test-scraped-game" in url
    assert "Roadmap Overview" in title
    assert "Passos da Platina" in markdown


@pytest.mark.anyio
async def test_fetch_and_index_force_reindex(async_client):
    game_name = "Test Scraped Game"

    # 1. First indexing
    resp1 = await async_client.post(
        "/api/v1/ingest/fetch-and-index",
        json={"game": game_name},
    )
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["status"] == "indexed"
    initial_chunks = data1["chunks_indexed"]

    # 2. Subsequent call without force_reindex returns already_indexed
    resp2 = await async_client.post(
        "/api/v1/ingest/fetch-and-index",
        json={"game": game_name, "force_reindex": False},
    )
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "already_indexed"

    # 3. Subsequent call with force_reindex=True re-indexes
    resp3 = await async_client.post(
        "/api/v1/ingest/fetch-and-index",
        json={"game": game_name, "force_reindex": True},
    )
    assert resp3.status_code == 200
    data3 = resp3.json()
    assert data3["status"] == "indexed"
    assert data3["chunks_indexed"] >= initial_chunks


@pytest.mark.anyio
async def test_extract_canonical_roadmap_generic_and_content_parsing():
    scraper_instance = TrophyGuideScraper()

    # 1. Unindexed game without content returns generic template with empty missables
    roadmap_empty = scraper_instance.extract_canonical_roadmap("Unknown Game")
    assert roadmap_empty["game"] == "Unknown Game"
    assert roadmap_empty["difficulty"] == "N/A"
    assert len(roadmap_empty["missable_trophies"]) == 0

    # 2. Witcher 3 without content also returns generic template (no hardcoded dict)
    roadmap_w3 = scraper_instance.extract_canonical_roadmap("The Witcher 3: Wild Hunt")
    assert roadmap_w3["game"] == "The Witcher 3: Wild Hunt"
    assert roadmap_w3["difficulty"] == "N/A"
    assert len(roadmap_w3["missable_trophies"]) == 0

    # 3. Content-based extraction parses metrics and missables generically
    sample_content = """
    Estimated trophy difficulty: 5/10
    Minimum playthroughs: 2
    Approximate amount of time to platinum: 40 hours
    ### Missable: Secret Ending
    ### Perdível: Ancient Relic
    """
    parsed = scraper_instance.extract_canonical_roadmap("Test Game", content=sample_content)
    assert parsed["difficulty"] == "5/10"
    assert parsed["playthroughs_required"] == 2
    assert parsed["time_required"] == "40 hours"
    assert len(parsed["missable_trophies"]) == 2
    names = [t.name for t in parsed["missable_trophies"]]
    assert "Missable: Secret Ending" in names
    assert "Perdível: Ancient Relic" in names


@pytest.mark.anyio
async def test_multi_source_domain_fallback_handles_http_errors():
    scraper_instance = TrophyGuideScraper()

    candidates = scraper_instance.get_candidate_urls("Test Scraped Game")
    assert any("powerpyx.com" in c.lower() for c in candidates)

    # Mock all HTTP calls returning 403 / 404 errors
    def mock_get(url, *args, **kwargs):
        url_str = str(url)
        resp = AsyncMock(spec=Response)
        if "playstationtrophies.org" in url_str:
            resp.status_code = 403
            resp.text = "Forbidden"
        elif "consolepulse.com" in url_str:
            resp.status_code = 404
            resp.text = "Not Found"
        else:
            resp.status_code = 403
            resp.text = "Cloudflare Block"
        resp.url = url_str
        return resp

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        pages = await scraper_instance.fetch_game_guide_with_subpages("Test Scraped Game")

        # Must not fail and must fall back gracefully to structured canonical guide
        assert len(pages) >= 1
        main_title, main_markdown, canonical_url, html = pages[0]
        assert "Roadmap Overview" in main_markdown or "Test Scraped Game" in main_title
        assert "Passos da Platina" in main_markdown


@pytest.mark.anyio
async def test_parse_roadmap_dom_psnprofiles_structure():
    scraper_instance = TrophyGuideScraper()

    psn_html = """
    <html>
      <body>
        <div class="trophy-info">
          <dl>
            <dt>Difficulty</dt>
            <dd>4/10</dd>
            <dt>Playthroughs</dt>
            <dd>2</dd>
            <dt>Estimated Time</dt>
            <dd>50 hours</dd>
          </dl>
        </div>
        <table class="trophy-list">
          <tr class="trophy-row">
            <td class="title"><a class="title" href="/trophies/1-master-of-the-arena">Master of the Arena</a></td>
            <td><span class="tag missable">Missable</span></td>
          </tr>
          <tr class="trophy-row">
            <td class="title"><a class="title" href="/trophies/2-full-crew">Full Crew</a></td>
            <td><span class="tag missable">Missable</span></td>
          </tr>
          <tr class="trophy-row">
            <td class="title"><a class="title" href="/trophies/3-passed-the-trial">Passed the Trial</a></td>
            <td><span class="tag story">Story</span></td>
          </tr>
        </table>
        <a href="/guide/123-the-witcher-3-collectibles">Collectibles Guide</a>
      </body>
    </html>
    """

    res = scraper_instance.parse_roadmap_dom(psn_html, base_url="https://psnprofiles.com")

    assert res["difficulty"] == "4/10"
    assert res["playthroughs"] == 2
    assert res["time_estimate"] == "50 hours"
    assert res["missable_trophies"] == ["Master of the Arena", "Full Crew"]
    assert "Passed the Trial" not in res["missable_trophies"]
    assert any("collectibles" in u for u in res["subpage_urls"])


@pytest.mark.anyio
async def test_parse_roadmap_dom_powerpyx_structure():
    scraper_instance = TrophyGuideScraper()

    powerpyx_html = """
    <html>
      <body>
        <div class="entry-content">
          <p><strong>Estimated trophy difficulty:</strong> 5/10</p>
          <p><strong>Minimum Playthroughs:</strong> 1</p>
          <p><strong>Approximate amount of time to platinum:</strong> 70-80 hours</p>
          <p><strong>Number of missable trophies:</strong> 2 – <a href="#card-collector">Card Collector</a>, <a href="#woodland-spirit">Woodland Spirit</a></p>
          <h3 class="entry-title"><a name="card-collector"></a>Card Collector</h3>
          <p><span class="missable">MISSABLE</span></p>
          <p>Acquire all gwent cards.</p>
          <h3 class="entry-title"><a name="woodland-spirit"></a>Woodland Spirit</h3>
          <p><strong>[Missable]</strong></p>
          <p>Contract trophy.</p>
          <h3 class="entry-title">Geralt and Friends</h3>
          <p>Win a round of gwent using only neutral cards.</p>
          <a href="https://www.powerpyx.com/the-witcher-3-all-gwent-cards-guide/">All Gwent Cards Guide</a>
        </div>
      </body>
    </html>
    """

    res = scraper_instance.parse_roadmap_dom(powerpyx_html, base_url="https://www.powerpyx.com")

    assert res["difficulty"] == "5/10"
    assert res["playthroughs"] == 1
    assert "70-80 hours" in res["time_estimate"]
    assert res["missable_trophies"] == ["Card Collector", "Woodland Spirit"]
    assert "Geralt and Friends" not in res["missable_trophies"]
    assert any("gwent" in u for u in res["subpage_urls"])


@pytest.mark.anyio
async def test_discover_guide_urls_powerpyx_search_and_fallback():
    scraper_instance = TrophyGuideScraper()

    search_results_html = """
    <html>
      <body>
        <article>
          <h2 class="entry-title">
            <a href="https://www.powerpyx.com/the-witcher-3-wild-hunt-trophy-guide-roadmap/">The Witcher 3: Wild Hunt Trophy Guide</a>
          </h2>
        </article>
        <article>
          <h2 class="entry-title">
            <a href="https://www.powerpyx.com/guides/the-witcher-3-blood-and-wine-trophy-guide.html">The Witcher 3: Blood and Wine Trophy Guide</a>
          </h2>
        </article>
        <!-- Noise -->
        <a href="https://www.powerpyx.com/guides/">Guides Index</a>
        <a href="https://www.powerpyx.com/tag/witcher-3/">Tag Page</a>
      </body>
    </html>
    """

    mock_resp = AsyncMock(spec=Response)
    mock_resp.status_code = 200
    mock_resp.text = search_results_html

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        urls = await scraper_instance.discover_guide_urls("The Witcher 3")

        # Discovered search result guides are present
        assert "https://www.powerpyx.com/the-witcher-3-wild-hunt-trophy-guide-roadmap/" in urls
        assert "https://www.powerpyx.com/guides/the-witcher-3-blood-and-wine-trophy-guide.html" in urls

        # Canonical fallback patterns are included
        assert any("playstationtrophies.org" in u for u in urls)
        assert any("psnprofiles.com" in u for u in urls)

        # Noise index links are filtered
        assert "https://www.powerpyx.com/guides/" not in urls

    # Fallback on search failure
    with patch("httpx.AsyncClient.get", side_effect=Exception("Connection refused")):
        fallback_urls = await scraper_instance.discover_guide_urls("The Witcher 3")
        assert len(fallback_urls) >= 3
        assert any("powerpyx.com" in u for u in fallback_urls)
        assert any("playstationtrophies.org" in u for u in fallback_urls)
        assert any("psnprofiles.com" in u for u in fallback_urls)


@pytest.mark.anyio
async def test_fetch_game_guide_with_subpages_browser_fallback_on_403():
    scraper_instance = TrophyGuideScraper()
    test_url = "https://www.powerpyx.com/protected-game-trophy-guide-roadmap/"

    rendered_html = """
    <html>
      <head><title>Protected Game Trophy Guide</title></head>
      <body>
        <h1>Protected Game Trophy Guide & Roadmap</h1>
        <p>Estimated trophy difficulty: 6/10</p>
        <p>Minimum Playthroughs: 2</p>
        <p>Roadmap content successfully rendered via headless browser.</p>
      </body>
    </html>
    """

    mock_resp_403 = AsyncMock(spec=Response)
    mock_resp_403.status_code = 403
    mock_resp_403.text = "Cloudflare Challenge"

    with patch("httpx.AsyncClient.get", return_value=mock_resp_403), \
         patch("src.services.scraper.fetch_rendered_html", new_callable=AsyncMock, return_value=rendered_html) as mock_browser:
        pages = await scraper_instance.fetch_game_guide_with_subpages("Protected Game", source_url=test_url)

        assert mock_browser.called
        assert len(pages) >= 1
        title, md, url, html = pages[0]
        assert "Protected Game Trophy Guide" in title
        assert "Roadmap content successfully rendered" in md
        assert url == test_url


@pytest.mark.anyio
async def test_fetch_and_index_syncs_player_trophies_missables(async_client):
    from src.database import get_db_session
    from sqlalchemy import text
    from unittest.mock import patch

    game_title = "Sync Test Game"
    player_id = "ply_sync_test"
    player_game_id = "pg_sync_test"
    trophy_id = "tr_sync_test_01"
    trophy_name = "Crucial Missable Trophy"

    # Setup DB rows
    async with get_db_session() as session:
        await session.execute(
            text("INSERT INTO players (id, psn_id, email) VALUES (:pid, :psn, :email) ON CONFLICT DO NOTHING"),
            {"pid": player_id, "psn": "sync_player", "email": "sync@test.com"},
        )
        await session.execute(
            text("INSERT INTO player_games (id, player_id, game_title) VALUES (:gid, :pid, :game) ON CONFLICT DO NOTHING"),
            {"gid": player_game_id, "pid": player_id, "game": game_title},
        )
        await session.execute(
            text(
                "INSERT INTO player_trophies (id, player_game_id, trophy_name, trophy_type, trophy_category, is_missable) "
                "VALUES (:tid, :gid, :tname, 'bronze', 'standard', false) "
                "ON CONFLICT (player_game_id, trophy_name) DO UPDATE SET is_missable = false, trophy_category = 'standard'"
            ),
            {"tid": trophy_id, "gid": player_game_id, "tname": trophy_name},
        )

    mock_guide_markdown = f"""# {game_title} Guide
## Troféus Perdíveis (Missable Trophies)
### {trophy_name}
Atenção: Troféu perdível (missable)! Não avance antes de coletar.
"""

    mock_pages = [("Guide Title", mock_guide_markdown, "https://example.com/guide", f"<html><body>{mock_guide_markdown}</body></html>")]

    try:
        with patch("src.services.scraper.scraper.fetch_game_guide_with_subpages", return_value=mock_pages):
            resp = await async_client.post(
                "/api/v1/ingest/fetch-and-index",
                json={"game": game_title, "force_reindex": True},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "indexed"
            assert trophy_name in data.get("missables_synced", [])

            # Verify in player_trophies table
            async with get_db_session() as session:
                res = await session.execute(
                    text("SELECT is_missable, trophy_category FROM player_trophies WHERE id = :tid"),
                    {"tid": trophy_id},
                )
                row = res.fetchone()
                assert row is not None
                assert row[0] is True, "is_missable should be updated to True"
                assert row[1] == "missable", "trophy_category should be updated to 'missable'"
    finally:
        async with get_db_session() as session:
            await session.execute(text("DELETE FROM player_trophies WHERE id = :tid"), {"tid": trophy_id})
            await session.execute(text("DELETE FROM player_games WHERE id = :gid"), {"gid": player_game_id})
            await session.execute(text("DELETE FROM players WHERE id = :pid"), {"pid": player_id})
            await session.execute(text("DELETE FROM guide_chunks WHERE game ILIKE :game"), {"game": game_title})


@pytest.mark.anyio
async def test_fetch_and_index_syncs_missables_from_html_dom_classes(async_client):
    game_title = "HTML Missable Test Game"
    test_url = "https://www.powerpyx.com/html-missable-game-trophy-guide-roadmap/"
    html_fixture = """
    <html>
      <head><title>HTML Missable Test Game Trophy Guide</title></head>
      <body>
        <h1>HTML Missable Test Game Trophy Guide</h1>
        <p>Complete roadmap overview.</p>
        <table class="trophy-list">
          <tr class="trophy-row">
            <td class="title"><a class="title">Collector of Ancient Coins</a></td>
            <td><span class="tag missable">Missable</span></td>
          </tr>
        </table>
      </body>
    </html>
    """

    mock_resp = AsyncMock(spec=Response)
    mock_resp.status_code = 200
    mock_resp.text = html_fixture
    mock_resp.url = test_url

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        try:
            resp = await async_client.post(
                "/api/v1/ingest/fetch-and-index",
                json={"game": game_title, "source_url": test_url, "force_reindex": True},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "Collector of Ancient Coins" in data.get("missables_synced", [])
        finally:
            async with get_db_session() as session:
                await session.execute(delete(GuideChunkModel).where(GuideChunkModel.game.ilike(game_title)))


@pytest.mark.anyio
async def test_missables_sync_does_not_update_unrelated_games_when_game_not_in_player_games(async_client):
    from sqlalchemy import text

    pid = "ply_shared_test"
    gid1 = "pg_shared_game_1"
    gid2 = "pg_shared_game_2"
    tid1 = "tr_shared_1"
    tid2 = "tr_shared_2"
    trophy_name = "Common Shared Trophy"

    # Setup 2 existing games with the same trophy name
    async with get_db_session() as session:
        await session.execute(
            text("INSERT INTO players (id, psn_id, email) VALUES (:pid, :psn, :email) ON CONFLICT DO NOTHING"),
            {"pid": pid, "psn": "shared_player", "email": "shared@test.com"},
        )
        await session.execute(
            text("INSERT INTO player_games (id, player_id, game_title) VALUES (:gid, :pid, :game) ON CONFLICT DO NOTHING"),
            {"gid": gid1, "pid": pid, "game": "Existing Game One"},
        )
        await session.execute(
            text("INSERT INTO player_games (id, player_id, game_title) VALUES (:gid, :pid, :game) ON CONFLICT DO NOTHING"),
            {"gid": gid2, "pid": pid, "game": "Existing Game Two"},
        )
        await session.execute(
            text(
                "INSERT INTO player_trophies (id, player_game_id, trophy_name, trophy_type, trophy_category, is_missable) "
                "VALUES (:tid, :gid, :tname, 'bronze', 'standard', false) "
                "ON CONFLICT (player_game_id, trophy_name) DO UPDATE SET is_missable = false, trophy_category = 'standard'"
            ),
            {"tid": tid1, "gid": gid1, "tname": trophy_name},
        )
        await session.execute(
            text(
                "INSERT INTO player_trophies (id, player_game_id, trophy_name, trophy_type, trophy_category, is_missable) "
                "VALUES (:tid, :gid, :tname, 'bronze', 'standard', false) "
                "ON CONFLICT (player_game_id, trophy_name) DO UPDATE SET is_missable = false, trophy_category = 'standard'"
            ),
            {"tid": tid2, "gid": gid2, "tname": trophy_name},
        )

    # Ingest a guide for a 3rd game that does NOT exist in player_games
    unregistered_game = "Nonexistent Game Three"
    mock_guide_md = f"""# {unregistered_game} Guide
## Troféus Perdíveis (Missable Trophies)
### {trophy_name}
Atenção: Troféu perdível (missable)!
"""
    mock_pages = [("Guide Title", mock_guide_md, "https://example.com/guide3", f"<html><body>{mock_guide_md}</body></html>")]

    try:
        with patch("src.services.scraper.scraper.fetch_game_guide_with_subpages", return_value=mock_pages):
            resp = await async_client.post(
                "/api/v1/ingest/fetch-and-index",
                json={"game": unregistered_game, "force_reindex": True},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["trophies_updated"] == 0

            # Verify neither existing game's trophy was modified
            async with get_db_session() as session:
                res1 = await session.execute(
                    text("SELECT is_missable, trophy_category FROM player_trophies WHERE id = :tid"),
                    {"tid": tid1},
                )
                row1 = res1.fetchone()
                assert row1[0] is False, "Game 1 trophy should NOT be marked missable"
                assert row1[1] == "standard"

                res2 = await session.execute(
                    text("SELECT is_missable, trophy_category FROM player_trophies WHERE id = :tid"),
                    {"tid": tid2},
                )
                row2 = res2.fetchone()
                assert row2[0] is False, "Game 2 trophy should NOT be marked missable"
                assert row2[1] == "standard"
    finally:
        async with get_db_session() as session:
            await session.execute(text("DELETE FROM player_trophies WHERE id IN (:tid1, :tid2)"), {"tid1": tid1, "tid2": tid2})
            await session.execute(text("DELETE FROM player_games WHERE id IN (:gid1, :gid2)"), {"gid1": gid1, "gid2": gid2})
            await session.execute(text("DELETE FROM players WHERE id = :pid"), {"pid": pid})
            await session.execute(text("DELETE FROM guide_chunks WHERE game ILIKE :game"), {"game": unregistered_game})





