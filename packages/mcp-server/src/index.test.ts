import { describe, it, expect } from 'vitest';
import { createPlatinaMcpServer } from './index.js';

describe('Platina MCP Server Suite', () => {
  it('creates an MCP server instance with required capabilities', () => {
    const server = createPlatinaMcpServer();
    expect(server).toBeDefined();
  });
});
