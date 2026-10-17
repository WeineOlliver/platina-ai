import { z } from 'zod';
import { env } from '../../../config/env.js';
import { psnCrawlerService } from '../../psn/crawler.js';

// Insight: Tool Schema Contract.
// We define both the JSON Schema descriptor that the LLM inspects to decide
// whether to call the tool, and the Zod schema used to validate the tool arguments at runtime.
export const checkPlayerProgressParamsSchema = z.object({
  psnId: z.string().min(2).describe('O PSN ID ou nome de usuário do jogador na PlayStation Network'),
  game: z.string().min(2).describe('O nome do jogo para verificar a lista de troféus (ex: Bloodborne, Elden Ring)'),
});

export type CheckPlayerProgressParams = z.infer<typeof checkPlayerProgressParamsSchema>;

export interface PlayerProgressData {
  psn_id: string;
  game: string;
  platform: string;
  total_trophies: number;
  unlocked_count: number;
  completion_percentage: number;
  pending_count: number;
  pending_missables_count: number;
  pending_missable_trophies: Array<{
    trophy_name: string;
    chapter_or_location?: string | undefined;
    trophy_type: string;
  }>;
  recently_unlocked: Array<{
    trophy_name: string;
    unlocked_at?: string | undefined;
  }>;
}

export class PlayerProgressTool {
  static readonly name = 'check_player_progress';
  static readonly description = 
    'Consulta os troféus já conquistados e pendentes de um jogador na PlayStation Network (PSN) para um jogo específico. Use esta ferramenta para descobrir quais troféus o jogador ainda precisa fazer e se ele tem troféus perdíveis pendentes.';

  static readonly toolDefinition = {
    type: 'function' as const,
    function: {
      name: PlayerProgressTool.name,
      description: PlayerProgressTool.description,
      parameters: {
        type: 'object',
        properties: {
          psnId: {
            type: 'string',
            description: 'O identificador PSN ID do jogador (ex: OlliverHunter)',
          },
          game: {
            type: 'string',
            description: 'O título do jogo (ex: Bloodborne, Elden Ring)',
          },
        },
        required: ['psnId', 'game'],
      },
    },
  };

  private baseUrl: string;

  constructor(baseUrl: string = env.INGESTION_SERVICE_URL) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
  }

  async execute(params: CheckPlayerProgressParams): Promise<PlayerProgressData | { error: string }> {
    const validated = checkPlayerProgressParamsSchema.safeParse(params);
    if (!validated.success) {
      return { error: `Parâmetros inválidos: ${validated.error.message}` };
    }

    const { psnId, game } = validated.data;

    // First attempt: live crawl via PlayStation Network Worker (if configured)
    if (process.env.PSN_WORKER_NPSSO) {
      try {
        const liveData = await psnCrawlerService.getPlayerTrophies(psnId, game);
        const unlocked = liveData.trophies.filter(t => t.isUnlocked);
        const pending = liveData.trophies.filter(t => !t.isUnlocked);
        const pendingMissables = pending.filter(t => t.isMissable);

        return {
          psn_id: liveData.psnId,
          game: liveData.game,
          platform: liveData.platform,
          total_trophies: liveData.totalTrophies,
          unlocked_count: liveData.unlockedCount,
          completion_percentage: liveData.progressPercentage,
          pending_count: pending.length,
          pending_missables_count: pendingMissables.length,
          pending_missable_trophies: pendingMissables.map(t => ({
            trophy_name: t.name,
            chapter_or_location: t.chapterOrLocation || undefined,
            trophy_type: t.type
          })),
          recently_unlocked: unlocked.slice(-3).map(t => ({
            trophy_name: t.name,
            unlocked_at: t.earnedDateTime || undefined
          }))
        };
      } catch (err: unknown) {
        // Fall back to internal microservice database query if PSN API times out or fails
      }
    }

    try {
      const url = `${this.baseUrl}/api/v1/players/${encodeURIComponent(psnId)}/progress?game=${encodeURIComponent(game)}`;
      const response = await fetch(url);

      if (response.status === 404) {
        return {
          error: `Jogador "${psnId}" ou jogo "${game}" não encontrado no banco de dados da PSN.`,
        };
      }

      if (!response.ok) {
        return {
          error: `Erro ao consultar serviço de troféus: HTTP ${response.status}`,
        };
      }

      return (await response.json()) as PlayerProgressData;
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Falha na conexão com serviço de progresso';
      return { error: `Falha na requisição: ${message}` };
    }
  }
}

export const playerProgressTool = new PlayerProgressTool();
