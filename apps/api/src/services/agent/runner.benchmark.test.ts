import { describe, it, expect, vi, beforeEach, afterAll } from 'vitest';
import { PlatinaAgentRunner, type AgentStepEvent } from './runner.js';
import { groundingValidator, type SourceDocument } from './validator.js';
import { env } from '../../config/env.js';
import { ingestionClient } from '../ingestion/client.js';

function countWords(text: string): number {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

function countBulletPoints(text: string): number {
  return text.split('\n').filter((line) => /^\s*[-*•]\s+/.test(line)).length;
}

describe('Platina AI Agent Runner Benchmark Suite', () => {
  beforeEach(() => {
    // Ensure AI provider allows runner execution during benchmark tests
    process.env.AI_PROVIDER = 'groq';
    (env as unknown as { AI_PROVIDER: string }).AI_PROVIDER = 'groq';
    process.env.OBSERVABILITY_SAMPLING_RATE = '0';
    (env as unknown as { OBSERVABILITY_SAMPLING_RATE: number }).OBSERVABILITY_SAMPLING_RATE = 0;
  });

  afterAll(() => {
    process.env.AI_PROVIDER = 'mock';
    (env as unknown as { AI_PROVIDER: string }).AI_PROVIDER = 'mock';
  });

  describe('Agent Conciseness & Output Format Benchmark', () => {
    const PROGRESSIVE_CTA = 'Quer os detalhes completos e rotas deste troféu?';
    const ROUTING_CTA = 'Qual rota você prefere encarar primeiro?';

    const BENCHMARK_RESPONSES = [
      {
        scenario: 'Bloodborne - Hunter\'s Essence (Missable Weapon)',
        response: [
          'Troféu: Hunter\'s Essence em Central Yharnam.',
          '- Encontre Eileen the Crow no balcão secreto perto do esgoto.',
          '- Ajude Eileen na luta contra Henryk no Túmulo de Oedon antes de Rom.',
          '- Complete a última fase da quest na Grande Catedral para obter a Blade of Mercy.',
          PROGRESSIVE_CTA,
        ].join('\n'),
      },
      {
        scenario: 'Elden Ring - Lança de Gransax (Missable Armament)',
        response: [
          'Troféu: Lança de Gransax em Leyndell, Capital Real.',
          '- Suba na lança monumental dourada fincada no centro da cidade.',
          '- Colete a arma obrigatoriamente antes de derrotar Maliketh em Farum Azula.',
          '- Se Maliketh for derrotado, a capital vira cinzas e a arma torna-se inacessível.',
          PROGRESSIVE_CTA,
        ].join('\n'),
      },
      {
        scenario: 'Grand Theft Auto V - Masterminds (Criminal Mastermind Heist)',
        response: [
          'Troféu: Masterminds no Golpe do Juízo Final.',
          '- Reúna a mesma equipe fixa para todos os 3 Atos de The Doomsday Heist.',
          '- Complete todas as preparações e finais em ordem sem perder nenhuma vida.',
          '- Reinicie imediatamente se alguém morrer antes de o jogo salvar o progresso.',
          PROGRESSIVE_CTA,
        ].join('\n'),
      },
      {
        scenario: 'Grand Theft Auto V - Post-Story Strategic Routing',
        response: [
          'Campanha concluída! Você tem 71% dos troféus e nenhum troféu perdível pendente.',
          '- Opção 1 (Velocidade): Conquiste rapidamente troféus do Modo Diretor como Vinewood Visionary e Majestic.',
          '- Opção 2 (Fundação / Grind Pesado): Encare os Golpes do Juízo Final focando em Masterminds e Elitist.',
          ROUTING_CTA,
        ].join('\n'),
      },
    ];

    it.each(BENCHMARK_RESPONSES)(
      'asserts response for "$scenario" is concise (<= 120 words, max 4 bullets) with CTA',
      ({ response }) => {
        const wordCount = countWords(response);
        const bulletCount = countBulletPoints(response);

        // Conciseness constraints
        expect(wordCount).toBeLessThanOrEqual(120);
        expect(bulletCount).toBeLessThanOrEqual(4);
        expect(bulletCount).toBeGreaterThanOrEqual(2);

        // Progressive disclosure CTA constraint (tactical single trophy or dual-option routing)
        expect(response).toMatch(/Quer os detalhes completos e rotas deste troféu\?|Qual rota você prefere/);
      }
    );
  });

  describe('PlatinaAgentRunner ReAct Execution & Conciseness Benchmark', () => {
    it('executes agent ReAct loop and streams concise tactical advice with CTA', async () => {
      const runner = new PlatinaAgentRunner();

      const mockGuideSources = {
        results: [
          {
            title: "Troféu: Hunter's Essence (Bloodborne)",
            content:
              "Para o troféu Hunter's Essence você deve coletar todas as armas de caçador. Fale com Eileen the Crow em Central Yharnam antes de derrotar Rom para receber a Blade of Mercy.",
          },
        ],
      };

      vi.spyOn(runner, 'executeTool').mockResolvedValue(mockGuideSources);

      // We pass tacticalAnswer which is fully grounded in mockGuideSources
      const tacticalAnswer = [
        "Troféu: Hunter's Essence em Central Yharnam.",
        '- Fale com Eileen the Crow em Central Yharnam antes de derrotar Rom para receber a Blade of Mercy.',
        'Quer os detalhes completos e rotas deste troféu?',
      ].join('\n');

      const correctiveResponse = [
        "Troféu: Hunter's Essence em Central Yharnam.",
        '- Fale com Eileen the Crow antes de derrotar Rom em Central Yharnam para obter a Blade of Mercy.',
        'Quer os detalhes completos e rotas deste troféu?',
      ].join('\n');

      const mockCreate = vi
        .fn()
        // Step 1: LLM decides to search trophy guides
        .mockResolvedValueOnce({
          choices: [
            {
              message: {
                role: 'assistant',
                tool_calls: [
                  {
                    id: 'call_search_1',
                    function: {
                      name: 'search_trophy_guides',
                      arguments: JSON.stringify({ query: 'Blade of Mercy', game: 'Bloodborne' }),
                    },
                  },
                ],
              },
            },
          ],
        })
        // Step 2: LLM receives search result and generates concise grounded advice
        .mockResolvedValueOnce({
          choices: [
            {
              message: {
                role: 'assistant',
                content: tacticalAnswer,
              },
            },
          ],
        })
        // Step 3: Corrective call if pre-flight re-prompts
        .mockResolvedValueOnce({
          choices: [
            {
              message: {
                role: 'assistant',
                content: correctiveResponse,
              },
            },
          ],
        });

      (runner as unknown as { client: { chat: { completions: { create: typeof mockCreate } } } }).client = {
        chat: { completions: { create: mockCreate } },
      };

      const events: AgentStepEvent[] = [];
      for await (const event of runner.run('Como pegar o troféu Hunter\'s Essence em Bloodborne?')) {
        events.push(event);
      }

      // Verify tool call was dispatched
      const toolCallEvent = events.find((e) => e.type === 'tool_call');
      expect(toolCallEvent).toBeDefined();
      expect(toolCallEvent?.toolName).toBe('search_trophy_guides');

      // Verify chunk content
      const chunkEvent = events.find((e) => e.type === 'chunk');
      expect(chunkEvent).toBeDefined();
      const output = chunkEvent?.content ?? '';

      // Assert word count <= 120 words
      expect(countWords(output)).toBeLessThanOrEqual(120);

      // Assert bullet points <= 4
      expect(countBulletPoints(output)).toBeLessThanOrEqual(4);

      // Assert progressive disclosure CTA
      expect(output).toContain('Quer os detalhes completos e rotas deste troféu?');

      // Assert done event
      const doneEvent = events.find((e) => e.type === 'done');
      expect(doneEvent).toBeDefined();
    });

    it('attaches verified sources markdown footer and emits sources event when guide chunks contain source_url', async () => {
      const runner = new PlatinaAgentRunner();

      const mockGuideSources = {
        results: [
          {
            title: 'PowerPyx - Bloodborne Trophy Guide',
            content: 'Para o troféu Hunter\'s Essence você deve coletar todas as armas de caçador em Central Yharnam.',
            source_url: 'https://www.powerpyx.com/bloodborne-trophy-guide',
          },
          {
            title: 'PSNProfiles - Bloodborne Weapons Walkthrough',
            content: 'Fale com Eileen the Crow antes de Rom para obter a Blade of Mercy.',
            source_url: 'https://psnprofiles.com/guide/bloodborne-weapons',
          },
        ],
      };

      vi.spyOn(runner, 'executeTool').mockResolvedValue(mockGuideSources);

      const tacticalAnswer = [
        'Troféu: Hunter\'s Essence em Central Yharnam.',
        '- Fale com Eileen the Crow antes de Rom para obter a Blade of Mercy.',
        'Quer os detalhes completos e rotas deste troféu?',
      ].join('\n');

      const mockCreate = vi.fn()
        .mockResolvedValueOnce({
          choices: [
            {
              message: {
                role: 'assistant',
                tool_calls: [
                  {
                    id: 'call_search_sources_1',
                    function: {
                      name: 'search_trophy_guides',
                      arguments: JSON.stringify({ query: 'Blade of Mercy', game: 'Bloodborne' }),
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
                content: tacticalAnswer,
              },
            },
          ],
        });

      (runner as unknown as { client: { chat: { completions: { create: typeof mockCreate } } } }).client = {
        chat: { completions: { create: mockCreate } },
      };

      const events: AgentStepEvent[] = [];
      for await (const event of runner.run('Como pegar o troféu Hunter\'s Essence em Bloodborne?', { lang: 'pt' })) {
        events.push(event);
      }

      // 1. Verify sources event is emitted with structured metadata
      const sourcesEvent = events.find((e) => e.type === 'sources');
      expect(sourcesEvent).toBeDefined();
      expect(sourcesEvent?.items).toEqual([
        {
          title: 'PowerPyx - Bloodborne Trophy Guide',
          url: 'https://www.powerpyx.com/bloodborne-trophy-guide',
        },
        {
          title: 'PSNProfiles - Bloodborne Weapons Walkthrough',
          url: 'https://psnprofiles.com/guide/bloodborne-weapons',
        },
      ]);

      // 2. Verify chunk content has deterministic markdown footer
      const chunkEvent = events.find((e) => e.type === 'chunk');
      expect(chunkEvent).toBeDefined();
      const output = chunkEvent?.content ?? '';
      expect(output).toContain('**Fontes verificadas:**');
      expect(output).toContain('- [PowerPyx - Bloodborne Trophy Guide](https://www.powerpyx.com/bloodborne-trophy-guide)');
      expect(output).toContain('- [PSNProfiles - Bloodborne Weapons Walkthrough](https://psnprofiles.com/guide/bloodborne-weapons)');
    });

    it('generates English response when lang: "en" is passed', async () => {
      const runner = new PlatinaAgentRunner();

      const mockGuideSources = {
        results: [
          {
            title: "Trophy: Hunter's Essence (Bloodborne)",
            content:
              "For the Hunter's Essence trophy you must collect all hunter weapons. Talk to Eileen the Crow in Central Yharnam before defeating Rom to receive the Blade of Mercy.",
          },
        ],
      };

      vi.spyOn(runner, 'executeTool').mockResolvedValue(mockGuideSources);

      const tacticalAnswerEn = [
        "Trophy: Hunter's Essence in Central Yharnam.",
        "- Talk to Eileen the Crow in Central Yharnam before defeating Rom to obtain the Blade of Mercy.",
        "Would you like the complete details and routes for this trophy?",
      ].join('\n');

      const mockCreate = vi
        .fn()
        // Step 1: LLM decides to search trophy guides
        .mockResolvedValueOnce({
          choices: [
            {
              message: {
                role: 'assistant',
                tool_calls: [
                  {
                    id: 'call_search_en_1',
                    function: {
                      name: 'search_trophy_guides',
                      arguments: JSON.stringify({ query: 'Hunter\'s Essence', game: 'Bloodborne' }),
                    },
                  },
                ],
              },
            },
          ],
        })
        // Step 2: LLM receives search result and generates English tactical advice
        .mockResolvedValueOnce({
          choices: [
            {
              message: {
                role: 'assistant',
                content: tacticalAnswerEn,
              },
            },
          ],
        });

      (runner as unknown as { client: { chat: { completions: { create: typeof mockCreate } } } }).client = {
        chat: { completions: { create: mockCreate } },
      };

      const events: AgentStepEvent[] = [];
      for await (const event of runner.run('How do I get Hunter\'s Essence in Bloodborne?', { lang: 'en' })) {
        events.push(event);
      }

      // Verify system prompt was configured in English
      const firstCallArgs = mockCreate.mock.calls[0][0];
      const systemMessage = firstCallArgs.messages.find((m: { role: string }) => m.role === 'system');
      expect(systemMessage?.content).toContain('You are Platina AI Agent, an autonomous PlayStation trophy hunting specialist.');
      expect(systemMessage?.content).toContain('Would you like the complete details and routes for this trophy?');

      // Verify tool call dispatched
      const toolCallEvent = events.find((e) => e.type === 'tool_call');
      expect(toolCallEvent).toBeDefined();
      expect(toolCallEvent?.toolName).toBe('search_trophy_guides');

      // Verify chunk content in English
      const chunkEvent = events.find((e) => e.type === 'chunk');
      expect(chunkEvent).toBeDefined();
      const output = chunkEvent?.content ?? '';
      expect(output).toContain("Trophy: Hunter's Essence in Central Yharnam.");
      expect(output).toContain('Would you like the complete details and routes for this trophy?');
      expect(countWords(output)).toBeLessThanOrEqual(120);

      const doneEvent = events.find((e) => e.type === 'done');
      expect(doneEvent).toBeDefined();
    });

    it('handles unindexed game in searchGuidesTool without triggering live scraping (pipeline v2)', async () => {
      const runner = new PlatinaAgentRunner();

      const mockCreate = vi.fn().mockResolvedValue({
        choices: [
          {
            message: {
              role: 'assistant',
              content:
                'Troféu: Card Collector em Velen.\n- Colete todas as cartas de Gwent no jogo base.\nQuer os detalhes completos e rotas deste troféu?',
            },
          },
        ],
      });

      (runner as unknown as { client: { chat: { completions: { create: typeof mockCreate } } } }).client = {
        chat: { completions: { create: mockCreate } },
      };

      const searchSpy = vi
        .spyOn(ingestionClient, 'search')
        .mockResolvedValue([]);

      const fetchAndIndexSpy = vi.spyOn(ingestionClient, 'fetchAndIndex');

      const events: AgentStepEvent[] = [];
      for await (const event of runner.run('Como pegar o troféu Card Collector em The Witcher 3?')) {
        events.push(event);
      }

      expect(fetchAndIndexSpy).not.toHaveBeenCalled();

      searchSpy.mockRestore();
      fetchAndIndexSpy.mockRestore();
    });

    it('generates deep walkthrough for Gwent cards with high token limit when detailed guide is requested', async () => {
      const runner = new PlatinaAgentRunner();

      const mockGwentChunks = {
        results: [
          {
            title: 'The Witcher 3: Wild Hunt - Guia de Cartas de Gwent (Card Collector)',
            content: [
              'Troféu Card Collector: Requer coletar todas as cartas de Gwent no jogo base.',
              '1. White Orchard innkeeper: Elsa vende cartas de líderes e unidades antes de sair da região.',
              '2. Zoltan/Baron in Velen: Complete a quest Velen Players derrotando o Barão Sanguinário Phillip Strenger.',
              '3. Dandelion in Vegelbud Masquerade: Durante a quest A Matter of Life and Death no baile de máscaras Vegelbud, vença as 3 rodadas consecutivas.',
              '4. High Stakes tournament in Passiflora em Novigrad com taxa de inscrição de 1000 coroas e baralho forte.',
            ].join('\n'),
          },
        ],
      };

      const executeToolSpy = vi.spyOn(runner, 'executeTool').mockResolvedValue(mockGwentChunks);

      const deepGwentWalkthroughResponse = [
        '# Passo a Passo Detalhado: Troféu Card Collector (The Witcher 3)',
        '',
        'O troféu Card Collector exige a obtenção de todas as cartas de Gwent no jogo base. Abaixo está o roteiro estruturado detalhando cada etapa crítica e os cuidados para não perder cartas perdíveis:',
        '',
        '| Região | Localização e NPC | Missão e Condição | Cuidados e Requisitos |',
        '| --- | --- | --- | --- |',
        '| White Orchard | Elsa na estalagem | Prólogo do jogo | Compre todas as cartas com a White Orchard innkeeper antes de sair da região para não perdê-las. |',
        '| Velen | Barão Sanguinário Phillip Strenger | Velen Players | Jogue contra Zoltan/Baron in Velen durante a missão Velen Players para obter a carta do Barão Sanguinário. |',
        '| Novigrad | Baile no Vegelbud | A Matter of Life and Death | Garanta Dandelion in Vegelbud Masquerade vencendo as 3 rodadas consecutivas no baile. |',
        '| Novigrad | Passiflora | High Stakes | Participe do High Stakes tournament in Passiflora com 1000 coroas e baralho forte para vencer o torneio. |',
        '',
        'Roteiro de Coleta por Região:',
        '- Em White Orchard, compre as cartas de Elsa com a White Orchard innkeeper antes de sair da região.',
        '- Em Velen, vença o Barão Sanguinário Phillip Strenger em Velen Players.',
        '- Em Novigrad, obtenha a carta de Dandelion in Vegelbud Masquerade durante A Matter of Life and Death.',
        '- No torneio de High Stakes tournament in Passiflora, vença todas as partidas decisivas com seu melhor baralho.',
        '',
        'Siga rigorosamente cada localização para assegurar a conquista do troféu Card Collector sem perder nenhuma carta.',
      ].join('\n');

      const mockCreate = vi
        .fn()
        // Step 1: Agent calls search_trophy_guides with limit: 8
        .mockResolvedValueOnce({
          choices: [
            {
              message: {
                role: 'assistant',
                tool_calls: [
                  {
                    id: 'call_search_gwent_deep',
                    function: {
                      name: 'search_trophy_guides',
                      arguments: JSON.stringify({
                        query: 'Card Collector',
                        game: 'The Witcher 3: Wild Hunt',
                        limit: 8,
                      }),
                    },
                  },
                ],
              },
            },
          ],
        })
        // Step 2: Agent synthesizes detailed structured walkthrough
        .mockResolvedValueOnce({
          choices: [
            {
              message: {
                role: 'assistant',
                content: deepGwentWalkthroughResponse,
              },
            },
          ],
        });

      (runner as unknown as { client: { chat: { completions: { create: typeof mockCreate } } } }).client = {
        chat: { completions: { create: mockCreate } },
      };

      const events: AgentStepEvent[] = [];
      const userMessage = 'Como pegar todas as cartas de Gwent em The Witcher 3? Quero um passo a passo detalhado';
      for await (const event of runner.run(userMessage)) {
        events.push(event);
      }

      // Verify tool call dispatched with limit: 8
      const toolCallEvent = events.find((e) => e.type === 'tool_call');
      expect(toolCallEvent).toBeDefined();
      expect(toolCallEvent?.toolName).toBe('search_trophy_guides');
      expect((toolCallEvent?.toolArgs as { limit?: number })?.limit).toBe(8);

      // Verify executeTool received limit: 8
      expect(executeToolSpy).toHaveBeenCalledWith(
        'search_trophy_guides',
        expect.objectContaining({ limit: 8 })
      );

      // Verify system prompt contained deep walkthrough instructions
      const firstCallArgs = mockCreate.mock.calls[0][0];
      const systemMessage = firstCallArgs.messages.find((m: { role: string }) => m.role === 'system');
      expect(systemMessage?.content).toContain('O usuário solicitou um guia detalhado e aprofundado');
      expect(systemMessage?.content).toContain('Você pode usar até 800 palavras');

      // Verify high token limit passed to completions API
      expect(firstCallArgs.max_tokens).toBe(2048);

      // Verify streamed chunk is detailed (> 120 words) and approved by validator
      const chunkEvent = events.find((e) => e.type === 'chunk');
      expect(chunkEvent).toBeDefined();
      const output = chunkEvent?.content ?? '';
      expect(countWords(output)).toBeGreaterThan(120);
      expect(countWords(output)).toBeLessThanOrEqual(800);
      expect(output).toContain('Card Collector');
      expect(output).toContain('Passiflora');
      expect(output).toContain('High Stakes');
      expect(output).toContain('Vegelbud');

      // Verify done event
      const doneEvent = events.find((e) => e.type === 'done');
      expect(doneEvent).toBeDefined();
    });

    it('activates deep walkthrough mode on affirmative follow-up to assistant CTA', async () => {
      const runner = new PlatinaAgentRunner();

      const mockGwentChunks = {
        results: [
          {
            title: 'The Witcher 3: Wild Hunt - Guia de Cartas de Gwent (Card Collector)',
            content: 'Para o troféu Card Collector você deve coletar todas as cartas no jogo base.',
          },
        ],
      };

      vi.spyOn(runner, 'executeTool').mockResolvedValue(mockGwentChunks);

      const mockCreate = vi.fn().mockResolvedValueOnce({
        choices: [
          {
            message: {
              role: 'assistant',
              content: 'Aqui está o guia completo passo a passo...',
            },
          },
        ],
      });

      (runner as unknown as { client: { chat: { completions: { create: typeof mockCreate } } } }).client = {
        chat: { completions: { create: mockCreate } },
      };

      const history = [
        {
          role: 'user' as const,
          content: 'Como pegar o troféu Card Collector em The Witcher 3?',
        },
        {
          role: 'assistant' as const,
          content:
            'Troféu: Card Collector em White Orchard.\nCompre as cartas com Elsa na estalagem antes de sair.\nQuer os detalhes completos e rotas deste troféu?',
        },
      ];

      for await (const _ of runner.run('Sim, manda os detalhes', { history })) {
        // iterate
      }

      // Verify that deep walkthrough system prompt was set for affirmative follow-up
      const firstCallArgs = mockCreate.mock.calls[0][0];
      const systemMessage = firstCallArgs.messages.find((m: { role: string }) => m.role === 'system');
      expect(systemMessage?.content).toContain('O usuário solicitou um guia detalhado e aprofundado');
      expect(firstCallArgs.max_tokens).toBe(2048);
    });
  });


  describe('Pre-Flight Grounding Verification Catches Fabricated Advice', () => {
    it('catches fabricated advice directly with groundingValidator when claims are ungrounded', async () => {
      const realGuideSources: SourceDocument[] = [
        {
          title: 'Elden Ring - Guia de Armas Lendárias',
          content:
            'A Lança de Gransax fica na lança gigante cravada em Leyndell, Capital Real. Ela deve ser coletada antes de derrotar Maliketh em Farum Azula. Após Maliketh, Leyndell vira cinzas.',
        },
      ];

      // Fabricated advice mentioning non-existent location and wrong boss
      const fabricatedAnswer = [
        'Troféu: Lança de Gransax em Caelid.',
        '- Derrote Radahn no Capítulo 5 para obter a lança.',
        'Quer os detalhes completos e rotas deste troféu?',
      ].join('\n');

      const validation = await groundingValidator.validate(fabricatedAnswer, realGuideSources);

      expect(validation.isValid).toBe(false);
      expect(validation.ungroundedClaims.length).toBeGreaterThan(0);
      expect(
        validation.ungroundedClaims.some(
          (c) => c.toLowerCase().includes('caelid') || c.toLowerCase().includes('capítulo 5')
        )
      ).toBe(true);
    });

    it('catches fabricated tactical advice when no source guide chunks were retrieved', async () => {
      const emptySources: SourceDocument[] = [];

      const fabricatedTacticalAnswer = [
        'Troféu: Yharnam Sunrise no Sonho do Caçador.',
        '- Aceite a proposta de Gehrman no final do jogo antes de queimar o workshop.',
        'Quer os detalhes completos e rotas deste troféu?',
      ].join('\n');

      const validation = await groundingValidator.validate(fabricatedTacticalAnswer, emptySources);

      expect(validation.isValid).toBe(false);
      expect(validation.ungroundedClaims.length).toBeGreaterThan(0);
      expect(validation.reason).toContain('sem fontes');
    });

    it('runner pre-flight verification gate intercepts fabricated output and triggers corrective re-prompt', async () => {
      const runner = new PlatinaAgentRunner();

      const retrievedSources = {
        total_results: 1,
        results: [
          {
            title: "Troféu: Hunter's Essence (Bloodborne)",
            content:
              "A Blade of Mercy é obtida através de Eileen the Crow em Central Yharnam antes de derrotar Rom.",
          },
        ],
      };

      vi.spyOn(runner, 'executeTool').mockResolvedValue(retrievedSources);

      const hallucinatedFirstAnswer = [
        "Troféu: Hunter's Essence em Caelid.",
        '- Derrote o chefe Radahn no Capítulo 5 para pegar a Blade of Mercy.',
        'Quer os detalhes completos e rotas deste troféu?',
      ].join('\n');

      const correctedGroundedAnswer = [
        "Troféu: Hunter's Essence em Central Yharnam.",
        '- Fale com Eileen the Crow antes de derrotar Rom em Central Yharnam para obter a Blade of Mercy.',
        'Quer os detalhes completos e rotas deste troféu?',
      ].join('\n');

      const mockCreate = vi
        .fn()
        // Step 1: Tool call search
        .mockResolvedValueOnce({
          choices: [
            {
              message: {
                role: 'assistant',
                tool_calls: [
                  {
                    id: 'call_search_2',
                    function: {
                      name: 'search_trophy_guides',
                      arguments: JSON.stringify({ query: 'Blade of Mercy', game: 'Bloodborne' }),
                    },
                  },
                ],
              },
            },
          ],
        })
        // Step 2: Model returns hallucinated answer
        .mockResolvedValueOnce({
          choices: [
            {
              message: {
                role: 'assistant',
                content: hallucinatedFirstAnswer,
              },
            },
          ],
        })
        // Step 3: Pre-flight validator catches fabrication and issues corrective prompt
        .mockResolvedValueOnce({
          choices: [
            {
              message: {
                role: 'assistant',
                content: correctedGroundedAnswer,
              },
            },
          ],
        });

      (runner as unknown as { client: { chat: { completions: { create: typeof mockCreate } } } }).client = {
        chat: { completions: { create: mockCreate } },
      };

      const events: AgentStepEvent[] = [];
      for await (const event of runner.run('Como pegar o troféu Hunter\'s Essence?')) {
        events.push(event);
      }

      // Assert corrective re-prompt was called
      expect(mockCreate).toHaveBeenCalledTimes(3);
      const correctiveCallArgs = mockCreate.mock.calls[2][0];
      const correctiveMessages = correctiveCallArgs.messages;
      const lastMessage = correctiveMessages[correctiveMessages.length - 1];

      expect(lastMessage.role).toBe('user');
      expect(lastMessage.content).toContain('A resposta anterior continha afirmações não sustentadas pelo guia');

      // The final chunk delivered to the user must be the corrected, grounded answer
      const chunkEvent = events.find((e) => e.type === 'chunk');
      expect(chunkEvent?.content).toBe(correctedGroundedAnswer);
      expect(chunkEvent?.content).not.toContain('Caelid');
      expect(chunkEvent?.content).not.toContain('Radahn');
      expect(chunkEvent?.content).toContain('Central Yharnam');
      expect(chunkEvent?.content).toContain('Quer os detalhes completos e rotas deste troféu?');
    });

    it('returns English ungrounded fallback when no guide found for specific trophy query', async () => {
      const runner = new PlatinaAgentRunner();

      const emptyResults = {
        total_results: 0,
        results: [],
      };

      vi.spyOn(runner, 'executeTool').mockResolvedValue(emptyResults);

      const hallucinatedAnswer = [
        "Trophy: Mystery Armament in Unknown Land.",
        "- Defeat the boss at Level 99 to unlock this weapon.",
        "Would you like the complete details and routes for this trophy?",
      ].join('\n');

      const mockCreate = vi
        .fn()
        .mockResolvedValueOnce({
          choices: [
            {
              message: {
                role: 'assistant',
                tool_calls: [
                  {
                    id: 'call_search_en_empty',
                    function: {
                      name: 'search_trophy_guides',
                      arguments: JSON.stringify({ query: 'Mystery Armament', game: 'Bloodborne' }),
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
                content: hallucinatedAnswer,
              },
            },
          ],
        });

      (runner as unknown as { client: { chat: { completions: { create: typeof mockCreate } } } }).client = {
        chat: { completions: { create: mockCreate } },
      };

      const events: AgentStepEvent[] = [];
      for await (const event of runner.run('How to unlock Mystery Armament trophy?', { lang: 'en' })) {
        events.push(event);
      }

      const chunkEvent = events.find((e) => e.type === 'chunk');
      expect(chunkEvent?.content).toBe(
        'Official guide not found for this objective.\nWould you like me to search complementary sources?'
      );
    });
  });
});
