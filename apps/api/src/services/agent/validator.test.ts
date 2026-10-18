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

  describe('Coverage-Based Validation Policy for Detailed Responses', () => {
    const detailedSources = [
      {
        title: 'The Witcher 3: Wild Hunt - Guia de Cartas de Gwent',
        content: `Para o troféu Card Collector você deve obter todas as cartas de Gwent.
Localização 1: Em White Orchard, compre as cartas com a estalajadeira Elsa antes de sair da região.
Localização 2: Em Velen, derrote o Barão Sanguinário Phillip Strenger na quest Velen Players.
Localização 3: Em Novigrad, vença as 3 partidas no baile de máscaras Vegelbud durante A Matter of Life and Death.
Localização 4: No torneio de High Stakes no Passiflora em Novigrad, vença todas as rodadas antes do final da quest.`,
      },
    ];

    it('approves a long detailed walkthrough response when claim coverage is >= 75%', async () => {
      // 14 supported claims from the guide, 2 ungrounded claims (Skellige, Zoltan)
      // Total 16 claims -> 14/16 = 87.5% coverage >= 75%
      const detailedAnswer = `Passo a Passo de Coleta de Cartas para Card Collector:

- Localização 1: Em White Orchard, compre as cartas com Elsa antes de sair da região.
- Localização 2: Em Velen, derrote o Barão Sanguinário Phillip Strenger na missão Velen Players.
- Localização 3: Em Novigrad, vença as partidas no baile de máscaras Vegelbud durante A Matter of Life and Death.
- Localização 4: No torneio de High Stakes no Passiflora em Novigrad, vença todas as rodadas antes do final da quest.
- Localização 5: Em Skellige, dispute uma carta rara com Zoltan no cais.

Siga todas as etapas acima com atenção redobrada aos encontros perdíveis.`;

      const result = await validator.validate(detailedAnswer, detailedSources);

      expect(result.isValid).toBe(true);
      expect(result.ungroundedClaims.some((c) => c.includes('Skellige'))).toBe(true);
    });

    it('approves a markdown table detailed response with >= 75% coverage', async () => {
      const tableAnswer = [
        'Tabela Detalhada de Localização de Cartas:',
        '| Região | Alvo / NPC | Missão | Cuidados |',
        '| --- | --- | --- | --- |',
        '| White Orchard | Elsa | Procura | Antes de sair da região |',
        '| Velen | Phillip Strenger | Velen Players | Barão Sanguinário |',
        '| Novigrad | Vegelbud | A Matter of Life and Death | Baile de máscaras |',
        '| Novigrad | Passiflora | High Stakes | Antes do final da quest |',
        '| Skellige | Ermion | Alquimia | Jogar baralho |',
      ].join('\n');

      const result = await validator.validate(tableAnswer, detailedSources);

      expect(result.isValid).toBe(true);
    });

    it('rejects a long detailed response when claim coverage is < 75%', async () => {
      // Multiple hallucinated locations/entities
      const hallucinatedDetailedAnswer = `Guia Detalhado de Cartas de Gwent para o Troféu Card Collector:

Passo a Passo de Coleta:
- White Orchard: Compre as cartas com Elsa na estalagem antes de sair.
- Caelid: Encontre o mercador Radahn em Caelid para comprar a carta lendária.
- Leyndell: Fale com Godfrey em Leyndell antes de queimar a capital.
- Yharnam: Derrote Gehrman em Yharnam para desbloquear o baralho especial.
- Farum Azula: Colete a última carta com Maliketh em Farum Azula.

Siga rigorosamente cada etapa acima para conquistar a platina.`;

      const result = await validator.validate(hallucinatedDetailedAnswer, detailedSources);

      expect(result.isValid).toBe(false);
      expect(result.ungroundedClaims.length).toBeGreaterThanOrEqual(3);
      expect(result.reason).toMatch(/cobertura|75%|contraditórias/i);
    });

    it('maintains strict zero-tolerance validation for short tactical briefs (<= 120 words)', async () => {
      // Short brief with 1 ungrounded claim must be rejected even if 3 out of 4 claims match (75%)
      const shortBrief = [
        "Troféu: Card Collector em White Orchard.",
        '- Compre cartas com Elsa em White Orchard antes de avançar.',
        '- Fale com Radahn em Caelid para cartas raras.',
        'Quer os detalhes completos e rotas deste troféu?',
      ].join('\n');

      const result = await validator.validate(shortBrief, detailedSources);

      expect(result.isValid).toBe(false);
      expect(result.ungroundedClaims.some((c) => c.includes('Caelid'))).toBe(true);
    });
  });
});
