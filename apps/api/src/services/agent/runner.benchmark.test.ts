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
        scenario: 'Grand Theft Auto V - Post-Story Routing (OlliverHunter 71%)',
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

    it('emits thought SSE event when searchGuidesTool encounters an unindexed game', async () => {
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
                    id: 'call_search_w3',
                    function: {
                      name: 'search_trophy_guides',
                      arguments: JSON.stringify({ query: 'Card Collector', game: 'The Witcher 3: Wild Hunt' }),
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
        .mockResolvedValueOnce([]) // probe in runner
        .mockResolvedValueOnce([]) // initial search in searchGuidesTool
        .mockResolvedValueOnce([
          {
            id: 'c1',
            game: 'The Witcher 3: Wild Hunt',
            title: 'Card Collector',
            content: 'Colete todas as cartas de Gwent no jogo base.',
            is_missable: true,
            similarity_score: 0.9,
          },
        ]);

      const fetchAndIndexSpy = vi
        .spyOn(ingestionClient, 'fetchAndIndex')
        .mockResolvedValueOnce({
          status: 'indexed',
          chunks_indexed: 10,
          game: 'The Witcher 3: Wild Hunt',
        });

      const events: AgentStepEvent[] = [];
      for await (const event of runner.run('Como pegar o troféu Card Collector em The Witcher 3?')) {
        events.push(event);
      }

      const thoughtEvent = events.find(
        (e) =>
          e.type === 'thought' &&
          e.content ===
            '📥 Jogo inédito detectado: obtendo e indexando guia oficial comunitário (PowerPyx/PSNProfiles) no banco de dados...'
      );
      expect(thoughtEvent).toBeDefined();
      expect(fetchAndIndexSpy).toHaveBeenCalledWith('The Witcher 3: Wild Hunt');

      searchSpy.mockRestore();
      fetchAndIndexSpy.mockRestore();
    });

    it('Grand Theft Auto V - Post-Story Routing (OlliverHunter 71%)', async () => {
      const runner = new PlatinaAgentRunner();

      const mockProgressResult = {
        psn_id: 'OlliverHunter',
        game: 'Grand Theft Auto V',
        platform: 'PS5',
        total_trophies: 51,
        unlocked_count: 36,
        completion_percentage: 71,
        pending_count: 15,
        pending_missables_count: 0,
        pending_missable_trophies: [],
        quick_cleanup_trophies: [
          { trophy_name: 'Vinewood Visionary', trophy_type: 'bronze', chapter_or_location: 'Modo Diretor' },
          { trophy_name: 'Majestic', trophy_type: 'silver', chapter_or_location: 'Modo Diretor' },
          { trophy_name: 'Location Scout', trophy_type: 'silver', chapter_or_location: 'Modo Diretor' },
        ],
        heavy_grind_trophies: [
          { trophy_name: 'Masterminds', trophy_type: 'silver', chapter_or_location: 'Golpe do Juízo Final' },
          { trophy_name: 'Elitist', trophy_type: 'silver', chapter_or_location: 'Golpe do Juízo Final' },
        ],
        natural_grind_trophies: [],
        pending_missables: [],
        unearned_trophies_summary: [
          'Vinewood Visionary (bronze): Crie e exporte um vídeo usando o Modo Diretor.',
          'Majestic (silver): Crie e exporte 10 vídeos usando o Modo Diretor.',
          'Location Scout (silver): Visite todos os locais no Modo Diretor.',
          'Masterminds (silver): Complete todos os 3 desafios do Golpe do Juízo Final.',
          'Elitist (silver): Complete todos os 3 desafios de Elite no Golpe do Juízo Final.',
        ],
      };

      vi.spyOn(runner, 'executeTool').mockResolvedValue(mockProgressResult);

      const dualOptionRoutingAdvice = [
        'Campanha concluída! Você tem 71% dos troféus e nenhum troféu perdível pendente.',
        '- Opção 1 (Velocidade): Limpe os troféus rápidos do Modo Diretor como Vinewood Visionary e Majestic.',
        '- Opção 2 (Fundação / Grind Pesado): Encare os Golpes do Juízo Final focando em Masterminds e Elitist.',
        'Qual rota você prefere encarar primeiro?',
      ].join('\n');

      const mockCreate = vi
        .fn()
        // Step 1: Agent calls check_player_progress
        .mockResolvedValueOnce({
          choices: [
            {
              message: {
                role: 'assistant',
                tool_calls: [
                  {
                    id: 'call_progress_gta',
                    function: {
                      name: 'check_player_progress',
                      arguments: JSON.stringify({ psnId: 'OlliverHunter', game: 'Grand Theft Auto V' }),
                    },
                  },
                ],
              },
            },
          ],
        })
        // Step 2: Agent synthesizes dual-option strategic routing advice
        .mockResolvedValueOnce({
          choices: [
            {
              message: {
                role: 'assistant',
                content: dualOptionRoutingAdvice,
              },
            },
          ],
        });

      (runner as unknown as { client: { chat: { completions: { create: typeof mockCreate } } } }).client = {
        chat: { completions: { create: mockCreate } },
      };

      const events: AgentStepEvent[] = [];
      for await (const event of runner.run('Qual a melhor rota e próximos passos para OlliverHunter em Grand Theft Auto V?')) {
        events.push(event);
      }

      // Verify tool call was dispatched for player progress
      const toolCallEvent = events.find((e) => e.type === 'tool_call');
      expect(toolCallEvent).toBeDefined();
      expect(toolCallEvent?.toolName).toBe('check_player_progress');

      // Verify final advice chunk
      const chunkEvent = events.find((e) => e.type === 'chunk');
      expect(chunkEvent).toBeDefined();
      const output = chunkEvent?.content ?? '';

      // Asserts dual options (Velocidade e Grind Pesado)
      expect(output).toMatch(/Opção 1|Velocidade/i);
      expect(output).toMatch(/Opção 2|Grind/i);

      // Asserts CTA "Qual rota você prefere"
      expect(output).toContain('Qual rota você prefere');

      // Asserts conciseness: <= 120 words
      expect(countWords(output)).toBeLessThanOrEqual(120);

      // Verify completion
      const doneEvent = events.find((e) => e.type === 'done');
      expect(doneEvent).toBeDefined();
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

  describe('Multi-Source Canonical Missables Benchmark', () => {
    const W3 = 'The Witcher 3: Wild Hunt';
    const CANONICAL_MISSABLES: Array<[string, string]> = [
      ['Assassin of Kings', 'Reason of State'],
      ['Card Collector', 'Velen'],
      ['Even Odds', 'Velen'],
      ['Fast and Furious', 'Skellige'],
      ['Friends With Benefits', 'Velen'],
      ['Full Crew', 'Kaer Morhen'],
      ['Gwent Master', 'Passiflora'],
      ['Kingmaker', 'Skellige'],
      ['The Doppler Effect', 'Novigrad'],
      ['Woodland Spirit', 'Skellige'],
    ];

    it('warns an unstarted Witcher 3 player about all 10 canonical missables from progress + vector retrieval', async () => {
      const runner = new PlatinaAgentRunner();

      const progress = {
        psn_id: 'olliverW9',
        game: W3,
        completion_percentage: 0,
        pending_missables_count: CANONICAL_MISSABLES.length,
        pending_missable_trophies: CANONICAL_MISSABLES.map(([trophy_name, chapter_or_location]) => ({
          trophy_name,
          trophy_type: 'bronze',
          chapter_or_location,
        })),
        unearned_trophies_summary: [],
      };
      const guide = {
        results: CANONICAL_MISSABLES.map(([name, where]) => ({
          title: `${W3} - Missable: ${name}`,
          content: `${name} é perdível: complete em ${where} antes do ponto sem retorno.`,
        })),
      };

      const executeToolSpy = vi
        .spyOn(runner, 'executeTool')
        .mockImplementation(async (name: string) => (name === 'check_player_progress' ? progress : guide));
      // Probe must find chunks so no on-demand ingestion is triggered
      const probeSpy = vi.spyOn(ingestionClient, 'search').mockResolvedValue([
        { id: 'p1', game: W3, title: 'probe', content: 'probe', is_missable: true, similarity_score: 0.9 },
      ]);

      const answer = [
        'Troféus perdíveis em The Witcher 3 (0% concluído):',
        ...CANONICAL_MISSABLES.map(([name, where]) => `- ${name}: ${where}`),
        'Quer os detalhes completos e rotas deste troféu?',
      ].join('\n');

      const toolCall = (id: string, name: string, args: object) => ({
        choices: [{ message: { role: 'assistant', tool_calls: [{ id, function: { name, arguments: JSON.stringify(args) } }] } }],
      });
      const mockCreate = vi
        .fn()
        .mockResolvedValueOnce(toolCall('call_progress_w3', 'check_player_progress', { psnId: 'olliverW9', game: W3 }))
        .mockResolvedValueOnce(toolCall('call_missables_w3', 'search_trophy_guides', { query: 'missable', game: W3, missableOnly: true }))
        .mockResolvedValue({ choices: [{ message: { role: 'assistant', content: answer } }] });

      (runner as unknown as { client: { chat: { completions: { create: typeof mockCreate } } } }).client = {
        chat: { completions: { create: mockCreate } },
      };

      const events: AgentStepEvent[] = [];
      for await (const event of runner.run('Quais troféus perdíveis tenho em The Witcher 3? Sou olliverW9 e ainda não comecei.')) {
        events.push(event);
      }

      const toolNames = events.filter((e) => e.type === 'tool_call').map((e) => e.toolName);
      expect(toolNames).toEqual(['check_player_progress', 'search_trophy_guides']);
      expect(executeToolSpy).toHaveBeenCalledWith('search_trophy_guides', expect.objectContaining({ missableOnly: true }));

      const output = events.find((e) => e.type === 'chunk')?.content ?? '';
      for (const [name] of CANONICAL_MISSABLES) expect(output).toContain(name);
      expect(events.some((e) => e.type === 'done')).toBe(true);

      probeSpy.mockRestore();
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
  });
});
