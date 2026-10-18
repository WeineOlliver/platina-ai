import { describe, it, expect } from 'vitest';
import { GroundingValidator, groundingValidator } from './validator.js';

describe('GroundingValidator Suite', () => {
  const validator = new GroundingValidator();

  it('validates and approves answer that is fully grounded in source guides', async () => {
    const sources = [
      {
        title: 'Bloodborne - Guia de Platina e Armas',
        content: "Para o troféu 'Hunter's Essence', você deve obter todas as armas de caçador. A arma Blade of Mercy é obtida com Eileen the Crow em Central Yharnam antes de derrotar Rom. Se Rom for derrotado, a questline falha.",
      },
    ];

    const answer = [
      "Troféu: Hunter's Essence em Central Yharnam.",
      'Fale com Eileen the Crow antes de derrotar Rom para garantir a Blade of Mercy.',
      'Quer os detalhes completos e rotas deste troféu?',
    ].join('\n');

    const result = await validator.validate(answer, sources);

    expect(result.isValid).toBe(true);
    expect(result.ungroundedClaims).toHaveLength(0);
    expect(result.reason).toBeUndefined();
  });

  it('rejects fabricated tactical advice when no source chunks are available', async () => {
    const sources: Array<{ content: string; title: string }> = [];

    const answer = [
      'Troféu: Yharnam Sunrise na Oficina do Caçador.',
      'Aceite a proposta de Gehrman no final do jogo para despertar sem lutar.',
      'Quer os detalhes completos e rotas deste troféu?',
    ].join('\n');

    const result = await validator.validate(answer, sources);

    expect(result.isValid).toBe(false);
    expect(result.ungroundedClaims.length).toBeGreaterThan(0);
    expect(result.reason).toContain('sem fontes');
  });

  it('allows conversational responses without tactical guide claims even when sources are empty', async () => {
    const sources: Array<{ content: string; title: string }> = [];

    const answer = 'Olá! Sou o Platina AI Agent. Como posso ajudar com a sua caçada aos troféus hoje?';

    const result = await validator.validate(answer, sources);

    expect(result.isValid).toBe(true);
    expect(result.ungroundedClaims).toHaveLength(0);
  });

  it('rejects advice with assertions absent or contradicted by the source guide', async () => {
    const sources = [
      {
        title: 'Elden Ring - Guia de Finais',
        content: 'O troféu Age of the Stars exige completar a quest da Ranni em Liurnia of the Lakes e entregar a Dark Moon Ring.',
      },
    ];

    const answer = [
      'Troféu: Age of the Stars em Caelid.',
      'Derrote o chefe Radahn no Capítulo 5 antes de falar com Melina em Volcano Manor.',
      'Quer os detalhes completos e rotas deste troféu?',
    ].join('\n');

    const result = await validator.validate(answer, sources);

    expect(result.isValid).toBe(false);
    expect(result.ungroundedClaims.length).toBeGreaterThan(0);
    expect(result.ungroundedClaims.some(c => c.toLowerCase().includes('caelid') || c.toLowerCase().includes('capítulo 5'))).toBe(true);
  });

  it('exports a singleton instance groundingValidator', () => {
    expect(groundingValidator).toBeInstanceOf(GroundingValidator);
  });
});
