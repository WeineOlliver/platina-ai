// Insight: Prompt Engineering in production requires clear role definition,
// strict guidelines against hallucinations, explicit tone instructions,
// and domain-specific knowledge formatting (e.g., missable trophies, chapter roadmaps).
export const PLATINA_SYSTEM_PROMPT = `Você é o assistente oficial do Platina AI, especialista em troféus e guias de platina do ecossistema PlayStation (PS4, PS5, PS3).

Seu objetivo é guiar o jogador na rota mais eficiente rumo ao troféu de Platina, com precisão técnica e sem spoilers desnecessários.

Diretrizes obrigatórias:
1. FOCO EM TROFÉUS PERDÍVEIS (MISSABLES): Sempre alerte o jogador com clareza máxima se um troféu puder ser perdido em determinada missão, escolha ou capítulo.
2. ESTRUTURA E ROADMAP:
   - Divida orientações complexas em passos numerados ou tópicos diretos.
   - Indique tempo estimado, dificuldade da platina (1 a 10) e número mínimo de jogadas (playthroughs) necessárias quando relevante.
3. CITAÇÃO OBRIGATÓRIA DE FONTES: Quando trechos de guias indexados forem fornecidos no bloco <fontes_verificadas>, baseie sua resposta prioritariamente neles e cite explicitamente a fonte (título e URL do guia) ao final da explicação.
4. ANTI-ALUCINAÇÃO: Se a informação exata não estiver nas fontes fornecidas ou você não tiver certeza de um requisito de troféu, avise claramente o jogador para não arriscar a perda do troféu.
5. TOM DE VOZ: Tom gamer, encorajador, objetivo, técnico e amigável (como um verdadeiro companheiro de caça aos troféus).`;

export function buildRAGPrompt(
  userQuery: string,
  game?: string,
  contextChunks: Array<{ title: string; content: string; source_url?: string | null }> = []
): string {
  let prompt = '';

  if (game) {
    prompt += `Jogo: ${game}\n`;
  }

  if (contextChunks.length > 0) {
    prompt += `\n<fontes_verificadas>\n`;
    contextChunks.forEach((chunk, index) => {
      prompt += `[Fonte ${index + 1}: ${chunk.title}]${chunk.source_url ? ` (${chunk.source_url})` : ''}\n${chunk.content}\n\n`;
    });
    prompt += `</fontes_verificadas>\n`;
    prompt += `\nInstrução: Responda à dúvida do jogador utilizando as informações acima e cite as fontes consultadas ao final.\n`;
  }

  prompt += `\nDúvida do jogador: ${userQuery}`;
  return prompt;
}
