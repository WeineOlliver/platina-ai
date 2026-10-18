import Groq from 'groq-sdk';
import { env } from '../../config/env.js';
import { playerProgressTool, PlayerProgressTool, type CheckPlayerProgressParams } from './tools/playerProgress.js';
import { searchGuidesTool, SearchGuidesTool, type SearchGuidesParams } from './tools/searchGuides.js';
import { groundingValidator } from './validator.js';

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

    const systemPrompt = `Você é o Platina AI Agent, um assistente gamer autônomo especialista em platinas PlayStation.
Você tem acesso a ferramentas para:
1. "check_player_progress": consultar os troféus já conquistados e pendentes de um jogador na PSN.
2. "search_trophy_guides": buscar trechos verificados no banco vetorial de guias de troféus.

Diretrizes do Agente:
- Se o usuário mencionar um PSN ID ou perguntar o que precisa fazer a seguir em um jogo, chame "check_player_progress" para ver a situação real dele.
- Se o retorno de "check_player_progress" trouxer "unearned_trophies_summary", USE essa lista de troféus pendentes reais do jogador para responder quais troféus faltam ou qual é o mais fácil/rápido de fazer, em vez de inventar troféus que ele não tem.
- Se houver troféus perdíveis pendentes ou o jogador tiver dúvidas sobre um troféu específico, chame "search_trophy_guides" com query curta e direta (ex: "Masterminds" ou "Cryptozoologist").
- Não execute mais de 2 chamadas de ferramentas na mesma resposta. Seja direto, prático e cite as fontes.

Persona Concisa e Tática (Formato Obrigatório de Resposta):
Sua resposta final deve ter no total MENOS DE 120 PALAVRAS e seguir rigorosamente esta estrutura:
- Linha 1: Troféu alvo + localização (ex: "Troféu: [Nome] em [Localização].").
- Linhas 2-3 (ou 2-4): Ação tática imediata para não perdê-lo (etapa imediata, condição crítica ou ponto de não retorno).
- Linha final: Call to action oferecendo walkthrough completo: "Quer os detalhes completos e rotas deste troféu?"`;

    const messages: Groq.Chat.ChatCompletionMessageParam[] = [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: userMessage },
    ];

    const collectedGuideSources: Array<{ content: string; title: string }> = [];

    const verifyAndStreamAnswer = async (
      rawContent: string,
      currentMessages: Groq.Chat.ChatCompletionMessageParam[]
    ): Promise<string> => {
      if (!this.client || !rawContent.trim()) {
        return rawContent;
      }

      const validation = await groundingValidator.validate(rawContent, collectedGuideSources);
      if (!validation.isValid) {
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

          const correctiveCompletion = await this.client.chat.completions.create(
            {
              model: this.model,
              messages: correctiveMessages,
            },
            { signal: options.signal }
          );

          const corrected = correctiveCompletion.choices[0]?.message?.content;
          if (corrected) {
            return corrected;
          }
        } catch {
          // If corrective re-prompt fails, return rawContent
        }
      }

      return rawContent;
    };

    let step = 0;

    while (step < maxSteps) {
      if (options.signal?.aborted) {
        break;
      }
      step++;

      const completion = await this.client.chat.completions.create(
        {
          model: this.model,
          messages,
          tools: this.getAvailableTools(),
          tool_choice: 'auto',
        },
        { signal: options.signal }
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
        yield { type: 'chunk', content: verifiedContent };
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

        yield {
          type: 'tool_call',
          toolName,
          toolArgs,
        };

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
    const fallbackCompletion = await this.client.chat.completions.create(
      {
        model: this.model,
        messages: [
          ...messages,
          {
            role: 'user',
            content: 'Sintetize agora a sua resposta final com base em todas as ferramentas que você executou acima.',
          },
        ],
      },
      { signal: options.signal }
    );
    const fallbackRawContent = fallbackCompletion.choices[0]?.message?.content ?? '';
    const verifiedContent = await verifyAndStreamAnswer(fallbackRawContent, messages);
    yield {
      type: 'chunk',
      content: verifiedContent || '\n[Aviso: O agente concluiu a coleta de dados das ferramentas.]',
    };
    yield { type: 'done' };
  }
}

export const platinaAgentRunner = new PlatinaAgentRunner();
