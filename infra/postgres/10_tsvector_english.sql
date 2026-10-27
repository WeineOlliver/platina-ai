-- Migration 10: Switch tsvector generated column from portuguese to english for internal English processing
ALTER TABLE guide_chunks DROP COLUMN IF EXISTS tsv;

ALTER TABLE guide_chunks ADD COLUMN tsv tsvector
GENERATED ALWAYS AS (
  to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content, ''))
) STORED;

CREATE INDEX IF NOT EXISTS idx_guide_chunks_tsv_gin ON guide_chunks USING gin(tsv);
