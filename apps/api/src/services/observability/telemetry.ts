import crypto from 'node:crypto';
import { env } from '../../config/env.js';

export interface RagTelemetryRecord {
  id?: string;
  sessionId?: string;
  game?: string;
  modelName?: string;
  retrievalLatencyMs: number;
  rerankerLatencyMs: number;
  llmLatencyMs: number;
  totalLatencyMs: number;
  sampledForQuality: boolean;
  faithfulnessScore?: number;
  contextRelevanceScore?: number;
  answerRelevanceScore?: number;
  queryPreview?: string;
  createdAt?: string;
}

export interface AggregatedMetrics {
  total_queries: number;
  sampled_queries: number;
  sampling_rate: number;
  avg_retrieval_latency_ms: number;
  p95_retrieval_latency_ms: number;
  avg_reranker_latency_ms: number;
  p95_reranker_latency_ms: number;
  avg_llm_latency_ms: number;
  p95_llm_latency_ms: number;
  avg_total_latency_ms: number;
  p95_total_latency_ms: number;
  avg_faithfulness_score: number | null;
  avg_context_relevance_score: number | null;
  avg_answer_relevance_score: number | null;
  recent_samples: RagTelemetryRecord[];
}

export interface TelemetryServiceOptions {
  samplingRate?: number;
  maxBufferSize?: number;
}

function calculateAverage(values: number[]): number {
  if (values.length === 0) return 0;
  const sum = values.reduce((acc, val) => acc + val, 0);
  return Number((sum / values.length).toFixed(2));
}

function calculateNullableAverage(values: number[]): number | null {
  if (values.length === 0) return null;
  const sum = values.reduce((acc, val) => acc + val, 0);
  return Number((sum / values.length).toFixed(2));
}

function calculateP95(values: number[]): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.min(sorted.length - 1, Math.max(0, Math.ceil(sorted.length * 0.95) - 1));
  const value = sorted[index] ?? 0;
  return Number(value.toFixed(2));
}

export class TelemetryService {
  private records: RagTelemetryRecord[] = [];
  private samplingRate: number;
  private maxBufferSize: number;

  constructor(options: TelemetryServiceOptions = {}) {
    this.samplingRate = options.samplingRate ?? env?.OBSERVABILITY_SAMPLING_RATE ?? 0.1;
    this.maxBufferSize = options.maxBufferSize ?? 1000;
  }

  async recordMetric(data: RagTelemetryRecord): Promise<RagTelemetryRecord> {
    const record: RagTelemetryRecord = {
      ...data,
      id: data.id ?? crypto.randomUUID(),
      createdAt: data.createdAt ?? new Date().toISOString(),
    };

    this.records.push(record);
    if (this.records.length > this.maxBufferSize) {
      this.records.shift();
    }

    return record;
  }

  async updateQualityScore(
    id: string,
    qualityData: {
      faithfulnessScore?: number;
      contextRelevanceScore?: number;
      answerRelevanceScore?: number;
    }
  ): Promise<RagTelemetryRecord | null> {
    const record = this.records.find((r) => r.id === id);
    if (!record) {
      return null;
    }

    if (qualityData.faithfulnessScore !== undefined) {
      record.faithfulnessScore = qualityData.faithfulnessScore;
    }
    if (qualityData.contextRelevanceScore !== undefined) {
      record.contextRelevanceScore = qualityData.contextRelevanceScore;
    }
    if (qualityData.answerRelevanceScore !== undefined) {
      record.answerRelevanceScore = qualityData.answerRelevanceScore;
    }

    return record;
  }

  shouldSample(samplingRate?: number): boolean {
    const rate = typeof samplingRate === 'number' ? samplingRate : this.samplingRate;
    return Math.random() < rate;
  }

  getAggregatedMetrics(): AggregatedMetrics {
    const total_queries = this.records.length;
    const sampled_queries = this.records.filter((r) => r.sampledForQuality).length;
    const sampling_rate =
      total_queries > 0
        ? Number((sampled_queries / total_queries).toFixed(4))
        : this.samplingRate;

    const retrievalLatencies = this.records.map((r) => r.retrievalLatencyMs);
    const rerankerLatencies = this.records.map((r) => r.rerankerLatencyMs);
    const llmLatencies = this.records.map((r) => r.llmLatencyMs);
    const totalLatencies = this.records.map((r) => r.totalLatencyMs);

    const faithfulnessScores = this.records
      .map((r) => r.faithfulnessScore)
      .filter((s): s is number => typeof s === 'number');

    const contextRelevanceScores = this.records
      .map((r) => r.contextRelevanceScore)
      .filter((s): s is number => typeof s === 'number');

    const answerRelevanceScores = this.records
      .map((r) => r.answerRelevanceScore)
      .filter((s): s is number => typeof s === 'number');

    const recent_samples = [...this.records].slice(-20).reverse();

    return {
      total_queries,
      sampled_queries,
      sampling_rate,
      avg_retrieval_latency_ms: calculateAverage(retrievalLatencies),
      p95_retrieval_latency_ms: calculateP95(retrievalLatencies),
      avg_reranker_latency_ms: calculateAverage(rerankerLatencies),
      p95_reranker_latency_ms: calculateP95(rerankerLatencies),
      avg_llm_latency_ms: calculateAverage(llmLatencies),
      p95_llm_latency_ms: calculateP95(llmLatencies),
      avg_total_latency_ms: calculateAverage(totalLatencies),
      p95_total_latency_ms: calculateP95(totalLatencies),
      avg_faithfulness_score: calculateNullableAverage(faithfulnessScores),
      avg_context_relevance_score: calculateNullableAverage(contextRelevanceScores),
      avg_answer_relevance_score: calculateNullableAverage(answerRelevanceScores),
      recent_samples,
    };
  }

  getRecords(): RagTelemetryRecord[] {
    return [...this.records];
  }

  clear(): void {
    this.records = [];
  }
}

// ponytail: in-memory buffer with fallback; sync to PostgreSQL/HTTP backend when direct DB client or ingest route is attached.
export const telemetryService = new TelemetryService();
