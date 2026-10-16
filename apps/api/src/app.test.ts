import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import type { FastifyInstance } from 'fastify';

// Force mock provider during automated test runs for speed & determinism
process.env.AI_PROVIDER = 'mock';

import { buildApp } from './app.js';

describe('Platina AI API - App Suite', () => {
  let app: FastifyInstance;

  beforeAll(async () => {
    app = await buildApp({ logger: false });
    await app.ready();
  });

  afterAll(async () => {
    await app.close();
  });

  it('GET /health returns 200 with service metadata', async () => {
    const response = await app.inject({
      method: 'GET',
      url: '/health',
    });

    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.status).toBe('ok');
    expect(body.service).toBe('@platina-ai/api');
    expect(typeof body.uptime).toBe('number');
  });

  it('GET /api/v1 returns 200 with welcome payload', async () => {
    const response = await app.inject({
      method: 'GET',
      url: '/api/v1',
    });

    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.message).toBe('Platina AI API v1 ready');
  });

  it('GET /non-existent returns 404', async () => {
    const response = await app.inject({
      method: 'GET',
      url: '/non-existent-route',
    });

    expect(response.statusCode).toBe(404);
  });

  it('POST /api/v1/chat fails validation with empty body', async () => {
    const response = await app.inject({
      method: 'POST',
      url: '/api/v1/chat',
      payload: {},
    });

    expect(response.statusCode).toBe(400);
  });

  it('POST /api/v1/chat streams Server-Sent Events', { timeout: 15000 }, async () => {
    const response = await app.inject({
      method: 'POST',
      url: '/api/v1/chat',
      payload: {
        message: 'Quais troféus perdíveis existem no capítulo 3 de Red Dead Redemption?',
        game: 'Red Dead Redemption',
      },
    });

    expect(response.statusCode).toBe(200);
    expect(response.headers['content-type']).toContain('text/event-stream');
    expect(response.headers['cache-control']).toContain('no-cache');

    const body = response.body;
    expect(body).toContain('data: {"type":"chunk"');
    expect(body).toContain('data: {"type":"done"');
  });

  describe('JWT Authentication Suite', () => {
    it('POST /api/v1/auth/login rejects invalid credentials with 401', async () => {
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/auth/login',
        payload: {
          email: 'hunter@platina.ai',
          password: 'wrong_password',
        },
      });

      expect(response.statusCode).toBe(401);
    });

    it('POST /api/v1/auth/login succeeds and returns JWT token', async () => {
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/auth/login',
        payload: {
          email: 'hunter@platina.ai',
          password: 'platina123',
        },
      });

      expect(response.statusCode).toBe(200);
      const data = response.json();
      expect(typeof data.token).toBe('string');
      expect(data.user.email).toBe('hunter@platina.ai');
      expect(data.user.username).toBe('hunter');
    });

    it('GET /api/v1/auth/me rejects request without Authorization header', async () => {
      const response = await app.inject({
        method: 'GET',
        url: '/api/v1/auth/me',
      });

      expect(response.statusCode).toBe(401);
    });

    it('GET /api/v1/auth/me returns authenticated user payload when valid token is supplied', async () => {
      // 1. Login to get token
      const loginRes = await app.inject({
        method: 'POST',
        url: '/api/v1/auth/login',
        payload: {
          email: 'arthur.morgan@van-der-linde.com',
          password: 'platina123',
        },
      });
      const { token } = loginRes.json();

      // 2. Call protected route
      const meRes = await app.inject({
        method: 'GET',
        url: '/api/v1/auth/me',
        headers: {
          authorization: `Bearer ${token}`,
        },
      });

      expect(meRes.statusCode).toBe(200);
      const meData = meRes.json();
      expect(meData.authenticated).toBe(true);
      expect(meData.user.email).toBe('arthur.morgan@van-der-linde.com');
      expect(meData.user.username).toBe('arthur.morgan');
    });
  });

  describe('Structured Output - Roadmap Suite', () => {
    it('POST /api/v1/trophies/roadmap fails validation when game is missing or too short', async () => {
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/trophies/roadmap',
        payload: { game: 'A' },
      });

      expect(response.statusCode).toBe(400);
    });

    it('POST /api/v1/trophies/roadmap returns valid structured roadmap schema', async () => {
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/trophies/roadmap',
        payload: { game: 'Bloodborne' },
      });

      expect(response.statusCode).toBe(200);
      const data = response.json();
      expect(data.game).toBe('Bloodborne');
      expect(typeof data.difficulty).toBe('number');
      expect(typeof data.estimatedHours).toBe('number');
      expect(typeof data.hasOnlineTrophies).toBe('boolean');
      expect(Array.isArray(data.missables)).toBe(true);
      expect(Array.isArray(data.recommendedRoute)).toBe(true);
      expect(data.recommendedRoute.length).toBeGreaterThan(0);
    });
  });

  describe('Agent Loop Suite', () => {
    it('POST /api/v1/agent/run streams thought and execution steps via SSE', async () => {
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/agent/run',
        payload: {
          message: 'O que devo fazer agora em Bloodborne?',
          psnId: 'OlliverHunter',
          game: 'Bloodborne',
        },
      });

      expect(response.statusCode).toBe(200);
      expect(response.headers['content-type']).toContain('text/event-stream');
      const body = response.body;
      expect(body).toContain('data: {"type":');
      expect(body).toContain('"done"');
    });
  });
});
