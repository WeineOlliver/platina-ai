import type { FastifyPluginAsync } from 'fastify';
import { telemetryService } from '../../services/observability/telemetry.js';

export const observabilityRoutes: FastifyPluginAsync = async (app) => {
  app.get('/metrics', async (_request, reply) => {
    const metrics = telemetryService.getAggregatedMetrics();
    return reply.status(200).send(metrics);
  });
};
