import { env } from '../../config/env.js';

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

export interface SearchParams {
  query: string;
  game?: string | undefined;
  missable_only?: boolean | undefined;
  missableOnly?: boolean | undefined;
  limit?: number | undefined;
  signal?: AbortSignal | undefined;
}

export interface FetchAndIndexResult {
  status: string;
  chunks_indexed: number;
  game: string;
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

  async fetchAndIndex(
    game: string,
    sourceUrl?: string
  ): Promise<FetchAndIndexResult> {
    const response = await fetch(`${this.baseUrl}/api/v1/ingest/fetch-and-index`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        game,
        source_url: sourceUrl,
      }),
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch and index guide: ${response.statusText}`);
    }

    const data = (await response.json()) as { status: string; chunks_indexed: number; game?: string };
    return {
      status: data.status,
      chunks_indexed: data.chunks_indexed,
      game: data.game ?? game,
    };
  }

  async search(
    paramsOrQuery: SearchParams | string,
    options: RetrievalSearchOptions = {}
  ): Promise<RetrievedChunk[]> {
    if (typeof paramsOrQuery === 'string') {
      return this.searchGuides(paramsOrQuery, options);
    }
    return this.searchGuides(paramsOrQuery.query, {
      game: paramsOrQuery.game,
      missable_only: paramsOrQuery.missable_only ?? paramsOrQuery.missableOnly,
      limit: paramsOrQuery.limit,
      signal: paramsOrQuery.signal,
    });
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

      const data = (await response.json()) as { results?: RetrievedChunk[] };
      return data.results ?? [];
    } catch {
      // Graceful degradation: return empty context if microservice call fails
      return [];
    }
  }
}

export const ingestionClient = new IngestionClient();
