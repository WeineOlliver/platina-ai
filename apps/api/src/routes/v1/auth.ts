import type { FastifyPluginAsync } from 'fastify';
import { z } from 'zod';

const loginSchema = z.object({
  email: z.string().email('Invalid email address'),
  password: z.string().min(6, 'Password must be at least 6 characters'),
});

// Insight: Stateless JWT authentication allows the API to horizontally scale across multiple
// container instances (e.g., Kubernetes pods) without requiring shared sticky sessions or centralized Redis session stores.
export const authRoutes: FastifyPluginAsync = async (app) => {
  // Public Login Route
  app.post('/auth/login', async (request, reply) => {
    const validation = loginSchema.safeParse(request.body);

    if (!validation.success) {
      return reply.badRequest(validation.error.message);
    }

    const { email, password } = validation.data;

    // For demonstration and initial portfolio testing:
    // In production with database, this verifies bcrypt/argon2 hash against PostgreSQL.
    if (password !== 'platina123') {
      return reply.unauthorized('Invalid email or password');
    }

    const username = email.split('@')[0] ?? 'trophy_hunter';
    const userPayload = {
      id: 'usr_7f8a9b1c',
      email,
      username,
    };

    const token = app.jwt.sign(userPayload);

    return {
      token,
      user: userPayload,
    };
  });

  // Protected Identity Route
  app.get(
    '/auth/me',
    { preHandler: [app.authenticate] },
    async (request) => {
      return {
        authenticated: true,
        user: request.user,
      };
    }
  );
};
