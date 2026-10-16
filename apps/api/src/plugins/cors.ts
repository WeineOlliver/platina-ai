import type { FastifyPluginAsync } from 'fastify';
import fp from 'fastify-plugin';
import fastifyCors from '@fastify/cors';
import { env } from '../config/env.js';

// Insight: Encapsulating third-party Fastify middleware as standalone plugins
// wrapped with `fastify-plugin` ensures cross-route availability while maintaining modularity.
const plugin: FastifyPluginAsync = async (app) => {
  await app.register(fastifyCors, {
    origin: env.CORS_ORIGIN === '*' ? true : env.CORS_ORIGIN.split(','),
    methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
    credentials: true,
  });
};

export const corsPlugin = fp(plugin, {
  name: 'cors-plugin',
});
