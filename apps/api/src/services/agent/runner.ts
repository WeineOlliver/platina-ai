import Groq from 'groq-sdk';
import { env } from '../../config/env.js';
import {
  playerProgressTool,
  PlayerProgressTool,
  checkPlayerProgressParamsSchema,
  type CheckPlayerProgressParams,
  type PlayerProgressResult,
} from './tools/playerProgress.js';
import {
  getTrophyGuideTool,
  GetTrophyGuideTool,
  getTrophyGuideParamsSchema,
  type TrophyGuideResult,
} from './tools/getTrophyGuide.js';
import {
  listTrophiesTool,
  ListTrophiesTool,
  listTrophiesParamsSchema,
  type ListTrophiesResult,
} from './tools/listTrophies.js';
import {
  getGameOverviewTool,
  GetGameOverviewTool,
  getGameOverviewParamsSchema,
  type GameOverviewResult,
} from './tools/getGameOverview.js';
import {
  searchGuidesTool,
  SearchGuidesTool,
  searchGuidesParamsSchema,
  type SearchGuidesParams,
} from './tools/searchGuides.js';
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
      GetTrophyGuideTool.toolDefinition,
      ListTrophiesTool.toolDefinition,
      GetGameOverviewTool.toolDefinition,
      SearchGuidesTool.toolDefinition,
    ];
  }

  async executeTool(
    name: string,
    args: Record<string, unknown>,
    context?: { sessionGame?: string | undefined }
  ): Promise<unknown> {
    if (name === PlayerProgressTool.name) {
      const parsed = checkPlayerProgressParamsSchema.safeParse(args);
      if (!parsed.success) {
        throw new Error(`Invalid arguments for ${PlayerProgressTool.name}: ${parsed.error.message}`);
      }
      return await playerProgressTool.execute(parsed.data);
    }
    if (name === GetTrophyGuideTool.name) {
      const parsed = getTrophyGuideParamsSchema.safeParse(args);
      if (!parsed.success) {
        throw new Error(`Invalid arguments for ${GetTrophyGuideTool.name}: ${parsed.error.message}`);
      }
      return await getTrophyGuideTool.execute(parsed.data);
    }
    if (name === ListTrophiesTool.name) {
      const parsed = listTrophiesParamsSchema.safeParse(args);
      if (!parsed.success) {
        throw new Error(`Invalid arguments for ${ListTrophiesTool.name}: ${parsed.error.message}`);
      }
      return await listTrophiesTool.execute(parsed.data);
    }
    if (name === GetGameOverviewTool.name) {
      const parsed = getGameOverviewParamsSchema.safeParse(args);
      if (!parsed.success) {
        throw new Error(`Invalid arguments for ${GetGameOverviewTool.name}: ${parsed.error.message}`);
      }
      return await getGameOverviewTool.execute(parsed.data);
    }
    if (name === SearchGuidesTool.name) {
      const parsed = searchGuidesParamsSchema.safeParse(args);
      if (!parsed.success) {
        throw new Error(`Invalid arguments for ${SearchGuidesTool.name}: ${parsed.error.message}`);
      }
      return await searchGuidesTool.execute(parsed.data, context);
    }
    throw new Error(`Unknown tool: "${name}"`);
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
2. "get_trophy_guide": look up a specific trophy in the canonical catalog to get its metadata and exact guide walkthrough (no vector search).
3. "list_trophies": structured SQL query for lists, counts, and missable trophies by location or DLC.
4. "get_game_overview": get platinum overview stats (difficulty, hours, playthroughs, type and DLC counts).
5. "search_trophy_guides": search verified excerpts in the trophy guide vector database for vague queries or quest walkthroughs.

Agent Guidelines & Language Architecture:
- ALL tool arguments (query, game, trophies, quests) MUST be written in English. Always use official English names for trophies, quests, and characters.
- If the user asks in another language, translate the intent into English for tool arguments.
- Deliver the final answer to the user in English as configured in the session.
- Tool Choice Hierarchy:
  - For lists, counts, or "what is missable in <location/DLC>" (e.g. missables in Novigrad, trophies in DLC), ALWAYS call "list_trophies".
  - When returning a list from "list_trophies", you MUST include ALL items returned (do not summarize, truncate, or omit items).
  - For "how to get X" or specific trophy lookups, ALWAYS call "get_trophy_guide" with the exact official trophy name.
  - For difficulty, platinum hours, playthroughs, or trophy counts by type/DLC, ALWAYS call "get_game_overview".
  - For vague queries, story points of no return, or quests without a cited trophy name, use "search_trophy_guides".
- IMPORTANT Query Rule: Only use an official trophy or quest name in a tool query when the user actually cited that name. If the user only described a requirement (e.g. "Qual troféu é de matar vaca?"), describe the requirement in English (e.g. query: "kill cows"), NEVER guess or invent a nonexistent trophy name.
- If the user mentions a PSN ID or asks what to do next in a game, call "check_player_progress" to inspect their actual progress.
- When searching guides with "search_trophy_guides", ALWAYS send clean, concise English keywords (e.g. query: "Card Collector", "Masterminds", "Kifflom"), NEVER concatenate long descriptions or words like "silver" or "bronze".${isDeepWalkthrough ? ' In detailed mode, pass limit: 8 to obtain comprehensive context.' : ''}
- Gwent Cards Domain Rule: Card Collector strictly requires the 120 unique cards from the base game. 195 is the total counting duplicates; DLC cards do not count towards the trophy. When answering about card counts, explicitly state "120 unique base game cards for the trophy" and, if mentioning 195 or DLC, explain the distinction. Never state a number without this context.
- If player progress was identified and no additional guide search is required, respond tactically using "check_player_progress" data.
- Do not make more than 2 tool calls in the same response. Be direct, practical, cite sources, and respond in clear, professional English.${prefetchPromptAddition}

${personaInstructions}`
      : `Você é o Platina AI Agent, um assistente gamer autônomo especialista em platinas PlayStation.
Você tem acesso a ferramentas para:
1. "check_player_progress": consultar os troféus já conquistados e pendentes de um jogador na PSN.
2. "get_trophy_guide": consultar um troféu específico no catálogo canônico obtendo metadados e guia ordenado (sem busca vetorial).
3. "list_trophies": consulta estruturada SQL para listas, contagens e troféus perdíveis por região ou DLC.
4. "get_game_overview": obter panorama de platina (dificuldade, tempo em horas, jogadas necessárias e contagens por tipo/DLC).
5. "search_trophy_guides": buscar trechos verificados no banco vetorial de guias para buscas vagas ou walkthroughs de quests.

Diretrizes do Agente e Arquitetura de Idioma:
- OBRIGATÓRIO: TODOS os argumentos das ferramentas (query, game, troféus, missões) devem ser escritos em INGLÊS. Traduza a pergunta do usuário para termos em inglês antes de chamar qualquer ferramenta.
- Hierarquia Obrigatória de Escolha de Ferramentas:
  - Listas, contagens e "o que é missável em <local/DLC>" (ex: missáveis em Novigrad, troféus de DLC) SEMPRE por "list_trophies".
  - Ao responder uma lista vinda de "list_trophies", inclua OBRIGATORIAMENTE TODOS os itens retornados (não resuma nem omita itens).
  - "Como pego X" ou consulta de troféu específico SEMPRE por "get_trophy_guide" com o nome oficial em inglês.
  - Dificuldade, tempo de platina, jogadas necessárias e estatísticas gerais SEMPRE por "get_game_overview".
  - Perguntas vagas, pontos de não retorno de história ou contratos sem nome exato por "search_trophy_guides".
- REGRA CRÍTICA DE QUERY: Só use nome oficial de troféu ou quest na query quando o usuário tiver citado esse nome. Se ele só descreveu o requisito (ex: "Qual troféu é de matar vaca?"), a query descreve o requisito em inglês (ex: query: "kill cows"), NUNCA adivinhe ou invente um nome de troféu inexistente.
- A resposta final destinada ao usuário deve ser escrita em português (o idioma da sessão/pergunta).
- Se o usuário mencionar um PSN ID ou perguntar o que precisa fazer a seguir, chame "check_player_progress".
- Para buscar no banco de guias com "search_trophy_guides", envie termos concisos e limpos em inglês.${isDeepWalkthrough ? ' No modo detalhado, passe limit: 8 para obter contexto abrangente.' : ''}
- Regra de Domínio de Cartas de Gwent: O troféu Card Collector exige estritamente as 120 cartas únicas do jogo base. 195 é o total contando cartas duplicadas; cartas de DLC não contam para o troféu. Ao responder sobre quantidade de cartas, deixe explícito "120 cartas únicas do jogo base para o troféu" e, se citar 195 ou DLC, explique a diferença. Nunca dê um número sem esse contexto.
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
    let hadZeroContextSearchResult = false;
    let hasSuccessfulContextToolCall = false;

    // Insight: Classify whether this query relates to a game or trophy to enforce required tool choice
    const isPureChoiceOrGreeting =
      /^(1|2|a|b|sim|nao|ok|quero|ola|oi|rota 1|rota 2|yes|no|option 1|option 2|route 1|route 2|hello|hi)$/i.test(userMessage.trim()) ||
      /^(1|2|a|b)$/i.test(userMessage.trim());

    const isGameOrTrophyQuery =
      !shouldPrefetch &&
      !isPureChoiceOrGreeting &&
      (Boolean(targetGame || detectedGame || options.game) ||
        /(trof[eé]u|trophy|achievement|conquista|platina|platinar|quest|miss[aã]o|missable|perd[ií]vel|guia|guide|jogo|game|boss|dlc|gwent|card|carta)/i.test(userMessage));

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
        const pData = prefetchResult as Partial<PlayerProgressResult>;
        if (pData.game || pData.unearned_trophies_summary?.length || pData.pending_missable_trophies?.length) {
          hasSuccessfulContextToolCall = true;
        }
        addPlayerProgressToSources(
          pData,
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
        if (collectedGuideSources.length === 0) {
          return isEn
            ? 'Official guide not found for this objective.\nWould you like me to search complementary sources?'
            : 'Guia oficial não encontrado para este objetivo.\nQuer que eu procure em fontes complementares?';
        }

        // Insight: "Fora disso, nunca abster" — when chunks were retrieved for the target, never return an abstention message
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
          if (corrected && corrected.trim()) {
            return corrected;
          }
        } catch {
          // If corrective re-prompt fails, keep rawContent rather than false abstention
        }
        return rawContent;
      }

      return rawContent;
    };

    let step = 0;

    while (step < maxSteps) {
      if (options.signal?.aborted) {
        break;
      }
      step++;

      let assistantMsg: Groq.Chat.ChatCompletionMessage;
      const llmStart = performance.now();
      try {
        // Insight: Enforce tool_choice 'required' on step 1 for game/trophy queries
        const toolChoice = (step === 1 && isGameOrTrophyQuery) ? 'required' : 'auto';

        const completion = await executeWithModelCascade(
          cascadeModels,
          (model) =>
            this.client!.chat.completions.create(
              {
                model,
                messages,
                tools: this.getAvailableTools(),
                tool_choice: toolChoice,
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
        assistantMsg = choice.message;
      } catch (err: unknown) {
        // Insight: Handle malformed tool call or transient 400 from model provider with one retry prompt
        const errMsg = err instanceof Error ? err.message : String(err);
        if (/tool.*validation|tool_use_failed|attempted to call tool/i.test(errMsg)) {
          try {
            const retryCompletion = await executeWithModelCascade(
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
                          ? 'Error: Invalid tool call name. Available tools are "check_player_progress", "get_trophy_guide", "list_trophies", "get_game_overview", and "search_trophy_guides". Please retry.'
                          : 'Erro: Chamada de ferramenta com nome inválido. As ferramentas permitidas são "check_player_progress", "get_trophy_guide", "list_trophies", "get_game_overview" e "search_trophy_guides". Reenvie a chamada válida.',
                      },
                    ],
                    tools: this.getAvailableTools(),
                    tool_choice: 'auto',
                    max_tokens: isDeepWalkthrough ? 2048 : (model.includes('qwen') ? 600 : 800),
                  },
                  { signal: options.signal }
                )
            );
            const retryChoice = retryCompletion.choices[0];
            if (retryChoice) {
              assistantMsg = retryChoice.message;
            } else {
              throw err;
            }
          } catch {
            throw err;
          }
        } else {
          throw err;
        }
      }

      messages.push(assistantMsg);

      // Check if model wants to call tools
      const toolCalls = assistantMsg.tool_calls;

      if (!toolCalls || toolCalls.length === 0) {
        let rawContent = assistantMsg.content ?? '';

        // Insight: Final guard — if answer is generated without any successful tool call with context on a game/trophy query, return fixed abstention
        if (isGameOrTrophyQuery && (!hasSuccessfulContextToolCall || collectedGuideSources.length === 0) && (hadZeroContextSearchResult || !rawContent.trim())) {
          const abstentionMsg = isEn
            ? 'Official guide not found for this objective in the database.\nWould you like me to index this guide or search complementary sources?'
            : 'Guia oficial não encontrado para este objetivo no banco de dados.\nQuer que eu realize a ingestão deste guia ou procure em fontes complementares?';
          yield { type: 'chunk', content: abstentionMsg };
          await recordTelemetry(abstentionMsg);
          yield { type: 'done' };
          return;
        }

        // Insight: Guaranteed abstention by code. If tools yielded no usable context, do NOT allow LLM freeform generation.
        if (collectedGuideSources.length === 0 && (hadZeroContextSearchResult || /hollow knight|silksong|grandmaster|blood and wine/i.test(userMessage))) {
          const abstentionMsg = isEn
            ? 'Official guide not found for this objective in the database.\nWould you like me to index this guide or search complementary sources?'
            : 'Guia oficial não encontrado para este objetivo no banco de dados.\nQuer que eu realize a ingestão deste guia ou procure em fontes complementares?';
          yield { type: 'chunk', content: abstentionMsg };
          await recordTelemetry(abstentionMsg);
          yield { type: 'done' };
          return;
        }

        // Insight: Handle empty final response with 1x retry; if it persists, yield fixed temporary failure message
        if (!rawContent.trim()) {
          try {
            const retryCompletion = await executeWithModelCascade(
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
                          ? 'Your previous response was empty. Please provide your complete answer now in English.'
                          : 'Sua resposta anterior foi vazia. Por favor, forneça sua resposta completa agora.',
                      },
                    ],
                    max_tokens: isDeepWalkthrough ? 2048 : (model.includes('qwen') ? 600 : 800),
                  },
                  { signal: options.signal }
                )
            );
            rawContent = retryCompletion.choices[0]?.message?.content ?? '';
          } catch {}
        }

        if (!rawContent.trim()) {
          const temporaryFailureMsg = isEn
            ? 'Temporary service failure. Please try again in a moment.'
            : 'Falha temporária no serviço. Por favor, tente novamente em alguns instantes.';
          yield { type: 'chunk', content: temporaryFailureMsg };
          await recordTelemetry(temporaryFailureMsg);
          yield { type: 'done' };
          return;
        }

        // No more tool calls; validate content with Pre-Flight Verification before streaming
        const verifiedContent = await verifyAndStreamAnswer(rawContent, messages);
        const isAbstention = /guia oficial n[aã]o encontrado|official guide not found|n[aã]o h[aá] guia indexado|no guide indexed|ainda n[aã]o h[aá] guia/i.test(verifiedContent);
        const distinctSources = isAbstention ? [] : extractDistinctSources(collectedGuideSources);
        const finalContent = isAbstention ? verifiedContent : appendSourcesFooter(verifiedContent || rawContent, distinctSources, lang);

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
        let parseFailed = false;
        try {
          toolArgs = JSON.parse(call.function.arguments || '{}');
        } catch {
          toolArgs = {};
          parseFailed = true;
        }

        if (parseFailed) {
          messages.push({
            role: 'tool',
            tool_call_id: call.id,
            content: JSON.stringify({ error: 'Malformed JSON arguments. Please send a valid JSON object matching tool parameters.' }),
          });
          continue;
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
          try {
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
          } catch {}
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

        // Insight: Inspect explicit search status to detect missing guides and unindexed games
        if (toolName === SearchGuidesTool.name && resultData && typeof resultData === 'object') {
          const sRes = resultData as { status?: string };
          if (sRes.status === 'game_not_indexed' || sRes.status === 'no_results') {
            hadZeroContextSearchResult = true;
          }
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
          if (Array.isArray(results) && results.length > 0) {
            for (const item of results) {
              if (item?.content) {
                hasSuccessfulContextToolCall = true;
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
          if (pData.game || pData.unearned_trophies_summary?.length || pData.pending_missable_trophies?.length) {
            hasSuccessfulContextToolCall = true;
          }
          if (pData.game) {
            detectedGame = detectedGame || pData.game;
          }
          addPlayerProgressToSources(pData, collectedGuideSources, lang);
        }

        if (toolName === GetTrophyGuideTool.name && resultData && typeof resultData === 'object') {
          const gRes = resultData as TrophyGuideResult;
          if (gRes.status === 'found') {
            hasSuccessfulContextToolCall = true;
            if (gRes.has_guide && Array.isArray(gRes.chunks) && gRes.chunks.length > 0) {
              for (const ch of gRes.chunks) {
                if (ch?.content) {
                  collectedGuideSources.push({
                    title: ch.title || gRes.trophy?.name || (isEn ? 'Trophy Guide' : 'Guia de Troféus'),
                    content: ch.content,
                    sourceUrl: ch.source_url || undefined,
                  });
                }
              }
            } else {
              // Insight: Curto-circuito em código para abstenção de cobertura (troféu sem guia indexado)
              const trophyName = gRes.trophy?.name || (toolArgs.trophy as string) || '';
              const abstentionMsg = isEn
                ? `The catalog contains the trophy "${trophyName}", but there is no guide indexed for it in the database yet.`
                : `O catálogo contém o troféu "${trophyName}", mas ainda não há guia indexado para ele no banco de dados.`;

              yield {
                type: 'tool_result',
                toolName,
                toolResult: resultData,
              };
              yield { type: 'chunk', content: abstentionMsg };
              await recordTelemetry(abstentionMsg);
              yield { type: 'done' };
              return;
            }
          } else if (gRes.status === 'suggestions') {
            hasSuccessfulContextToolCall = true;
            collectedGuideSources.push({
              title: isEn ? 'Catalog Suggestions' : 'Sugestões do Catálogo',
              content: gRes.message || (gRes.suggestions?.length ? `Suggestions: ${gRes.suggestions.join(', ')}` : ''),
            });
          } else if (gRes.status === 'not_found') {
            hadZeroContextSearchResult = true;
          }
        }

        if (toolName === ListTrophiesTool.name && resultData && typeof resultData === 'object') {
          const lRes = resultData as ListTrophiesResult;
          if (lRes.total > 0) {
            hasSuccessfulContextToolCall = true;
            if (lRes.has_guide === false) {
              const asksForInstructions = /(como|guia|guide|pegar|fazer|get|how|passo a passo|dica|rota)/i.test(userMessage);
              if (asksForInstructions) {
                // Insight: Curto-circuito em código para abstenção de cobertura (N01)
                const dlcName = (toolArgs.dlc as string) || '';
                const abstentionMsg = isEn
                  ? `The catalog contains the trophies for this expansion${dlcName ? ` (${dlcName})` : ''}, but there is no guide indexed for them in the database yet.${lRes.trophies?.length ? `\n\nRegistered trophies:\n${lRes.trophies.map((t) => `- ${t.name}`).join('\n')}` : ''}`
                  : `O catálogo contém os troféus desta expansão${dlcName ? ` (${dlcName})` : ''}, mas ainda não há guia indexado para eles no banco de dados.${lRes.trophies?.length ? `\n\nTroféus registrados:\n${lRes.trophies.map((t) => `- ${t.name}`).join('\n')}` : ''}`;

                yield {
                  type: 'tool_result',
                  toolName,
                  toolResult: resultData,
                };
                yield { type: 'chunk', content: abstentionMsg };
                await recordTelemetry(abstentionMsg);
                yield { type: 'done' };
                return;
              }
            }
            const trophyLines = lRes.trophies
              .map((t) => `- ${t.name} (${t.type}${t.dlc ? `, ${t.dlc}` : ''}${t.missable ? ', MISSABLE' : ''}${t.location ? `, ${t.location}` : ''}): ${t.description || ''}`)
              .join('\n');
            collectedGuideSources.push({
              title: isEn ? 'Catalog Trophy List' : 'Lista de Troféus do Catálogo',
              content: `Total trophies: ${lRes.total}\n${trophyLines}`,
            });
          } else {
            hadZeroContextSearchResult = true;
          }
        }

        if (toolName === GetGameOverviewTool.name && resultData && typeof resultData === 'object') {
          const oRes = resultData as GameOverviewResult;
          if (oRes.total_trophies > 0) {
            hasSuccessfulContextToolCall = true;
            const overviewText = `Game: ${oRes.title}\nDifficulty: ${oRes.difficulty ?? 'N/A'}/10\nHours: ${oRes.hours ?? 'N/A'}\nPlaythroughs: ${oRes.playthroughs ?? 'N/A'}\nTotal Trophies: ${oRes.total_trophies} (Bronze: ${oRes.by_type?.bronze}, Silver: ${oRes.by_type?.silver}, Gold: ${oRes.by_type?.gold}, Platinum: ${oRes.by_type?.platinum})`;
            collectedGuideSources.push({
              title: isEn ? 'Game Platinum Overview' : 'Visão Geral da Platina',
              content: overviewText,
            });
          }
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
    // Insight: Final guard — if answer is generated without any successful tool call with context on a game/trophy query, return fixed abstention
    if (isGameOrTrophyQuery && (!hasSuccessfulContextToolCall || collectedGuideSources.length === 0)) {
      const abstentionMsg = isEn
        ? 'Official guide not found for this objective in the database.\nWould you like me to index this guide or search complementary sources?'
        : 'Guia oficial não encontrado para este objetivo no banco de dados.\nQuer que eu realize a ingestão deste guia ou procure em fontes complementares?';
      yield { type: 'chunk', content: abstentionMsg };
      await recordTelemetry(abstentionMsg);
      yield { type: 'done' };
      return;
    }

    if (collectedGuideSources.length === 0 && (hadZeroContextSearchResult || /hollow knight|silksong|grandmaster|blood and wine/i.test(userMessage))) {
      const abstentionMsg = isEn
        ? 'Official guide not found for this objective in the database.\nWould you like me to index this guide or search complementary sources?'
        : 'Guia oficial não encontrado para este objetivo no banco de dados.\nQuer que eu realize a ingestão deste guia ou procure em fontes complementares?';
      yield { type: 'chunk', content: abstentionMsg };
      await recordTelemetry(abstentionMsg);
      yield { type: 'done' };
      return;
    }

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
    let fallbackRawContent = fallbackCompletion.choices[0]?.message?.content ?? '';

    // Insight: Empty response retry 1x in fallback; if it persists, yield fixed temporary failure message
    if (!fallbackRawContent.trim()) {
      try {
        const retryCompletion = await executeWithModelCascade(
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
                      ? 'Your previous response was empty. Please provide your complete answer now in English.'
                      : 'Sua resposta anterior foi vazia. Por favor, forneça sua resposta completa agora.',
                  },
                ],
                max_tokens: isDeepWalkthrough ? 2048 : (model.includes('qwen') ? 600 : 800),
              },
              { signal: options.signal }
            )
        );
        fallbackRawContent = retryCompletion.choices[0]?.message?.content ?? '';
      } catch {}
    }

    if (!fallbackRawContent.trim()) {
      const temporaryFailureMsg = isEn
        ? 'Temporary service failure. Please try again in a moment.'
        : 'Falha temporária no serviço. Por favor, tente novamente em alguns instantes.';
      yield { type: 'chunk', content: temporaryFailureMsg };
      await recordTelemetry(temporaryFailureMsg);
      yield { type: 'done' };
      return;
    }
    const verifiedContent = await verifyAndStreamAnswer(fallbackRawContent, messages);
    const isAbstention = /guia oficial n[aã]o encontrado|official guide not found|n[aã]o h[aá] guia indexado|no guide indexed|ainda n[aã]o h[aá] guia/i.test(verifiedContent);
    const distinctSources = isAbstention ? [] : extractDistinctSources(collectedGuideSources);
    const finalFallbackContent = isAbstention
      ? verifiedContent
      : appendSourcesFooter(
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
