export interface SourceDocument {
  content: string;
  title: string;
}

export interface ValidationResult {
  isValid: boolean;
  ungroundedClaims: string[];
  reason?: string;
}

const COMMON_IGNORED_WORDS = new Set([
  'o', 'a', 'os', 'as', 'um', 'uma', 'uns', 'umas', 'para', 'com', 'por', 'em', 'no', 'na',
  'nos', 'nas', 'de', 'do', 'da', 'dos', 'das', 'se', 'que', 'como', 'quando', 'onde',
  'qual', 'quais', 'troféu', 'trofeu', 'trophy', 'fale', 'quer', 'aceite', 'derrote', 'vá',
  'pegue', 'use', 'siga', 'não', 'nao', 'sim', 'este', 'esta', 'esse', 'essa', 'aquele',
  'aquela', 'você', 'voce', 'jogador', 'atenção', 'atencao', 'aviso', 'guia', 'nota', 'passo',
  'dica', 'rotas', 'detalhes', 'completos', 'sou', 'platina', 'agent', 'olá', 'ola', 'hoje',
  'sua', 'seu', 'suas', 'seus', 'ajudar', 'caçada', 'cacada', 'jogo', 'final', 'lutar',
  'garantir', 'sem', 'despertar', 'fazer',
]);

export class GroundingValidator {
  /**
   * Validates whether an agent answer is grounded in the provided guide sources.
   * If sources are absent, rejects any specific tactical guide claims.
   * If sources are present, checks that factual assertions are supported by the text.
   */
  async validate(
    answer: string,
    sources: SourceDocument[]
  ): Promise<ValidationResult> {
    const hasTactical = this.hasTacticalGuideClaims(answer);
    const claims = this.extractFactualAssertions(answer);

    // If no sources are present
    if (!sources || sources.length === 0) {
      if (hasTactical) {
        return {
          isValid: false,
          ungroundedClaims: claims.length > 0 ? claims : ['Afirmações táticas de guia sem fonte'],
          reason: 'Afirmações táticas de guia foram feitas sem fontes de guia disponíveis para validação.',
        };
      }
      return {
        isValid: true,
        ungroundedClaims: [],
      };
    }

    // Sources are present: combine and normalize guide corpus
    // We normalize diacritics / accents for robust matching
    const normalize = (t: string) =>
      t
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLowerCase();

    const fullCorpus = normalize(sources.map((s) => `${s.title}\n${s.content}`).join('\n\n'));

    const supportedClaims: string[] = [];
    const ungroundedClaims: string[] = [];

    for (const claim of claims) {
      const normalizedClaim = normalize(claim.trim());
      if (!normalizedClaim || normalizedClaim.length < 2) continue;

      if (!this.isClaimSupported(normalizedClaim, fullCorpus)) {
        ungroundedClaims.push(claim);
      } else {
        supportedClaims.push(claim);
      }
    }

    const totalClaims = supportedClaims.length + ungroundedClaims.length;

    const wordCount = answer.trim().split(/\s+/).filter(Boolean).length;
    const bulletCount = answer
      .split('\n')
      .filter((line) => /^\s*([-*•]|\d+\.)\s+/.test(line)).length;
    const hasMarkdownTable = /\|.+\|/.test(answer) && /\|[-:\s|]+\|/.test(answer);

    const isDetailed = wordCount > 180 || bulletCount > 4 || hasMarkdownTable;

    if (isDetailed && totalClaims > 0) {
      const coverage = supportedClaims.length / totalClaims;
      if (coverage >= 0.75) {
        return {
          isValid: true,
          ungroundedClaims,
        };
      }
      return {
        isValid: false,
        ungroundedClaims,
        reason: `Cobertura insuficiente de afirmações verificadas no guia (${Math.round(coverage * 100)}% < 75%).`,
      };
    }

    if (ungroundedClaims.length > 0) {
      return {
        isValid: false,
        ungroundedClaims,
        reason: 'Afirmações não encontradas ou contraditórias com as fontes do guia.',
      };
    }

    return {
      isValid: true,
      ungroundedClaims: [],
    };
  }

  private hasTacticalGuideClaims(text: string): boolean {
    // Specific trophy label
    if (/(?:trof[eé]u|trophy):\s*[A-Za-zÀ-Ú0-9]/i.test(text)) return true;
    // Missable / point-of-no-return conditions
    if (/(?:perd[ií]vel|missable|ponto de n[aã]o retorno|bloquead[oa]|questline falha)/i.test(text)) return true;
    // Specific conditions or deadlines
    if (/(?:antes de|depois de|após)\s+[A-Za-zÀ-Ú0-9]/i.test(text)) return true;
    // Specific game action directives
    if (/\b(?:derrote|colete|obtenha|fale com|aceite a proposta)\b/i.test(text)) return true;
    // Chapters / acts
    if (/\b(?:cap[ií]tulo|chapter|ato)\s+\d+\b/i.test(text)) return true;

    return false;
  }

  private extractFactualAssertions(text: string): string[] {
    const assertions = new Set<string>();

    // 1. Quoted terms (often trophy names or items)
    const quoteRegex = /["']([^"']{3,})["']/g;
    let match: RegExpExecArray | null;
    while ((match = quoteRegex.exec(text)) !== null) {
      const quoted = match[1]?.trim();
      if (quoted && !this.isIgnoredTerm(quoted)) {
        assertions.add(quoted);
      }
    }

    // 2. Trophy name labels: "Troféu: <Name>" or "Trophy: <Name>"
    const trophyRegex = /(?:trof[eé]u|trophy):\s*([A-Za-zÀ-Ú0-9'’ -]+?)(?=\s+(?:em|na|no|antes|fale|derrote|\.|\n|$))/gi;
    while ((match = trophyRegex.exec(text)) !== null) {
      const name = match[1]?.trim();
      if (name && !this.isIgnoredTerm(name)) {
        assertions.add(name);
      }
    }

    // 3. Locations: "em <Location>", "na área de <Location>", "na <Location>", "no <Location>"
    const locationRegex = /\b(?:em|na área de|no mapa de|na região de|na|no)\s+([A-ZÀ-Ú][a-zA-ZÀ-Ú0-9'’]+(?:\s+[A-ZÀ-Úa-zÀ-Ú0-9'’]+)*)\b/g;
    while ((match = locationRegex.exec(text)) !== null) {
      const loc = match[1]?.trim();
      if (loc && !this.isIgnoredTerm(loc)) {
        assertions.add(loc);
      }
    }

    // 4. Deadlines, conditions and chapters
    const deadlineRegex = /(?:antes de|após|depois de)\s+([A-Za-zÀ-Ú0-9'’]+(?:\s+[A-Za-zÀ-Ú0-9'’]+){0,4})/gi;
    while ((match = deadlineRegex.exec(text)) !== null) {
      const condition = match[0]?.trim();
      if (condition && !this.isIgnoredTerm(condition)) {
        assertions.add(condition);
      }
    }

    const chapterRegex = /\b(?:cap[ií]tulo|chapter|ato)\s+\d+\b/gi;
    while ((match = chapterRegex.exec(text)) !== null) {
      assertions.add(match[0].trim());
    }

    // 5. Action targets / Proper nouns (e.g., "fale com <Name>", "derrote <Name>", etc.)
    const actionTargetRegex = /\b(?:fale com|derrote|proposta de|arma)\s+([A-ZÀ-Ú][a-zA-ZÀ-Ú0-9'’]+(?:\s+[A-ZÀ-Úa-zÀ-Ú0-9'’]+)*)/gi;
    while ((match = actionTargetRegex.exec(text)) !== null) {
      const target = match[1]?.trim();
      if (target && !this.isIgnoredTerm(target)) {
        assertions.add(target);
      }
    }

    // 6. Generic Capitalized entities (2+ Capitalized words)
    const entityRegex = /\b([A-ZÀ-Ú][a-zà-ú0-9'’]+(?:\s+[A-ZÀ-Ú][a-zà-ú0-9'’]+)+)\b/g;
    while ((match = entityRegex.exec(text)) !== null) {
      const entity = match[1]?.trim();
      if (entity && !this.isIgnoredTerm(entity) && !entity.toLowerCase().includes('platina ai')) {
        assertions.add(entity);
      }
    }

    return Array.from(assertions);
  }

  private isIgnoredTerm(term: string): boolean {
    const clean = term.toLowerCase().replace(/[^\w\sÀ-Úà-ú]/g, '').trim();
    if (clean.length < 3) return true;
    const words = clean.split(/\s+/);
    return words.every((w) => COMMON_IGNORED_WORDS.has(w));
  }

  private isClaimSupported(normalizedClaim: string, corpus: string): boolean {
    if (corpus.includes(normalizedClaim)) {
      return true;
    }

    const tokens = normalizedClaim
      .replace(/[^\w\sÀ-Úà-ú]/g, ' ')
      .split(/\s+/)
      .filter((t) => t.length > 2 && !COMMON_IGNORED_WORDS.has(t));

    if (tokens.length === 0) return true;

    const matchedTokens = tokens.filter((t) => corpus.includes(t));
    const threshold = tokens.length <= 2 ? tokens.length : Math.ceil(tokens.length * 0.7);
    return matchedTokens.length >= threshold;
  }
}

export const groundingValidator = new GroundingValidator();
