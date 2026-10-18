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
    -- 1536 dimensions matches OpenAI text-embedding-3-small, Ada-002, and standard vector models
    embedding vector(1536),
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('portuguese', coalesce(title, '') || ' ' || coalesce(content, ''))) STORED,
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
