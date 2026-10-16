import type { FastifyPluginAsync } from 'fastify';
import { roadmapRequestSchema } from '../../schemas/roadmap.js';
import { structuredLlmService } from '../../services/llm/structured.js';

export const roadmapRoutes: FastifyPluginAsync = async (app) => {
  app.post('/trophies/roadmap', async (request, reply) => {
    // 1. Validação do input do cliente
    const validation = roadmapRequestSchema.safeParse(request.body);
    if (!validation.success) {
      return reply.badRequest(validation.error.message);
    }

    const { game } = validation.data;

    try {
      // 2. Chama o serviço de LLM estruturado
      const roadmap = await structuredLlmService.generateRoadmap(game);
      return reply.send(roadmap);
    } catch (err: unknown) {
      request.log.error({ err }, 'Falha ao gerar roadmap estruturado');
      const message = err instanceof Error ? err.message : 'Erro interno ao gerar roadmap';
      return reply.internalServerError(message);
    }
  });
};
