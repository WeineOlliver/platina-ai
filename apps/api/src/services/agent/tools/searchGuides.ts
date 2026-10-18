import { z } from 'zod';
import { ingestionClient, type RetrievedChunk } from '../../ingestionClient.js';

export const searchGuidesParamsSchema = z.object({
  query: z.string().min(2).describe('A pergunta de busca ou o nome exato do troféu/chefe/item a pesquisar no guia'),
  game: z.string().optional().describe('Título do jogo para filtrar os guias (ex: Bloodborne, Elden Ring)'),
  missableOnly: z.boolean().optional().describe('Filtrar apenas trechos com avisos de troféus perdíveis'),
  limit: z.number().min(1).max(10).default(3).describe('Quantidade máxima de trechos a retornar'),
});

export type SearchGuidesParams = z.input<typeof searchGuidesParamsSchema>;

export class SearchGuidesTool {
  static readonly name = 'search_trophy_guides';
  static readonly description =
    'Realiza uma busca semântica no banco de dados vetorial (pgvector) de guias de platina oficiais e comunitários. Use esta ferramenta para obter instruções passo a passo, requisitos de desbloqueio, fraquezas de chefes ou condições para não perder troféus.';

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
            description: 'A pergunta ou termos-chave para buscar no guia de troféus',
          },
          game: {
            type: 'string',
            description: 'Nome do jogo para filtrar a busca',
          },
          missableOnly: {
            type: 'boolean',
            description: 'Se verdadeiro, restringe a busca apenas para troféus perdíveis',
          },
          limit: {
            type: 'integer',
            description: 'Número máximo de trechos a retornar (padrão: 3, máx: 10)',
          },
        },
        required: ['query'],
      },
    },
  };

  async execute(params: SearchGuidesParams): Promise<{ results: RetrievedChunk[] } | { error: string }> {
    const validated = searchGuidesParamsSchema.safeParse(params);
    if (!validated.success) {
      return { error: `Parâmetros inválidos: ${validated.error.message}` };
    }

    const { query, game, missableOnly, limit } = validated.data;

    try {
      const searchParams = {
        query,
        game,
        missable_only: missableOnly,
        limit,
      };

      let results = await ingestionClient.search(searchParams);

      if (results.length === 0 && game) {
        try {
          await ingestionClient.fetchAndIndex(game);
          results = await ingestionClient.search(searchParams);
        } catch {
          // Graceful fallback if on-demand ingestion fails
        }
      }

      return { results };
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Falha na busca vetorial';
      return { error: `Erro na busca semântica de guias: ${message}` };
    }
  }
}

export const searchGuidesTool = new SearchGuidesTool();
