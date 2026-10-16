import fastify, { type FastifyInstance, type FastifyServerOptions } from 'fastify';
import { env } from './config/env.js';
import { corsPlugin } from './plugins/cors.js';
import { sensiblePlugin } from './plugins/sensible.js';
import { healthRoutes } from './routes/health.js';
import { v1Routes } from './routes/v1/index.js';

// Insight: The Factory Pattern (`buildApp`) separates server instantiation from network binding.
// This allows integration test suites (e.g. Vitest with fastify.inject()) to execute rapid, in-memory
// HTTP assertions without occupying system TCP ports or causing port collision issues in parallel CI runs.
export const buildApp = async (opts: FastifyServerOptions = {}): Promise<FastifyInstance> => {
  const isProduction = env.NODE_ENV === 'production';

  const app = fastify({
    logger: isProduction
      ? { level: env.LOG_LEVEL }
      : {
          level: env.LOG_LEVEL,
          transport: {
            target: 'pino-pretty',
            options: {
              colorize: true,
              translateTime: 'HH:MM:ss Z',
              ignore: 'pid,hostname',
            },
          },
        },
    ...opts,
  });

  // Core Plugins
  await app.register(sensiblePlugin);
  await app.register(corsPlugin);

  // Routes
  await app.register(healthRoutes);
  await app.register(v1Routes, { prefix: '/api/v1' });

  return app;
};
