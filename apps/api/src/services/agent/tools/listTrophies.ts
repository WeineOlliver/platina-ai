import { z } from 'zod';
import { env } from '../../../config/env.js';

export const listTrophiesParamsSchema = z.object({
  game: z.string().min(1).describe('Official game title or slug in English (e.g. "The Witcher 3: Wild Hunt")'),
  type: z.enum(['bronze', 'silver', 'gold', 'platinum']).optional().describe('Filter by trophy type'),
  dlc: z.string().optional().describe('Filter by DLC or expansion name (e.g. "Hearts of Stone", "Blood and Wine"), or "Base Game" / "base" for main game only'),
  location: z.string().optional().describe('Filter by region/location (e.g. "Novigrad", "Velen", "White Orchard", "Skellige")'),
  description_query: z.string().optional().describe('English keyword filter on trophy description (e.g. "contract", "difficulty")'),
  missable: z.boolean().optional().describe('Filter missable trophies only (true/false)'),
  missing_for_psn_id: z.string().optional().describe('Filter only trophies not yet unlocked by this player PSN ID'),
});

export type ListTrophiesParams = z.infer<typeof listTrophiesParamsSchema>;

export interface ListTrophiesItem {
  id: string;
  name: string;
  type: string;
  description?: string | null;
  dlc?: string | null;
  location?: string | string[] | null;
  missable: boolean;
  missable_sources?: string[];
  linked_chunks_count?: number;
}

export interface ListTrophiesResult {
  game_id: string;
  total: number;
  has_guide: boolean;
  linked_chunks_count: number;
  trophies: ListTrophiesItem[];
  error?: string;
}

export class ListTrophiesTool {
  static readonly name = 'list_trophies';
  readonly name = ListTrophiesTool.name;
  static readonly description =
    'Consulta o catálogo canônico de troféus via SQL com filtros por tipo, DLC, localização, missable e troféus pendentes para um PSN ID. Retorna a lista completa de troféus e métricas de cobertura de guias. Use SEMPRE para contagens, listas completas de troféus e troféus perdíveis por região/DLC.';

  static readonly toolDefinition = {
    type: 'function' as const,
    function: {
      name: ListTrophiesTool.name,
      description: ListTrophiesTool.description,
      parameters: {
        type: 'object',
        properties: {
          game: {
            type: 'string',
            description: 'Official game title or slug in English (e.g. "The Witcher 3: Wild Hunt")',
          },
          type: {
            type: 'string',
            enum: ['bronze', 'silver', 'gold', 'platinum'],
            description: 'Filter by trophy type',
          },
          dlc: {
            type: 'string',
            description: 'Filter by DLC name (e.g. "Hearts of Stone", "Blood and Wine"), or "Base Game" for main game',
          },
          location: {
            type: 'string',
            description: 'Filter by location (e.g. "Novigrad", "Velen", "White Orchard", "Skellige")',
          },
          description_query: {
            type: 'string',
            description: 'Filter trophies by English words in their description (e.g. "contract", "difficulty")',
          },
          missable: {
            type: 'boolean',
            description: 'Filter missable trophies only',
          },
          missing_for_psn_id: {
            type: 'string',
            description: 'Filter trophies still pending/unlocked for this PSN ID',
          },
        },
        required: ['game'],
      },
    },
  };
  readonly toolDefinition = ListTrophiesTool.toolDefinition;

  private baseUrl: string;

  constructor(baseUrl: string = env.INGESTION_SERVICE_URL) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
  }

  async execute(params: ListTrophiesParams): Promise<ListTrophiesResult> {
    const validated = listTrophiesParamsSchema.safeParse(params);
    if (!validated.success) {
      return {
        game_id: '',
        total: 0,
        has_guide: false,
        linked_chunks_count: 0,
        trophies: [],
        error: `Parâmetros inválidos: ${validated.error.message}`,
      };
    }

    const { game, type, dlc, location, description_query, missable, missing_for_psn_id } = validated.data;

    try {
      const urlParams = new URLSearchParams({ game });
      if (type) urlParams.append('type', type);
      if (dlc) urlParams.append('dlc', dlc);
      if (location) urlParams.append('location', location);
      if (description_query) urlParams.append('description_query', description_query);
      if (missable !== undefined) urlParams.append('missable', String(missable));
      if (missing_for_psn_id) urlParams.append('missing_for_psn_id', missing_for_psn_id);

      const url = `${this.baseUrl}/api/v1/catalog/trophies?${urlParams.toString()}`;
      const response = await fetch(url);

      if (!response.ok) {
        return {
          game_id: '',
          total: 0,
          has_guide: false,
          linked_chunks_count: 0,
          trophies: [],
          error: `Catalog service error: HTTP ${response.status}`,
        };
      }

      const data = (await response.json()) as ListTrophiesResult;
      return data;
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Falha na conexão com serviço de catálogo';
      return {
        game_id: '',
        total: 0,
        has_guide: false,
        linked_chunks_count: 0,
        trophies: [],
        error: `Falha na requisição: ${message}`,
      };
    }
  }
}

export const listTrophiesTool = new ListTrophiesTool();
