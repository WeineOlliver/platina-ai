import type { FastifyPluginAsync } from 'fastify';
import fp from 'fastify-plugin';
import fastifyRateLimit from '@fastify/rate-limit';

// Insight: Rate limiting protects both our internal event loop and external LLM API quotas.
// It mitigates Denial of Service (DoS) attacks and prevents accidental infinite loops from frontends
// running through the entire monthly Groq/OpenAI token quota.
const plugin: FastifyPluginAsync = async (app) => {
  await app.register(fastifyRateLimit, {
    max: 100, // Máximo de 100 requisições por janela
    timeWindow: '1 minute',
    allowList: ['127.0.0.1'], // Permite testes locais contínuos
    errorResponseBuilder: (request, context) => {
      return {
        statusCode: 429,
        error: 'Too Many Requests',
        message: `Limite de requisições excedido. Tente novamente em ${context.after}.`,
        retryAfter: context.after,
      };
    },
  });
};

export const rateLimitPlugin = fp(plugin, {
  name: 'rate-limit-plugin',
});
