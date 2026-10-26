import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import type { FastifyInstance } from 'fastify';

process.env.AI_PROVIDER = 'mock';

import { buildApp } from '../../app.js';
import { telemetryService } from '../../services/observability/telemetry.js';

describe('Observability Routes Suite - GET /api/v1/observability/metrics', () => {
  let app: FastifyInstance;

  beforeAll(async () => {
    app = await buildApp({ logger: false });
    await app.ready();
  });

  afterAll(async () => {
    await app.close();
  });

  beforeEach(() => {
    telemetryService.clear();
  });

  it('GET /api/v1/observability/metrics returns 200 with initial aggregated metrics schema', async () => {
    const response = await app.inject({
      method: 'GET',
      url: '/api/v1/observability/metrics',
    });

    expect(response.statusCode).toBe(200);
    const body = response.json();

    expect(body).toHaveProperty('total_queries', 0);
    expect(body).toHaveProperty('sampled_queries', 0);
    expect(body).toHaveProperty('sampling_rate');
    expect(typeof body.sampling_rate).toBe('number');

    expect(body).toHaveProperty('avg_retrieval_latency_ms', 0);
    expect(body).toHaveProperty('p95_retrieval_latency_ms', 0);
    expect(body).toHaveProperty('avg_reranker_latency_ms', 0);
    expect(body).toHaveProperty('p95_reranker_latency_ms', 0);
    expect(body).toHaveProperty('avg_llm_latency_ms', 0);
    expect(body).toHaveProperty('p95_llm_latency_ms', 0);
    expect(body).toHaveProperty('avg_total_latency_ms', 0);
    expect(body).toHaveProperty('p95_total_latency_ms', 0);

    expect(body).toHaveProperty('avg_faithfulness_score', null);
    expect(body).toHaveProperty('avg_context_relevance_score', null);
    expect(body).toHaveProperty('avg_answer_relevance_score', null);
    expect(body).toHaveProperty('recent_samples');
    expect(Array.isArray(body.recent_samples)).toBe(true);
    expect(body.recent_samples).toHaveLength(0);
  });

  it('GET /api/v1/observability/metrics returns calculated metrics after telemetry records are recorded', async () => {
    await telemetryService.recordMetric({
      sessionId: 'test-session-1',
      game: 'Bloodborne',
      modelName: 'llama-3.3-70b-versatile',
      retrievalLatencyMs: 40.5,
      rerankerLatencyMs: 15.2,
      llmLatencyMs: 120.0,
      totalLatencyMs: 175.7,
      sampledForQuality: true,
      faithfulnessScore: 0.95,
      contextRelevanceScore: 0.90,
      answerRelevanceScore: 0.92,
      queryPreview: 'Where is the Saw Cleaver?',
    });

    const response = await app.inject({
      method: 'GET',
      url: '/api/v1/observability/metrics',
    });

    expect(response.statusCode).toBe(200);
    const body = response.json();

    expect(body.total_queries).toBe(1);
    expect(body.sampled_queries).toBe(1);
    expect(body.avg_retrieval_latency_ms).toBe(40.5);
    expect(body.p95_retrieval_latency_ms).toBe(40.5);
    expect(body.avg_reranker_latency_ms).toBe(15.2);
    expect(body.p95_reranker_latency_ms).toBe(15.2);
    expect(body.avg_llm_latency_ms).toBe(120);
    expect(body.p95_llm_latency_ms).toBe(120);
    expect(body.avg_total_latency_ms).toBe(175.7);
    expect(body.p95_total_latency_ms).toBe(175.7);
    expect(body.avg_faithfulness_score).toBe(0.95);
    expect(body.avg_context_relevance_score).toBe(0.9);
    expect(body.avg_answer_relevance_score).toBe(0.92);
    expect(body.recent_samples).toHaveLength(1);
    expect(body.recent_samples[0].game).toBe('Bloodborne');
    expect(body.recent_samples[0].queryPreview).toBe('Where is the Saw Cleaver?');
  });
});
