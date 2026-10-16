import type { FastifyPluginAsync } from 'fastify';
import { chatRequestSchema } from '../../schemas/chat.js';
import { createChatStream } from '../../services/chatStream.js';

// Insight: Server-Sent Events (SSE) over HTTP is the industry standard for LLM streaming responses.
// By calling `reply.hijack()`, we take explicit control of the underlying Node.js ServerResponse socket.
// This allows continuous event flushing with zero-overhead streaming while handling client disconnects cleanly.
export const chatRoutes: FastifyPluginAsync = async (app) => {
  app.post('/chat', async (request, reply) => {
    // 1. Strict schema validation
    const validationResult = chatRequestSchema.safeParse(request.body);

    if (!validationResult.success) {
      return reply.badRequest(validationResult.error.message);
    }

    const chatRequest = validationResult.data;

    // 2. Hijack the Fastify response pipeline
    reply.hijack();

    // 3. Set standard SSE HTTP headers
    // Insight: When reply.hijack() is used, Fastify's onSend hook is bypassed.
    // We explicitly attach CORS headers so browsers (including file:// or cross-origin frontends)
    // do not terminate the streaming connection due to CORS enforcement.
    const origin = request.headers.origin || '*';
    reply.raw.writeHead(200, {
      'Access-Control-Allow-Origin': origin,
      'Access-Control-Allow-Credentials': 'true',
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      'Connection': 'keep-alive',
      'X-Accel-Buffering': 'no',
    });

    const abortController = new AbortController();
    reply.raw.on('close', () => {
      if (!reply.raw.writableFinished) {
        abortController.abort();
        request.log.info({ message: 'Client closed connection, stream aborted' });
      }
    });

    // 4. Stream Server-Sent Events to the client
    try {
      const stream = createChatStream(chatRequest, { signal: abortController.signal });

      for await (const chunk of stream) {
        if (abortController.signal.aborted || reply.raw.destroyed) {
          break;
        }

        const payload = `data: ${JSON.stringify(chunk)}\n\n`;
        reply.raw.write(payload);
      }
    } catch (err) {
      request.log.error({ err }, 'Error during SSE stream');
      if (!reply.raw.destroyed) {
        reply.raw.write(`event: error\ndata: ${JSON.stringify({ error: 'Stream error' })}\n\n`);
      }
    } finally {
      if (!reply.raw.destroyed) {
        reply.raw.end();
      }
    }
  });
};
