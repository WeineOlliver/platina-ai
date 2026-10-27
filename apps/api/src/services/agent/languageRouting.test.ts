// Insight: Language routing tests verify decoupling between internal English tool arguments/queries
// and the user's preferred session language for final answers.
import { describe, it, expect, vi } from 'vitest';
import { PlatinaAgentRunner, type AgentStepEvent } from './runner.js';
import { ingestionClient } from '../ingestionClient.js';

describe('Agent Language Routing & Tool Execution Suite', () => {
  it('translates PT user question into English tool call query and parameters', async () => {
    const runner = new PlatinaAgentRunner();

    const mockCreate = vi.fn().mockResolvedValueOnce({
      choices: [
        {
          message: {
            role: 'assistant',
            content: null,
            tool_calls: [
              {
                id: 'call_translate_1',
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
    }).mockResolvedValueOnce({
      choices: [
        {
          message: {
            role: 'assistant',
            content: 'Para o troféu Card Collector, vença os torneios em Passiflora e colete 120 cartas únicas.',
          },
        },
      ],
    });

    (runner as unknown as { client: { chat: { completions: { create: typeof mockCreate } } } }).client = {
      chat: { completions: { create: mockCreate } },
    };

    const events: AgentStepEvent[] = [];
    for await (const event of runner.run('Como eu pego o troféu de todas as cartas?', {
      game: 'The Witcher 3: Wild Hunt',
      lang: 'pt',
    })) {
      events.push(event);
    }

    const toolCallEvent = events.find((e) => e.type === 'tool_call');
    expect(toolCallEvent).toBeDefined();
    expect(toolCallEvent?.toolName).toBe('search_trophy_guides');
    expect((toolCallEvent?.toolArgs as { query: string }).query).toBe('Card Collector');
    expect((toolCallEvent?.toolArgs as { game: string }).game).toBe('The Witcher 3: Wild Hunt');
  });

  it('delivers final answer strictly in session language (pt vs en)', async () => {
    const runner = new PlatinaAgentRunner();

    // 1. Session with lang: 'pt'
    const mockCreatePt = vi.fn().mockResolvedValueOnce({
      choices: [
        {
          message: {
            role: 'assistant',
            content: 'Olá! Sou o Platina AI, especialista em troféus. Como posso ajudar com sua platina?',
          },
        },
      ],
    });

    (runner as unknown as { client: { chat: { completions: { create: typeof mockCreatePt } } } }).client = {
      chat: { completions: { create: mockCreatePt } },
    };

    const ptEvents: AgentStepEvent[] = [];
    for await (const event of runner.run('olá', { lang: 'pt' })) {
      ptEvents.push(event);
    }
    const ptChunk = ptEvents.find((e) => e.type === 'chunk');
    expect(ptChunk?.content).toContain('Olá! Sou o Platina AI');

    // 2. Session with lang: 'en'
    const mockCreateEn = vi.fn().mockResolvedValueOnce({
      choices: [
        {
          message: {
            role: 'assistant',
            content: 'Hello! I am Platina AI, your trophy hunting guide. How can I help with your platinum?',
          },
        },
      ],
    });

    (runner as unknown as { client: { chat: { completions: { create: typeof mockCreateEn } } } }).client = {
      chat: { completions: { create: mockCreateEn } },
    };

    const enEvents: AgentStepEvent[] = [];
    for await (const event of runner.run('olá', { lang: 'en' })) {
      enEvents.push(event);
    }
    const enChunk = enEvents.find((e) => e.type === 'chunk');
    expect(enChunk?.content).toContain('Hello! I am Platina AI');
  });

  it('searchGuides automatically uses active session game when omitted by the model', async () => {
    const runner = new PlatinaAgentRunner();

    const mockChunk = {
      id: 'chunk_w3_auto_session',
      game: 'The Witcher 3: Wild Hunt',
      title: 'Card Collector Guide',
      content: 'Detailed instructions on Gwent tournaments.',
      is_missable: true,
      similarity_score: 0.95,
      source_url: 'https://psnprofiles.com/guide/2842-the-witcher-3',
    };

    const searchSpy = vi
      .spyOn(ingestionClient as unknown as { searchWithMetrics: (...args: unknown[]) => Promise<unknown> }, 'searchWithMetrics')
      .mockResolvedValueOnce({
        chunks: [mockChunk],
        retrieval_latency_ms: 12,
        reranker_latency_ms: 4,
      });

    const mockCreate = vi.fn().mockResolvedValueOnce({
      choices: [
        {
          message: {
            role: 'assistant',
            content: null,
            // Model calls tool WITHOUT providing "game"
            tool_calls: [
              {
                id: 'call_no_game',
                type: 'function',
                function: {
                  name: 'search_trophy_guides',
                  arguments: JSON.stringify({
                    query: 'Card Collector',
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
            content: 'Troféu: Card Collector no torneio de Passiflora.',
          },
        },
      ],
    });

    (runner as unknown as { client: { chat: { completions: { create: typeof mockCreate } } } }).client = {
      chat: { completions: { create: mockCreate } },
    };

    const events: AgentStepEvent[] = [];
    for await (const event of runner.run('Como pego o troféu Card Collector?', {
      game: 'The Witcher 3: Wild Hunt',
      lang: 'pt',
    })) {
      events.push(event);
    }

    expect(searchSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        game: 'The Witcher 3: Wild Hunt',
        query: 'Card Collector',
      })
    );

    searchSpy.mockRestore();
  });
});
