import type { FastifyPluginAsync } from 'fastify';

// Insight: A robust health check endpoint is foundational for container orchestration (Kubernetes liveness/readiness probes).
// It returns system metadata, uptime, and confirms the event loop is healthy.
export const healthRoutes: FastifyPluginAsync = async (app) => {
  app.get('/health', async () => {
    return {
      status: 'ok',
      service: '@platina-ai/api',
      uptime: process.uptime(),
      timestamp: new Date().toISOString(),
      nodeVersion: process.version,
    };
  });
};
