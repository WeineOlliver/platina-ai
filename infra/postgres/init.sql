-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Table to store indexed trophy guide chunks
CREATE TABLE IF NOT EXISTS guide_chunks (
    id VARCHAR(64) PRIMARY KEY,
    game VARCHAR(100) NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    is_missable BOOLEAN DEFAULT FALSE,
    source_url VARCHAR(500),
    metadata JSONB DEFAULT '{}'::jsonb,
    context_prefix VARCHAR(255) DEFAULT '',
    -- 384 dimensions matches FastEmbed BAAI/bge-small-en-v1.5
    embedding vector(384),
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(context_prefix, '') || ' ' || coalesce(title, '') || ' ' || coalesce(content, ''))) STORED,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Fast exact filtering indexes
CREATE INDEX IF NOT EXISTS idx_guide_chunks_game ON guide_chunks(game);
CREATE INDEX IF NOT EXISTS idx_guide_chunks_is_missable ON guide_chunks(is_missable);
CREATE INDEX IF NOT EXISTS idx_guide_chunks_tsv_gin ON guide_chunks USING gin (tsv);

-- HNSW (Hierarchical Navigable Small World) index for fast approximate nearest neighbor (ANN) vector search.
-- Insight: HNSW offers higher query throughput and better recall than IVFFlat without requiring a training step.
CREATE INDEX IF NOT EXISTS idx_guide_chunks_embedding_hnsw 
ON guide_chunks 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Observability and Telemetry for RAG Pipeline Latencies and Quality Sampling
CREATE TABLE IF NOT EXISTS rag_metrics_telemetry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(64) NULL,
    game VARCHAR(120) NULL,
    model_name VARCHAR(100) NULL,
    retrieval_latency_ms DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    reranker_latency_ms DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    llm_latency_ms DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    total_latency_ms DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    sampled_for_quality BOOLEAN NOT NULL DEFAULT FALSE,
    faithfulness_score DOUBLE PRECISION NULL,
    context_relevance_score DOUBLE PRECISION NULL,
    answer_relevance_score DOUBLE PRECISION NULL,
    query_preview TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rag_metrics_telemetry_created_at 
ON rag_metrics_telemetry (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_rag_metrics_telemetry_sampled 
ON rag_metrics_telemetry (sampled_for_quality);
