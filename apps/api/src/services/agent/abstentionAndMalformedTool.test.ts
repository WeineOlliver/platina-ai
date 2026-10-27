// Insight: Suite testing guaranteed abstention and recovery from malformed tool calls
import { describe, it, expect, vi } from 'vitest';
import { PlatinaAgentRunner, type AgentStepEvent } from './runner.js';
import { ingestionClient } from '../ingestionClient.js';

describe('Agent Abstention & Tool Call Robustness Suite', () => {
  it('guarantees fixed abstention message without freeform LLM generation when game is unindexed', async () => {
    process.env.PLATINA_DISABLE_LIVE_SCRAPING = 'true';
    const runner = new PlatinaAgentRunner();

    // Mock search returning empty array (unindexed game)
    vi.spyOn(ingestionClient, 'searchWithMetrics').mockResolvedValue({
      chunks: [],
      retrieval_latency_ms: 5,
      reranker_latency_ms: 2,
    });
    vi.spyOn(ingestionClient, 'search').mockResolvedValue([]);

    const mockCreate = vi.fn().mockResolvedValueOnce({
      choices: [
        {
          message: {
            role: 'assistant',
            content: null,
            tool_calls: [
              {
                id: 'call_unindexed_1',
                type: 'function',
                function: {
                  name: 'search_trophy_guides',
                  arguments: JSON.stringify({
                    query: 'Platinum Guide',
                    game: 'Hollow Knight Silksong',
                  }),
                },
              },
            ],
          },
        },
      ],
    }).mockResolvedValueOnce({
      choices: [
        {
          message: {
            role: 'assistant',
            // LLM attempts freeform generation despite zero guide chunks
            content: 'Você deve derrotar todos os chefes em Pharloom e coletar todas as relics.',
          },
        },
      ],
    });

    (runner as unknown as { client: { chat: { completions: { create: typeof mockCreate } } } }).client = {
      chat: { completions: { create: mockCreate } },
    };

    const events: AgentStepEvent[] = [];
    for await (const event of runner.run('Como platinar Hollow Knight Silksong?', { lang: 'pt' })) {
      events.push(event);
    }

    const chunkEvent = events.find((e) => e.type === 'chunk');
    expect(chunkEvent).toBeDefined();
    // Must strictly return the fixed abstention message, ignoring the LLM freeform text
    expect(chunkEvent?.content).toContain('Guia oficial não encontrado para este objetivo no banco de dados');
    expect(chunkEvent?.content).not.toContain('Pharloom');
  });

  it('abstains with fixed message when querying nonexistent trophy in an indexed game without confusing similar trophies', async () => {
    const runner = new PlatinaAgentRunner();

    vi.spyOn(ingestionClient, 'searchWithMetrics').mockResolvedValue({
      chunks: [],
      retrieval_latency_ms: 5,
      reranker_latency_ms: 2,
    });
    // Indexed game check succeeds for Witcher 3
    vi.spyOn(ingestionClient, 'search').mockResolvedValueOnce([]).mockResolvedValueOnce([{ id: 'c1', title: 'Trophy' }] as never);

    const mockCreate = vi.fn().mockResolvedValueOnce({
      choices: [
        {
          message: {
            role: 'assistant',
            content: null,
            tool_calls: [
              {
                id: 'call_fake_trophy',
                type: 'function',
                function: {
                  name: 'search_trophy_guides',
                  arguments: JSON.stringify({
                    query: 'Gwent Grandmaster',
                    game: 'The Witcher 3: Wild Hunt',
                  }),
                },
              },
            ],
          },
        },
      ],
    }).mockResolvedValueOnce({
      choices: [
        {
          message: {
            role: 'assistant',
            // Freeform hallucination confusing Grandmaster with Master
            content: 'O troféu Gwent Grandmaster exige vencer o torneio em Passiflora.',
          },
        },
      ],
    });

    (runner as unknown as { client: { chat: { completions: { create: typeof mockCreate } } } }).client = {
      chat: { completions: { create: mockCreate } },
    };

    const events: AgentStepEvent[] = [];
    for await (const event of runner.run('Como pego o troféu Gwent Grandmaster?', {
      game: 'The Witcher 3: Wild Hunt',
      lang: 'pt',
    })) {
      events.push(event);
    }

    const chunkEvent = events.find((e) => e.type === 'chunk');
    expect(chunkEvent?.content).toContain('Guia oficial não encontrado para este objetivo no banco de dados');
    expect(chunkEvent?.content).not.toContain('Passiflora');
  });

  it('retries gracefully upon receiving malformed tool call name from the provider', async () => {
    const runner = new PlatinaAgentRunner();

    // 1st LLM call throws malformed tool name error (e.g. from Groq syntax corruption)
    // 2nd LLM call succeeds with valid tool call
    const mockCreate = vi
      .fn()
      .mockRejectedValueOnce(
        new Error(
          'Tool call validation failed: attempted to call tool "search_trophy_guides<|channel|>commentary" which was not in request.tools'
        )
      )
      .mockResolvedValueOnce({
        choices: [
          {
            message: {
              role: 'assistant',
              content: null,
              tool_calls: [
                {
                  id: 'call_valid_retry',
                  type: 'function',
                  function: {
                    name: 'search_trophy_guides',
                    arguments: JSON.stringify({
                      query: 'Card Collector',
                      game: 'The Witcher 3: Wild Hunt',
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
              content: 'Card Collector guide instructions.',
            },
          },
        ],
      });

    (runner as unknown as { client: { chat: { completions: { create: typeof mockCreate } } } }).client = {
      chat: { completions: { create: mockCreate } },
    };

    const events: AgentStepEvent[] = [];
    for await (const event of runner.run('Como pego Card Collector?', {
      game: 'The Witcher 3: Wild Hunt',
      lang: 'pt',
    })) {
      events.push(event);
    }

    // Must have retried and yielded the valid tool call
    const toolCallEvent = events.find((e) => e.type === 'tool_call');
    expect(toolCallEvent).toBeDefined();
    expect(toolCallEvent?.toolName).toBe('search_trophy_guides');
  });
});
