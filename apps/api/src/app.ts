import { readFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';
import fastify, { type FastifyInstance, type FastifyServerOptions } from 'fastify';
import { env } from './config/env.js';
import { corsPlugin } from './plugins/cors.js';
import { sensiblePlugin } from './plugins/sensible.js';
import { authPlugin } from './plugins/auth.js';
import { rateLimitPlugin } from './plugins/rateLimit.js';
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
  await app.register(rateLimitPlugin);
  await app.register(authPlugin);

  // Serve UI test page directly from server (same-origin, zero CORS issues)
  app.get('/ui', async (request, reply) => {
    const candidatePaths = [
      resolve(process.cwd(), '../../test-chat.html'),
      resolve(process.cwd(), '../test-chat.html'),
      resolve(process.cwd(), 'test-chat.html'),
    ];
    const foundPath = candidatePaths.find((p) => existsSync(p));
    if (!foundPath) {
      return reply.notFound('test-chat.html not found');
    }
    reply.type('text/html; charset=utf-8');
    return readFileSync(foundPath, 'utf-8');
  });

  // Routes
  await app.register(healthRoutes);
  await app.register(v1Routes, { prefix: '/api/v1' });

  return app;
};
