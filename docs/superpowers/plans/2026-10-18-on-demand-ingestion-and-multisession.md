# On-Demand Guide Ingestion & Multi-Session Chat UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement real web scraping ingestion for unindexed game guides in the Python service and multi-session tabbed chat in the frontend UI, with real-time SSE progress indicators.

**Architecture:** 
1. `services/ingest`: Add `TrophyGuideScraper` using `httpx` and `BeautifulSoup4` to scrape PowerPyx/PSNProfiles guide roadmaps, parse headings, and index into `guide_chunks` via `POST /api/v1/ingest/fetch-and-index`.
2. `apps/api`: Add `fetchAndIndex(game)` to `IngestionClient`, hook auto-ingestion into `PlatinaAgentRunner` when queries return 0 chunks, emitting SSE event `{ type: "thought", content: "📥 Jogo inédito detectado: indexando guia..." }`.
3. `test-chat.html`: Implement persistent tabbed multi-session architecture in `localStorage` with `[+ Nova Platina]` button, isolating chat histories, game titles, and tool logs across games.

**Tech Stack:** Python 3.12, FastAPI, httpx, beautifulsoup4, TypeScript, Fastify, Vitest, Pytest.

**Spec:** `docs/superpowers/specs/2026-10-18-on-demand-ingestion-and-multisession-design.md`

## Global Constraints
- Scraper must use standard headers and fall back gracefully if HTML parsing fails.
- Ingestion must populate `tsv` full-text search and embeddings atomically.
- SSE stream must remain active while ingestion runs by yielding `thought` frames.
- Multi-session UI must isolate `chatHistory` per tab to prevent cross-game context pollution.

---

### Task 1: Web Scraper Service & On-Demand Ingestion Endpoint in Python

**Files:**
- Create: `services/ingest/src/services/scraper.py`
- Modify: `services/ingest/src/routes/ingest.py`
- Test: `services/ingest/tests/test_scraper.py`

**Interfaces:**
- Produces: `POST /api/v1/ingest/fetch-and-index` returning `{"status": "indexed", "game": str, "chunks_indexed": int}`.

- [ ] **Step 1: Write test in `test_scraper.py` mocking guide scraping and indexing**
- [ ] **Step 2: Add `beautifulsoup4` and implement `TrophyGuideScraper` in `services/ingest/src/services/scraper.py`**
- [ ] **Step 3: Implement route `POST /api/v1/ingest/fetch-and-index` in `services/ingest/src/routes/ingest.py`**
- [ ] **Step 4: Run `uv run pytest tests/test_scraper.py -vv`**
- [ ] **Step 5: Commit**

---

### Task 2: Node.js Ingestion Client & Agent Auto-Ingestion Hook

**Files:**
- Modify: `apps/api/src/services/ingestion/client.ts`
- Modify: `apps/api/src/services/agent/runner.ts`
- Test: `apps/api/src/services/agent/tools/searchGuides.test.ts`

**Interfaces:**
- Consumes: `POST /api/v1/ingest/fetch-and-index`
- Produces: Dynamic guide auto-indexing and SSE `thought` notification during agent run.

- [ ] **Step 1: Add `fetchAndIndex(game: string)` to `IngestionClient`**
- [ ] **Step 2: Update `runner.ts` to trigger `fetchAndIndex` and emit `thought` SSE event when search yields 0 chunks for a valid game**
- [ ] **Step 3: Run Vitest tests to verify passes**
- [ ] **Step 4: Commit**

---

### Task 3: Multi-Session Tabbed Chat Interface in Frontend

**Files:**
- Modify: `test-chat.html`

**Interfaces:**
- Consumes: `localStorage` multi-session schema
- Produces: Independent chat tabs (`GTA V`, `The Witcher 3`) with `[+ Nova Platina]`, tab switching, and per-tab history isolation.

- [ ] **Step 1: Implement tab bar UI and session management functions (`createNewSession`, `switchSession`, `deleteSession`) in `test-chat.html`**
- [ ] **Step 2: Bind dynamic active game title and isolate `chatHistory` strictly to the current session**
- [ ] **Step 3: Handle `thought` SSE events in UI with subtle animated progress indicators**
- [ ] **Step 4: Verify in local browser and commit**

---

### Task 4: End-to-End Verification, Seed Expansion & Documentation

**Files:**
- Modify: `docs/interview-prep.md`
- Modify: `docs/learning-log.md`

- [ ] **Step 1: Test on-demand ingestion for The Witcher 3 in end-to-end integration test**
- [ ] **Step 2: Add Question Q58 in `docs/interview-prep.md` explaining On-Demand Ingestion vs Batch Pipelines**
- [ ] **Step 3: Update `docs/learning-log.md`**
- [ ] **Step 4: Commit and push to main**
