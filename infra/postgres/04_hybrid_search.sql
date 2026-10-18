-- Migration 04: Full-Text Search tsvector and GIN index for true Hybrid Search (Dense + Sparse)
ALTER TABLE guide_chunks ADD COLUMN IF NOT EXISTS tsv tsvector 
GENERATED ALWAYS AS (
  to_tsvector('portuguese', coalesce(title, '') || ' ' || coalesce(content, ''))
) STORED;

CREATE INDEX IF NOT EXISTS idx_guide_chunks_tsv_gin ON guide_chunks USING gin(tsv);
