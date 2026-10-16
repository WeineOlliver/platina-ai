import type { FastifyPluginAsync } from 'fastify';
import fp from 'fastify-plugin';
import fastifySensible from '@fastify/sensible';

// Insight: By default, Fastify encapsulates plugins in child contexts.
// Wrapping with `fastify-plugin` (fp) breaks encapsulation, making decorators
// like `reply.badRequest()` or `reply.notFound()` globally available across all routes and child contexts.
const plugin: FastifyPluginAsync = async (app) => {
  await app.register(fastifySensible);
};

export const sensiblePlugin = fp(plugin, {
  name: 'sensible-plugin',
});
