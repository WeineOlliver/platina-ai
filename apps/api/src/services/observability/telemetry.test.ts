import { describe, it, expect, beforeEach, vi } from 'vitest';
import { TelemetryService, type RagTelemetryRecord } from './telemetry.js';
import { IngestionClient } from '../ingestion/client.js';

describe('TelemetryService Suite', () => {
  let telemetry: TelemetryService;

  beforeEach(() => {
    telemetry = new TelemetryService({ samplingRate: 0.1 });
  });

  describe('recordMetric', () => {
    it('records a telemetry metric with generated id and timestamp if missing', async () => {
      const record = await telemetry.recordMetric({
        retrievalLatencyMs: 120,
        rerankerLatencyMs: 45,
        llmLatencyMs: 800,
        totalLatencyMs: 965,
        sampledForQuality: false,
        queryPreview: 'Where is the moonlight greatsword?',
        game: 'Elden Ring',
      });

      expect(record.id).toBeDefined();
      expect(typeof record.id).toBe('string');
      expect(record.createdAt).toBeDefined();
      expect(record.retrievalLatencyMs).toBe(120);
      expect(record.rerankerLatencyMs).toBe(45);
      expect(record.llmLatencyMs).toBe(800);
      expect(record.totalLatencyMs).toBe(965);
      expect(record.sampledForQuality).toBe(false);
      expect(record.game).toBe('Elden Ring');

      const all = telemetry.getRecords();
      expect(all).toHaveLength(1);
      expect(all[0].id).toBe(record.id);
    });

    it('preserves user-provided id and timestamp if supplied', async () => {
      const customId = 'custom-uuid-123';
      const customTime = '2026-10-26T12:00:00.000Z';

      const record = await telemetry.recordMetric({
        id: customId,
        createdAt: customTime,
        retrievalLatencyMs: 50,
        rerankerLatencyMs: 20,
        llmLatencyMs: 400,
        totalLatencyMs: 470,
        sampledForQuality: true,
      });

      expect(record.id).toBe(customId);
      expect(record.createdAt).toBe(customTime);
    });
  });

  describe('updateQualityScore', () => {
    it('updates faithfulness, context and answer relevance scores on existing record', async () => {
      const record = await telemetry.recordMetric({
        retrievalLatencyMs: 100,
        rerankerLatencyMs: 30,
        llmLatencyMs: 500,
        totalLatencyMs: 630,
        sampledForQuality: true,
      });

      const updated = await telemetry.updateQualityScore(record.id!, {
        faithfulnessScore: 0.95,
        contextRelevanceScore: 0.88,
        answerRelevanceScore: 0.92,
      });

      expect(updated).not.toBeNull();
      expect(updated?.faithfulnessScore).toBe(0.95);
      expect(updated?.contextRelevanceScore).toBe(0.88);
      expect(updated?.answerRelevanceScore).toBe(0.92);

      const inStore = telemetry.getRecords().find((r: RagTelemetryRecord) => r.id === record.id);
      expect(inStore?.faithfulnessScore).toBe(0.95);
    });

    it('returns null when updating non-existent id', async () => {
      const updated = await telemetry.updateQualityScore('non-existent-id', {
        faithfulnessScore: 0.9,
      });
      expect(updated).toBeNull();
    });
  });

  describe('shouldSample', () => {
    it('returns true when sampling rate is 1.0', () => {
      expect(telemetry.shouldSample(1.0)).toBe(true);
    });

    it('returns false when sampling rate is 0.0', () => {
      expect(telemetry.shouldSample(0.0)).toBe(false);
    });

    it('samples probabilistically using math.random', () => {
      const randomSpy = vi.spyOn(Math, 'random');
      randomSpy.mockReturnValueOnce(0.05); // < 0.1 -> true
      expect(telemetry.shouldSample(0.1)).toBe(true);

      randomSpy.mockReturnValueOnce(0.15); // >= 0.1 -> false
      expect(telemetry.shouldSample(0.1)).toBe(false);

      randomSpy.mockRestore();
    });
  });

  describe('getAggregatedMetrics', () => {
    it('handles empty records cleanly without divide by zero', () => {
      const metrics = telemetry.getAggregatedMetrics();
      expect(metrics.total_queries).toBe(0);
      expect(metrics.sampled_queries).toBe(0);
      expect(metrics.sampling_rate).toBe(0.1);
      expect(metrics.avg_retrieval_latency_ms).toBe(0);
      expect(metrics.p95_retrieval_latency_ms).toBe(0);
      expect(metrics.avg_reranker_latency_ms).toBe(0);
      expect(metrics.p95_reranker_latency_ms).toBe(0);
      expect(metrics.avg_llm_latency_ms).toBe(0);
      expect(metrics.p95_llm_latency_ms).toBe(0);
      expect(metrics.avg_total_latency_ms).toBe(0);
      expect(metrics.p95_total_latency_ms).toBe(0);
      expect(metrics.avg_faithfulness_score).toBeNull();
      expect(metrics.avg_context_relevance_score).toBeNull();
      expect(metrics.avg_answer_relevance_score).toBeNull();
      expect(metrics.recent_samples).toEqual([]);
    });

    it('calculates accurate averages and p95 percentiles across latency distributions', async () => {
      // Insert 100 records with latencies 1 to 100
      for (let i = 1; i <= 100; i++) {
        await telemetry.recordMetric({
          retrievalLatencyMs: i * 2,
          rerankerLatencyMs: i,
          llmLatencyMs: i * 10,
          totalLatencyMs: i * 13,
          sampledForQuality: i % 10 === 0, // 10 sampled
          faithfulnessScore: i % 10 === 0 ? 0.8 : undefined,
          contextRelevanceScore: i % 10 === 0 ? 0.9 : undefined,
          answerRelevanceScore: i % 10 === 0 ? 0.85 : undefined,
        });
      }

      const metrics = telemetry.getAggregatedMetrics();

      expect(metrics.total_queries).toBe(100);
      expect(metrics.sampled_queries).toBe(10);
      expect(metrics.sampling_rate).toBe(0.1);

      // p95 of 1..100 (reranker) is 95
      expect(metrics.p95_reranker_latency_ms).toBe(95);
      // p95 of 2..200 (retrieval) is 190
      expect(metrics.p95_retrieval_latency_ms).toBe(190);
      // p95 of 10..1000 (llm) is 950
      expect(metrics.p95_llm_latency_ms).toBe(950);
      // p95 of 13..1300 (total) is 1235
      expect(metrics.p95_total_latency_ms).toBe(1235);

      // Averages (sum of 1..100 = 5050 / 100 = 50.5)
      expect(metrics.avg_reranker_latency_ms).toBe(50.5);
      expect(metrics.avg_retrieval_latency_ms).toBe(101);
      expect(metrics.avg_llm_latency_ms).toBe(505);
      expect(metrics.avg_total_latency_ms).toBe(656.5);

      // Quality score averages
      expect(metrics.avg_faithfulness_score).toBe(0.8);
      expect(metrics.avg_context_relevance_score).toBe(0.9);
      expect(metrics.avg_answer_relevance_score).toBe(0.85);

      // recent_samples capped at 20, newest first
      expect(metrics.recent_samples).toHaveLength(20);
      expect(metrics.recent_samples[0].rerankerLatencyMs).toBe(100);
      expect(metrics.recent_samples[19].rerankerLatencyMs).toBe(81);
    });
  });
});

describe('IngestionClient searchWithMetrics Suite', () => {
  it('parses retrieval and reranker latencies from search response', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        results: [
          {
            id: 'chunk-1',
            game: 'Bloodborne',
            title: 'Saw Cleaver Guide',
            content: 'Trick weapon details',
            is_missable: false,
            similarity_score: 0.91,
          },
        ],
        retrieval_latency_ms: 18.4,
        reranker_latency_ms: 6.2,
      }),
    });

    vi.stubGlobal('fetch', fetchMock);

    const client = new IngestionClient('http://test-ingest:8000');
    const result = await client.searchWithMetrics({
      query: 'Saw Cleaver location',
      game: 'Bloodborne',
    });

    expect(result.chunks).toHaveLength(1);
    expect(result.chunks[0].title).toBe('Saw Cleaver Guide');
    expect(result.retrieval_latency_ms).toBe(18.4);
    expect(result.reranker_latency_ms).toBe(6.2);

    vi.unstubAllGlobals();
  });

  it('handles error gracefully and returns zero latencies and empty chunks', async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error('Network error'));
    vi.stubGlobal('fetch', fetchMock);

    const client = new IngestionClient('http://test-ingest:8000');
    const result = await client.searchWithMetrics('any query');

    expect(result.chunks).toEqual([]);
    expect(result.retrieval_latency_ms).toBe(0);
    expect(result.reranker_latency_ms).toBe(0);

    vi.unstubAllGlobals();
  });
});