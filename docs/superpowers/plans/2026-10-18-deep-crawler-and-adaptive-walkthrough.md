# Recursive Subpage Crawling & Adaptive Deep Walkthrough Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement recursive subpage discovery and crawling (e.g. Gwent cards, collectible tables, missable quests) in the Python scraper and adaptive walkthrough mode ($\ge 75\%$ grounding coverage, up to 800 words) in the Node.js agent runner.

**Architecture:** 
1. `services/ingest`: Extend `TrophyGuideScraper` to parse links to all canonical subpages (collectibles, weapons, quests, gwent), fetch their content in parallel, chunk them semantically with subpage titles, and index with `force_reindex=True` support.
2. `apps/api`: Update `SearchGuidesTool` schema (`limit` up to 10), update `PlatinaAgentRunner` to recognize deep walkthrough intents across turns, and extend `GroundingValidator` with a $\ge 75\%$ claim coverage policy for long answers.

**Tech Stack:** Python 3.12, BeautifulSoup4, httpx, TypeScript, Fastify, Vitest, Pytest.

**Spec:** `docs/superpowers/specs/2026-10-18-deep-crawler-and-adaptive-walkthrough-design.md`

## Global Constraints
- Scraper subpage traversal capped at 15 direct subpages per game.
- Ingestion must update `guide_chunks` with granular chunk titles (e.g. `[Game] - Gwent Card Locations: Velen & Novigrad`).
- Grounding validator must apply $\ge 75\%$ coverage policy for answers $> 150$ words while keeping strict validation on short briefs.
- Deep walkthrough mode must support up to 800 words and top-10 chunk retrieval.

---

### Task 1: Recursive Subpage Scraper & Batch Ingestion in Python

**Files:**
- Modify: `services/ingest/src/services/scraper.py`
- Modify: `services/ingest/src/routes/ingest.py`
- Test: `services/ingest/tests/test_scraper.py`

**Interfaces:**
- Produces: `TrophyGuideScraper.fetch_game_guide_with_subpages(game, source_url, max_subpages=15) -> list[tuple[str, str, str]]` (returns `[(title, markdown, url)]`).
- Produces: `POST /api/v1/ingest/fetch-and-index` accepting `force_reindex: bool = False`.

- [ ] **Step 1: Write tests in `test_scraper.py` asserting subpage discovery and recursive parsing**
- [ ] **Step 2: Implement `discover_subpages` and parallel subpage fetching in `scraper.py`**
- [ ] **Step 3: Update `fetch-and-index` route to chunk and index all discovered subpages into PostgreSQL with `force_reindex` support**
- [ ] **Step 4: Re-index The Witcher 3 with exhaustive subpages (including Gwent card locations)**
- [ ] **Step 5: Run `uv run pytest tests/test_scraper.py -vv` and commit**

---

### Task 2: Grounding Validator Coverage Policy & Adaptive Walkthrough Prompt in Node.js

**Files:**
- Modify: `apps/api/src/services/agent/tools/searchGuides.ts`
- Modify: `apps/api/src/services/agent/validator.ts`
- Modify: `apps/api/src/services/agent/runner.ts`
- Test: `apps/api/src/services/agent/validator.test.ts`
- Test: `apps/api/src/services/agent/runner.benchmark.test.ts`

**Interfaces:**
- Consumes: `guide_chunks` subpage text
- Produces: Multi-step detailed walkthroughs up to 800 words when requested, validated with $\ge 75\%$ claim coverage.

- [ ] **Step 1: Update `SearchGuidesTool` schema allowing `limit: z.number().min(1).max(10).default(3)`**
- [ ] **Step 2: Update `GroundingValidator.validate` with $\ge 75\%$ claim coverage policy for long answers**
- [ ] **Step 3: Update `runner.ts` to detect deep walkthrough requests (explicit keywords + affirmative follow-ups to CTA) and instruct exhaustive structured answers up to 800 words with top-8 retrieval**
- [ ] **Step 4: Write benchmark tests in `runner.benchmark.test.ts` verifying detailed walkthrough generation**
- [ ] **Step 5: Run `npm test` and `npm run build`**
- [ ] **Step 6: Commit**

---

### Task 3: End-to-End Verification & Documentation Update

**Files:**
- Modify: `docs/interview-prep.md`
- Modify: `docs/learning-log.md`

- [ ] **Step 1: Verify end-to-end Gwent query returning the exhaustive multi-step card guide**
- [ ] **Step 2: Add Question Q59 in `docs/interview-prep.md` on Adaptive Verbosity & Claim-Coverage Grounding**
- [ ] **Step 3: Update `docs/learning-log.md`**
- [ ] **Step 4: Commit and push to main**
