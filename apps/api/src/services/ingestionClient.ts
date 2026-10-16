import { env } from '../config/env.js';

export interface RetrievedChunk {
  id: string;
  game: string;
  title: string;
  content: string;
  is_missable: boolean;
  source_url?: string | null;
  similarity_score: number;
}

export interface RetrievalSearchOptions {
  game?: string | undefined;
  missable_only?: boolean | undefined;
  limit?: number | undefined;
  signal?: AbortSignal | undefined;
}

// Insight: Circuit Breaker / Graceful Fallback pattern.
// If the Python ingestion service is unreachable (e.g. cold start, network split),
// the chat API should degrade gracefully by falling back to base LLM inference
// rather than failing the client's HTTP request with a 500 error.
export class IngestionClient {
  private baseUrl: string;

  constructor(baseUrl: string = env.INGESTION_SERVICE_URL) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
  }

  async searchGuides(
    query: string,
    options: RetrievalSearchOptions = {}
  ): Promise<RetrievedChunk[]> {
    try {
      const init: RequestInit = {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          game: options.game,
          missable_only: options.missable_only ?? false,
          limit: options.limit ?? 3,
        }),
      };
      if (options.signal) {
        init.signal = options.signal;
      }

      const response = await fetch(`${this.baseUrl}/api/v1/ingest/search`, init);

      if (!response.ok) {
        return [];
      }

      const data = await response.json() as { results?: RetrievedChunk[] };
      return data.results ?? [];
    } catch {
      // Graceful degradation: return empty context if microservice call fails
      return [];
    }
  }
}

export const ingestionClient = new IngestionClient();
