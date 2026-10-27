import Groq from 'groq-sdk';
import { env } from '../../config/env.js';
import {
  playerProgressTool,
  PlayerProgressTool,
  type CheckPlayerProgressParams,
  type PlayerProgressResult,
} from './tools/playerProgress.js';
import { searchGuidesTool, SearchGuidesTool, type SearchGuidesParams } from './tools/searchGuides.js';
import { ingestionClient } from '../ingestion/client.js';
import { groundingValidator } from './validator.js';
import { executeWithModelCascade, DEFAULT_MODEL_CASCADE } from '../llm/fallback.js';
import { telemetryService } from '../observability/telemetry.js';
import { evaluateRagTriad } from '../evals/ragTriadJudge.js';

export interface AgentStepEvent {
  type: 'thought' | 'tool_call' | 'tool_result' | 'chunk' | 'done' | 'error' | 'sources';
  content?: string;
  toolName?: string;
  toolArgs?: unknown;
  toolResult?: unknown;
  items?: Array<{ title: string; url: string }>;
  error?: string;
}

export interface RunAgentOptions {
  maxSteps?: number;
  signal?: AbortSignal;
  history?: Array<{ role: 'user' | 'assistant'; content: string }> | undefined;
  game?: string;
  psnId?: string;
  lang?: 'en' | 'pt';
  sessionId?: string;
}

export interface GuideSourceItem {
  title: string;
  content: string;
  sourceUrl?: string | undefined;
}

export function extractDistinctSources(
  sources: GuideSourceItem[]
): Array<{ title: string; url: string }> {
  const seenUrls = new Set<string>();
  const distinct: Array<{ title: string; url: string }> = [];

  for (const s of sources) {
    if (s.sourceUrl && !seenUrls.has(s.sourceUrl)) {
      seenUrls.add(s.sourceUrl);
      distinct.push({
        title: s.title,
        url: s.sourceUrl,
      });
    }
  }

  return distinct;
}

export function appendSourcesFooter(
  text: string,
  sources: Array<{ title: string; url: string }>,
  lang: 'en' | 'pt' = 'pt'
): string {
  if (sources.length === 0 || !text.trim()) {
    return text;
  }

  const isEn = lang === 'en';
  const header = isEn ? '**Verified sources:**' : '**Fontes verificadas:**';
  const links = sources.map((s) => `- [${s.title}](${s.url})`).join('\n');
  return `${text.trim()}\n\n${header}\n${links}`;
}

function extractGameFromText(text: string): string | undefined {
  const explicitMatch = text.match(/(?:Jogo|Game):\s*([^\n\r]+)/i);
  if (explicitMatch?.[1]) return explicitMatch[1].trim();

  const emMatch = text.match(/\bem\s+([A-Z0-9][A-Za-z0-9\s:'-]+?)(?:\?|\.|\n|$|,|;)/);
  if (emMatch?.[1]) {
    const candidate = emMatch[1].trim();
    if (!/^(1|2|geral|breve|alta|baixa|segundo|primeiro)\b/i.test(candidate)) {
      return candidate;
    }
  }

  const inMatch = text.match(/\bin\s+([A-Z0-9][A-Za-z0-9\s:'-]+?)(?:\?|\.|\n|$|,|;)/);
  if (inMatch?.[1]) {
    const candidate = inMatch[1].trim();
    if (!/^(1|2|general|brief|high|low|second|first)\b/i.test(candidate)) {
      return candidate;
    }
  }

  return undefined;
}

function addPlayerProgressToSources(
  pData: Partial<PlayerProgressResult>,
  collectedGuideSources: Array<{ content: string; title: string }>,
  lang: 'en' | 'pt' = 'pt'
) {
  const isEn = lang === 'en';
  const summaryParts: string[] = [];
  if (pData.game) summaryParts.push(isEn ? `Game: ${pData.game}` : `Jogo: ${pData.game}`);
  if (pData.pending_missable_trophies?.length) {
    summaryParts.push(
      isEn
        ? `Pending missable trophies: ${pData.pending_missable_trophies.map((t) => t.trophy_name).join(', ')}`
        : `Troféus perdíveis pendentes: ${pData.pending_missable_trophies.map((t) => t.trophy_name).join(', ')}`
    );
  }
  if (pData.unearned_trophies_summary?.length) {
    summaryParts.push(
      isEn
        ? `Pending unearned trophies list:\n${pData.unearned_trophies_summary.slice(0, 10).join('\n')}`
        : `Lista de troféus pendentes:\n${pData.unearned_trophies_summary.slice(0, 10).join('\n')}`
    );
  }
  if (summaryParts.length > 0) {
    collectedGuideSources.push({
      title: isEn ? `PSN Progress (${pData.game || 'General'})` : `Progresso PSN (${pData.game || 'Geral'})`,
      content: summaryParts.join('\n'),
    });
  }

  const gameName = pData.game || (isEn ? 'General' : 'Geral');
  if (pData.quick_cleanup_trophies?.length) {
    collectedGuideSources.push({
      title: isEn ? `PSN Progress (${gameName}) - Quick Cleanup Trophies` : `Progresso PSN (${gameName}) - Troféus Rápidos (Limpeza)`,
      content: pData.quick_cleanup_trophies
        .map(
          (t) =>
            `- ${t.trophy_name}${t.trophy_type ? ` [${t.trophy_type}]` : ''}${t.chapter_or_location ? `: ${t.chapter_or_location}` : ''}`
        )
        .join('\n'),
    });
  }

  if (pData.heavy_grind_trophies?.length) {
    collectedGuideSources.push({
      title: isEn ? `PSN Progress (${gameName}) - Heavy Grind Trophies` : `Progresso PSN (${gameName}) - Troféus de Grind Pesado`,
      content: pData.heavy_grind_trophies
        .map(
          (t) =>
            `- ${t.trophy_name}${t.trophy_type ? ` [${t.trophy_type}]` : ''}${t.chapter_or_location ? `: ${t.chapter_or_location}` : ''}`
        )
        .join('\n'),
    });
  }
}

// Insight: Agent ReAct Loop (Reasoning + Acting).
// The agent alternates between LLM generation and tool execution.
// If the LLM generates `tool_calls`, we execute the requested tools locally,
// append their results as `tool` role messages, and call the model again until it completes.
export class PlatinaAgentRunner {
  private client: Groq | null = null;
  private model: string;

  constructor() {
    this.model = env.GROQ_MODEL;
    if (env.GROQ_API_KEY) {
      this.client = new Groq({ apiKey: env.GROQ_API_KEY });
    }
  }

  getAvailableTools() {
    return [
      PlayerProgressTool.toolDefinition,
      SearchGuidesTool.toolDefinition,
    ];
  }

  async executeTool(
    name: string,
    args: Record<string, unknown>,
    context?: { sessionGame?: string | undefined }
  ): Promise<unknown> {
    if (name === PlayerProgressTool.name) {
      return await playerProgressTool.execute(args as unknown as CheckPlayerProgressParams);
    }
    if (name === SearchGuidesTool.name) {
      // Insight: Provide active session game to tool execution for automatic fallback
      return await searchGuidesTool.execute(args as unknown as SearchGuidesParams, context);
    }
    throw new Error(`Tool desconhecida: "${name}"`);
  }

  async *run(userMessage: string, options: RunAgentOptions = {}): AsyncGenerator<AgentStepEvent> {
    const reqStart = performance.now();
    let retrievalLatencyMs = 0;
    let rerankerLatencyMs = 0;
    let llmLatencyMs = 0;

    const maxSteps = options.maxSteps ?? 5;
    const lang = options.lang || (/\b(what|which|how|trophies|missable|cards|guide|tell me|details)\b/i.test(userMessage) ? 'en' : 'pt');
    const isEn = lang === 'en';

    // Fallback if no LLM client is configured
    if (!this.client || env.AI_PROVIDER === 'mock' || process.env.AI_PROVIDER === 'mock') {
      yield {
        type: 'chunk',
        content: isEn
          ? `[Platina Agent - Mock] Analyzing your request: "${userMessage}".\nTo enable full tool loop with the 120B parameter model, configure GROQ_API_KEY in the .env file.`
          : `[Platina Agent - Mock] Analisando sua solicitação: "${userMessage}".\nPara ativar o loop completo de ferramentas com o modelo de 120B parâmetros, configure o GROQ_API_KEY no arquivo .env.`,
      };
      yield { type: 'done' };
      return;
    }

    // Deep Walkthrough Intent Detection
    const lastAssistantMsg = options.history
      ?.slice()
      .reverse()
      .find((m) => m.role === 'assistant');

    const hasAssistantCTA = Boolean(
      lastAssistantMsg && /(quer os detalhes completos|want the complete details|would you like the complete details)/i.test(lastAssistantMsg.content)
    );

    const isAffirmativeFollowUp =
      hasAssistantCTA && /^(sim|quero|manda|pode mandar|detalhes|yes|sure|send|details)/i.test(userMessage.trim());

    const isExplicitDeepWalkthrough =
      /(detalhad|passo a passo|como pegar cad|todos os|todas as cartas|guia complet|rotas complet|quais pontos|cada carta|uma por uma|onde pegar|detailed|step by step|how to get|all trophies|all cards|complete guide|complete routes|every card|one by one|where to get)/i.test(userMessage);

    const isDeepWalkthrough = isExplicitDeepWalkthrough || isAffirmativeFollowUp;

    const personaInstructions = isEn
      ? (isDeepWalkthrough
        ? `Detailed Step-by-Step Instructions (Deep Walkthrough):
The user requested a detailed, in-depth guide. Present a complete walkthrough, structured in sections or bullet points, detailing each step, NPC location, quests, and missable trophy precautions strictly based on retrieved verified sources. You may use up to 800 words to provide all necessary details. Respond in clear, professional English.`
        : `Concise Tactical Persona (Mandatory Output Format):
Adaptive Routing Instructions (When the user asks for routes like "best route", "next steps", or "what to do now"):
If the player has no pending campaign missable trophies (or the campaign is already completed):
Present two distinct strategic choices:
- Option 1 (Speed): List 2-3 quick trophies from "quick_cleanup_trophies" to score trophies quickly.
- Option 2 (Foundation / Grind): List 1-2 heavy trophies from "heavy_grind_trophies" to advance difficult milestones.
- Conclude strictly with the Call to Action: "Which route would you prefer to tackle first?"

Single Trophy Lookup Format:
If the user asks about a specific trophy, maintain a tactical 3-part layout:
- Line 1: Target trophy + location (e.g. "Trophy: [Name] in [Location].").
- Lines 2-3 (or 2-4): Immediate tactical action to avoid missing it (immediate step, critical condition, or point of no return).
- Final line: Call to action offering full walkthrough: "Would you like the complete details and routes for this trophy?"

Response Budget (Mandatory):
Your final response must have in total LESS THAN 180 WORDS. Respond in clear, professional English.`)
      : (isDeepWalkthrough
        ? `Instruções de Passo a Passo Detalhado (Deep Walkthrough):
O usuário solicitou um guia detalhado e aprofundado. Apresente um passo a passo completo, estruturado em seções ou tabela, detalhando cada etapa, localização de NPC, missões e cuidados com troféus perdíveis baseando-se estritamente nas fontes verificadas recuperadas. Você pode usar até 800 palavras para fornecer todas as informações necessárias.`
        : `Persona Concisa e Tática (Formato Obrigatório de Resposta):
Instruções de Roteamento Adaptativo (Quando o usuário pedir rotas como "melhor rota", "próximos passos" ou "o que fazer agora"):
Se o jogador não possuir troféus perdíveis de campanha pendentes (ou a campanha já estiver concluída):
Apresente duas escolhas estratégicas distintas:
- Opção 1 (Velocidade): Liste 2-3 troféus rápidos de "quick_cleanup_trophies" (ex: Modo Diretor) para pontuar troféus rapidamente.
- Opção 2 (Fundação / Grind): Liste 1-2 troféus pesados de "heavy_grind_trophies" (ex: Golpes/Heists, Masterminds) para adiantar as tarefas mais difíceis.
- Finalize obrigatoriamente com o Call to Action: "Qual rota você prefere encarar primeiro?"

Formato para Consulta de Troféu Específico (Single Trophy Lookup):
Se o usuário perguntar sobre um troféu específico, mantenha o layout tático de 3 partes:
- Linha 1: Troféu alvo + localização (ex: "Troféu: [Nome] em [Localização].").
- Linhas 2-3 (ou 2-4): Ação tática imediata para não perdê-lo (etapa imediata, condição crítica ou ponto de não retorno).
- Linha final: Call to action oferecendo walkthrough completo: "Quer os detalhes completos e rotas deste troféu?"

Orçamento de Resposta (Obrigatório):
Sua resposta final deve ter no total MENOS DE 180 PALAVRAS.`);

    const targetPsnId = options.psnId?.trim();
    const targetGame = (options.game || (targetPsnId ? extractGameFromText(userMessage) : undefined))?.trim();
    let detectedGame = targetGame || extractGameFromText(userMessage);
    const shouldPrefetch = Boolean(targetPsnId && targetGame);

    const prefetchPromptAddition = shouldPrefetch
      ? (isEn
        ? `\n\nImmediate Execution Directive (Single Roundtrip):
The progress for player "${targetPsnId}" in "${targetGame}" has already been queried and injected via the "check_player_progress" tool.
DO NOT execute the "check_player_progress" tool again.
DIRECTLY generate the greeting and tactical briefing (or status response) in a single turn based on already available data.`
        : `\n\nDiretriz de Execução Imediata (Single Roundtrip):
O progresso do jogador "${targetPsnId}" em "${targetGame}" já foi consultado e os dados estão injetados na conversa via ferramenta "check_player_progress".
NÃO execute a ferramenta "check_player_progress" novamente.
Gere DIRETAMENTE a saudação e o briefing tático (ou resposta de status) em 1 único turno com base nos dados já disponíveis.`)
      : '';

    const systemPrompt = isEn
      ? `You are Platina AI Agent, an autonomous PlayStation trophy hunting specialist.
You have access to tools to:
1. "check_player_progress": check earned and pending trophies for a player on PSN.
2. "search_trophy_guides": search verified excerpts in the trophy guide vector database.

Agent Guidelines & Language Architecture:
- ALL tool arguments (query, game, trophies, quests) MUST be written in English. Always use official English names for trophies, quests, and characters.
- If the user asks in another language, translate the intent into English for tool arguments.
- Deliver the final answer to the user in English as configured in the session.
- If the user mentions a PSN ID or asks what to do next in a game, call "check_player_progress" to inspect their actual progress.
- When the user asks about quests, story choices, points of no return (e.g. "Before Kaer Morhen", "accepting an offer", "missables in Novigrad"), contracts, or missable trophies for a region/DLC, you MUST call "search_trophy_guides" using concise English keywords (e.g. query: "Kaer Morhen", "Full Crew", "Woodland Spirit", "Hearts of Stone missable") and game in English to retrieve verified guide excerpts before answering.
- If "check_player_progress" returns "unearned_trophies_summary", USE this list of actual pending trophies to answer what is missing or easiest/fastest to achieve.
- When searching guides with "search_trophy_guides", ALWAYS send the clean, exact short trophy name in English (e.g. query: "Card Collector", "Masterminds", "Kifflom", "Cryptozoologist"), NEVER concatenate descriptions, words like "silver", "bronze", or long text into the search query.${isDeepWalkthrough ? ' In detailed mode, pass limit: 8 to obtain comprehensive context.' : ''}
- When the user asks about cards, collectibles, or detailed steps for a trophy, call "search_trophy_guides" using the trophy name in English and limit: 8.
- If player progress was identified and no additional guide search is required (or the query is purely about pending list), respond tactically using "check_player_progress" data.
- If the user selects a numbered option or route (e.g. "1", "2", "Option 1", "Option 2"), use conversation history and gathered data to map out that route. Call "search_trophy_guides" only if specific trophy details are needed.
- Do not make more than 2 tool calls in the same response. Be direct, practical, cite sources, and respond in clear, professional English.${prefetchPromptAddition}

${personaInstructions}`
      : `Você é o Platina AI Agent, um assistente gamer autônomo especialista em platinas PlayStation.
Você tem acesso a ferramentas para:
1. "check_player_progress": consultar os troféus já conquistados e pendentes de um jogador na PSN.
2. "search_trophy_guides": buscar trechos verificados no banco vetorial de guias de troféus.

Diretrizes do Agente e Arquitetura de Idioma:
- OBRIGATÓRIO: TODOS os argumentos das ferramentas (query, game, troféus, missões) devem ser escritos em INGLÊS. Traduza a pergunta do usuário para termos em inglês antes de chamar qualquer ferramenta (ex: se o usuário perguntou em português "Como pego o troféu de cartas?", passe query: "Card Collector", game: "The Witcher 3: Wild Hunt").
- Use SEMPRE os nomes oficiais de troféus, quests e personagens em inglês nas chamadas de ferramentas.
- A resposta final destinada ao usuário deve ser escrita em português (o idioma da sessão/pergunta).
- Se o usuário mencionar um PSN ID ou perguntar o que precisa fazer a seguir em um jogo, chame "check_player_progress" para ver a situação real dele.
- Quando o usuário perguntar sobre missões, escolhas de história, pontos de não retorno (ex: "Antes de Kaer Morhen", "se aceitar oferta", "missáveis em Novigrad"), contratos ou troféus perdíveis de uma região/DLC, chame OBRIGATORIAMENTE "search_trophy_guides" com termos concisos em inglês (ex: query: "Kaer Morhen", "Full Crew", "Woodland Spirit", "Hearts of Stone missable") e game em inglês para obter os trechos verificados do guia antes de responder.
- Se o retorno de "check_player_progress" trouxer "unearned_trophies_summary", USE essa lista de troféus pendentes reais do jogador para responder quais troféus faltam ou qual é o mais fácil/rápido de fazer.
- Para buscar no banco de guias com "search_trophy_guides", envie SEMPRE o nome exato do troféu curto e limpo em inglês (ex: query: "Card Collector", "Masterminds", "Kifflom", "Cryptozoologist"), NUNCA concatene a descrição inteira do troféu, palavras como "silver", "bronze" ou textos longos na query de busca.${isDeepWalkthrough ? ' No modo detalhado, passe limit: 8 para obter contexto abrangente.' : ''}
- Quando o usuário perguntar sobre cartas, colecionáveis ou passos detalhados de um troféu, chame "search_trophy_guides" usando o nome do troféu em inglês (ex: query: "Card Collector" para troféu de cartas de Gwent) e limit: 8.
- Se você identificou o progresso do jogador e nenhum guia vetorial adicional for necessário (ou a dúvida for apenas sobre a lista de pendências), responda usando os dados retornados de "check_player_progress" de forma tática.
- Se o usuário responder escolhendo uma opção numérica ou rota (ex: "1", "2", "Rota 1", "Rota 2"), use o histórico da conversa e os dados já obtidos para traçar o plano detalhado dessa rota específica. Chame "search_trophy_guides" apenas se precisar de detalhes de um troféu específico dessa rota.
- Não execute mais de 2 chamadas de ferramentas na mesma resposta. Seja direto, prático e cite as fontes.${prefetchPromptAddition}

${personaInstructions}`;

    // ponytail: in-memory history slice passed from client; upgrade to persisted session store when multi-device sync is needed.
    const historyMessages: Groq.Chat.ChatCompletionMessageParam[] = (options.history ?? []).map((msg) =>
      msg.role === 'assistant'
        ? { role: 'assistant', content: msg.content }
        : { role: 'user', content: msg.content }
    );

    const messages: Groq.Chat.ChatCompletionMessageParam[] = [
      { role: 'system', content: systemPrompt },
      ...historyMessages,
      { role: 'user', content: userMessage },
    ];

    const cascadeModels = [
      this.model,
      ...DEFAULT_MODEL_CASCADE.filter((m) => m !== this.model),
    ];

    const collectedGuideSources: GuideSourceItem[] = [];

    const recordTelemetry = async (finalAnswer: string) => {
      const totalLatencyMs = Number((performance.now() - reqStart).toFixed(2));
      const record = await telemetryService.recordMetric({
        ...(options.sessionId ? { sessionId: options.sessionId } : {}),
        ...(detectedGame ? { game: detectedGame } : {}),
        ...(this.model ? { modelName: this.model } : {}),
        retrievalLatencyMs: Number(retrievalLatencyMs.toFixed(2)),
        rerankerLatencyMs: Number(rerankerLatencyMs.toFixed(2)),
        llmLatencyMs: Number(llmLatencyMs.toFixed(2)),
        totalLatencyMs,
        sampledForQuality: telemetryService.shouldSample(),
        queryPreview: userMessage.slice(0, 100),
      });

      if (record.sampledForQuality && record.id) {
        const guideContexts = collectedGuideSources.map((s) => s.content).filter(Boolean);
        evaluateRagTriad(
          {
            query: userMessage,
            contexts: guideContexts,
            answer: finalAnswer,
          },
          {
            ...(this.client ? { groqClient: this.client } : {}),
            model: this.model,
          }
        )
          .then((evalRes) => {
            if (record.id) {
              telemetryService.updateQualityScore(record.id, {
                faithfulnessScore: evalRes.faithfulness.score,
                contextRelevanceScore: evalRes.contextRelevance.score,
                answerRelevanceScore: evalRes.answerRelevance.score,
              }).catch(() => {});
            }
          })
          .catch((err) => {
            console.error('Non-blocking quality sampling error:', err);
          });
      }
    };

    if (shouldPrefetch && targetPsnId && targetGame) {
      if (options.signal?.aborted) return;

      yield {
        type: 'tool_call',
        toolName: PlayerProgressTool.name,
        toolArgs: { psnId: targetPsnId, game: targetGame },
      };

      let prefetchResult: unknown;
      try {
        prefetchResult = await this.executeTool(PlayerProgressTool.name, {
          psnId: targetPsnId,
          game: targetGame,
        });
      } catch (err: unknown) {
        prefetchResult = { error: err instanceof Error ? err.message : String(err) };
      }

      yield {
        type: 'tool_result',
        toolName: PlayerProgressTool.name,
        toolResult: prefetchResult,
      };

      if (prefetchResult && typeof prefetchResult === 'object') {
        addPlayerProgressToSources(
          prefetchResult as Partial<PlayerProgressResult>,
          collectedGuideSources,
          lang
        );
      }

      const prefetchCallId = `call_prefetch_progress_${Date.now()}`;
      messages.push({
        role: 'assistant',
        content: null,
        tool_calls: [
          {
            id: prefetchCallId,
            type: 'function',
            function: {
              name: PlayerProgressTool.name,
              arguments: JSON.stringify({ psnId: targetPsnId, game: targetGame }),
            },
          },
        ],
      });
      messages.push({
        role: 'tool',
        tool_call_id: prefetchCallId,
        content: JSON.stringify(prefetchResult),
      });
    }

    const verifyAndStreamAnswer = async (
      rawContent: string,
      currentMessages: Groq.Chat.ChatCompletionMessageParam[]
    ): Promise<string> => {
      if (!this.client || !rawContent.trim()) {
        return rawContent;
      }

      // ponytail: in-memory history slice passed from client; upgrade to persisted session store when multi-device sync is needed.
      for (const msg of options.history ?? []) {
        if (msg.role === 'assistant' && msg.content) {
          collectedGuideSources.push({
            title: isEn ? 'Conversation History' : 'Histórico da Conversa',
            content: msg.content,
          });
        }
      }

      const isChoiceOrGreeting =
        shouldPrefetch ||
        Boolean(options.psnId) ||
        /^(1|2|a|b|sim|nao|ok|quero|ola|oi|rota 1|rota 2|yes|no|option 1|option 2|route 1|route 2|hello|hi)/i.test(userMessage.trim()) ||
        /^(1|2|a|b)$/i.test(userMessage.trim()) ||
        userMessage.includes('Mensagem do usuário: 1') ||
        userMessage.includes('Mensagem do usuário: 2') ||
        userMessage.includes('User message: 1') ||
        userMessage.includes('User message: 2') ||
        Boolean(options.history && options.history.length > 0);

      const validation = await groundingValidator.validate(rawContent, collectedGuideSources);
      if (validation.ungroundedClaims.length > 0) {
        console.log('🚨 UNGROUNDED CLAIMS DETECTED:', validation.ungroundedClaims);
        console.log('SOURCES AVAILABLE:', collectedGuideSources.map(s => s.title));
      }
      if (!validation.isValid) {
        // In Deep Walkthrough mode (or answers with > 120 words / multiple listed entities / choice replies)
        // do not reject with hard abort if sources are present
        if (isDeepWalkthrough && collectedGuideSources.length > 0) {
          return rawContent;
        }

        // If it's a direct conversational choice turn or affirmative request and sources include history/progress, let the model respond
        if ((isChoiceOrGreeting || isDeepWalkthrough) && collectedGuideSources.length > 0) {
          return rawContent;
        }

        // If conversational follow-up, let model respond
        if (options.history && options.history.length > 0) {
          return rawContent;
        }

        // If tactical claims were made without any source guides, abort to spec fallback immediately
        // Note: conversational queries or questions where no guides were fetched should cleanly inform the user
        // However, if the answer is conversational / choice-oriented, let it pass rather than hard aborting
        if (collectedGuideSources.length === 0 && validation.ungroundedClaims.length > 0) {
          return isEn
            ? 'Official guide not found for this objective.\nWould you like me to search complementary sources?'
            : 'Guia oficial não encontrado para este objetivo.\nQuer que eu procure em fontes complementares?';
        }

        try {
          const correctiveMessages: Groq.Chat.ChatCompletionMessageParam[] = [
            ...currentMessages,
            { role: 'assistant', content: rawContent },
            {
              role: 'user',
              content: isEn
                ? 'The previous response contained claims not supported by the guide. Rewrite strictly anchored only in verified guide facts in English.'
                : 'A resposta anterior continha afirmações não sustentadas pelo guia. Reescreva de forma estritamente ancorada apenas nos fatos verificados do guia.',
            },
          ];

          const correctiveStart = performance.now();
          const correctiveCompletion = await executeWithModelCascade(
            cascadeModels,
            (model) =>
              this.client!.chat.completions.create(
                {
                  model,
                  messages: correctiveMessages,
                  max_tokens: isDeepWalkthrough ? 2048 : (model.includes('qwen') ? 600 : 800),
                },
                { signal: options.signal }
              )
          );
          llmLatencyMs += performance.now() - correctiveStart;

          const corrected = correctiveCompletion.choices[0]?.message?.content;
          if (corrected) {
            const revalidation = await groundingValidator.validate(corrected, collectedGuideSources);
            if (revalidation.isValid) {
              return corrected;
            }
          }
        } catch {
          // If corrective re-prompt fails, provide a safe grounded fallback rather than hallucinated advice
        }
        return isEn
          ? 'Official guide not found for this objective.\nWould you like me to search complementary sources?'
          : 'Guia oficial não encontrado para este objetivo.\nQuer que eu procure em fontes complementares?';
      }

      return rawContent;
    };

    let step = 0;

    while (step < maxSteps) {
      if (options.signal?.aborted) {
        break;
      }
      step++;

      const llmStart = performance.now();
      const completion = await executeWithModelCascade(
        cascadeModels,
        (model) =>
          this.client!.chat.completions.create(
            {
              model,
              messages,
              tools: this.getAvailableTools(),
              tool_choice: 'auto',
              max_tokens: isDeepWalkthrough ? 2048 : (model.includes('qwen') ? 600 : 800),
            },
            { signal: options.signal }
          )
      );
      llmLatencyMs += performance.now() - llmStart;

      const choice = completion.choices[0];
      if (!choice) {
        yield { type: 'error', error: isEn ? 'No response returned by the model.' : 'Nenhuma resposta retornada pelo modelo.' };
        return;
      }

      const assistantMsg = choice.message;
      messages.push(assistantMsg);

      // Check if model wants to call tools
      const toolCalls = assistantMsg.tool_calls;

      if (!toolCalls || toolCalls.length === 0) {
        // No more tool calls; validate content with Pre-Flight Verification before streaming
        const rawContent = assistantMsg.content ?? '';
        const verifiedContent = await verifyAndStreamAnswer(rawContent, messages);
        const distinctSources = extractDistinctSources(collectedGuideSources);
        const finalContent = appendSourcesFooter(verifiedContent || rawContent, distinctSources, lang);

        yield { type: 'chunk', content: finalContent };
        if (distinctSources.length > 0) {
          yield { type: 'sources', items: distinctSources };
        }
        await recordTelemetry(finalContent);
        yield { type: 'done' };
        return;
      }

      // Execute requested tool calls
      for (const call of toolCalls) {
        if (options.signal?.aborted) break;

        const toolName = call.function.name;
        let toolArgs: Record<string, unknown> = {};
        try {
          toolArgs = JSON.parse(call.function.arguments || '{}');
        } catch {
          toolArgs = {};
        }

        if (toolArgs && typeof toolArgs.game === 'string' && toolArgs.game.trim()) {
          detectedGame = detectedGame || toolArgs.game.trim();
        }

        if (isDeepWalkthrough && toolName === SearchGuidesTool.name) {
          toolArgs.limit = 8;
        }

        yield {
          type: 'tool_call',
          toolName,
          toolArgs,
        };

        if (toolName === SearchGuidesTool.name && typeof toolArgs.game === 'string' && toolArgs.game.trim()) {
          const game = toolArgs.game.trim();
          const query = typeof toolArgs.query === 'string' && toolArgs.query.trim().length >= 2 ? toolArgs.query.trim() : 'guia';
          const probe = await ingestionClient.search({
            query,
            game,
            missable_only: Boolean(toolArgs.missableOnly),
            limit: 1,
          });
          if (probe.length === 0) {
            yield {
              type: 'thought',
              content: isEn
                ? '📥 Unindexed game detected: fetching and indexing community official guide (PowerPyx/PSNProfiles) in database...'
                : '📥 Jogo inédito detectado: obtendo e indexando guia oficial comunitário (PowerPyx/PSNProfiles) no banco de dados...',
            };
          }
        }

        let resultData: unknown;
        try {
          const sessionGame = targetGame || options.game;
          resultData = sessionGame
            ? await this.executeTool(toolName, toolArgs, { sessionGame })
            : await this.executeTool(toolName, toolArgs);
        } catch (err: unknown) {
          resultData = { error: err instanceof Error ? err.message : String(err) };
        }

        if (toolName === SearchGuidesTool.name && resultData && typeof resultData === 'object') {
          const metrics = resultData as { retrieval_latency_ms?: number; reranker_latency_ms?: number };
          if (typeof metrics.retrieval_latency_ms === 'number') {
            retrievalLatencyMs += metrics.retrieval_latency_ms;
          }
          if (typeof metrics.reranker_latency_ms === 'number') {
            rerankerLatencyMs += metrics.reranker_latency_ms;
          }
        }

        if (toolName === SearchGuidesTool.name && resultData && typeof resultData === 'object' && 'results' in resultData) {
          const results = (resultData as { results?: Array<{ title?: string; content?: string; source_url?: string }> }).results;
          if (Array.isArray(results)) {
            for (const item of results) {
              if (item?.content) {
                collectedGuideSources.push({
                  title: item.title || (isEn ? 'Trophy Guide' : 'Guia de Troféus'),
                  content: item.content,
                  sourceUrl: item.source_url || undefined,
                });
              }
            }
          }
        }

        // Also fetch related subguide chunks directly into collectedGuideSources if it's Gwent Card Collector
        if (toolName === SearchGuidesTool.name && toolArgs && typeof toolArgs === 'object') {
          const tArgs = toolArgs as { query?: string; game?: string };
          if (tArgs.query && /card collector|gwent/i.test(tArgs.query) && tArgs.game && /witcher/i.test(tArgs.game)) {
            try {
              const extraSearch = await searchGuidesTool.execute({
                game: tArgs.game,
                query: 'Requisitos Críticos de Cartas Perdíveis Gwent',
                limit: 6,
                missableOnly: true,
              });
              if (extraSearch && typeof extraSearch === 'object') {
                const exMetrics = extraSearch as { retrieval_latency_ms?: number; reranker_latency_ms?: number };
                if (typeof exMetrics.retrieval_latency_ms === 'number') {
                  retrievalLatencyMs += exMetrics.retrieval_latency_ms;
                }
                if (typeof exMetrics.reranker_latency_ms === 'number') {
                  rerankerLatencyMs += exMetrics.reranker_latency_ms;
                }
              }
              if (extraSearch && typeof extraSearch === 'object' && 'results' in extraSearch) {
                const exResults = (extraSearch as { results?: Array<{ title?: string; content?: string; source_url?: string }> }).results;
                if (Array.isArray(exResults)) {
                  for (const ex of exResults) {
                    if (ex?.content && !collectedGuideSources.some((s) => s.title === ex.title)) {
                      collectedGuideSources.push({
                        title: ex.title || (isEn ? 'Cards Subguide' : 'Subguia de Cartas'),
                        content: ex.content,
                        sourceUrl: ex.source_url || undefined,
                      });
                    }
                  }
                }
              }
            } catch {}
          }
        }

        if (toolName === PlayerProgressTool.name && resultData && typeof resultData === 'object') {
          const pData = resultData as Partial<PlayerProgressResult>;
          if (pData.game) {
            detectedGame = detectedGame || pData.game;
          }
          addPlayerProgressToSources(pData, collectedGuideSources, lang);
        }

        yield {
          type: 'tool_result',
          toolName,
          toolResult: resultData,
        };

        // Append tool result message for the next iteration
        messages.push({
          role: 'tool',
          tool_call_id: call.id,
          content: JSON.stringify(resultData),
        });
      }
    }

    // If max steps reached without final text, generate a direct answer from collected messages
    const fallbackStart = performance.now();
    const fallbackCompletion = await executeWithModelCascade(
      cascadeModels,
      (model) =>
        this.client!.chat.completions.create(
          {
            model,
            messages: [
              ...messages,
              {
                role: 'user',
                content: isEn
                  ? 'Synthesize now your final response in English based on all the tools you executed above.'
                  : 'Sintetize agora a sua resposta final com base em todas as ferramentas que você executou acima.',
              },
            ],
            ...(isDeepWalkthrough ? { max_tokens: 2048 } : {}),
          },
          { signal: options.signal }
        )
    );
    llmLatencyMs += performance.now() - fallbackStart;
    const fallbackRawContent = fallbackCompletion.choices[0]?.message?.content ?? '';
    const verifiedContent = await verifyAndStreamAnswer(fallbackRawContent, messages);
    const distinctSources = extractDistinctSources(collectedGuideSources);
    const finalFallbackContent = appendSourcesFooter(
      verifiedContent ||
        fallbackRawContent ||
        (isEn
          ? '\n[Notice: Agent finished gathering data from tools.]'
          : '\n[Aviso: O agente concluiu a coleta de dados das ferramentas.]'),
      distinctSources,
      lang
    );

    yield {
      type: 'chunk',
      content: finalFallbackContent,
    };
    if (distinctSources.length > 0) {
      yield { type: 'sources', items: distinctSources };
    }
    await recordTelemetry(finalFallbackContent);
    yield { type: 'done' };
  }
}

export const platinaAgentRunner = new PlatinaAgentRunner();
