import type { FastifyPluginAsync } from 'fastify';

// Insight: Versioning APIs (/api/v1) at the route prefix level decouples client contracts
// from future architectural changes, enabling seamless non-breaking upgrades.
export const v1Routes: FastifyPluginAsync = async (app) => {
  app.get('/', async () => {
    return {
      message: 'Platina AI API v1 ready',
      docs: '/api/v1/docs',
    };
  });
};
