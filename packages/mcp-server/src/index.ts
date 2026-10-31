import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  ListResourcesRequestSchema,
  ReadResourceRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import { z } from 'zod';

// Environment configurations
const INGESTION_SERVICE_URL = process.env.INGESTION_SERVICE_URL || 'http://localhost:8000';
const API_SERVICE_URL = process.env.API_SERVICE_URL || 'http://localhost:3000';

export function createPlatinaMcpServer() {
  const server = new Server(
    {
      name: 'platina-ai-mcp-server',
      version: '0.1.0',
    },
    {
      capabilities: {
        tools: {},
        resources: {},
      },
    }
  );

  // 1. MCP Resources: Expose read-only documents (Guides and Trophy Data)
  server.setRequestHandler(ListResourcesRequestSchema, async () => {
    return {
      resources: [
        {
          uri: 'platina://guides/bloodborne',
          name: 'Guia de Platina - Bloodborne',
          description: 'Visão geral e advertências sobre missables de Bloodborne',
          mimeType: 'text/markdown',
        },
        {
          uri: 'platina://guides/elden-ring',
          name: 'Guia de Platina - Elden Ring',
          description: 'Visão geral e armamentos lendários de Elden Ring',
          mimeType: 'text/markdown',
        },
      ],
    };
  });

  server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
    const { uri } = request.params;
    if (uri === 'platina://guides/bloodborne') {
      return {
        contents: [
          {
            uri,
            mimeType: 'text/markdown',
            text: '# Guia Bloodborne\nAviso Crítico: Eileen the Crow é perdível antes da Lua Vermelha no Distrito da Catedral.',
          },
        ],
      };
    }
    if (uri === 'platina://guides/elden-ring') {
      return {
        contents: [
          {
            uri,
            mimeType: 'text/markdown',
            text: '# Guia Elden Ring\nAviso Crítico: Lança de Gransax é perdível antes de derrotar Maliketh em Farum Azula.',
          },
        ],
      };
    }
    throw new Error(`Recurso não encontrado: ${uri}`);
  });

  // 2. MCP Tools: Expose active capabilities to MCP clients
  server.setRequestHandler(ListToolsRequestSchema, async () => {
    return {
      tools: [
        {
          name: 'get_player_trophies',
          description: 'Inspect earned and pending trophies for the project owner on PSN for a specific game.',
          inputSchema: {
            type: 'object',
            properties: {
              game: { type: 'string', description: 'Game title' },
            },
            required: ['game'],
          },
        },
        {
          name: 'search_trophy_guide',
          description: 'Semantic search in trophy guides via pgvector database.',
          inputSchema: {
            type: 'object',
            properties: {
              query: { type: 'string', description: 'Search term or question about trophy' },
              game: { type: 'string', description: 'Filter by specific game' },
              missableOnly: { type: 'boolean', description: 'Restrict to missable trophies' },
            },
            required: ['query'],
          },
        },
        {
          name: 'get_next_step_briefing',
          description: 'Generate a structured tactical briefing with missable trophy alerts for the project owner in the current game session.',
          inputSchema: {
            type: 'object',
            properties: {
              game: { type: 'string', description: 'Game title' },
            },
            required: ['game'],
          },
        },
      ],
    };
  });

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;

    if (name === 'get_player_trophies') {
      const game = String(args?.game || '');
      const res = await fetch(`${INGESTION_SERVICE_URL}/api/v1/players/me/progress?game=${encodeURIComponent(game)}`);
      if (!res.ok) {
        return {
          content: [{ type: 'text', text: `Failed to fetch trophy progress: HTTP ${res.status}` }],
          isError: true,
        };
      }
      const data = await res.json();
      return {
        content: [{ type: 'text', text: JSON.stringify(data, null, 2) }],
      };
    }

    if (name === 'search_trophy_guide') {
      const query = String(args?.query || '');
      const game = args?.game ? String(args.game) : undefined;
      const missableOnly = Boolean(args?.missableOnly);

      const res = await fetch(`${INGESTION_SERVICE_URL}/api/v1/ingest/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, game, missable_only: missableOnly, limit: 3 }),
      });
      if (!res.ok) {
        return {
          content: [{ type: 'text', text: `Vector search query failed: HTTP ${res.status}` }],
          isError: true,
        };
      }
      const data = await res.json();
      return {
        content: [{ type: 'text', text: JSON.stringify(data, null, 2) }],
      };
    }

    if (name === 'get_next_step_briefing') {
      const game = String(args?.game || '');
      const res = await fetch(`${API_SERVICE_URL}/api/v1/agent/next-step`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ game }),
      });
      if (!res.ok) {
        return {
          content: [{ type: 'text', text: `Failed to generate tactical briefing: HTTP ${res.status}` }],
          isError: true,
        };
      }
      const data = await res.json();
      return {
        content: [{ type: 'text', text: JSON.stringify(data, null, 2) }],
      };
    }

    throw new Error(`Tool desconhecida: ${name}`);
  });

  return server;
}

export async function main() {
  const server = createPlatinaMcpServer();
  const transport = new StdioServerTransport();
  await server.connect(transport);
  process.stderr.write('Platina AI MCP Server listening on stdio\n');
}

if (process.argv[1]?.endsWith('index.js') || process.argv[1]?.endsWith('src/index.ts')) {
  main().catch((err) => {
    process.stderr.write(`Fatal error in MCP Server: ${err}\n`);
    process.exit(1);
  });
}
