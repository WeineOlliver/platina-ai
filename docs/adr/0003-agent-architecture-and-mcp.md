# 3. Agentic Architecture, Tool Calling Contracts, and Model Context Protocol (MCP)

Date: 2026-10-16

## Status
Accepted

## Context
As Platina AI matured from static RAG document injection into an interactive assistant, several architectural challenges emerged:
1. **Dynamic Tool Execution vs. Static Prompt Stuffing:** Naive RAG pipelines query vector databases on every interaction, causing unnecessary latency and query costs for non-technical turns (e.g., greetings). The system needed an autonomous reasoning loop to invoke tools only when justified.
2. **Deterministic Catalog vs. Vector Search:** General walkthrough queries benefit from semantic vector search, but trophy requirements, counts, and missable listings require structured relational SQL queries. The project answers from trophy guides and the game trophy catalog; it does not access any PlayStation Network account or process third-party player personal data.
3. **Safety & Infinite Recursion:** Agent loops calling LLMs iteratively risk runaway token usage and infinite loops if termination boundaries are not enforced.
4. **Third-Party Interoperability:** Proprietary API endpoints lock users into proprietary frontends. Exposing tools via an emerging open standard would enable direct integration into native developer tools (Claude Desktop, Claude Code CLI, Cursor).

## Decision

1. **ReAct Execution Loop in Fastify:**
   - Implemented an asynchronous ReAct (Reasoning + Acting) execution engine in `PlatinaAgentRunner`.
   - The loop alternates between model reasoning, local tool execution, and context observation, streaming intermediate event frames (`tool_call`, `tool_result`, `chunk`, `done`) in real time over Server-Sent Events (SSE).
   - Enforced a hard recursion boundary of `maxSteps: 5` and wired process cancellation to `AbortSignal`.

2. **Zod Runtime Schema Isolation:**
   - Decoupled tool definition from execution. Each tool registers a JSON Schema descriptor for model planning and enforces strict Zod schema validation (`getTrophyGuideParamsSchema`, `listTrophiesParamsSchema`, `searchGuidesParamsSchema`) before executing backend code.
   - Any hallucinated parameters are trapped and returned as structured errors to the model rather than crashing internal microservices.

3. **Canonical Relational Catalog & Entity Linking:**
   - Grounded queries in canonical game and trophy records in PostgreSQL, linked to verified community walkthrough chunks (PowerPyx, PSNProfiles) with zero external account dependencies.

4. **Standalone MCP Server (`@platina-ai/mcp-server`):**
   - Built a dedicated Model Context Protocol server using `@modelcontextprotocol/sdk` communicating over standard input/output (`stdio`).
   - Exposed read-only guides as **MCP Resources** (`platina://guides/{game}`) and operations as **MCP Tools** (`get_trophy_guide`, `list_trophies`, `search_trophy_guide`).

## Consequences

- **Positive:**
  - High factual precision: multi-hop reasoning combines exact SQL catalog inspection with verified vector guide chunks.
  - Zero personal data footprint: operates entirely on publicly verified game guides and trophy metadata without PlayStation Network credentials or telemetry.
  - Intermediate SSE events provide a responsive user experience during multi-step reasoning.
  - Zero-code external interoperability: developers can query Platina AI directly from Claude Desktop or terminal agents via standard MCP configuration.
  - Robust bounds against runaway API billing.

- **Trade-offs:**
  - Multi-step loops consume multiple LLM roundtrips per query, increasing total completion time compared to single-shot static responses.
  - Maintaining dual interfaces (REST/SSE in Fastify and stdio in MCP) requires synchronized tool schemas across packages.
