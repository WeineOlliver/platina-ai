import { type RagTriadInput } from './types.js';

export interface EvaluationScenario extends RagTriadInput {
  id: string;
  category: 'missable_trophy' | 'routing' | 'boss_strategy' | 'unindexed_fallback';
  expectedThresholds: {
    minContextRelevance: number;
    minFaithfulness: number;
    minAnswerRelevance: number;
  };
}

export const GOLDEN_RAG_TRIAD_DATASET: EvaluationScenario[] = [
  {
    id: 'ER-BOLT-01',
    category: 'missable_trophy',
    query: 'Como pegar a Lança de Gransax em Elden Ring antes que fique inacessível?',
    contexts: [
      'A Lança de Gransax é uma arma lendária fincada na lança gigante cravada em Leyndell, Capital Real. Ela DEVE ser coletada antes de derrotar Maliketh em Farum Azula. Após Farum Azula, Leyndell vira a Capital das Cinzas e a lança fica inacessível para sempre no seu playthrough atual.',
    ],
    answer: 'Troféu: Lança de Gransax em Leyndell, Capital Real.\n- Suba na lança monumental dourada fincada no centro da cidade.\n- Colete a arma antes de derrotar Maliketh em Farum Azula.\nQuer os detalhes completos e rotas deste troféu?',
    expectedThresholds: {
      minContextRelevance: 0.8,
      minFaithfulness: 0.85,
      minAnswerRelevance: 0.85,
    },
  },
  {
    id: 'BB-BLADE-02',
    category: 'missable_trophy',
    query: 'Como obter a Blade of Mercy com Eileen the Crow em Bloodborne?',
    contexts: [
      'Para o troféu Hunter\'s Essence você deve coletar todas as armas de caçador. A arma Blade of Mercy é obtida através da questline de Eileen the Crow em Central Yharnam antes de derrotar Rom. Se Rom for derrotado prematuramente, Eileen desaparecerá.',
    ],
    answer: 'Troféu: Hunter\'s Essence em Central Yharnam.\n- Fale com Eileen the Crow em Central Yharnam antes de derrotar Rom.\n- Avance sua missão para receber a Blade of Mercy.\nQuer os detalhes completos e rotas deste troféu?',
    expectedThresholds: {
      minContextRelevance: 0.8,
      minFaithfulness: 0.85,
      minAnswerRelevance: 0.85,
    },
  },
  {
    id: 'W3-GWENT-03',
    category: 'missable_trophy',
    query: 'Onde comprar as cartas perdíveis de Elsa no início de The Witcher 3?',
    contexts: [
      'Para o troféu Card Collector (Colecionador de Cartas) em Pomar Branco: Compre todas as cartas de Gwent da estalajadeira Elsa na taverna do Pomar Branco antes de partir para Vizima. Mais tarde, vença as 3 partidas no torneio durante o baile de máscaras na propriedade Vegelbud para ganhar a carta Dandelion.',
    ],
    answer: 'Troféu: Card Collector em Pomar Branco.\n- Compre todas as cartas de Gwent com Elsa na taverna antes de ir para Vizima.\n- Atenção: Elsa deixa o local após o prólogo e as cartas tornam-se inacessíveis.\nQuer os detalhes completos e rotas deste troféu?',
    expectedThresholds: {
      minContextRelevance: 0.8,
      minFaithfulness: 0.85,
      minAnswerRelevance: 0.85,
    },
  },
  {
    id: 'FALLBACK-04',
    category: 'unindexed_fallback',
    query: 'Onde acho a relíquia secreta no jogo Desconhecido 2026?',
    contexts: [],
    answer: 'Guia oficial não encontrado para este objetivo.\nQuer que eu procure em fontes complementares?',
    expectedThresholds: {
      minContextRelevance: 0.0,
      minFaithfulness: 0.9,
      minAnswerRelevance: 0.7,
    },
  },
];
