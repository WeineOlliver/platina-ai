import type { FastifyPluginAsync } from 'fastify';
import { chatRoutes } from './chat.js';
import { authRoutes } from './auth.js';
import { roadmapRoutes } from './roadmap.js';
import { agentRoutes } from './agent.js';

// Insight: Versioning APIs (/api/v1) at the route prefix level decouples client contracts
// from future architectural changes, enabling seamless non-breaking upgrades.
export const v1Routes: FastifyPluginAsync = async (app) => {
  app.get('/', async () => {
    return {
      message: 'Platina AI API v1 ready',
      docs: '/api/v1/docs',
    };
  });

  await app.register(authRoutes);
  await app.register(chatRoutes);
  await app.register(roadmapRoutes);
  await app.register(agentRoutes);
};
