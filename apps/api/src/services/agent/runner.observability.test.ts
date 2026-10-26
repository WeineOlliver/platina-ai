import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { PlatinaAgentRunner } from './runner.js';
import { telemetryService } from '../observability/telemetry.js';
import { SearchGuidesTool } from './tools/searchGuides.js';

describe('PlatinaAgentRunner Observability Suite', () => {
  beforeEach(() => {
    telemetryService.clear();
    process.env.AI_PROVIDER = 'groq';
    process.env.GROQ_API_KEY = 'mock_key_for_telemetry_test';
  });

  afterEach(() => {
    telemetryService.clear();
    vi.restoreAllMocks();
  });

  it('records telemetry metrics with LLM and total latencies upon runner completion', async () => {
    const runner = new PlatinaAgentRunner();

    const mockCreate = vi.fn().mockImplementation(async () => {
      // Simulate small LLM inference delay
      await new Promise((resolve) => setTimeout(resolve, 15));
      return {
        id: 'chatcmpl_telemetry_1',
        choices: [
          {
            index: 0,
            message: {
              role: 'assistant',
              content: 'Olá! Posso ajudar com a sua platina.',
              tool_calls: undefined,
            },
            finish_reason: 'stop',
          },
        ],
      };
    });

    (runner as unknown as { client: { chat: { completions: { create: typeof mockCreate } } } }).client = {
      chat: { completions: { create: mockCreate } },
    } as unknown as { chat: { completions: { create: typeof mockCreate } } };

    const events: unknown[] = [];
    for await (const event of runner.run('Olá, como você funciona?', { game: 'Bloodborne' })) {
      events.push(event);
    }

    const records = telemetryService.getRecords();
    expect(records.length).toBe(1);

    const record = records[0];
    expect(record.game).toBe('Bloodborne');
    expect(record.queryPreview).toBe('Olá, como você funciona?');
    expect(record.modelName).toBeDefined();
    expect(record.llmLatencyMs).toBeGreaterThan(0);
    expect(record.totalLatencyMs).toBeGreaterThanOrEqual(record.llmLatencyMs);
  });

  it('captures retrieval and reranker latency from searchGuidesTool execution', async () => {
    const runner = new PlatinaAgentRunner();

    const mockGuideResult = {
      results: [
        {
          id: 'chunk_bloodborne_1',
          game: 'Bloodborne',
          title: 'Hunter Essence',
          content: 'Coletar todas as armas de caçador em Yharnam.',
          is_missable: false,
          similarity_score: 0.95,
          source_url: 'https://psnprofiles.com/guide/bloodborne',
        },
      ],
      retrieval_latency_ms: 125,
      reranker_latency_ms: 42,
    };

    vi.spyOn(runner, 'executeTool').mockResolvedValue(mockGuideResult);

    let callCount = 0;
    const mockCreate = vi.fn().mockImplementation(async () => {
      callCount++;
      if (callCount === 1) {
        return {
          id: 'chatcmpl_step_1',
          choices: [
            {
              index: 0,
              message: {
                role: 'assistant',
                content: null,
                tool_calls: [
                  {
                    id: 'call_search_1',
                    type: 'function',
                    function: {
                      name: SearchGuidesTool.name,
                      arguments: JSON.stringify({ query: 'Hunter Essence', game: 'Bloodborne' }),
                    },
                  },
                ],
              },
              finish_reason: 'tool_calls',
            },
          ],
        };
      }

      return {
        id: 'chatcmpl_step_2',
        choices: [
          {
            index: 0,
            message: {
              role: 'assistant',
              content: 'Para obter o Hunter Essence, colete todas as armas de caçador em Yharnam.',
              tool_calls: undefined,
            },
            finish_reason: 'stop',
          },
        ],
      };
    });

    (runner as unknown as { client: { chat: { completions: { create: typeof mockCreate } } } }).client = {
      chat: { completions: { create: mockCreate } },
    } as unknown as { chat: { completions: { create: typeof mockCreate } } };

    for await (const _ of runner.run('Como pegar o troféu Hunter Essence em Bloodborne?')) {
      // iterate generator
    }

    const records = telemetryService.getRecords();
    expect(records.length).toBe(1);

    const record = records[0];
    expect(record.retrievalLatencyMs).toBe(125);
    expect(record.rerankerLatencyMs).toBe(42);
    expect(record.game).toBe('Bloodborne');
  });

  it('triggers asynchronous quality evaluation when sampled for quality', async () => {
    const runner = new PlatinaAgentRunner();

    vi.spyOn(telemetryService, 'shouldSample').mockReturnValue(true);

    const mockCreate = vi.fn().mockImplementation(async () => {
      return {
        id: 'chatcmpl_sample_1',
        choices: [
          {
            index: 0,
            message: {
              role: 'assistant',
              content: 'Guia oficial não encontrado para este objetivo. Quer que eu procure em fontes complementares?',
              tool_calls: undefined,
            },
            finish_reason: 'stop',
          },
        ],
      };
    });

    (runner as unknown as { client: { chat: { completions: { create: typeof mockCreate } } } }).client = {
      chat: { completions: { create: mockCreate } },
    } as unknown as { chat: { completions: { create: typeof mockCreate } } };

    for await (const _ of runner.run('Como acho o troféu X em Jogo Desconhecido?')) {
      // iterate generator to completion
    }

    const records = telemetryService.getRecords();
    expect(records.length).toBe(1);
    expect(records[0].sampledForQuality).toBe(true);

    // Wait a brief microtask tick for async background evaluation to settle
    await new Promise((resolve) => setTimeout(resolve, 80));

    const updatedRecord = telemetryService.getRecords()[0];
    expect(typeof updatedRecord.faithfulnessScore).toBe('number');
    expect(typeof updatedRecord.contextRelevanceScore).toBe('number');
    expect(typeof updatedRecord.answerRelevanceScore).toBe('number');
  });

  it('skips quality evaluation when shouldSample returns false', async () => {
    const runner = new PlatinaAgentRunner();

    vi.spyOn(telemetryService, 'shouldSample').mockReturnValue(false);

    const mockCreate = vi.fn().mockImplementation(async () => {
      return {
        id: 'chatcmpl_nosample_1',
        choices: [
          {
            index: 0,
            message: {
              role: 'assistant',
              content: 'Olá! Como posso ajudar?',
              tool_calls: undefined,
            },
            finish_reason: 'stop',
          },
        ],
      };
    });

    (runner as unknown as { client: { chat: { completions: { create: typeof mockCreate } } } }).client = {
      chat: { completions: { create: mockCreate } },
    } as unknown as { chat: { completions: { create: typeof mockCreate } } };

    for await (const _ of runner.run('Olá assistente!')) {
      // iterate
    }

    const records = telemetryService.getRecords();
    expect(records.length).toBe(1);
    expect(records[0].sampledForQuality).toBe(false);

    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(records[0].faithfulnessScore).toBeUndefined();
  });
});
