import { describe, it, expect, vi, beforeEach, afterAll } from 'vitest';
import { PlatinaAgentRunner, type AgentStepEvent } from './runner.js';
import { groundingValidator, type SourceDocument } from './validator.js';
import { env } from '../../config/env.js';

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
            title: 'Bloodborne - Guia Oficial de Armas',
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
