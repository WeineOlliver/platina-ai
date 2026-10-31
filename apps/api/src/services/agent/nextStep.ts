import { z } from 'zod';
import Groq from 'groq-sdk';
import { env } from '../../config/env.js';
import { playerProgressTool, type PlayerProgressResult } from './tools/playerProgress.js';
import { searchGuidesTool } from './tools/searchGuides.js';

export const nextStepAdviceSchema = z.object({
  game: z.string(),
  currentProgressPercentage: z.number(),
  urgentWarning: z.string().nullable().describe('Alerta crítico de troféu perdível ou ponto sem retorno'),
  targetTrophy: z.object({
    name: z.string(),
    type: z.string(),
    isMissable: z.boolean(),
  }),
  actionableStep: z.string().describe('Instrução clara e objetiva do que fazer na sessão atual de jogo'),
  checklist: z.array(z.string()).describe('Lista sequencial de 2 a 4 passos imediatos para o jogador realizar'),
  estimatedSessionMinutes: z.number().describe('Tempo estimado para concluir este passo na sessão'),
  sourceGuideReference: z.string().describe('Referência ou citação do guia consultado'),
});

export type NextStepAdvice = z.infer<typeof nextStepAdviceSchema>;

export class NextStepAdvisor {
  private client: Groq | null = null;
  private model: string;

  constructor() {
    this.model = env.GROQ_MODEL;
    if (env.GROQ_API_KEY) {
      this.client = new Groq({ apiKey: env.GROQ_API_KEY });
    }
  }

  async generateNextStepAdvice(game: string, psnId: string = 'me'): Promise<NextStepAdvice> {
    // 1. Fetch live player progress for project owner
    let progress: PlayerProgressResult;
    const progressRes = await playerProgressTool.execute({ game });
    if ('error' in progressRes) {
      if (!this.client || env.AI_PROVIDER === 'mock' || process.env.AI_PROVIDER === 'mock') {
        progress = {
          psn_id: psnId,
          game,
          platform: 'PS5',
          total_trophies: 6,
          unlocked_count: 3,
          completion_percentage: 50,
          pending_count: 3,
          pending_missables_count: 1,
          pending_missable_trophies: [
            {
              trophy_name: "Hunter's Essence",
              chapter_or_location: 'Central Yharnam',
              trophy_type: 'gold',
            },
          ],
          recently_unlocked: [],
        };
      } else {
        throw new Error(`Não foi possível obter o progresso do jogador: ${progressRes.error}`);
      }
    } else {
      progress = progressRes;
    }

    // 2. Determine highest priority trophy (missables take precedence)
    const pendingMissable = progress.pending_missable_trophies[0];
    const targetTrophyName = pendingMissable
      ? pendingMissable.trophy_name
      : (progress.pending_count > 0 ? 'Próximo troféu de progressão' : 'Platina Conquistada');

    // 3. Retrieve relevant guide chunks from pgvector
    const guideSearch = await searchGuidesTool.execute({
      query: `${game} ${targetTrophyName} guia missable estratégia`,
      game,
      limit: 3,
    });

    const guideSnippets = 'results' in guideSearch && guideSearch.results.length > 0
      ? guideSearch.results.map((r) => `[${r.title || 'Guia'}]: ${r.content}`).join('\n\n')
      : 'Siga a rota principal prestando atenção em NPCs e diálogos antes de avançar de capítulo.';

    // Mock fallback when in local mock mode
    if (!this.client || env.AI_PROVIDER === 'mock' || process.env.AI_PROVIDER === 'mock') {
      return {
        game,
        currentProgressPercentage: progress.completion_percentage,
        urgentWarning: pendingMissable
          ? `Atenção: O troféu "${pendingMissable.trophy_name}" é PERDÍVEL se você avançar a história principal sem concluir sua etapa atual!`
          : null,
        targetTrophy: {
          name: targetTrophyName,
          type: pendingMissable?.trophy_type || 'bronze',
          isMissable: Boolean(pendingMissable),
        },
        actionableStep: pendingMissable
          ? `Fale com a NPC no local indicado e não derrote o chefe do capítulo antes de concluir o diálogo.`
          : `Continue avançando na campanha principal.`,
        checklist: [
          'Verifique seu inventário atual',
          'Encontre a NPC antes de passar a névoa do chefe',
          'Converse até esgotar todas as opções de diálogo',
        ],
        estimatedSessionMinutes: 45,
        sourceGuideReference: 'PowerPyx Platinum Trophy Guide',
      };
    }

    // 4. Prompt Groq with strict JSON output schema
    const prompt = `Você é o estrategista de troféus Platina AI.
Analise a situação atual do jogador ${psnId} em ${game} e recomende o próximo passo mais inteligente e seguro da sessão de jogo.

DADOS REAIS DA PSN DO JOGADOR:
- Conclusão: ${progress.completion_percentage}% (${progress.unlocked_count}/${progress.total_trophies} troféus)
- Troféus perdíveis pendentes: ${progress.pending_missables_count}
${pendingMissable ? `- Missable mais urgente: ${pendingMissable.trophy_name} (${pendingMissable.chapter_or_location || 'Local desconhecido'})` : '- Nenhum troféu perdível pendente detectado.'}

TRECHOS VERIFICADOS DOS GUIAS (RAG):
${guideSnippets}

Responda ESTRITAMENTE em formato JSON com o seguinte schema:
{
  "game": string,
  "currentProgressPercentage": number,
  "urgentWarning": string | null,
  "targetTrophy": {
    "name": string,
    "type": string,
    "isMissable": boolean
  },
  "actionableStep": string,
  "checklist": string[],
  "estimatedSessionMinutes": number,
  "sourceGuideReference": string
}`;

    const completion = await this.client.chat.completions.create({
      model: this.model,
      response_format: { type: 'json_object' },
      messages: [
        {
          role: 'system',
          content: 'Você é um assistente de IA especialista em jogos PlayStation que responde exclusivamente em formato JSON válido conforme o schema solicitado.',
        },
        { role: 'user', content: prompt },
      ],
      temperature: 0.2,
    });

    const rawContent = completion.choices[0]?.message?.content;
    if (!rawContent) {
      throw new Error('O modelo não retornou conteúdo na recomendação de próximo passo.');
    }

    const parsed = JSON.parse(rawContent);
    return nextStepAdviceSchema.parse(parsed);
  }
}

export const nextStepAdvisor = new NextStepAdvisor();
