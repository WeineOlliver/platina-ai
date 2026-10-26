-- Migration 09: Observability and Telemetry for RAG Pipeline Latencies and Quality Sampling
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
