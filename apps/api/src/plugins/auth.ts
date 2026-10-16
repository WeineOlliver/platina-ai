import type { FastifyPluginAsync, FastifyReply, FastifyRequest } from 'fastify';
import fp from 'fastify-plugin';
import fastifyJwt from '@fastify/jwt';
import { env } from '../config/env.js';

export interface UserPayload {
  id: string;
  email: string;
  username: string;
}

declare module 'fastify' {
  interface FastifyInstance {
    authenticate: (request: FastifyRequest, reply: FastifyReply) => Promise<void>;
  }
}

declare module '@fastify/jwt' {
  interface FastifyJWT {
    user: UserPayload;
  }
}

// Insight: Centralizing authentication as a Fastify decorator hook (`app.authenticate`)
// follows the DRY (Don't Repeat Yourself) principle. Routes can enforce protection simply by
// adding `{ preHandler: [app.authenticate] }` to route configuration options.
const plugin: FastifyPluginAsync = async (app) => {
  await app.register(fastifyJwt, {
    secret: env.JWT_SECRET,
    sign: {
      expiresIn: env.JWT_EXPIRES_IN,
    },
  });

  app.decorate('authenticate', async (request: FastifyRequest, reply: FastifyReply) => {
    try {
      await request.jwtVerify();
    } catch {
      return reply.unauthorized('Invalid, missing, or expired Bearer token');
    }
  });
};

export const authPlugin = fp(plugin, {
  name: 'auth-plugin',
  dependencies: ['sensible-plugin'],
});
