import Groq from 'groq-sdk';
import { env } from '../../config/env.js';
import { trophyRoadmapSchema, type TrophyRoadmap } from '../../schemas/roadmap.js';
import { withRetry } from '../../utils/retry.js';

export class StructuredLlmService {
  private client: Groq | null = null;
  private model: string;

  constructor() {
    this.model = env.GROQ_MODEL;
    if (env.GROQ_API_KEY) {
      this.client = new Groq({ apiKey: env.GROQ_API_KEY });
    }
  }

  /**
   * Gera um roadmap de platina estruturado e garantido via schema JSON.
   */
  async generateRoadmap(game: string): Promise<TrophyRoadmap> {
    // Fallback de teste/mock se não houver chave configurada ou se estiver em modo mock
    if (process.env.AI_PROVIDER === 'mock' || env.AI_PROVIDER === 'mock' || !this.client) {
      return {
        game,
        difficulty: 6,
        estimatedHours: 50,
        minimumPlaythroughs: 1,
        hasOnlineTrophies: false,
        missables: [
          {
            trophyName: 'Exemplo de Troféu Perdível',
            chapterOrLocation: 'Capítulo 2',
            missableReason: 'Não avance a missão principal antes de completar a quest secundária.',
          },
        ],
        recommendedRoute: [
          'Passo 1: Aproveite a história e colete itens perdíveis.',
          'Passo 2: Faça backup do save antes da decisão final.',
          'Passo 3: Limpeza de troféus restantes.',
        ],
      };
    }

    // Insight: Para garantir saída estruturada estrita, combinamos:
    // 1. `response_format: { type: 'json_object' }` na API do Groq (garantia sintática).
    // 2. Um prompt com o schema explícito dos campos e tipos.
    // 3. Validação em tempo de execução com `trophyRoadmapSchema.parse()` (Zod).
    // Se o modelo desviar de tipos ou omitir chaves obrigatórias, o Zod falha fast no backend
    // antes de entregar dados corrompidos ao cliente.
    const systemPrompt = `Você é um assistente especialista em platinas do ecossistema PlayStation.
Sua tarefa é analisar o jogo solicitado e gerar um guia/roadmap estruturado para a conquista da Platina.
Você DEVE responder ESTRITAMENTE em formato JSON válido, sem texto introdutório nem marcações fora do JSON.`;

    const userPrompt = `Gere a análise da platina e o roadmap para o jogo: "${game}".
Responda exclusivamente com um objeto JSON contendo exatamente as seguintes propriedades:
- "game": string com o nome oficial do jogo.
- "difficulty": número de 1 a 10 indicando a dificuldade da platina.
- "estimatedHours": número com o tempo médio em horas para platinar.
- "minimumPlaythroughs": número mínimo de jogadas necessárias.
- "hasOnlineTrophies": booleano (true se tiver troféus multiplayer/servidor obrigatórios, false caso contrário).
- "missables": array de objetos, onde cada objeto tem:
    * "trophyName": string com o nome do troféu.
    * "chapterOrLocation": string indicando onde ele pode ser perdido.
    * "missableReason": string explicando o que o jogador não pode fazer para não perdê-lo.
- "recommendedRoute": array de strings com as etapas recomendadas na ordem ideal de execução.`;

    // Insight: Chamadas a LLMs são sujeitas a falhas temporárias (rate limit 429 ou 503).
    // Envolvemos a requisição com `withRetry` (exponential backoff com jitter)
    // para recuperar transientes automaticamente sem expor erros ao usuário.
    const client = this.client;
    const model = this.model;

    const response = await withRetry(async () => {
      return await client.chat.completions.create({
        model,
        response_format: { type: 'json_object' },
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: userPrompt },
        ],
      });
    }, {
      maxRetries: 3,
      initialDelayMs: 600,
    });

    const content = response.choices[0]?.message?.content;
    if (!content) {
      throw new Error('Groq retornou uma resposta vazia');
    }

    const parsedJson = JSON.parse(content);

    // Validação estrita com Zod: garante tipos e propriedades em tempo de execução
    return trophyRoadmapSchema.parse(parsedJson);
  }
}

export const structuredLlmService = new StructuredLlmService();
