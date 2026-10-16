import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import type { FastifyInstance } from 'fastify';
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

  it('POST /api/v1/chat streams Server-Sent Events', async () => {
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
});
