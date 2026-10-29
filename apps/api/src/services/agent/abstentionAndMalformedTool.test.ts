// Insight: Suite testing guaranteed abstention and recovery from malformed tool calls
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { PlatinaAgentRunner, type AgentStepEvent } from './runner.js';
import { ingestionClient } from '../ingestionClient.js';
import { telemetryService } from '../observability/telemetry.js';

describe('Agent Abstention & Tool Call Robustness Suite', () => {
  beforeEach(() => {
    vi.spyOn(telemetryService, 'shouldSample').mockReturnValue(false);
  });
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

  it('forces tool_choice required on the first LLM call for game/trophy questions (V05 / V07)', async () => {
    // Insight: Camino 1 — V05 and V07 cases enforce tool_choice 'required' on step 1
    const runner = new PlatinaAgentRunner();

    const mockCreate = vi.fn().mockResolvedValue({
      choices: [
        {
          message: {
            role: 'assistant',
            content: null,
            tool_calls: [
              {
                id: 'call_v05',
                type: 'function',
                function: {
                  name: 'search_trophy_guides',
                  arguments: JSON.stringify({
                    query: 'ignite gas dragon dream',
                    game: 'The Witcher 3: Wild Hunt',
                  }),
                },
              },
            ],
          },
        },
      ],
    });

    (runner as unknown as { client: { chat: { completions: { create: typeof mockCreate } } } }).client = {
      chat: { completions: { create: mockCreate } },
    };

    // Test V05: 'Tem troféu de explodir gás?'
    const eventsV05: AgentStepEvent[] = [];
    for await (const event of runner.run('Tem troféu de explodir gás?', {
      game: 'The Witcher 3: Wild Hunt',
      lang: 'pt',
    })) {
      eventsV05.push(event);
      if (event.type === 'tool_call') break;
    }

    expect(mockCreate).toHaveBeenCalled();
    const firstCallArgsV05 = mockCreate.mock.calls[0][0];
    expect(firstCallArgsV05.tool_choice).toBe('required');

    // Test V07: 'Tem troféu de juntar bônus de pontos de poder?'
    mockCreate.mockClear();
    for await (const event of runner.run('Tem troféu de juntar bônus de pontos de poder?', {
      game: 'The Witcher 3: Wild Hunt',
      lang: 'pt',
    })) {
      if (event.type === 'tool_call') break;
    }

    const firstCallArgsV07 = mockCreate.mock.calls[0][0];
    expect(firstCallArgsV07.tool_choice).toBe('required');
  });

  it('guarantees fixed abstention when response is generated without any successful context tool call', async () => {
    // Insight: Camino 2 — Final guard returns fixed abstention message when zero context is collected
    const runner = new PlatinaAgentRunner();

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
                id: 'call_search_empty',
                type: 'function',
                function: {
                  name: 'search_trophy_guides',
                  arguments: JSON.stringify({
                    query: 'nonexistent secret trophy',
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
            content: 'Aqui está uma dica inventada sem fontes reais.',
          },
        },
      ],
    });

    (runner as unknown as { client: { chat: { completions: { create: typeof mockCreate } } } }).client = {
      chat: { completions: { create: mockCreate } },
    };

    const events: AgentStepEvent[] = [];
    for await (const event of runner.run('Como pego o troféu secreto inventado?', {
      game: 'The Witcher 3: Wild Hunt',
      lang: 'pt',
    })) {
      events.push(event);
    }

    const chunkEvent = events.find((e) => e.type === 'chunk');
    expect(chunkEvent).toBeDefined();
    expect(chunkEvent?.content).toContain('Guia oficial não encontrado para este objetivo no banco de dados');
    expect(chunkEvent?.content).not.toContain('dica inventada');
  });

  it('retries once on empty final response and returns fixed temporary failure if still empty', async () => {
    // Insight: Camino 3 — Empty final response triggers 1x retry; if it persists, returns fixed temporary failure
    const runner = new PlatinaAgentRunner();

    const chunkData = [
      {
        id: 'c1',
        game: 'The Witcher 3: Wild Hunt',
        title: 'Power Overwhelming',
        content: 'Have all Place of Power bonuses active simultaneously.',
        is_missable: false,
        source_url: 'https://example.com/guide',
        similarity_score: 0.9,
      },
    ];
    vi.spyOn(ingestionClient, 'searchWithMetrics').mockResolvedValue({
      chunks: chunkData,
      retrieval_latency_ms: 5,
      reranker_latency_ms: 2,
    });
    vi.spyOn(ingestionClient, 'search').mockResolvedValue(chunkData);

    const mockCreate = vi.fn()
      // Call 1: tool call
      .mockResolvedValueOnce({
        choices: [
          {
            message: {
              role: 'assistant',
              content: null,
              tool_calls: [
                {
                  id: 'call_power',
                  type: 'function',
                  function: {
                    name: 'search_trophy_guides',
                    arguments: JSON.stringify({
                      query: 'Power Overwhelming',
                      game: 'The Witcher 3: Wild Hunt',
                    }),
                  },
                },
              ],
            },
          },
        ],
      })
      // Call 2: empty answer
      .mockResolvedValueOnce({
        choices: [
          {
            message: {
              role: 'assistant',
              content: '',
            },
          },
        ],
      })
      // Call 3: retry also empty
      .mockResolvedValueOnce({
        choices: [
          {
            message: {
              role: 'assistant',
              content: '   ',
            },
          },
        ],
      });

    (runner as unknown as { client: { chat: { completions: { create: typeof mockCreate } } } }).client = {
      chat: { completions: { create: mockCreate } },
    };

    const events: AgentStepEvent[] = [];
    for await (const event of runner.run('Como pego o troféu Power Overwhelming?', {
      game: 'The Witcher 3: Wild Hunt',
      lang: 'pt',
    })) {
      events.push(event);
    }

    const chunkEvent = events.find((e) => e.type === 'chunk');
    expect(chunkEvent).toBeDefined();
    // Must never return empty to user, instead return fixed temporary failure
    expect(chunkEvent?.content).toContain('Falha temporária no serviço');
    expect(mockCreate).toHaveBeenCalledTimes(3);
  });
});
