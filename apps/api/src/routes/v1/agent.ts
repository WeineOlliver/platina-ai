import type { FastifyPluginAsync } from 'fastify';
import { z } from 'zod';
import { platinaAgentRunner } from '../../services/agent/runner.js';
import { nextStepAdvisor } from '../../services/agent/nextStep.js';

const nextStepQuerySchema = z.object({
  psnId: z.string().min(2, 'PSN ID é obrigatório'),
  game: z.string().min(2, 'Nome do jogo é obrigatório'),
});

const agentQuerySchema = z.object({
  message: z.string().trim().min(1, 'A mensagem não pode ser vazia'),
  psnId: z.string().optional(),
  game: z.string().optional(),
  history: z
    .array(
      z.object({
        role: z.enum(['user', 'assistant']),
        content: z.string(),
      })
    )
    .optional(),
});

export const agentRoutes: FastifyPluginAsync = async (app) => {
  // Proactive Next Step recommendation endpoint
  app.post('/agent/next-step', async (request, reply) => {
    const validation = nextStepQuerySchema.safeParse(request.body);
    if (!validation.success) {
      return reply.badRequest(validation.error.message);
    }

    const { psnId, game } = validation.data;
    try {
      const advice = await nextStepAdvisor.generateNextStepAdvice(psnId, game);
      return reply.status(200).send(advice);
    } catch (err: unknown) {
      request.log.error({ err }, 'Erro ao gerar recomendação de próximo passo');
      const msg = err instanceof Error ? err.message : 'Falha interna';
      return reply.internalServerError(msg);
    }
  });
  app.post('/agent/run', async (request, reply) => {
    const validation = agentQuerySchema.safeParse(request.body);
    if (!validation.success) {
      return reply.badRequest(validation.error.message);
    }

    const { message, psnId, game, history } = validation.data;
    request.log.info({ message, psnId, game, historyLength: history?.length }, '📨 Executando agent run');
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
        ...(history ? { history } : {}),
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
      const errorDetail = err instanceof Error ? err.message : String(err);
      if (!reply.raw.destroyed) {
        reply.raw.write(`event: error\ndata: ${JSON.stringify({ error: errorDetail })}\n\n`);
      }
    } finally {
      if (!reply.raw.destroyed) {
        reply.raw.end();
      }
    }
  });
};
