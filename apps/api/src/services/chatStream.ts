import { randomUUID } from 'node:crypto';
import type { ChatRequest, ChatStreamChunk } from '../schemas/chat.js';

// Insight: Using AsyncGenerators (`async function*`) is the modern TypeScript paradigm
// for asynchronous data streams. It cleanly separates the data production logic (whether from
// Anthropic, OpenAI, or a local pipeline) from the HTTP transport layer (SSE in Fastify).
export interface StreamOptions {
  signal?: AbortSignal | undefined;
}

export async function* createChatStream(
  request: ChatRequest,
  options: StreamOptions = {}
): AsyncGenerator<ChatStreamChunk> {
  const conversationId = request.conversationId ?? randomUUID();

  // If client aborted before starting, exit early
  if (options.signal?.aborted) {
    return;
  }

  // Insight: Until the Anthropic API client is wired in the next task,
  // we provide a realistic token stream answering trophy/platinum questions.
  // This allows frontend/client developers to immediately build against the SSE contract.
  const sampleResponse = `[Platina AI] Analisando sua dúvida sobre troféus de ${request.game ?? 'PlayStation'}...

Para otimizar sua rota rumo à platina, preste atenção aos troféus perdíveis (missables) antes de avançar nos capítulos principais. Em breve trarei os dados indexados diretamente dos guias!`;

  const words = sampleResponse.split(' ');

  for (const word of words) {
    if (options.signal?.aborted) {
      break;
    }

    yield {
      type: 'chunk',
      content: `${word} `,
      conversationId,
    };

    // Small delay to simulate LLM token generation rate (~30ms)
    await new Promise((resolve) => setTimeout(resolve, 25));
  }

  // Terminal done event
  yield {
    type: 'done',
    conversationId,
  };
}
