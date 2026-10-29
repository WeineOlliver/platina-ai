import { describe, it, expect, vi, beforeEach } from 'vitest';
import { getTrophyGuideTool } from './getTrophyGuide.js';
import { listTrophiesTool } from './listTrophies.js';
import { getGameOverviewTool } from './getGameOverview.js';
import { PlatinaAgentRunner } from '../runner.js';

describe('Catalog Tools & Coverage-Based Abstention Suite', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe('getTrophyGuideTool', () => {
    it('has correct tool name and description', () => {
      expect(getTrophyGuideTool.name).toBe('get_trophy_guide');
      expect(getTrophyGuideTool.toolDefinition.function.name).toBe('get_trophy_guide');
      expect(getTrophyGuideTool.toolDefinition.function.parameters.required).toContain('game');
      expect(getTrophyGuideTool.toolDefinition.function.parameters.required).toContain('trophy');
    });

    it('resolves exact trophy and returns ordered chunks', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          status: 'found',
          trophy: {
            id: 'the-witcher-3-wild-hunt-what-was-that',
            name: 'What Was That?',
            type: 'bronze',
            dlc: null,
            missable: false,
          },
          chunks: [
            { id: 'c1', title: 'What Was That? (Part 1)', content: 'Parry 10 times in a row.' },
            { id: 'c2', title: 'What Was That? (Part 2)', content: 'Counterattack without taking damage.' },
          ],
          linked_chunks_count: 2,
          has_guide: true,
        }),
      });
      global.fetch = mockFetch;

      const result = await getTrophyGuideTool.execute({
        game: 'The Witcher 3: Wild Hunt',
        trophy: 'What Was That?',
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/catalog/trophy-guide?game=The%20Witcher%203%3A%20Wild%20Hunt&trophy=What%20Was%20That%3F')
      );
      expect(result.status).toBe('found');
      if (result.status === 'found') {
        expect(result.trophy?.name).toBe('What Was That?');
        expect(result.chunks).toHaveLength(2);
        expect(result.has_guide).toBe(true);
      }
    });

    it('returns suggestions when trophy is misspelled or fuzzy match is needed', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          status: 'suggestions',
          suggestions: ['What Was That?', 'That Is The Question'],
          chunks: [],
          linked_chunks_count: 0,
          has_guide: false,
        }),
      });
      global.fetch = mockFetch;

      const result = await getTrophyGuideTool.execute({
        game: 'The Witcher 3: Wild Hunt',
        trophy: 'What That',
      });

      expect(result.status).toBe('suggestions');
      expect(result.suggestions).toContain('What Was That?');
      expect(result.has_guide).toBe(false);
    });

    it('returns has_guide: false for trophy in unindexed DLC (N01)', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          status: 'found',
          trophy: {
            id: 'the-witcher-3-wild-hunt-david-and-golyat',
            name: 'David and Golyat',
            type: 'bronze',
            dlc: 'Blood and Wine',
            missable: false,
          },
          chunks: [],
          linked_chunks_count: 0,
          has_guide: false,
        }),
      });
      global.fetch = mockFetch;

      const result = await getTrophyGuideTool.execute({
        game: 'The Witcher 3: Wild Hunt',
        trophy: 'David and Golyat',
      });

      expect(result.status).toBe('found');
      if (result.status === 'found') {
        expect(result.trophy?.dlc).toBe('Blood and Wine');
        expect(result.has_guide).toBe(false);
        expect(result.linked_chunks_count).toBe(0);
      }
    });

    it('returns error/not_found for unindexed game', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        json: async () => ({ detail: "Game 'Silksong' not found in catalog." }),
      });
      global.fetch = mockFetch;

      const result = await getTrophyGuideTool.execute({
        game: 'Silksong',
        trophy: 'Any Trophy',
      });

      expect(result.status).toBe('not_found');
    });
  });

  describe('listTrophiesTool', () => {
    it('has correct tool name and description', () => {
      expect(listTrophiesTool.name).toBe('list_trophies');
      expect(listTrophiesTool.toolDefinition.function.name).toBe('list_trophies');
    });

    it('filters trophies by dlc and detects zero-chunk coverage (N01)', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          game_id: 'the-witcher-3-wild-hunt',
          total: 13,
          has_guide: false,
          linked_chunks_count: 0,
          trophies: [
            { id: 't1', name: 'The Witcher’s Gone South', type: 'bronze', dlc: 'Blood and Wine', missable: false },
            { id: 't2', name: 'David and Golyat', type: 'bronze', dlc: 'Blood and Wine', missable: false },
          ],
        }),
      });
      global.fetch = mockFetch;

      const result = await listTrophiesTool.execute({
        game: 'The Witcher 3: Wild Hunt',
        dlc: 'Blood and Wine',
      });

      expect(result.total).toBe(13);
      expect(result.has_guide).toBe(false);
      expect(result.linked_chunks_count).toBe(0);
      expect(result.trophies[0].name).toBe('The Witcher’s Gone South');
    });

    it('filters missables by location Novigrad (H03)', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          game_id: 'the-witcher-3-wild-hunt',
          total: 3,
          has_guide: true,
          linked_chunks_count: 8,
          trophies: [
            { id: 't1', name: 'Gwent Master', type: 'bronze', location: 'Novigrad', missable: true },
            { id: 't2', name: 'Assassin of Kings', type: 'silver', location: 'Novigrad', missable: true },
            { id: 't3', name: 'The Doppler Effect', type: 'bronze', location: 'Novigrad', missable: true },
          ],
        }),
      });
      global.fetch = mockFetch;

      const result = await listTrophiesTool.execute({
        game: 'The Witcher 3: Wild Hunt',
        location: 'Novigrad',
        missable: true,
      });

      expect(result.total).toBe(3);
      const names = result.trophies.map((t) => t.name);
      expect(names).toContain('Gwent Master');
      expect(names).toContain('Assassin of Kings');
      expect(names).toContain('The Doppler Effect');
    });
  });

  describe('getGameOverviewTool', () => {
    it('has correct tool name and returns game stats', async () => {
      expect(getGameOverviewTool.name).toBe('get_game_overview');
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          game_id: 'the-witcher-3-wild-hunt',
          title: 'The Witcher 3: Wild Hunt',
          difficulty: 7.0,
          hours: 150,
          playthroughs: 1,
          total_trophies: 79,
          by_type: { bronze: 57, silver: 18, gold: 3, platinum: 1 },
          by_dlc: [
            { name: 'Base Game', count: 53, linked_chunks_count: 72 },
            { name: 'Hearts of Stone', count: 13, linked_chunks_count: 4 },
            { name: 'Blood and Wine', count: 13, linked_chunks_count: 0 },
          ],
        }),
      });
      global.fetch = mockFetch;

      const result = await getGameOverviewTool.execute({
        game: 'The Witcher 3: Wild Hunt',
      });

      expect(result.total_trophies).toBe(79);
      expect(result.difficulty).toBe(7.0);
      expect(result.hours).toBe(150);
      expect(result.playthroughs).toBe(1);
      expect(result.by_type.platinum).toBe(1);
    });
  });

  describe('PlatinaAgentRunner Coverage-Based Abstention & Catalog Tools Integration', () => {
    it('triggers coverage-based abstention when querying an unindexed DLC with trophies in catalog (N01)', async () => {
      const runner = new PlatinaAgentRunner();

      // Mock Groq LLM to request list_trophies for Blood and Wine
      const mockCreate = vi
        .fn()
        .mockResolvedValueOnce({
          choices: [
            {
              message: {
                role: 'assistant',
                tool_calls: [
                  {
                    id: 'call_dlc_1',
                    type: 'function',
                    function: {
                      name: 'list_trophies',
                      arguments: JSON.stringify({
                        game: 'The Witcher 3: Wild Hunt',
                        dlc: 'Blood and Wine',
                      }),
                    },
                  },
                ],
              },
            },
          ],
        })
        .mockResolvedValueOnce({
          choices: [
            {
              message: {
                role: 'assistant',
                content: 'Here are the Blood and Wine trophies and instructions to get them: go to Toussaint and kill beasts.',
              },
            },
          ],
        });

      (runner as unknown as { client: { chat: { completions: { create: typeof mockCreate } } } }).client = {
        chat: { completions: { create: mockCreate } },
      };

      // Mock fetch for catalog/trophies returning has_guide: false
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          game_id: 'the-witcher-3-wild-hunt',
          total: 13,
          has_guide: false,
          linked_chunks_count: 0,
          trophies: [
            { id: 't1', name: 'The Witcher’s Gone South', type: 'bronze', dlc: 'Blood and Wine', missable: false },
            { id: 't2', name: 'David and Golyat', type: 'bronze', dlc: 'Blood and Wine', missable: false },
          ],
        }),
      });
      global.fetch = mockFetch;

      const events: Array<{ type: string; content?: string }> = [];
      for await (const event of runner.run('Como pego os troféus do Blood and Wine?')) {
        events.push(event);
      }

      const chunkEvent = events.find((e) => e.type === 'chunk');
      expect(chunkEvent?.content).toBeDefined();
      // Must abstain with fixed message stating catalog knows the trophies but no guide is indexed yet
      expect(chunkEvent?.content).toMatch(/catálogo (contém|possui|conhece).*não há guia indexado/i);
    });

    it('resolves D10 "What Was That?" directly via get_trophy_guide without vector search hallucination', async () => {
      const runner = new PlatinaAgentRunner();

      const mockCreate = vi
        .fn()
        .mockResolvedValueOnce({
          choices: [
            {
              message: {
                role: 'assistant',
                tool_calls: [
                  {
                    id: 'call_d10',
                    type: 'function',
                    function: {
                      name: 'get_trophy_guide',
                      arguments: JSON.stringify({
                        game: 'The Witcher 3: Wild Hunt',
                        trophy: 'What Was That?',
                      }),
                    },
                  },
                ],
              },
            },
          ],
        })
        .mockResolvedValueOnce({
          choices: [
            {
              message: {
                role: 'assistant',
                content: 'To unlock What Was That?, counterattack 10 times consecutively without taking damage.',
              },
            },
          ],
        });

      (runner as unknown as { client: { chat: { completions: { create: typeof mockCreate } } } }).client = {
        chat: { completions: { create: mockCreate } },
      };

      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          status: 'found',
          trophy: {
            id: 'the-witcher-3-wild-hunt-what-was-that',
            name: 'What Was That?',
            type: 'bronze',
            dlc: null,
            missable: false,
          },
          chunks: [
            {
              id: 'c1',
              title: 'What Was That?',
              content: 'Counterattack 10 times consecutively without taking damage or parrying.',
              source_url: 'https://powerpyx.com/witcher3-what-was-that',
              is_missable: false,
            },
          ],
          linked_chunks_count: 1,
          has_guide: true,
        }),
      });
      global.fetch = mockFetch;

      const events: Array<{ type: string; content?: string }> = [];
      for await (const event of runner.run('How to unlock What Was That? in The Witcher 3', { lang: 'en' })) {
        events.push(event);
      }

      const chunkEvent = events.find((e) => e.type === 'chunk');
      expect(chunkEvent?.content).toContain('What Was That?');
      expect(chunkEvent?.content).toMatch(/counterattack 10 times/i);
    });
  });
});
