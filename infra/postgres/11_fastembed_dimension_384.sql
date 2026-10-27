-- Migration 11: Switch guide_chunks embedding dimension to vector(384) for fastembed BAAI/bge-small-en-v1.5
-- Discard existing vectors (TRUNCATE) because previous 1536-dim embeddings are incompatible.

TRUNCATE TABLE guide_chunks;

-- Drop old HNSW index configured for 1536 dimensions
DROP INDEX IF EXISTS idx_guide_chunks_embedding_hnsw;

-- Alter column to 384 dimensions
ALTER TABLE guide_chunks ALTER COLUMN embedding TYPE vector(384);

-- Recreate HNSW vector index for 384 dimensions
CREATE INDEX IF NOT EXISTS idx_guide_chunks_embedding_hnsw
ON guide_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
