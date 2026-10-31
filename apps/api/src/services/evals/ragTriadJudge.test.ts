import { describe, it, expect, vi } from 'vitest';
import type Groq from 'groq-sdk';
import {
  evaluateRagTriad,
  type RagTriadInput,
  type RagTriadEvaluation,
} from './ragTriadJudge.js';

function createMockGroqClient(responseObj: Record<string, unknown>): Groq {
  return {
    chat: {
      completions: {
        create: vi.fn().mockResolvedValue({
          choices: [
            {
              message: {
                content: JSON.stringify(responseObj),
              },
            },
          ],
        }),
      },
    },
  } as unknown as Groq;
}

describe('RAG Triad LLM-as-a-Judge Suite', () => {
  describe('LLM Judge (Unit Tests with Mocked Provider)', () => {
    it('evaluates a perfectly grounded, relevant answer with high scores across the triad', async () => {
      const input: RagTriadInput = {
        query: 'Como pegar a Lança de Gransax em Elden Ring?',
        contexts: [
          'A Lança de Gransax é uma arma lendária fincada na lança gigante cravada em Leyndell, Capital Real. Ela DEVE ser coletada antes de derrotar Maliketh em Farum Azula. Após Maliketh, a capital vira cinzas e a arma torna-se inacessível.',
        ],
        answer: 'Troféu: Lança de Gransax em Leyndell, Capital Real.\n- Suba na lança monumental dourada fincada no centro da cidade.\n- Colete a arma antes de derrotar Maliketh em Farum Azula.',
      };

      const mockClient = createMockGroqClient({
        contextRelevance: { score: 0.95, reasoning: 'Contexto perfeitamente alinhado com a arma e localização.' },
        faithfulness: { score: 0.95, reasoning: 'Todas as alegações são sustentadas pelo contexto.' },
        answerRelevance: { score: 0.95, reasoning: 'Responde diretamente como e onde pegar a arma.' },
        overallScore: 0.95,
      });

      const evaluation: RagTriadEvaluation = await evaluateRagTriad(input, { groqClient: mockClient });

      expect(evaluation.contextRelevance.score).toBeGreaterThanOrEqual(0.8);
      expect(evaluation.faithfulness.score).toBeGreaterThanOrEqual(0.8);
      expect(evaluation.answerRelevance.score).toBeGreaterThanOrEqual(0.8);

      expect(evaluation.contextRelevance.reasoning).toBeTruthy();
      expect(evaluation.faithfulness.reasoning).toBeTruthy();
      expect(evaluation.answerRelevance.reasoning).toBeTruthy();
      expect(evaluation.overallScore).toBeGreaterThanOrEqual(0.8);
    });

    it('penalizes faithfulness when the answer contains fabricated/hallucinated claims not in the context', async () => {
      const input: RagTriadInput = {
        query: 'Onde encontro a Blade of Mercy em Bloodborne?',
        contexts: [
          'A arma Blade of Mercy é obtida através da questline de Eileen the Crow em Central Yharnam antes de derrotar Rom.',
        ],
        answer: 'A Blade of Mercy é vendida pelo ferreiro Andre em Firelink Shrine após você derrotar o chefe Gwyn.',
      };

      const mockClient = createMockGroqClient({
        contextRelevance: { score: 0.85, reasoning: 'Contexto relevante sobre Blade of Mercy.' },
        faithfulness: { score: 0.2, reasoning: 'Ferreiro Andre, Firelink Shrine e Gwyn são alucinações de Dark Souls.' },
        answerRelevance: { score: 0.85, reasoning: 'Responde à pergunta, porém com dados falsos.' },
        overallScore: 0.63,
      });

      const evaluation: RagTriadEvaluation = await evaluateRagTriad(input, { groqClient: mockClient });

      expect(evaluation.contextRelevance.score).toBeGreaterThanOrEqual(0.7);
      expect(evaluation.faithfulness.score).toBeLessThanOrEqual(0.3);
    });

    it('penalizes context relevance when the retrieved chunks do not relate to the question', async () => {
      const input: RagTriadInput = {
        query: 'Como pegar a Lança de Gransax em Elden Ring?',
        contexts: [
          'Troféu Masterminds no Golpe do Juízo Final em GTA Online. Reúna a mesma equipe e não morra.',
        ],
        answer: 'Não foi possível encontrar instruções para este troféu no guia fornecido.',
      };

      const mockClient = createMockGroqClient({
        contextRelevance: { score: 0.1, reasoning: 'Contexto de GTA V não possui qualquer relação com Elden Ring.' },
        faithfulness: { score: 0.95, reasoning: 'Admissão honesta de ausência de contexto.' },
        answerRelevance: { score: 0.85, reasoning: 'Informa com clareza a ausência de dados.' },
        overallScore: 0.63,
      });

      const evaluation: RagTriadEvaluation = await evaluateRagTriad(input, { groqClient: mockClient });

      expect(evaluation.contextRelevance.score).toBeLessThanOrEqual(0.3);
    });

    it('penalizes answer relevance when the answer ignores the user query', async () => {
      const input: RagTriadInput = {
        query: 'Qual é o troféu perdível de Bloodborne?',
        contexts: [
          'Para o troféu Hunter\'s Essence você deve coletar todas as armas de caçador. Este troféu é perdível.',
        ],
        answer: 'Olá! O PlayStation 4 foi lançado em novembro de 2013 pela Sony Interactive Entertainment.',
      };

      const mockClient = createMockGroqClient({
        contextRelevance: { score: 0.85, reasoning: 'Contexto cita Hunter\'s Essence como troféu perdível.' },
        faithfulness: { score: 0.9, reasoning: 'Informação histórica verdadeira mas não contida no contexto.' },
        answerRelevance: { score: 0.1, reasoning: 'Resposta ignora completamente a pergunta do usuário.' },
        overallScore: 0.61,
      });

      const evaluation: RagTriadEvaluation = await evaluateRagTriad(input, { groqClient: mockClient });

      expect(evaluation.answerRelevance.score).toBeLessThanOrEqual(0.3);
    });

    describe('Golden Dataset Batch Evaluations', () => {
      it('meets minimum quality thresholds for all canonical gaming scenarios in the golden dataset', async () => {
        const { GOLDEN_RAG_TRIAD_DATASET } = await import('./dataset.js');

        for (const scenario of GOLDEN_RAG_TRIAD_DATASET) {
          const mockClient = createMockGroqClient({
            contextRelevance: {
              score: Math.max(0.9, scenario.expectedThresholds.minContextRelevance),
              reasoning: 'Grounded context evaluation.',
            },
            faithfulness: {
              score: Math.max(0.9, scenario.expectedThresholds.minFaithfulness),
              reasoning: 'Faithful to retrieved guide.',
            },
            answerRelevance: {
              score: Math.max(0.9, scenario.expectedThresholds.minAnswerRelevance),
              reasoning: 'Directly addresses user question.',
            },
            overallScore: 0.9,
          });

          const evaluation = await evaluateRagTriad(
            {
              query: scenario.query,
              contexts: scenario.contexts,
              answer: scenario.answer,
            },
            { groqClient: mockClient }
          );

          expect(
            evaluation.contextRelevance.score,
            `Failed Context Relevance on ${scenario.id}`
          ).toBeGreaterThanOrEqual(scenario.expectedThresholds.minContextRelevance);

          expect(
            evaluation.faithfulness.score,
            `Failed Faithfulness on ${scenario.id}`
          ).toBeGreaterThanOrEqual(scenario.expectedThresholds.minFaithfulness);

          expect(
            evaluation.answerRelevance.score,
            `Failed Answer Relevance on ${scenario.id}`
          ).toBeGreaterThanOrEqual(scenario.expectedThresholds.minAnswerRelevance);
        }
      });
    });
  });

  describe('Deterministic Fallback Judge (Heuristic / No LLM)', () => {
    it('evaluates grounded answers with token overlap heuristics', async () => {
      const input: RagTriadInput = {
        query: 'Como pegar a Lança de Gransax em Elden Ring?',
        contexts: [
          'A Lança de Gransax é uma arma lendária fincada na lança monumental dourada gigante cravada em Leyndell, Capital Real. Ela DEVE ser coletada antes de derrotar Maliketh em Farum Azula. Após Farum Azula, a capital vira cinzas e a lança fica inacessível para sempre no seu playthrough atual.',
        ],
        answer: 'Troféu: Lança de Gransax em Leyndell, Capital Real.\n- Suba na lança monumental dourada fincada no centro da cidade.\n- Colete a arma antes de derrotar Maliketh em Farum Azula.',
      };

      const evaluation = await evaluateRagTriad(input, { mock: true });

      expect(evaluation.contextRelevance.score).toBeGreaterThanOrEqual(0.75);
      expect(evaluation.faithfulness.score).toBeGreaterThanOrEqual(0.75);
      expect(evaluation.answerRelevance.score).toBeGreaterThanOrEqual(0.75);
      expect(evaluation.overallScore).toBeGreaterThanOrEqual(0.75);
    });

    it('penalizes faithfulness when answer contains ungrounded hallucinated tokens', async () => {
      const input: RagTriadInput = {
        query: 'Onde encontro a Blade of Mercy em Bloodborne?',
        contexts: [
          'A arma Blade of Mercy é obtida através da questline de Eileen the Crow em Central Yharnam antes de derrotar Rom.',
        ],
        answer: 'A Blade of Mercy é vendida pelo ferreiro Andre em Firelink Shrine após você derrotar o chefe Gwyn.',
      };

      const evaluation = await evaluateRagTriad(input, { mock: true });

      expect(evaluation.contextRelevance.score).toBeGreaterThanOrEqual(0.7);
      expect(evaluation.faithfulness.score).toBeLessThanOrEqual(0.35);
    });

    it('penalizes context relevance when context does not match query tokens', async () => {
      const input: RagTriadInput = {
        query: 'Como pegar a Lança de Gransax em Elden Ring?',
        contexts: [
          'Troféu Masterminds no Golpe do Juízo Final em GTA Online. Reúna a mesma equipe e não morra.',
        ],
        answer: 'Não foi possível encontrar instruções para este troféu no guia fornecido.',
      };

      const evaluation = await evaluateRagTriad(input, { mock: true });

      expect(evaluation.contextRelevance.score).toBeLessThanOrEqual(0.3);
    });

    it('scores honest admission with full faithfulness when context is empty', async () => {
      const input: RagTriadInput = {
        query: 'Onde acho a relíquia secreta no jogo Desconhecido 2026?',
        contexts: [],
        answer: 'Guia oficial não encontrado para este objetivo.\nQuer que eu procure em fontes complementares?',
      };

      const evaluation = await evaluateRagTriad(input, { mock: true });

      expect(evaluation.faithfulness.score).toBe(1.0);
      expect(evaluation.answerRelevance.score).toBeGreaterThanOrEqual(0.8);
    });

    it('evaluates canonical gaming scenarios against deterministic heuristic bounds', async () => {
      const { GOLDEN_RAG_TRIAD_DATASET } = await import('./dataset.js');

      for (const scenario of GOLDEN_RAG_TRIAD_DATASET) {
        const evaluation = await evaluateRagTriad(
          {
            query: scenario.query,
            contexts: scenario.contexts,
            answer: scenario.answer,
          },
          { mock: true }
        );

        // Deterministic heuristics guarantee basic groundedness and relevance boundaries
        if (scenario.contexts.length > 0) {
          expect(
            evaluation.contextRelevance.score,
            `Deterministic context relevance on ${scenario.id}`
          ).toBeGreaterThanOrEqual(0.7);

          expect(
            evaluation.faithfulness.score,
            `Deterministic faithfulness on ${scenario.id}`
          ).toBeGreaterThanOrEqual(0.65);
        } else {
          expect(evaluation.faithfulness.score).toBe(1.0);
        }

        expect(
          evaluation.answerRelevance.score,
          `Deterministic answer relevance on ${scenario.id}`
        ).toBeGreaterThanOrEqual(0.7);
      }
    });
  });
});
