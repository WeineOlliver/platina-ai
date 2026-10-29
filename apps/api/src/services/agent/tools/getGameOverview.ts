import { z } from 'zod';
import { env } from '../../../config/env.js';

export const getGameOverviewParamsSchema = z.object({
  game: z.string().min(1).describe('Official game title or slug in English (e.g. "The Witcher 3: Wild Hunt")'),
});

export type GetGameOverviewParams = z.infer<typeof getGameOverviewParamsSchema>;

export interface GameOverviewResult {
  game_id: string;
  title: string;
  difficulty?: number | null;
  hours?: number | null;
  playthroughs?: number | null;
  metadata_source?: string | null;
  total_trophies: number;
  by_type: {
    bronze: number;
    silver: number;
    gold: number;
    platinum: number;
  };
  by_dlc: Array<{
    name: string;
    count: number;
    linked_chunks_count: number;
  }>;
  error?: string;
}

export class GetGameOverviewTool {
  static readonly name = 'get_game_overview';
  readonly name = GetGameOverviewTool.name;
  static readonly description =
    'Obtém o panorama geral de platina do jogo no catálogo canônico: dificuldade estimada, tempo em horas, quantidade de jogadas (playthroughs) necessárias e distribuição de troféus por tipo e por DLC. Use para responder sobre dificuldade, tempo para platina e visão geral do jogo.';

  static readonly toolDefinition = {
    type: 'function' as const,
    function: {
      name: GetGameOverviewTool.name,
      description: GetGameOverviewTool.description,
      parameters: {
        type: 'object',
        properties: {
          game: {
            type: 'string',
            description: 'Official game title or slug in English (e.g. "The Witcher 3: Wild Hunt")',
          },
        },
        required: ['game'],
      },
    },
  };
  readonly toolDefinition = GetGameOverviewTool.toolDefinition;

  private baseUrl: string;

  constructor(baseUrl: string = env.INGESTION_SERVICE_URL) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
  }

  async execute(params: GetGameOverviewParams): Promise<GameOverviewResult> {
    const validated = getGameOverviewParamsSchema.safeParse(params);
    if (!validated.success) {
      return {
        game_id: '',
        title: '',
        total_trophies: 0,
        by_type: { bronze: 0, silver: 0, gold: 0, platinum: 0 },
        by_dlc: [],
        error: `Parâmetros inválidos: ${validated.error.message}`,
      };
    }

    const { game } = validated.data;

    try {
      const url = `${this.baseUrl}/api/v1/catalog/overview?game=${encodeURIComponent(game)}`;
      const response = await fetch(url);

      if (!response.ok) {
        return {
          game_id: '',
          title: '',
          total_trophies: 0,
          by_type: { bronze: 0, silver: 0, gold: 0, platinum: 0 },
          by_dlc: [],
          error: `Catalog service error: HTTP ${response.status}`,
        };
      }

      const data = (await response.json()) as GameOverviewResult;
      return data;
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Falha na conexão com serviço de catálogo';
      return {
        game_id: '',
        title: '',
        total_trophies: 0,
        by_type: { bronze: 0, silver: 0, gold: 0, platinum: 0 },
        by_dlc: [],
        error: `Falha na requisição: ${message}`,
      };
    }
  }
}

export const getGameOverviewTool = new GetGameOverviewTool();
