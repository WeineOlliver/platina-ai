# Tactical Trophy Route Planner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a deterministic, telemetry-driven tactical trophy route planner that structures unearned trophies into `quick_cleanup`, `heavy_grind`, `natural_grind`, and `missable` categories, guiding players through adaptive routes (Fast Clearance vs Heavy Grind First) under 120 words.

**Architecture:** 
1. Database schema & ORM extension (`infra/postgres` + `services/ingest`): Add `trophy_category` column to `player_trophies` and update `PlayerProgressService` to group unearned trophies into structured buckets.
2. Fastify ReAct agent prompt & grounding integration (`apps/api`): Enable adaptive routing logic in `runner.ts`, feeding pre-grouped telemetry buckets directly into the grounding verification gate so route prompts never trip the similarity cutoff or hallucinate.

**Tech Stack:** TypeScript, Fastify, Python 3.12, FastAPI, SQLAlchemy, PostgreSQL 16, Vitest, Pytest.

**Spec:** `docs/superpowers/specs/2026-10-18-tactical-route-planner-design.md`

## Global Constraints
- Database schema migration must retain backwards compatibility (default `trophy_category = 'standard'`).
- `GET /api/v1/players/{psn_id}/progress` must output `quick_cleanup_trophies`, `heavy_grind_trophies`, `natural_grind_trophies`, and `pending_missables`.
- Agent routing advice must adhere strictly to the concise limit ($\le 120$ words) presenting Route A (Fast Clearance) and Route B (Heavy Grind First) with a follow-up CTA.
- No raw routing conversational strings (*"qual a melhor rota"*) are sent directly to vector retrieval; telemetry buckets provide the grounding facts.

## Review Focus
- Players with unfinished campaigns must be warned about `missable` trophies before any cleanup advice.
- Players with campaigns finished must see Route A (Fast Clearance) and Route B (Heavy Grind First) derived deterministically from the database categories.
- Requests with no PSN ID must ask for the ID while offering a brief 3-step high-level game roadmap without failing or raising ungrounded errors.
- Pre-flight grounding validator must pass structured telemetry without triggering false-positive halluncination rejections.

---

### Task 1: Database Schema & SQLAlchemy Model Extension for Trophy Categories

**Files:**
- Create: `infra/postgres/05_trophy_categories.sql`
- Modify: `infra/postgres/init.sql`
- Modify: `services/ingest/src/models/player.py`
- Test: `services/ingest/tests/test_player_categories.py`

**Interfaces:**
- Produces: `PlayerTrophyModel.trophy_category` column (`VARCHAR(32)`).

- [ ] **Step 1: Write failing test verifying `trophy_category` exists on `PlayerTrophyModel`**
- [ ] **Step 2: Create migration `05_trophy_categories.sql` and apply to database container**
- [ ] **Step 3: Update `services/ingest/src/models/player.py` mapping `trophy_category`**
- [ ] **Step 4: Run pytest to verify passes**
- [ ] **Step 5: Commit**

---

### Task 2: Structured Progress Telemetry Bucketing in Python Service

**Files:**
- Modify: `services/ingest/src/schemas/player.py`
- Modify: `services/ingest/src/services/player.py`
- Test: `services/ingest/tests/test_player.py`

**Interfaces:**
- Consumes: `PlayerTrophyModel`
- Produces: `PlayerProgressResponse` with `quick_cleanup_trophies`, `heavy_grind_trophies`, `natural_grind_trophies` arrays.

- [ ] **Step 1: Write tests in `test_player.py` expecting categorized buckets**
- [ ] **Step 2: Update `PlayerProgressResponse` schema with new bucket fields**
- [ ] **Step 3: Update `PlayerProgressService.get_progress` to bucket unearned trophies**
- [ ] **Step 4: Seed test data for GTA V (`05_seed_gta_categories.sql`) categorizing Director Mode as `quick_cleanup` and Doomsday/Heists as `heavy_grind`**
- [ ] **Step 5: Run pytest across `services/ingest` and commit**

---

### Task 3: Node.js Tool Client & Grounding Validator Integration

**Files:**
- Modify: `apps/api/src/services/agent/tools/playerProgress.ts`
- Modify: `apps/api/src/services/agent/runner.ts`
- Test: `apps/api/src/services/agent/tools/playerProgress.test.ts`

**Interfaces:**
- Consumes: `GET /api/v1/players/{psn_id}/progress`
- Produces: `PlayerProgressResult` containing categorized buckets in `runner.ts` context.

- [ ] **Step 1: Update `PlayerProgressResult` type in `playerProgress.ts`**
- [ ] **Step 2: Update `collectedGuideSources` in `runner.ts` to format structured buckets into grounding context**
- [ ] **Step 3: Run Vitest `playerProgress.test.ts` to verify integration**
- [ ] **Step 4: Commit**

---

### Task 4: Adaptive Routing Persona Prompt & Route Dual-Option Logic

**Files:**
- Modify: `apps/api/src/services/agent/runner.ts`
- Test: `apps/api/src/services/agent/runner.benchmark.test.ts`

**Interfaces:**
- Consumes: Categorized player telemetry
- Produces: Concise dual-route suggestion (Route A vs Route B) when campaign is finished.

- [ ] **Step 1: Add benchmark test in `runner.benchmark.test.ts` asserting Route A & Route B presentation for GTA V 71% progress**
- [ ] **Step 2: Update agent system prompt in `runner.ts` to instruct dual-route presentation (Fast Clearance vs Heavy Grind First) when campaign is complete**
- [ ] **Step 3: Run Vitest benchmark tests and assert word count $\le 120$ words and 0 grounding errors**
- [ ] **Step 4: Commit**

---

### Task 5: End-to-End Verification & Documentation Update

**Files:**
- Modify: `docs/interview-prep.md`
- Modify: `docs/learning-log.md`
- Test: Full Vitest and Pytest test runs

- [ ] **Step 1: Run full automated test suite across `services/ingest` and `apps/api`**
- [ ] **Step 2: Document Question Q56 in `docs/interview-prep.md` on deterministic telemetry categorization vs LLM routing**
- [ ] **Step 3: Update `docs/learning-log.md`**
- [ ] **Step 4: Commit and push to main**
