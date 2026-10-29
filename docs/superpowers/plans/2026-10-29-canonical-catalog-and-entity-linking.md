# Canonical Catalog & Entity Linking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform Platina AI from loose string matching into a canonical game & trophy catalog schema with entity-linked guide chunks, structured SQL tools (`list_trophies`, `get_trophy_guide`, `get_game_overview`), coverage-based abstention, and deterministic synthetic golden evaluation generation.

**Architecture:**
- Relational catalog in PostgreSQL (`games`, `trophies`) linked via foreign keys to `guide_chunks` (`game_id`, `trophy_id`) and `player_trophies` (`trophy_id`).
- Offline HTML catalog importer (`python -m src.catalog.import <game_id> <trophies_html> [guide_html]`) for PSNProfiles without triggering Cloudflare WAF.
- Entity linking at chunking time matching chunk titles against canonical trophy names and aliases.
- Specialized semantic Gwent card chunker preserving vendor/region boundaries and missable tags.
- Direct catalog retrieval tools in Fastify/TypeScript + FastAPI Python endpoints, bypassing vector search for exact trophy and list queries.
- Automated deterministic golden test case generator (`generate_cases.py`) with 70/30 dev/test split.

**Tech Stack:** Python 3.14 (FastAPI, SQLAlchemy, BeautifulSoup4, pgvector), TypeScript (Node 24, Fastify, Zod, Groq SDK), PostgreSQL 16.

**Spec:** Attached context in `.hermes/composer-pastes/pasted_content_2026-10-29_01-05-50-031_3a8942.txt`

## Global Constraints

- Separate git commits per phase: schema, importer, entity linking, gwent cards, tools, prompt and abstention, seeds, generator, eval.
- Diffs minimais, sem abstrações de uso único, com `// Insight:` (TS) ou comentário curto (Python).
- Internal processing strictly in English (tool calls, schemas, queries, catalog entities).
- No web scraping of protected Cloudflare endpoints during runtime; import strictly from saved local snapshots.
- No `git push` unless requested.

## Review Focus

1. `player_trophies` migration must fail gracefully and list unmapped trophies if any existing record cannot be matched.
2. Stopword queries like "What Was That?" (D10) must resolve directly through catalog lookup rather than vector search.
3. Coverage-based abstention: when querying unindexed DLCs (e.g. Blood and Wine in N01) where trophies exist in catalog but have 0 linked chunks, the agent must return the fixed catalog abstention message without freeform LLM advice.
4. Gwent card chunking must keep entire vendor/location tables/lists atomic without chopping mid-entry at 1200 chars.
5. Faithfulness and answer relevance judge metrics must strictly filter out abstained runs to prevent skewing quality averages.

---

### Task 1: Database Schema & SQLAlchemy Models

**Files:**
- Create: `infra/postgres/12_canonical_catalog.sql`
- Create: `services/ingest/src/models/catalog.py`
- Modify: `services/ingest/src/models/chunk.py`
- Modify: `services/ingest/src/models/player.py`
- Test: `services/ingest/tests/test_catalog_schema.py`

**Interfaces:**
- Produces: `GameModel`, `TrophyModel`, `GuideChunkModel.game_id`, `GuideChunkModel.trophy_id`, `PlayerTrophyModel.trophy_id`.

- [ ] **Step 1: Write test for catalog schema and models**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement SQL migration `infra/postgres/12_canonical_catalog.sql` and SQLAlchemy models**
  - Create `games`: `id` PK (slug), `title`, `np_communication_id`, `aliases` text[], `difficulty` numeric, `hours` int, `playthroughs` int, `metadata_source` text.
  - Create `trophies`: `id` PK, `game_id` FK, `psn_trophy_id` int, `name`, `type`, `description`, `dlc` (null = base), `location`, `missable` bool, `missable_sources` text[], `aliases` text[], `UNIQUE(game_id, name)`.
  - Add `game_id` FK and `trophy_id` FK to `guide_chunks`.
  - Add `trophy_id` FK to `player_trophies`.
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit `feat(schema): add canonical games and trophies catalog tables with guide and player foreign keys`**

---

### Task 2: Catalog Importer (Official PSNProfiles HTML Snapshots)

**Files:**
- Create: `services/ingest/src/catalog/importer.py`
- Create: `services/ingest/src/catalog/import.py` (CLI entrypoint `python -m src.catalog.import`)
- Test: `services/ingest/tests/catalog/test_importer.py`

**Interfaces:**
- Consumes: `trophies_html` (PSNProfiles list), `guide_html` (PSNProfiles guide)
- Produces: Idempotent upsert into `games` and `trophies`.

- [ ] **Step 1: Write test with synthetic HTML fixtures for trophy list, DLC grouping, and missable roadmap parsing**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement `import_catalog(game_id, trophies_html_path, guide_html_path=None)`**
  - Parse Base Game, Hearts of Stone, Blood and Wine from trophy list.
  - Parse difficulty, hours, playthroughs, and MISSABLE tags from guide.
  - Upsert into `games` and `trophies`.
  - Log how many trophies were left without location.
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Execute import on real snapshots for `the-witcher-3-wild-hunt`**
- [ ] **Step 6: Commit `feat(catalog): add idempotent HTML catalog importer for games and trophies`**

---

### Task 3: Entity Linking on Guide Ingestion

**Files:**
- Create: `services/ingest/src/services/entity_linker.py`
- Modify: `services/ingest/src/services/chunker.py`
- Modify: `services/ingest/src/routes/ingest.py`
- Modify: `services/ingest/tests/eval/run_golden.py`
- Test: `services/ingest/tests/test_entity_linking.py`

**Interfaces:**
- Consumes: chunk title, `game_id`, database `trophies` table.
- Produces: `chunk.trophy_id`, updated hierarchical context prefix using canonical `trophy.dlc`.

- [ ] **Step 1: Write unit tests for entity linking (normalization, Part suffix removal, alias matching)**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement `link_chunk_to_trophy(title, game_id, session)`**
  - Match normalized title with `trophies.name` or `trophies.aliases`.
  - Assign `trophy_id` and canonical `dlc` to context prefix.
  - Print summary: count linked, count unlinked, and unlinked titles list.
  - Index `psnprofiles_guide_witcher3.html` alongside PowerPyx.
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit `feat(ingest): add entity linking between guide chunks and canonical trophies`**

---

### Task 4: Gwent Cards Guide Chunking & Indexing

**Files:**
- Create: `services/ingest/src/services/gwent_chunker.py`
- Modify: `services/ingest/src/routes/ingest.py`
- Modify: `services/ingest/tests/eval/run_golden.py`
- Modify: `golden_witcher3.json`
- Modify: `services/ingest/tests/golden/golden_witcher3.json`
- Test: `services/ingest/tests/test_gwent_chunker.py`

**Interfaces:**
- Consumes: `gwent_cards_witcher3.html`
- Produces: Atomic chunks per region / vendor, all linked to "Card Collector" (`trophy_id`), with context prefix `"The Witcher 3: Wild Hunt › Base Game › Card Collector › <region/group>"`.
- Produces: 3 manual golden test cases (`verified: false`).

- [ ] **Step 1: Write test verifying Gwent chunker structure, atomic lines, and missable preservation**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement `chunk_gwent_guide(html_content, game_id, card_collector_trophy_id)`**
  - Parse regions (White Orchard, Vizima, Velen, Novigrad, Skellige, High Stakes).
  - Break by vendor/NPC and roadmap steps without cutting lists.
  - Preserve `(MISSABLE!)` tags.
  - Add 3 test cases to `golden_witcher3.json` (`verified: false`).
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit `feat(ingest): add structured Gwent card chunker and 3 unverified golden test scenarios`**

---

### Task 5: Catalog Query Tools & Coverage-Based Abstention

**Files:**
- Create: `services/ingest/src/routes/catalog.py`
- Modify: `services/ingest/src/main.py`
- Modify: `services/ingest/src/services/search.py` (filter by exact `game_id`)
- Create: `apps/api/src/services/agent/tools/getTrophyGuide.ts`
- Create: `apps/api/src/services/agent/tools/listTrophies.ts`
- Create: `apps/api/src/services/agent/tools/getGameOverview.ts`
- Modify: `apps/api/src/services/agent/tools/playerProgress.ts`
- Modify: `apps/api/src/services/agent/runner.ts` (system prompt, coverage abstention, tool choice)
- Test: `apps/api/src/services/agent/tools/catalogTools.test.ts`
- Test: `services/ingest/tests/test_catalog_routes.py`

**Interfaces:**
- `get_trophy_guide(game, trophy)` -> Trophy metadata + ordered chunks (no vector search).
- `list_trophies(game, filters)` -> SQL filtered list of trophies.
- `get_game_overview(game)` -> difficulty, hours, playthroughs, type/DLC counts.

- [ ] **Step 1: Write tests for catalog endpoints and agent tools (exact trophy, fuzzy, DLC without guide, stopword D10, unindexed game)**
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement Python catalog routes and TypeScript tools**
  - Implement `/api/v1/catalog/...` in ingest service.
  - Implement tools in `apps/api/src/services/agent/tools/`.
  - Update agent system prompt: lists/counts via `list_trophies`, specific trophy lookup via `get_trophy_guide`, overview via `get_game_overview`.
  - Implement coverage abstention: if a DLC has trophies in catalog but 0 linked chunks, return fixed catalog abstention.
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit `feat(agent): add catalog query tools, coverage-based abstention, and update system prompt`**

---

### Task 6: Seed Migration for Player Trophies

**Files:**
- Create: `infra/postgres/13_seed_witcher_canonical.sql`
- Modify: `services/ingest/tests/test_player.py`
- Modify: `services/ingest/tests/test_player_categories.py`
- Test: `services/ingest/tests/test_player_canonical_seed.py`

**Interfaces:**
- Produces: Clean player seed referencing canonical `trophy_id` for `the-witcher-3-wild-hunt` with 0 earned trophies.

- [ ] **Step 1: Verify existing tests and build canonical seed referencing `trophies.id`**
- [ ] **Step 2: Run test verifying player progress reflects canonical catalog**
- [ ] **Step 3: Commit `feat(seeds): replace manual Witcher 3 seeds with canonical catalog trophy references`**

---

### Task 7: Synthetic Golden Set Generator

**Files:**
- Create: `services/ingest/tests/golden/generate_cases.py`
- Modify: `services/ingest/tests/eval/run_golden.py`
- Test: `services/ingest/tests/golden/test_generate_cases.py`

**Interfaces:**
- Command: `python -m tests.golden.generate_cases <game_id>`
- Produces: `services/ingest/tests/golden/generated_the-witcher-3-wild-hunt.json` with deterministic 70/30 dev/test split.
- `run_golden.py` flags: `--split dev|test|all`.

- [ ] **Step 1: Write test for deterministic case generation and 70/30 split**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement `generate_cases.py` and `--split` flag in `run_golden.py`**
  - Generate SQL list cases and RAG tip cases with distinctive `must_contain` tokens.
  - Report manual vs generated in distinct rows in evaluation tables.
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit `feat(eval): add automated golden case generator with deterministic dev-test split`**

---

### Task 8: Evaluation, Judge Recalculation & Final Report

**Files:**
- Modify: `services/ingest/tests/eval/run_golden.py`
- Modify: `docs/golden_eval_report_english_architecture.md`

**Interfaces:**
- Recalculate judge metrics excluding abstentions.
- Run complete golden eval on dev set with FastEmbed.

- [ ] **Step 1: Update metric aggregation in `run_golden.py` to exclude abstained runs from faithfulness/answer_relevance**
- [ ] **Step 2: Reindex all guides (PowerPyx + PSNProfiles + Gwent cards), generate cases, and execute `run_golden.py --split dev`**
- [ ] **Step 3: Compile delivery details in `docs/golden_eval_report_english_architecture.md`**
- [ ] **Step 4: Commit `docs(eval): update consolidated golden evaluation report with canonical catalog benchmarks`**
