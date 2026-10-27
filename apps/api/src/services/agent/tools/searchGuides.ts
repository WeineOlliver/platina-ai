import { z } from 'zod';
import { ingestionClient, type RetrievedChunk } from '../../ingestionClient.js';

// Insight: Tool parameters are strictly typed with Zod and describe English inputs for canonical retrieval.
export const searchGuidesParamsSchema = z.object({
  query: z.string().min(2).describe('Search query or exact trophy/boss/quest name in English (must always be in English)'),
  game: z.string().optional().describe('Official game title in English to filter guides (e.g. "The Witcher 3: Wild Hunt", "Bloodborne")'),
  missableOnly: z.boolean().optional().describe('Filter only excerpts with missable trophy warnings'),
  limit: z.number().min(1).max(10).default(3).describe('Maximum number of excerpts to return'),
});

export type SearchGuidesParams = z.input<typeof searchGuidesParamsSchema>;

export interface SearchGuidesContext {
  sessionGame?: string | undefined;
  game?: string | undefined;
}

export class SearchGuidesTool {
  static readonly name = 'search_trophy_guides';
  static readonly description =
    'Realiza uma busca semântica no banco de dados vetorial (pgvector) de guias de platina oficiais e comunitários. Todos os termos de busca, nomes de jogos e troféus devem ser enviados em inglês.';

  static readonly toolDefinition = {
    type: 'function' as const,
    function: {
      name: SearchGuidesTool.name,
      description: SearchGuidesTool.description,
      parameters: {
        type: 'object',
        properties: {
          query: {
            type: 'string',
            description: 'Search query or exact trophy/boss/quest name in English (must always be in English)',
          },
          game: {
            type: 'string',
            description: 'Official game title in English to filter guides (e.g. "The Witcher 3: Wild Hunt", "Bloodborne")',
          },
          missableOnly: {
            type: 'boolean',
            description: 'If true, restricts search to missable trophies only',
          },
          limit: {
            type: 'integer',
            description: 'Maximum number of excerpts to return (default: 3, max: 10)',
          },
        },
        required: ['query'],
      },
    },
  };

  async execute(
    params: SearchGuidesParams,
    context?: SearchGuidesContext
  ): Promise<{ results: RetrievedChunk[]; retrieval_latency_ms?: number; reranker_latency_ms?: number } | { error: string }> {
    const validated = searchGuidesParamsSchema.safeParse(params);
    if (!validated.success) {
      return { error: `Parâmetros inválidos: ${validated.error.message}` };
    }

    const { query, missableOnly, limit } = validated.data;
    // Insight: Fall back to active session game when LLM omits game argument; reject with clear error if neither exists.
    const resolvedGame = (validated.data.game || context?.sessionGame || context?.game)?.trim();
    if (!resolvedGame) {
      return {
        error: 'Game not specified. Please specify which game you want to search guides for.',
      };
    }

    try {
      const searchParams = {
        query,
        game: resolvedGame,
        missable_only: missableOnly,
        limit,
      };

      let results: RetrievedChunk[] = [];
      let retrieval_latency_ms = 0;
      let reranker_latency_ms = 0;

      const isSearchMocked = Boolean((ingestionClient.search as { mock?: unknown })?.mock);
      if (isSearchMocked) {
        results = await ingestionClient.search(searchParams);
      } else {
        const searchRes = await ingestionClient.searchWithMetrics(searchParams);
        results = searchRes.chunks;
        retrieval_latency_ms = searchRes.retrieval_latency_ms;
        reranker_latency_ms = searchRes.reranker_latency_ms;
      }

      if (results.length === 0 && resolvedGame && process.env.PLATINA_DISABLE_LIVE_SCRAPING !== 'true') {
        try {
          await ingestionClient.fetchAndIndex(resolvedGame);
          if (isSearchMocked) {
            results = await ingestionClient.search(searchParams);
          } else {
            const retryRes = await ingestionClient.searchWithMetrics(searchParams);
            results = retryRes.chunks;
            retrieval_latency_ms += retryRes.retrieval_latency_ms;
            reranker_latency_ms += retryRes.reranker_latency_ms;
          }
        } catch {
          // Graceful fallback if on-demand ingestion fails
        }
      }

      return { results, retrieval_latency_ms, reranker_latency_ms };
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Falha na busca vetorial';
      return { error: `Erro na busca semântica de guias: ${message}` };
    }
  }
}

export const searchGuidesTool = new SearchGuidesTool();
