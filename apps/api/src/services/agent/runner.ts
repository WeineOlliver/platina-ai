import Groq from 'groq-sdk';
import { env } from '../../config/env.js';
import { playerProgressTool, PlayerProgressTool, type CheckPlayerProgressParams } from './tools/playerProgress.js';
import { searchGuidesTool, SearchGuidesTool, type SearchGuidesParams } from './tools/searchGuides.js';

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
    if (!this.client || env.AI_PROVIDER === 'mock') {
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
- Se houver troféus perdíveis pendentes ou o jogador tiver dúvidas sobre um troféu, chame "search_trophy_guides" para consultar a estratégia exata no guia.
- Seja amigável, direto, focado em evitar troféus perdíveis (missables) e cite as fontes consultadas.`;

    const messages: Groq.Chat.ChatCompletionMessageParam[] = [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: userMessage },
    ];

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
        // No more tool calls; stream final assistant text response
        const content = assistantMsg.content ?? '';
        yield { type: 'chunk', content };
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

    yield {
      type: 'chunk',
      content: '\n[Aviso: O agente atingiu o limite máximo de etapas de raciocínio.]',
    };
    yield { type: 'done' };
  }
}

export const platinaAgentRunner = new PlatinaAgentRunner();
