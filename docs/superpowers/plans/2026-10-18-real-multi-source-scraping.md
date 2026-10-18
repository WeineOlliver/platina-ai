# Real Multi-Source Guide Ingestion & Database Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Revert all hardcoded Witcher 3 strings and duplicate seeded trophies, isolate test cleanup from production data, implement real dynamic discovery via PowerPyx search + Playwright (for Cloudflare-protected sites like PSNProfiles/PlayStationTrophies), and derive `is_missable` strictly from actual scraped community guides for any game.

**Architecture:**
1. Roll back hardcoded fallback strings from `services/ingest/src/services/scraper.py` and remove duplicate trophies from `infra/postgres/08_complete_catalog_missables.sql`. Fix `cleanup_test_game` fixture to use an isolated prefix so tests never wipe real ingested chunks.
2. Add Playwright (Chromium headless) to `services/ingest` for Cloudflare-bypassing fetches when httpx encounters 403.
3. Build a generic `GuideDiscoverer` that searches PowerPyx (`/?s=<query>`) and Google/DuckDuckGo, fetches the real roadmap via Playwright/httpx, and parses the genuine roadmap structure (Difficulty, Playthroughs, Missable trophies, Collectible subpages) dynamically for any game.
4. Index real crawled data for The Witcher 3 (and other catalog games) into `guide_chunks` and update `player_trophies.is_missable` strictly from the parsed guide data.

**Tech Stack:** Python 3.12, Playwright (Chromium headless), BeautifulSoup4, httpx, PostgreSQL 16 (pgvector), Fastify, TypeScript.

**Spec:** Generic Multi-Source Scraping & Grounded Trophy Ingestion

## Global Constraints
- ZERO hardcoded trophy names, quest descriptions, or cards in `scraper.py`. Everything must come from fetched web HTML.
- Never wipe real game chunks during unit tests. Test fixtures must only touch `Test*` prefixed games.
- Duplicated trophies in `player_trophies` (e.g., "Three Man Army" vs "Three-Man Army") must be cleaned up.
- Playwright runs headlessly; if Playwright is unavailable, fall back cleanly with informative error, never fabricate fake text.
- 100% of existing tests must pass.

## Review Focus
1. What happens if Playwright fails to launch or times out? Scraper must log error and fall back without hanging.
2. What happens if a guide doesn't have a clear "Missable" section? Scraper marks missables as empty rather than inventing them.
3. Does running `pytest` delete "The Witcher 3: Wild Hunt" chunks? Must be strictly prevented by isolating test identifiers.
4. Are trophy name comparisons case-insensitive and normalized when matching against `player_trophies`?
5. Does the Fastify agent continue to function with actual scraped chunks?

---

### Task 1: Revert Hardcoded Data & Fix Destructive Test Fixture

**Files:**
- Modify: `services/ingest/src/services/scraper.py`
- Modify: `services/ingest/tests/test_scraper.py`
- Modify: `infra/postgres/08_complete_catalog_missables.sql`
- Script/SQL: Clean up duplicate trophies in `platina-postgres`

**Interfaces:**
- `cleanup_test_game` in `test_scraper.py` must ONLY delete chunks where `game ILIKE 'Test%'`.
- Remove `generate_witcher_3_gwent_guide` and hardcoded Witcher 3 blocks in `extract_canonical_roadmap`.
- Revert duplicate trophy inserts (`tr_gta_m_kifflom_alt`, `tr_gta_m_3man_alt`).

- [ ] **Step 1: Write test in `test_scraper.py` confirming `cleanup_test_game` does NOT delete "The Witcher 3: Wild Hunt"**
- [ ] **Step 2: Clean up scraper.py: strip out hardcoded Witcher text and hardcoded Gwent card generators**
- [ ] **Step 3: Remove duplicate GTA trophies from postgres and update 08_complete_catalog_missables.sql**
- [ ] **Step 4: Run pytest in `services/ingest` to verify no regressions**
- [ ] **Step 5: Commit changes**

---

### Task 2: Install Playwright & Build Generic Browser Fetcher

**Files:**
- Modify: `services/ingest/pyproject.toml`
- Create: `services/ingest/src/services/browser.py`
- Test: `services/ingest/tests/test_browser.py`

**Interfaces:**
- Produces: `async def fetch_rendered_html(url: str, timeout: float = 30.0) -> Optional[str]`
- Handles Cloudflare Turnstile / JS challenge rendering by launching headless Chromium with realistic headers.

- [ ] **Step 1: Add playwright to `pyproject.toml` and install chromium via `uv run playwright install chromium`**
- [ ] **Step 2: Write test in `test_browser.py` mocking browser fetch and testing real fetch with fallback**
- [ ] **Step 3: Implement `fetch_rendered_html` in `browser.py`**
- [ ] **Step 4: Run pytest to verify browser fetcher passes**
- [ ] **Step 5: Commit changes**

---

### Task 3: Generic Guide Discovery & True DOM Roadmap Parser

**Files:**
- Modify: `services/ingest/src/services/scraper.py`
- Test: `services/ingest/tests/test_scraper.py`

**Interfaces:**
- Produces: `TrophyGuideScraper.discover_guide_urls(game: str) -> list[str]` using PowerPyx site search (`/?s=...`) + DuckDuckGo HTML.
- Produces: `TrophyGuideScraper.parse_roadmap_dom(html: str) -> dict` dynamically extracting:
  - Difficulty, Playthroughs, Time
  - Missable trophy names extracted from DOM tags (`.missable`, `dt:contains('Missable')`, or regex in guide body)
  - Subpage links (collectibles, cards, walkthroughs)

- [ ] **Step 1: Write unit tests with real HTML fixtures from PowerPyx and PSNProfiles asserting parsed missables**
- [ ] **Step 2: Implement dynamic search discovery and DOM roadmap parser in `scraper.py`**
- [ ] **Step 3: Integrate `fetch_rendered_html` from `browser.py` when HTTP 403 is received from httpx**
- [ ] **Step 4: Run `uv run pytest -vv` in `services/ingest`**
- [ ] **Step 5: Commit changes**

---

### Task 4: Real Re-indexing of Catalog & E2E Validation

**Files:**
- Modify: `services/ingest/src/routes/ingest.py`
- Test: `apps/api/src/services/agent/runner.benchmark.test.ts`
- Documentation: `docs/learning-log.md`

- [ ] **Step 1: Trigger real dynamic fetch and index for The Witcher 3 via `POST /api/v1/ingest/fetch-and-index`**
- [ ] **Step 2: Confirm `guide_chunks` contains real scraped chunks and verify `player_trophies.is_missable` matches genuine roadmap**
- [ ] **Step 3: Run full test suites: `uv run pytest -vv` and `npm test`**
- [ ] **Step 4: Commit and push**
