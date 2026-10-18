# RAG Hardening, Compact Generation, and Pre-Flight Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement true hybrid search (BM25 + pgvector), strict similarity threshold cutoffs, a cross-encoder reranker, compact progressive agent responses, and pre-flight citation grounding verification.

**Architecture:** 
1. PostgreSQL generated `tsvector` with GIN indexing combined with pgvector cosine similarity via Reciprocal Rank Fusion (RRF) in Python (`services/ingest`).
2. Reranker filtering top candidates down to top-3 with a hard cutoff ($\ge 0.65$ normalized score).
3. Fastify agent runner (`apps/api`) enforcing concise output and pre-flight assertion verification before streaming verified text to the client.

**Tech Stack:** TypeScript, Fastify, Python 3.12, FastAPI, SQLAlchemy, PostgreSQL 16 (pgvector, tsvector), Groq SDK (openai/gpt-oss-120b), Vitest, Pytest.

**Spec:** `docs/superpowers/specs/2026-10-17-rag-hardening-design.md`

## Global Constraints
- Python services must remain lightweight (zero heavy CUDA/PyTorch dependencies).
- Minimum normalized similarity score of `0.65` required; queries failing this return an explicit *"Official guide not found"* response without LLM guesswork.
- Agent default responses must be concise (under 120 words, 2-4 bullet points) offering a deep walkthrough on follow-up.
- Pre-flight claim verification (Option B) buffers generated content, validates claims against chunk citations, and re-prompts if ungrounded claims appear.

## Review Focus
- Queries matching exact keywords but having poor semantic vector similarity (e.g., exact trophy code or rare weapon name) must be surfaced by BM25.
- Queries with zero related content in the database must cleanly abort at the threshold and not hallucinate instructions.
- Responses containing fabricated boss weaknesses or nonexistent NPC locations must be caught and corrected by the pre-flight grounding validator.
- Streaming SSE protocol must seamlessly deliver the verified text without protocol errors after pre-flight inspection.

---

### Task 1: Database Full-Text Search Schema & SQLAlchemy Model Update

**Files:**
- Modify: `infra/postgres/init.sql`
- Modify: `services/ingest/src/models/chunk.py`
- Test: `services/ingest/tests/test_hybrid_schema.py`

**Interfaces:**
- Produces: `GuideChunkModel.tsv` column mapped in SQLAlchemy and migration SQL.

- [ ] **Step 1: Write test asserting `tsv` column exists and executes full-text match**
- [ ] **Step 2: Run test to verify it passes against PostgreSQL container**
- [ ] **Step 3: Update `src/models/chunk.py` adding `tsv` column mapping**
- [ ] **Step 4: Commit**

---

### Task 2: Hybrid Search (Dense Cosine + Sparse BM25 via RRF) & Similarity Cutoff

**Files:**
- Modify: `services/ingest/src/services/search.py`
- Modify: `services/ingest/src/schemas/search.py`
- Test: `services/ingest/tests/test_search.py`

**Interfaces:**
- Consumes: `GuideChunkModel`, `embedding_service.embed_query`
- Produces: `vector_search_service.search(request)` returning chunks filtered by threshold $\ge 0.65$ with hybrid score.

- [ ] **Step 1: Write tests for keyword exact match, semantic match, and low-score cutoff filtering**
- [ ] **Step 2: Implement Reciprocal Rank Fusion (RRF) and similarity threshold in `search.py`**
- [ ] **Step 3: Run pytest to verify all test cases pass**
- [ ] **Step 4: Commit**

---

### Task 3: Lightweight Cross-Encoder Reranker Service

**Files:**
- Create: `services/ingest/src/services/reranker.py`
- Modify: `services/ingest/src/services/search.py`
- Test: `services/ingest/tests/test_reranker.py`

**Interfaces:**
- Produces: `reranker_service.rerank(query: str, candidates: list[SearchResultItem], top_k: int = 3) -> list[SearchResultItem]`

- [ ] **Step 1: Write unit test validating reranking of high-relevance chunks to top position**
- [ ] **Step 2: Implement lightweight cross-scorer in `reranker.py`**
- [ ] **Step 3: Hook reranker into `VectorSearchService.search()`**
- [ ] **Step 4: Run pytest to verify passes**
- [ ] **Step 5: Commit**

---

### Task 4: Concise Progressive Agent Prompt & Grounding Pre-Flight Validator

**Files:**
- Create: `apps/api/src/services/agent/validator.ts`
- Modify: `apps/api/src/services/agent/runner.ts`
- Test: `apps/api/src/services/agent/validator.test.ts`

**Interfaces:**
- Consumes: `chunk.content`, `chunk.id`, `assistantMsg.content`
- Produces: `groundingValidator.validate(response: string, sources: RetrievedChunk[]): Promise<{ isValid: boolean; ungroundedClaims: string[] }>`

- [ ] **Step 1: Write Vitest tests for claim verification and rejection of ungrounded hallucinations**
- [ ] **Step 2: Implement `groundingValidator` in `validator.ts`**
- [ ] **Step 3: Update `runner.ts` with concise prompt persona and pre-flight verification gate (Option B)**
- [ ] **Step 4: Run Vitest tests to verify passes**
- [ ] **Step 5: Commit**

---

### Task 5: End-to-End Evaluation Benchmark Suite (Recall@3 and Faithfulness)

**Files:**
- Create: `services/ingest/tests/test_rag_benchmark.py`
- Create: `apps/api/src/services/agent/runner.benchmark.test.ts`

- [ ] **Step 1: Implement 10-query benchmark dataset covering Bloodborne, Elden Ring, and GTA V**
- [ ] **Step 2: Assert Recall@3 in Pytest and Faithfulness assertion check in Vitest**
- [ ] **Step 3: Run test suites across both services**
- [ ] **Step 4: Commit and push to main**
