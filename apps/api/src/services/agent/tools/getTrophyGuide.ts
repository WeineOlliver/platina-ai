import { z } from 'zod';
import { env } from '../../../config/env.js';

export const getTrophyGuideParamsSchema = z.object({
  game: z.string().min(1).describe('Official game title or slug in English (e.g. "The Witcher 3: Wild Hunt")'),
  trophy: z.string().min(1).describe('Exact official trophy name in English (e.g. "What Was That?", "Card Collector")'),
});

export type GetTrophyGuideParams = z.infer<typeof getTrophyGuideParamsSchema>;

export interface TrophyGuideResult {
  status: 'found' | 'suggestions' | 'not_found' | 'error';
  game?: string;
  trophy?: {
    id: string;
    game_id?: string;
    psn_trophy_id?: number | null;
    name: string;
    type: string;
    description?: string | null;
    dlc?: string | null;
    location?: string | null;
    missable: boolean;
    missable_sources?: string[];
    aliases?: string[];
  };
  chunks: Array<{
    id: string;
    title: string;
    content: string;
    source_url?: string;
    is_missable: boolean;
    context_prefix?: string;
  }>;
  linked_chunks_count: number;
  has_guide: boolean;
  suggestions?: string[];
  message?: string;
  error?: string;
}

export class GetTrophyGuideTool {
  static readonly name = 'get_trophy_guide';
  readonly name = GetTrophyGuideTool.name;
  static readonly description =
    'Busca informações detalhadas de um troféu específico no catálogo canônico e retorna seus metadados (tipo, descrição, DLC, localização, se é perdível) e os trechos de guia ordenados, sem busca vetorial. Use quando o usuário perguntar como pegar um troféu específico ou citar um nome exato de troféu.';

  static readonly toolDefinition = {
    type: 'function' as const,
    function: {
      name: GetTrophyGuideTool.name,
      description: GetTrophyGuideTool.description,
      parameters: {
        type: 'object',
        properties: {
          game: {
            type: 'string',
            description: 'Official game title or slug in English (e.g. "The Witcher 3: Wild Hunt")',
          },
          trophy: {
            type: 'string',
            description: 'Exact official trophy name in English (e.g. "What Was That?", "Card Collector")',
          },
        },
        required: ['game', 'trophy'],
      },
    },
  };
  readonly toolDefinition = GetTrophyGuideTool.toolDefinition;

  private baseUrl: string;

  constructor(baseUrl: string = env.INGESTION_SERVICE_URL) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
  }

  async execute(params: GetTrophyGuideParams): Promise<TrophyGuideResult> {
    const validated = getTrophyGuideParamsSchema.safeParse(params);
    if (!validated.success) {
      return {
        status: 'error',
        linked_chunks_count: 0,
        has_guide: false,
        chunks: [],
        error: `Parâmetros inválidos: ${validated.error.message}`,
      };
    }

    const { game, trophy } = validated.data;

    try {
      const url = `${this.baseUrl}/api/v1/catalog/trophy-guide?game=${encodeURIComponent(game)}&trophy=${encodeURIComponent(trophy)}`;
      const response = await fetch(url);

      if (response.status === 404) {
        return {
          status: 'not_found',
          linked_chunks_count: 0,
          has_guide: false,
          chunks: [],
          error: `Game or trophy not found in catalog for "${game}".`,
        };
      }

      if (!response.ok) {
        return {
          status: 'error',
          linked_chunks_count: 0,
          has_guide: false,
          chunks: [],
          error: `Catalog service error: HTTP ${response.status}`,
        };
      }

      const data = (await response.json()) as TrophyGuideResult;
      return data;
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Falha na conexão com serviço de catálogo';
      return {
        status: 'error',
        linked_chunks_count: 0,
        has_guide: false,
        chunks: [],
        error: `Falha na requisição: ${message}`,
      };
    }
  }
}

export const getTrophyGuideTool = new GetTrophyGuideTool();
