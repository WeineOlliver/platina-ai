import { describe, it, expect, vi } from 'vitest';
import {
  evaluateRagTriad,
  type RagTriadInput,
  type RagTriadEvaluation,
} from './ragTriadJudge.js';

describe('RAG Triad LLM-as-a-Judge Suite', () => {
  it('evaluates a perfectly grounded, relevant answer with high scores across the triad', async () => {
    const input: RagTriadInput = {
      query: 'Como pegar a Lança de Gransax em Elden Ring?',
      contexts: [
        'A Lança de Gransax é uma arma lendária fincada na lança gigante cravada em Leyndell, Capital Real. Ela DEVE ser coletada antes de derrotar Maliketh em Farum Azula. Após Maliketh, a capital vira cinzas e a arma torna-se inacessível.',
      ],
      answer: 'Troféu: Lança de Gransax em Leyndell, Capital Real.\n- Suba na lança monumental dourada fincada no centro da cidade.\n- Colete a arma antes de derrotar Maliketh em Farum Azula.',
    };

    const evaluation: RagTriadEvaluation = await evaluateRagTriad(input);

    // Verify metrics exist and have numeric bounds
    expect(evaluation.contextRelevance.score).toBeGreaterThanOrEqual(0.8);
    expect(evaluation.faithfulness.score).toBeGreaterThanOrEqual(0.8);
    expect(evaluation.answerRelevance.score).toBeGreaterThanOrEqual(0.8);

    // Check structure
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

    const evaluation: RagTriadEvaluation = await evaluateRagTriad(input);

    // Context is relevant to the question
    expect(evaluation.contextRelevance.score).toBeGreaterThanOrEqual(0.7);
    // Faithfulness must be heavily penalized because Andre/Firelink/Gwyn are complete hallucinations
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

    const evaluation: RagTriadEvaluation = await evaluateRagTriad(input);

    // Context is completely unrelated
    expect(evaluation.contextRelevance.score).toBeLessThanOrEqual(0.3);
  }, 15000);

  it('penalizes answer relevance when the answer ignores the user query', async () => {
    const input: RagTriadInput = {
      query: 'Qual é o troféu perdível de Bloodborne?',
      contexts: [
        'Para o troféu Hunter\'s Essence você deve coletar todas as armas de caçador. Este troféu é perdível.',
      ],
      answer: 'Olá! O PlayStation 4 foi lançado em novembro de 2013 pela Sony Interactive Entertainment.',
    };

    const evaluation: RagTriadEvaluation = await evaluateRagTriad(input);

    expect(evaluation.answerRelevance.score).toBeLessThanOrEqual(0.3);
  }, 15000);

  describe('Golden Dataset Batch Evaluations', () => {
    it('meets minimum quality thresholds for all canonical gaming scenarios in the golden dataset', async () => {
      const { GOLDEN_RAG_TRIAD_DATASET } = await import('./dataset.js');

      for (const scenario of GOLDEN_RAG_TRIAD_DATASET) {
        const evaluation = await evaluateRagTriad({
          query: scenario.query,
          contexts: scenario.contexts,
          answer: scenario.answer,
        });

        // Assertions against calibrated thresholds
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
    }, 45000);
  });
});
