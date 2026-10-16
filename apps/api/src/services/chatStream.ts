import { randomUUID } from 'node:crypto';
import type { ChatRequest, ChatStreamChunk } from '../schemas/chat.js';
import { getLlmProvider } from './llm/provider.js';

export interface StreamOptions {
  signal?: AbortSignal | undefined;
}

// Insight: Decoupling stream chunk formatting from LLM execution allows swapping
// the underlying provider seamlessly without breaking SSE streaming contracts.
export async function* createChatStream(
  request: ChatRequest,
  options: StreamOptions = {}
): AsyncGenerator<ChatStreamChunk> {
  const conversationId = request.conversationId ?? randomUUID();

  if (options.signal?.aborted) {
    return;
  }

  const provider = getLlmProvider();
  const prompt = request.game
    ? `Jogo: ${request.game}\nPergunta do jogador: ${request.message}`
    : request.message;

  try {
    for await (const token of provider.streamChat(prompt, { signal: options.signal })) {
      if (options.signal?.aborted) {
        break;
      }

      yield {
        type: 'chunk',
        content: token,
        conversationId,
      };
    }

    yield {
      type: 'done',
      conversationId,
    };
  } catch (err: unknown) {
    if (options.signal?.aborted) {
      return;
    }

    const errorMessage = err instanceof Error ? err.message : 'Unknown LLM stream error';
    yield {
      type: 'error',
      error: errorMessage,
      conversationId,
    };
  }
}
