# 2. Chunking Strategy and Vector Embedding Architecture

Date: 2026-10-16

## Status
Accepted

## Context
In generative AI assistants for PlayStation trophy hunting, high-accuracy context retrieval is critical. Unlike generic document QA, a trophy guide carries strict domain semantics:
1. Requirements for a specific trophy must remain atomic. Splitting across arbitrary token lengths risks divorcing the trophy title from its prerequisite boss fights or missable warnings.
2. Narrative walkthrough sections can be lengthy, requiring chunking that preserves semantic continuity.
3. The system needs to support hybrid filtering (e.g., retrieving exclusively missable chunks for a target game).
4. The embedding pipeline must support both cost-free local testing and scalable production embeddings (1536 dimensions) without vendor lock-in.

## Decision
1. **Hierarchical Markdown Heading Chunking:**
   - Primary segmentation occurs on Markdown header boundaries (`#`, `##`, `###`), preserving individual trophy and chapter structures as atomic units.
   - For oversized sections exceeding 1,200 characters, we fall back to a sliding character window with 200-character overlap that respects paragraph (`\n\n`) and sentence (`. `) boundaries.

2. **Heuristic Metadata Enrichment:**
   - During chunking, an automated scanner searches for critical game-state keywords (*missable*, *perdível*, *ponto de não retorno*), populating an `is_missable: bool` metadata column.

3. **1536-Dimensional Vector Embeddings:**
   - We standardize on a 1536-dimension coordinate space compatible with standard vector models (OpenAI `text-embedding-3-small`, Ada-002, and high-performance dense projections).
   - All vectors are L2-normalized to unit length prior to storage, allowing cosine similarity queries to execute as optimized vector dot products.

4. **PostgreSQL + pgvector with HNSW Indexing:**
   - Storage is unified inside PostgreSQL 16 via `pgvector`.
   - Indexing uses HNSW (`vector_cosine_ops`, `m=16, ef_construction=64`) to achieve sub-second query latency and superior recall without requiring pre-training steps.

## Consequences
- **Positive:** Chunks preserve complete trophy instructions; hybrid search allows combining SQL `WHERE` clauses with cosine distance ordering; zero multi-database synchronization overhead.
- **Trade-offs:** HNSW indexes consume slightly more RAM than IVFFlat during initial construction, but eliminate recall degradation and re-clustering operational burdens.
