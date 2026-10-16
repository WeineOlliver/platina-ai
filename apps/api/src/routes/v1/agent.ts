import type { FastifyPluginAsync } from 'fastify';
import { z } from 'zod';
import { platinaAgentRunner } from '../../services/agent/runner.js';

const agentQuerySchema = z.object({
  message: z.string().min(2, 'A mensagem deve ter pelo menos 2 caracteres'),
  psnId: z.string().optional(),
  game: z.string().optional(),
});

export const agentRoutes: FastifyPluginAsync = async (app) => {
  app.post('/agent/run', async (request, reply) => {
    const validation = agentQuerySchema.safeParse(request.body);
    if (!validation.success) {
      return reply.badRequest(validation.error.message);
    }

    const { message, psnId, game } = validation.data;
    const promptWithContext = [
      psnId ? `PSN ID do jogador: ${psnId}` : null,
      game ? `Jogo: ${game}` : null,
      `Mensagem do usuário: ${message}`,
    ]
      .filter(Boolean)
      .join('\n');

    reply.hijack();

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
      }
    });

    try {
      const generator = platinaAgentRunner.run(promptWithContext, {
        signal: abortController.signal,
      });

      for await (const event of generator) {
        if (abortController.signal.aborted || reply.raw.destroyed) {
          break;
        }

        const payload = `data: ${JSON.stringify(event)}\n\n`;
        reply.raw.write(payload);
      }
    } catch (err: unknown) {
      request.log.error({ err }, 'Erro no loop do agente');
      if (!reply.raw.destroyed) {
        reply.raw.write(`event: error\ndata: ${JSON.stringify({ error: 'Erro no loop do agente' })}\n\n`);
      }
    } finally {
      if (!reply.raw.destroyed) {
        reply.raw.end();
      }
    }
  });
};
