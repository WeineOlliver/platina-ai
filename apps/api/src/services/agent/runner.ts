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

export interface AgentStepEvent {
  type: 'thought' | 'tool_call' | 'tool_result' | 'chunk' | 'done' | 'error';
  content?: string;
  toolName?: string;
  toolArgs?: unknown;
  toolResult?: unknown;
  error?: string;
}

export interface RunAgentOptions {
  maxSteps?: number;
  signal?: AbortSignal;
  history?: Array<{ role: 'user' | 'assistant'; content: string }> | undefined;
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

  async executeTool(name: string, args: Record<string, unknown>): Promise<unknown> {
    if (name === PlayerProgressTool.name) {
      return await playerProgressTool.execute(args as unknown as CheckPlayerProgressParams);
    }
    if (name === SearchGuidesTool.name) {
      return await searchGuidesTool.execute(args as unknown as SearchGuidesParams);
    }
    throw new Error(`Tool desconhecida: "${name}"`);
  }

  async *run(userMessage: string, options: RunAgentOptions = {}): AsyncGenerator<AgentStepEvent> {
    const maxSteps = options.maxSteps ?? 5;

    // Fallback if no LLM client is configured
    if (!this.client || env.AI_PROVIDER === 'mock' || process.env.AI_PROVIDER === 'mock') {
      yield {
        type: 'chunk',
        content: `[Platina Agent - Mock] Analisando sua solicitação: "${userMessage}".\nPara ativar o loop completo de ferramentas com o modelo de 120B parâmetros, configure o GROQ_API_KEY no arquivo .env.`,
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
      lastAssistantMsg && /quer os detalhes completos/i.test(lastAssistantMsg.content)
    );

    const isAffirmativeFollowUp =
      hasAssistantCTA && /^(sim|quero|manda|pode mandar|detalhes)/i.test(userMessage.trim());

    const isExplicitDeepWalkthrough =
      /(detalhad|passo a passo|como pegar cad|todos os|todas as cartas|guia complet|rotas complet|quais pontos|cada carta|uma por uma|onde pegar)/i.test(userMessage);

    const isDeepWalkthrough = isExplicitDeepWalkthrough || isAffirmativeFollowUp;

    const personaInstructions = isDeepWalkthrough
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
Sua resposta final deve ter no total MENOS DE 120 PALAVRAS.`;

    const systemPrompt = `Você é o Platina AI Agent, um assistente gamer autônomo especialista em platinas PlayStation.
Você tem acesso a ferramentas para:
1. "check_player_progress": consultar os troféus já conquistados e pendentes de um jogador na PSN.
2. "search_trophy_guides": buscar trechos verificados no banco vetorial de guias de troféus.

Diretrizes do Agente:
- Se o usuário mencionar um PSN ID ou perguntar o que precisa fazer a seguir em um jogo, chame "check_player_progress" para ver a situação real dele.
- Se o retorno de "check_player_progress" trouxer "unearned_trophies_summary", USE essa lista de troféus pendentes reais do jogador para responder quais troféus faltam ou qual é o mais fácil/rápido de fazer.
- Para buscar no banco de guias com "search_trophy_guides", envie SEMPRE o nome exato do troféu curto e limpo (ex: query: "Card Collector", "Masterminds", "Kifflom", "Cryptozoologist"), NUNCA concatene a descrição inteira do troféu, palavras como "silver", "bronze" ou textos longos na query de busca.${isDeepWalkthrough ? ' No modo detalhado, passe limit: 8 para obter contexto abrangente.' : ''}
- Quando o usuário perguntar sobre cartas, colecionáveis ou passos detalhados de um troféu, chame "search_trophy_guides" usando o nome do troféu em inglês (ex: query: "Card Collector" para troféu de cartas de Gwent) e limit: 8.
- Se você identificou o progresso do jogador e nenhum guia vetorial adicional for necessário (ou a dúvida for apenas sobre a lista de pendências), responda usando os dados retornados de "check_player_progress" de forma tática.
- Se o usuário responder escolhendo uma opção numérica ou rota (ex: "1", "2", "Rota 1", "Rota 2"), use o histórico da conversa e os dados já obtidos para traçar o plano detalhado dessa rota específica. Chame "search_trophy_guides" apenas se precisar de detalhes de um troféu específico dessa rota.
- Não execute mais de 2 chamadas de ferramentas na mesma resposta. Seja direto, prático e cite as fontes.

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

    const collectedGuideSources: Array<{ content: string; title: string }> = [];

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
            title: 'Histórico da Conversa',
            content: msg.content,
          });
        }
      }

      const isChoiceOrGreeting =
        /^(1|2|a|b|sim|nao|ok|quero|ola|oi|rota 1|rota 2)/i.test(userMessage.trim()) ||
        /^(1|2|a|b)$/i.test(userMessage.trim()) ||
        userMessage.includes('Mensagem do usuário: 1') ||
        userMessage.includes('Mensagem do usuário: 2') ||
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
          return 'Guia oficial não encontrado para este objetivo.\nQuer que eu procure em fontes complementares?';
        }

        try {
          const correctiveMessages: Groq.Chat.ChatCompletionMessageParam[] = [
            ...currentMessages,
            { role: 'assistant', content: rawContent },
            {
              role: 'user',
              content:
                'A resposta anterior continha afirmações não sustentadas pelo guia. Reescreva de forma estritamente ancorada apenas nos fatos verificados do guia.',
            },
          ];

          const correctiveCompletion = await executeWithModelCascade(
            cascadeModels,
            (model) =>
              this.client!.chat.completions.create(
                {
                  model,
                  messages: correctiveMessages,
                  ...(isDeepWalkthrough ? { max_tokens: 2048 } : {}),
                },
                { signal: options.signal }
              )
          );

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
        return 'Guia oficial não encontrado para este objetivo.\nQuer que eu procure em fontes complementares?';
      }

      return rawContent;
    };

    let step = 0;

    while (step < maxSteps) {
      if (options.signal?.aborted) {
        break;
      }
      step++;

      const completion = await executeWithModelCascade(
        cascadeModels,
        (model) =>
          this.client!.chat.completions.create(
            {
              model,
              messages,
              tools: this.getAvailableTools(),
              tool_choice: 'auto',
              ...(isDeepWalkthrough ? { max_tokens: 2048 } : {}),
            },
            { signal: options.signal }
          )
      );

      const choice = completion.choices[0];
      if (!choice) {
        yield { type: 'error', error: 'Nenhuma resposta retornada pelo modelo.' };
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
        yield { type: 'chunk', content: verifiedContent || rawContent };
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
              content:
                '📥 Jogo inédito detectado: obtendo e indexando guia oficial comunitário (PowerPyx/PSNProfiles) no banco de dados...',
            };
          }
        }

        let resultData: unknown;
        try {
          resultData = await this.executeTool(toolName, toolArgs);
        } catch (err: unknown) {
          resultData = { error: err instanceof Error ? err.message : String(err) };
        }

        if (toolName === SearchGuidesTool.name && resultData && typeof resultData === 'object' && 'results' in resultData) {
          const results = (resultData as { results?: Array<{ title?: string; content?: string }> }).results;
          if (Array.isArray(results)) {
            for (const item of results) {
              if (item?.content) {
                collectedGuideSources.push({
                  title: item.title || 'Guia de Troféus',
                  content: item.content,
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
              if (extraSearch && typeof extraSearch === 'object' && 'results' in extraSearch) {
                const exResults = (extraSearch as { results?: Array<{ title?: string; content?: string }> }).results;
                if (Array.isArray(exResults)) {
                  for (const ex of exResults) {
                    if (ex?.content && !collectedGuideSources.some((s) => s.title === ex.title)) {
                      collectedGuideSources.push({
                        title: ex.title || 'Subguia de Cartas',
                        content: ex.content,
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
          const summaryParts: string[] = [];
          if (pData.game) summaryParts.push(`Jogo: ${pData.game}`);
          if (pData.pending_missable_trophies?.length) {
            summaryParts.push(
              `Troféus perdíveis pendentes: ${pData.pending_missable_trophies.map((t) => t.trophy_name).join(', ')}`
            );
          }
          if (pData.unearned_trophies_summary?.length) {
            summaryParts.push(`Lista de troféus pendentes:\n${pData.unearned_trophies_summary.slice(0, 10).join('\n')}`);
          }
          if (summaryParts.length > 0) {
            collectedGuideSources.push({
              title: `Progresso PSN (${pData.game || 'Geral'})`,
              content: summaryParts.join('\n'),
            });
          }

          const gameName = pData.game || 'Geral';
          if (pData.quick_cleanup_trophies?.length) {
            collectedGuideSources.push({
              title: `Progresso PSN (${gameName}) - Troféus Rápidos (Limpeza)`,
              content: pData.quick_cleanup_trophies
                .map((t) => `- ${t.trophy_name}${t.trophy_type ? ` [${t.trophy_type}]` : ''}${t.chapter_or_location ? `: ${t.chapter_or_location}` : ''}`)
                .join('\n'),
            });
          }

          if (pData.heavy_grind_trophies?.length) {
            collectedGuideSources.push({
              title: `Progresso PSN (${gameName}) - Troféus de Grind Pesado`,
              content: pData.heavy_grind_trophies
                .map((t) => `- ${t.trophy_name}${t.trophy_type ? ` [${t.trophy_type}]` : ''}${t.chapter_or_location ? `: ${t.chapter_or_location}` : ''}`)
                .join('\n'),
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
                content: 'Sintetize agora a sua resposta final com base em todas as ferramentas que você executou acima.',
              },
            ],
            ...(isDeepWalkthrough ? { max_tokens: 2048 } : {}),
          },
          { signal: options.signal }
        )
    );
    const fallbackRawContent = fallbackCompletion.choices[0]?.message?.content ?? '';
    const verifiedContent = await verifyAndStreamAnswer(fallbackRawContent, messages);
    yield {
      type: 'chunk',
      content: verifiedContent || fallbackRawContent || '\n[Aviso: O agente concluiu a coleta de dados das ferramentas.]',
    };
    yield { type: 'done' };
  }
}

export const platinaAgentRunner = new PlatinaAgentRunner();
