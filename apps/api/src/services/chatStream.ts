import { randomUUID } from 'node:crypto';
import type { ChatRequest, ChatStreamChunk } from '../schemas/chat.js';
import { getLlmProvider } from './llm/provider.js';
import { buildRAGPrompt } from './llm/prompts.js';
import { ingestionClient } from './ingestionClient.js';

export interface StreamOptions {
  signal?: AbortSignal | undefined;
}

// Insight: RAG (Retrieval-Augmented Generation) Orchestration:
// 1. In parallel or before LLM invocation, query the vector store for verified guide chunks.
// 2. Format chunks into context tags (<fontes_verificadas>).
// 3. Instruct the LLM to ground its answer in the retrieved text and cite the source URLs.
export async function* createChatStream(
  request: ChatRequest,
  options: StreamOptions = {}
): AsyncGenerator<ChatStreamChunk> {
  const conversationId = request.conversationId ?? randomUUID();

  if (options.signal?.aborted) {
    return;
  }

  // 1. Retrieve relevant guide chunks from pgvector via ingestion microservice
  const relevantChunks = await ingestionClient.searchGuides(request.message, {
    game: request.game,
    limit: 3,
    signal: options.signal,
  });

  // 2. Construct grounded RAG prompt
  const prompt = buildRAGPrompt(request.message, request.game, relevantChunks);

  const provider = getLlmProvider();

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
