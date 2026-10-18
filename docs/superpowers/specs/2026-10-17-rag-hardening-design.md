# Design Document: RAG Hardening, Compact Generation, and Verification Engine

**Date:** 2026-10-17  
**Status:** Draft (Pending User Approval)  
**Authors:** Weine Oliveira, Claude  

---

## 1. Intent & Problem Statement
Users playing games like *Bloodborne*, *Elden Ring*, and *GTA V* want fast, trustworthy guidance during gameplay. Currently, the agent can generate verbose responses that feel speculative or hallucinated, and retrieval relies solely on cosine distance without lexical matching or similarity cutoffs.

This design hardens the end-to-end RAG and generation pipeline so that:
1. Answers are **concise, tactical, and progressive** (short answer by default; deep walkthrough only upon follow-up request).
2. Retrieval uses **hybrid search** (dense pgvector + full-text BM25/tsvector) with strict **similarity score thresholds**.
3. A **reranker and citation-grounding validator** prevents the model from stating facts not backed by retrieved chunks.
4. An automated **evals suite** measures retrieval recall and answer faithfulness.

---

## 2. Goals & Anti-Goals

### Goals
- **Concise Default Answers:** Standard responses must be 2 to 4 bullet points max, under 120 words, with a clear prompt: *"Want step-by-step details for this trophy?"*.
- **Hybrid Retrieval:** Combine pgvector cosine distance (`<=>`) with PostgreSQL full-text search (`tsvector` / `tsquery`) via Reciprocal Rank Fusion (RRF) or weighted scoring.
- **Minimum Similarity Threshold:** If the highest chunk score is below `0.65`, return an honest *"Official guide not found"* message instead of allowing hallucinated advice.
- **Top-K Reranking:** Fetch top-15 candidate chunks from hybrid retrieval and rerank down to the top-3 most relevant chunks before prompt injection.
- **Strict Grounding & Citation:** The model must reference chunk IDs, and a lightweight verification pass verifies claims against retrieved chunks.
- **Automated Evals:** A dedicated evaluation script in Python measuring Context Recall and Faithfulness.

### Anti-Goals
- We will **not** build production thumbs-up/down UI feedback in this phase (explicitly postponed by user request).
- We will **not** add heavy external paid services (e.g., Cohere Rerank API); reranking and embeddings must run cost-free locally or via existing open infrastructure.

---

## 3. Architecture & Technical Decisions

### A. Storage & Retrieval (Python / `services/ingest`)
1. **Schema Update:** `guide_chunks` table includes a generated `tsv` column (`to_tsvector('portuguese', coalesce(title, '') || ' ' || coalesce(content, ''))`) with a GIN index.
2. **Hybrid Search Pipeline (`src/services/search.py`):**
   - Query executes dense cosine distance and sparse `tsvector @@ plainto_tsquery`.
   - Results are fused using RRF (Reciprocal Rank Fusion): $\text{Score} = \frac{1}{60 + \text{rank}_{\text{dense}}} + \frac{1}{60 + \text{rank}_{\text{sparse}}}$.
   - Chunks below the minimum similarity threshold (`0.65` normalized) are dropped.
3. **Cross-Encoder Reranker (`src/services/reranker.py`):**
   - A lightweight scoring step evaluates query-chunk text pairs to select the top 3 chunks for context injection.

### B. Generation & Progressive Disclosure (Node.js / `apps/api`)
1. **Concise Prompt Persona (`src/services/agent/runner.ts`):**
   - Prompt updated with strict brevity rules:
     - 1 line: Target trophy + location.
     - 2-3 lines: The immediate tactical action to not miss it.
     - 1 line: Call to action offering full walkthrough.
2. **Post-Generation Grounding Validator & Pre-Flight Check (`src/services/agent/validator.ts`):**
   - **Behavior (Option B - Enforced):** The agent buffers the generated text before rendering to the client, performs claim extraction, and cross-references against retrieved guide chunk sources.
   - If ungrounded or speculative assertions are detected, the validator triggers an internal corrective re-prompt to strip unverified claims, guaranteeing only 100% grounded facts reach the user.

### C. Technical Clarifications Resolved
- **Reranker Engine:** Heuristic token-overlap and BM25-score cross-scorer in Python, zero heavy CUDA/PyTorch dependencies.
- **Cutoff Metric:** Normalized similarity $\ge 0.65$ across fused results; sub-threshold queries return an explicit *"Official guide not found"* response without LLM guesswork.
- **Eval Decoupling:** Python measures Recall@3 and RRF precision in pytest; Node.js measures Faithfulness and schema validation in Vitest.

### C. Automated Evaluations (`services/ingest/tests/test_rag_metrics.py`)
1. Golden dataset of 10 test queries covering trophy names, boss names, and missable triggers.
2. Evaluates:
   - **Retrieval Recall@3**: Did the correct chunk land in top 3?
   - **Answer Faithfulness**: Are the claims supported by the context without external hallucinations?

---

## 4. What is Left to the Builder
- Selection between pure SQL RRF vs. in-memory scoring in Python.
- Exact regex parser for claim extraction in the lightweight validator.
