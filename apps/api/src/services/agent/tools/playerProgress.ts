import { z } from 'zod';
import { env } from '../../../config/env.js';
import { psnCrawlerService } from '../../psn/crawler.js';

// Insight: Tool Schema Contract.
// We define both the JSON Schema descriptor that the LLM inspects to decide
// whether to call the tool, and the Zod schema used to validate the tool arguments at runtime.
// Official game titles and arguments are always in English.
export const checkPlayerProgressParamsSchema = z.object({
  game: z.string().min(2).describe('Official game title in English (e.g. "The Witcher 3: Wild Hunt", "Bloodborne")'),
});

export type CheckPlayerProgressParams = z.infer<typeof checkPlayerProgressParamsSchema>;

export interface PlayerProgressResult {
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
    trophy_id?: string | undefined;
  }>;
  unearned_trophies_summary?: string[];
  recently_unlocked: Array<{
    trophy_name: string;
    unlocked_at?: string | undefined;
  }>;
  quick_cleanup_trophies?: Array<{
    trophy_name: string;
    chapter_or_location?: string | undefined;
    trophy_type?: string | undefined;
  }>;
  heavy_grind_trophies?: Array<{
    trophy_name: string;
    chapter_or_location?: string | undefined;
    trophy_type?: string | undefined;
  }>;
  natural_grind_trophies?: Array<{
    trophy_name: string;
    chapter_or_location?: string | undefined;
    trophy_type?: string | undefined;
  }>;
  pending_missables?: Array<{
    trophy_name: string;
    chapter_or_location?: string | undefined;
    trophy_type?: string | undefined;
  }>;
}

export type PlayerProgressData = PlayerProgressResult;

export class PlayerProgressTool {
  static readonly name = 'check_player_progress';
  static readonly description = 
    "Inspect earned and pending trophies for the project owner on the PlayStation Network (PSN) for a specific game. Use this tool to discover which trophies the project owner still needs and check for pending missable trophies.";

  static readonly toolDefinition = {
    type: 'function' as const,
    function: {
      name: PlayerProgressTool.name,
      description: PlayerProgressTool.description,
      parameters: {
        type: 'object',
        properties: {
          game: {
            type: 'string',
            description: 'Official game title in English (e.g. "The Witcher 3: Wild Hunt", "Bloodborne")',
          },
        },
        required: ['game'],
      },
    },
  };

  private baseUrl: string;

  constructor(baseUrl: string = env.INGESTION_SERVICE_URL) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
  }

  async execute(params: CheckPlayerProgressParams): Promise<PlayerProgressResult | { error: string }> {
    const validated = checkPlayerProgressParamsSchema.safeParse(params);
    if (!validated.success) {
      return { error: `Invalid parameters: ${validated.error.message}` };
    }

    const { game } = validated.data;

    // First attempt: internal microservice database query for owner profile
    try {
      const url = `${this.baseUrl}/api/v1/players/me/progress?game=${encodeURIComponent(game)}`;
      const response = await fetch(url);

      if (response.ok) {
        return (await response.json()) as PlayerProgressResult;
      }
    } catch {
      // Fall back to live crawl if microservice is offline or times out
    }

    // Fallback: live crawl via PlayStation Network Worker (if configured)
    if (env.PSN_WORKER_NPSSO || process.env.PSN_WORKER_NPSSO) {
      try {
        const liveData = await psnCrawlerService.getPlayerTrophies(game);
        const unlocked = liveData.trophies.filter(t => t.isUnlocked);
        const pending = liveData.trophies.filter(t => !t.isUnlocked);
        const pendingMissables = pending.filter(t => t.isMissable);

        const quickCleanup = pending.filter(
          (t) =>
            t.chapterOrLocation?.toLowerCase().includes('director mode') ||
            [
              'Vinewood Visionary',
              'Majestic',
              'Humans of Los Santos',
              'Animal Lover',
              'Ensemble Piece',
              'Cult Movie',
              'Location Scout',
              'Method Actor',
              'Cryptozoologist',
            ].includes(t.name)
        );

        const heavyGrind = pending.filter(
          (t) =>
            t.chapterOrLocation?.toLowerCase().includes('heist') ||
            t.chapterOrLocation?.toLowerCase().includes('doomsday') ||
            ['Live a Little', 'Mastermind', 'Masterminds', 'Elitist'].includes(t.name)
        );

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
          unearned_trophies_summary: pending.slice(0, 15).map(t => `${t.name} (${t.type}): ${t.detail}`),
          recently_unlocked: unlocked.slice(-3).map(t => ({
            trophy_name: t.name,
            unlocked_at: t.earnedDateTime || undefined
          })),
          quick_cleanup_trophies: quickCleanup.map(t => ({
            trophy_name: t.name,
            chapter_or_location: t.chapterOrLocation || undefined,
            trophy_type: t.type,
          })),
          heavy_grind_trophies: heavyGrind.map(t => ({
            trophy_name: t.name,
            chapter_or_location: t.chapterOrLocation || undefined,
            trophy_type: t.type,
          })),
          natural_grind_trophies: [],
          pending_missables: pendingMissables.map(t => ({
            trophy_name: t.name,
            chapter_or_location: t.chapterOrLocation || undefined,
            trophy_type: t.type,
          })),
        };
      } catch (err: unknown) {
        // live crawl failed or not found
      }
    }

    // Direct error check if microservice gave a specific error response
    try {
      const url = `${this.baseUrl}/api/v1/players/me/progress?game=${encodeURIComponent(game)}`;
      const response = await fetch(url);
      if (response.status === 404) {
        return {
          error: `Game "${game}" not found in project owner profile on PSN.`,
        };
      }
      if (!response.ok) {
        return {
          error: `Error querying trophy service: HTTP ${response.status}`,
        };
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to connect to progress service';
      return { error: `Request failed: ${message}` };
    }

    return {
      error: `Game "${game}" not found in project owner profile on PSN.`,
    };
  }
}

export const playerProgressTool = new PlayerProgressTool();
