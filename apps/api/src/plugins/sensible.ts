import type { FastifyPluginAsync } from 'fastify';
import fastifySensible from '@fastify/sensible';

// Insight: @fastify/sensible decorates Fastify with standard HTTP error constructors
// (e.g., `reply.notFound()`, `reply.badRequest()`). This standardizes RFC 7807 compliant
// error payloads without polluting business logic with repetitive manual status codes.
export const sensiblePlugin: FastifyPluginAsync = async (app) => {
  await app.register(fastifySensible);
};
