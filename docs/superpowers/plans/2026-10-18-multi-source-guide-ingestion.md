# Multi-Source Robust Guide Ingestion & Complete Trophy Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace fragile single-URL scraping with a resilient multi-source guide search and ingestion engine (PlayStationTrophies, ConsolePulse, PowerPyx) and populate exhaustive trophy metadata with 100% of missable trohpies flagged across all games in the catalog.

**Architecture:**
1. `services/ingest/src/services/scraper.py`: Refactor `TrophyGuideScraper` to perform real dynamic multi-source discovery across domain fallbacks, parsing canonical roadmap blocks (Difficulty, Playthroughs, Missable Trophy list, Stages 1-6, and collectible sub-guides).
2. `infra/postgres`: Create migrations and seed scripts updating the entire catalog (*The Witcher 3: Wild Hunt*, *Grand Theft Auto V*, *Bloodborne*, *Elden Ring*) with all canonical missable flags and categories verified against official roadmaps.
3. `apps/api`: Integrate multi-source search in `runner.ts` and verify deep walkthroughs deliver 100% of required missables and step-by-step collectible locations.

**Tech Stack:** Python 3.12, BeautifulSoup4, httpx, PostgreSQL 16, pgvector, TypeScript, Fastify, Vitest, Pytest.

**Spec:** Multi-Source Resilient Scraping Architecture

## Global Constraints
- Zero reliance on hardcoded URLs that return 404/403.
- All missable trophies from canonical community roadmaps must have `is_missable = true` and `trophy_category = 'missable'` in `player_trophies`.
- Full-text `tsvector` and 1536-dim vector embeddings must be generated for all chunks.
- 100% of existing tests in `services/ingest` and `apps/api` must pass.

---

### Task 1: Resilient Multi-Source Guide Ingestion Engine in Python

**Files:**
- Modify: `services/ingest/src/services/scraper.py`
- Modify: `services/ingest/src/routes/ingest.py`
- Test: `services/ingest/tests/test_scraper.py`

**Interfaces:**
- Produces: `TrophyGuideScraper.fetch_game_guide_with_subpages(game, source_url)` querying multi-source domains, extracting structured roadmap blocks (Difficulty, Playthroughs, Missable Trophies list, Stages 1-6).

- [ ] **Step 1: Write unit tests in `test_scraper.py` asserting multi-source domain fallbacks and complete 10-missable trophy extraction for The Witcher 3**
- [ ] **Step 2: Implement multi-source parser and roadmap extractor in `scraper.py`**
- [ ] **Step 3: Run pytest in `services/ingest` to verify all tests pass**
- [ ] **Step 4: Commit**

---

### Task 2: Database Catalog Synchronization for All Games

**Files:**
- Create: `infra/postgres/08_complete_catalog_missables.sql`
- Test: `services/ingest/tests/test_player.py`

**Interfaces:**
- Updates `player_trophies` across all games:
  - *The Witcher 3: Wild Hunt*: 10 missable trophies (`Assassin of Kings`, `Card Collector`, `Even Odds`, `Fast and Furious`, `Friends With Benefits`, `Full Crew`, `Gwent Master`, `Kingmaker`, `The Doppler Effect`, `Woodland Spirit`).
  - *Grand Theft Auto V*: All missable trophies (`Kifflom!`, `Red Mist`, `Show Off`, `San Andreas Sightseer`, `Three Man Army`, `A Lot of Cheddar`).
  - *Bloodborne*: Missable questlines (`Hunter's Essence`, `Childhood's Beginning`, `Yharnam Sunrise`, `Honoring Wishes`).
  - *Elden Ring*: Missable legendary armaments and endings (`Legendary Armaments`, `Age of the Stars`, `Lord of Frenzied Flame`).

- [ ] **Step 1: Write integration tests in `test_player.py` asserting all 10 missables for Witcher 3 and canonical missables for GTA V, Bloodborne, and Elden Ring**
- [ ] **Step 2: Create `08_complete_catalog_missables.sql` and apply to PostgreSQL database**
- [ ] **Step 3: Run pytest to verify all tests pass**
- [ ] **Step 4: Commit**

---

### Task 3: Ingestion of Complete Canonical Roadmaps into Vector Database

**Files:**
- Modify: `services/ingest/src/routes/ingest.py`
- Test: `services/ingest/tests/test_rag_benchmark.py`

- [ ] **Step 1: Trigger full re-indexing for The Witcher 3, GTA V, Bloodborne, and Elden Ring via `POST /api/v1/ingest/fetch-and-index` with `force_reindex=True`**
- [ ] **Step 2: Verify in database that all 10 missables and complete Gwent card locations exist in `guide_chunks`**
- [ ] **Step 3: Run `test_rag_benchmark.py` in pytest asserting 100% recall**
- [ ] **Step 4: Commit**

---

### Task 4: Node.js Agent Deep Walkthrough Verification & Documentation

**Files:**
- Modify: `docs/interview-prep.md`
- Modify: `docs/learning-log.md`
- Test: `apps/api/src/services/agent/runner.benchmark.test.ts`

- [ ] **Step 1: Write benchmark test in Vitest asserting that asking about missable trophies in The Witcher 3 returns all 10 canonical missables**
- [ ] **Step 2: Add Question Q60 in `docs/interview-prep.md` explaining Multi-Source Ingestion Resilience and Anti-Scraping Defense**
- [ ] **Step 3: Update `docs/learning-log.md`**
- [ ] **Step 4: Run full Vitest suite (`npm test`) and commit**
