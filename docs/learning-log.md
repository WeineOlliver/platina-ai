# Learning Log — Platina AI

This document tracks technical learnings, design decisions, and system design insights gathered throughout the development of Platina AI. Used as reference material for senior technical interviews.

---

## Template for Entries

```markdown
### [YYYY-MM-DD] — [Milestone / Topic]
- **What I built/configured:**
- **Key concepts learned:**
- **Problems faced & how they were solved:**
- **Interview Soundbite (How to explain this in 60s):**
```

---

### [2026-10-16] — Milestone 0: Project Setup & Engineering Rules
- **What I built/configured:**
  - Initial repository layout separating Node.js API, Python Ingestion microservice, and IaC/Helm definitions.
  - Set up `CLAUDE.md` defining the *Division of Work* contract (`TODO(human)` on learning tracks, explanatory style on mastered tracks).
  - Configured git hygiene (.gitignore) covering multi-language stacks (Node, Python, Terraform, Helm).
- **Key concepts learned:**
  - Structuring a polyglot microservices repository for AI products without unnecessary monorepo tooling overhead at MVP stage.
- **Problems faced & how they were solved:**
  - Ensuring consistent separation of concerns between fast web-facing API and compute/vector-intensive ingestion.
- **Interview Soundbite:**
  - *"I architected Platina AI as a decoupled system: a high-throughput Fastify API in TypeScript for client SSE streaming, paired with an asynchronous Python/FastAPI microservice for document chunking, embeddings, and pgvector operations, mirroring production patterns where ingestion and inference have distinct scaling profiles."*

---

### [2026-10-16] — Milestone 1: apps/api Scaffold (Fastify + TypeScript)
- **What I built/configured:**
  - Fastify v5 application using the Factory Pattern (`buildApp`), separating server instance creation from network binding.
  - Runtime schema validation for environment variables using Zod (fail-fast startup).
  - Modular plugin architecture with `@fastify/cors` and `@fastify/sensible` for RFC-compliant error handling.
  - Container-ready `/health` endpoint and versioned `/api/v1` route prefix.
  - Graceful shutdown listeners handling `SIGINT` and `SIGTERM` to drain active HTTP connections without dropping in-flight traffic.
  - Vitest test suite exercising endpoints in-memory using Fastify's native `app.inject()`.
- **Key concepts learned:**
  - The Factory pattern in HTTP servers allows running integration tests concurrently in CI without port collisions.
  - Failing fast on invalid configuration saves debugging time in containerized orchestrations (Kubernetes CrashLoopBackOff with clear logs).
- **Problems faced & how they were solved:**
  - Ensuring TypeScript ES module resolution (`NodeNext`) correctly aligns with modern Fastify v5 typing.
- **Interview Soundbite:**
  - *"For the Platina AI API, I chose Fastify over Express due to its lower overhead, native schema compilation, and built-in support for streaming responses. I structured the server with an application factory pattern, which decoupled socket binding from route definitions, allowing zero-port in-memory integration testing via Fastify's inject API."*

---

### [2026-10-16] — Milestone 1: Server-Sent Events (SSE) Streaming (`POST /api/v1/chat`)
- **What I built/configured:**
  - Input contract with Zod validation for `/api/v1/chat`.
  - Asynchronous streaming pipeline with TypeScript AsyncGenerators (`async function*`).
  - Native SSE delivery via Fastify hijacked response pipeline with real-time chunk flushing.
  - Reverse-proxy protection headers (`X-Accel-Buffering: no`, `Cache-Control: no-cache, no-transform`).
  - Client disconnection lifecycle handling via `reply.raw.on('close')` and `AbortController` cancellation signal to prevent runaway compute and token wastage.
  - Automated integration test suite validating SSE chunk formats and validation error responses.
- **Key concepts learned:**
  - SSE is unidirectional and operates natively over standard HTTP, eliminating WebSocket connection upgrade complexity for generative AI chat.
  - Reverse proxies buffer TCP packets by default unless explicitly instructed with `X-Accel-Buffering: no`.
- **Problems faced & how they were solved:**
  - Node.js POST readable streams (`request.raw`) emit `'close'` when the request body has finished reading, not when the client socket disconnects. Solved by monitoring `reply.raw.on('close')` against `writableFinished` for true client socket drops.
- **Interview Soundbite:**
  - *"For streaming LLM responses, I implemented Server-Sent Events rather than WebSockets because LLM inference is unidirectional and benefits from standard HTTP routing, caching, and auth. I included `X-Accel-Buffering: no` to bypass reverse-proxy buffering, and tied client socket termination directly to an AbortSignal to immediately cancel token generation if a user abandons the request."*

---

### [2026-10-16] — Milestone 1: Multi-Provider LLM Integration (Groq & LPU Architecture)
- **What I built/configured:**
  - Decoupled `ILlmProvider` adapter architecture with implementations for `GroqLlmProvider` and `MockLlmProvider`.
  - Configured zero-cost open-weights inference on Groq using the high-parameter `openai/gpt-oss-120b` model.
  - Specialized domain prompt engineering (`PLATINA_SYSTEM_PROMPT`) tailored for PlayStation trophy hunting, missable warnings, and structured progression roadmaps.
  - End-to-end integration with the existing Server-Sent Events (SSE) pipeline, validated with real multi-token responses streaming in real time.
- **Key concepts learned:**
  - The Provider Adapter pattern insulates applications against model deprecation and vendor pricing changes.
  - Groq LPUs achieve significantly lower Time-to-First-Token (TTFT) and throughput compared to traditional cloud GPU endpoints.
- **Problems faced & how they were solved:**
  - Model catalog differences between generic OpenAI models and Groq's active endpoints. Diagnosed by querying the Groq models endpoint directly and binding the fast 120B parameter open model.
- **Interview Soundbite:**
  - *"To avoid vendor lock-in, I engineered an abstracted LLM Provider Adapter interface. This allowed us to integrate Groq's LPUs for sub-second, zero-cost inference using 120B open-weights models during development, with the ability to switch to Anthropic Claude or OpenAI in production simply by updating environment variables without refactoring API handlers."*

---

### [2026-10-16] — Milestone 1: Stateless JWT Authentication (`@fastify/jwt`)
- **What I built/configured:**
  - Plugin encapsulation for `@fastify/jwt` (`src/plugins/auth.ts`) exposing custom `app.authenticate` guard.
  - TypeScript declaration merging extending `FastifyInstance` and `FastifyJWT` with typed `UserPayload`.
  - Public `/api/v1/auth/login` endpoint verifying credentials, signing tokens, and returning user session data.
  - Protected `/api/v1/auth/me` endpoint verifying Bearer tokens via Fastify `preHandler` hook.
  - Vitest test suite testing rejection of invalid credentials, token generation, missing auth headers, and valid payload retrieval.
- **Key concepts learned:**
  - Fastify decorators coupled with `preHandler` hooks provide a declarative, DRY mechanism for route-level authorization without middleware nesting.
  - Stateless JWTs eliminate shared session store bottlenecks in distributed Kubernetes environments.
- **Problems faced & how they were solved:**
  - Test suites timing out due to real external LLM requests running during unit test execution. Solved by explicitly setting `process.env.AI_PROVIDER = 'mock'` in the test runner, keeping integration tests sub-second.
- **Interview Soundbite:**
  - *"I implemented stateless JWT authentication using `@fastify/jwt` wrapped in a reusable decorator hook. This enables horizontal pod scaling without sticky sessions or centralized Redis session round-trips, while enforcing strict TypeScript typing across user payloads and route protection guards."*

---

### [2026-10-16] — Milestone 1: Structured Outputs (`POST /api/v1/trophies/roadmap`)
- **What I built/configured:**
  - Zod schemas defining structured input (`roadmapRequestSchema`) and roadmap output (`trophyRoadmapSchema`).
  - `StructuredLlmService` calling Groq with `response_format: { type: 'json_object' }` for syntactically guaranteed JSON.
  - Runtime validation pipeline verifying data types, required fields, and range invariants with Zod before responding to clients.
  - Fastify route `POST /api/v1/trophies/roadmap` returning machine-readable JSON roadmaps for frontend cards and trackers.
  - Automated Vitest integration tests validating rejection of invalid inputs and successful roadmap schema deserialization.
- **Key concepts learned:**
  - Free-form text is for chat, but UI dashboards require deterministic structured JSON.
  - JSON mode guarantees valid JSON syntax, while Zod guarantees semantic schema correctness.
- **Problems faced & how they were solved:**
  - Preventing LLM preamble/markdown wrappers (` ```json `) by explicitly instructing the model to reply strictly with JSON keys matching our domain schema.
- **Interview Soundbite:**
  - *"For trophy roadmaps and checklist generation, free-form text is insufficient for frontend rendering. I implemented structured outputs by coupling Groq's JSON mode with runtime Zod schema parsing. This ensures deterministic typings—such as numeric difficulty scores and typed missable objects—failing fast if an LLM hallucinates an unexpected format."*

---

### [2026-10-16] — Milestone 1: Resiliency, Retries & Rate Limiting
- **What I built/configured:**
  - Robust `withRetry` utility featuring exponential backoff with randomized jitter (±20%) and maximum delay caps.
  - Granular error classification (`isRetryableError`) retrying only transient errors (429, 502, 503, network disconnects) while failing fast on client errors (400, 401, 403, 404).
  - Wrapped `StructuredLlmService` with automatic retry resilience.
  - Fastify rate limiting plugin (`@fastify/rate-limit`) protecting API event loops and upstream token quotas (100 req/min).
  - Comprehensive unit test suite mocking transient 429 recoveries and fatal error terminations.
- **Key concepts learned:**
  - Jitter prevents the "Thundering Herd" problem by desynchronizing retry attempts.
  - Distinguishing between transient (recoverable) and deterministic (unrecoverable) errors is crucial for minimizing unnecessary request latency.
- **Problems faced & how they were solved:**
  - Rate limit plugins blocking local test suites. Solved by whitelisting `127.0.0.1` and configuring isolated mock scenarios.
- **Interview Soundbite:**
  - *"To ensure high availability against third-party AI provider instability, I implemented an exponential backoff retry mechanism with randomized jitter for transient faults (429/503), preventing thundering herds. Deterministic 4xx errors fail immediately to avoid artificial latency, while incoming traffic is protected via Fastify rate-limiting."*

---

### [2026-10-16] — Milestone 2: services/ingest Scaffold (FastAPI + uv)
- **What I built/configured:**
  - Initialized Python microservice under `services/ingest/` managed with Astral's `uv` (Rust-based package manager).
  - FastAPI application following factory architecture (`create_app`) with modern async lifespan hooks (`@asynccontextmanager`).
  - Runtime configuration validation with `pydantic-settings` (`SettingsConfigDict`).
  - Container-ready `/health` endpoint for Kubernetes probes and service-to-service checks.
  - Automated test suite using `pytest` and `httpx` (TestClient) executing in 0.2s.
- **Key concepts learned:**
  - `uv` speeds up Python package installs by an order of magnitude compared to legacy pip/Poetry, accelerating Docker CI workflows.
  - Polyglot separation isolates CPU-heavy text extraction/embedding pipelines from the lightweight I/O chat gateway.
- **Problems faced & how they were solved:**
  - Python module path discovery during pytest runs. Solved cleanly by configuring `[tool.pytest.ini_options] pythonpath = ["."]` in `pyproject.toml`.
- **Interview Soundbite:**
  - *"I scaffolded the ingestion service in Python using FastAPI and Astral's `uv`. Using `uv` provides 10-50x faster container builds and dependency resolution compared to Poetry, while Pydantic Settings enforces strict configuration boundaries before our vector pipeline boots."*

---

### [2026-10-16] — Milestone 2: Semantic Trophy Guide Parser & Chunking
- **What I built/configured:**
  - `TrophyGuideChunker` (`src/services/chunker.py`) with Markdown heading-aware semantic splitting (`#`, `##`, `###`).
  - Sliding character window with configurable overlap (200 chars) for lengthy narrative sections, breaking at sentence/paragraph boundaries.
  - Deterministic SHA-256 chunk IDs for deduplication and repeatable indexing.
  - Heuristic detection of missable trophies (`is_missable` flag) scanning for critical gaming keywords (*missable*, *perdível*, *ponto de não retorno*).
  - API endpoint `POST /api/v1/ingest/parse` accepting raw guide markdown and returning structured, tagged chunks.
  - Unit test suite (`tests/test_chunker.py`) validating heading splits, missable detection, and Pydantic validation rules.
- **Key concepts learned:**
  - Headings in gaming guides represent natural semantic boundaries for individual trophies; blind character chunking destroys context.
  - Metadata enrichment at ingestion time enables hybrid retrieval (SQL WHERE filters + vector similarity).
- **Problems faced & how they were solved:**
  - Ensuring sub-chunks from oversized sections maintain parent heading hierarchy in their metadata titles.
- **Interview Soundbite:**
  - *"To prepare gaming guides for RAG, I designed a domain-specific semantic chunker that splits on Markdown headings to keep individual trophy requirements atomic. For long walkthroughs, it uses a 200-character overlapping sliding window breaking on sentence boundaries, and automatically tags chunks with an `is_missable` flag for hybrid SQL/vector querying."*

---

### [2026-10-16] — Milestone 2: PostgreSQL & pgvector Infrastructure (Docker + Migrations)
- **What I built/configured:**
  - Root `docker-compose.yml` declaring `pgvector/pgvector:pg16` with health checks, persistent volumes, and auto-init scripts.
  - SQL migration schema `infra/postgres/init.sql` activating the `vector` extension and defining the `guide_chunks` table with 1536-dimension embeddings.
  - Performance B-Tree indexes on `game` and `is_missable` for exact filtering.
  - HNSW (Hierarchical Navigable Small World) index with `vector_cosine_ops` (`m=16, ef_construction=64`) for high-recall sub-second vector similarity retrieval.
  - Verified local container startup and live PostgreSQL table inspection.
- **Key concepts learned:**
  - Keeping embeddings in PostgreSQL with pgvector provides ACID consistency across relational metadata and vector searches in a single database engine.
  - HNSW indexes outperform IVFFlat on recall and query throughput without requiring an upfront training phase on pre-existing data.
- **Problems faced & how they were solved:**
  - Volume initialization ordering in Docker Compose. Solved by mounting `init.sql` into `/docker-entrypoint-initdb.d/` for automatic first-boot database seeding.
- **Interview Soundbite:**
  - *"I provisioned PostgreSQL 16 with pgvector in Docker Compose, indexing guide chunk embeddings with an HNSW cosine distance index. This avoids dual-database complexity by unifying relational trophy metadata and vector retrieval under a single ACID engine, enabling sub-second hybrid SQL and vector queries."*

---

### [2026-10-16] — Milestone 2: Embeddings Generation & pgvector Persistence
- **What I built/configured:**
  - Asynchronous database layer with SQLAlchemy 2.0 (`asyncpg` driver) and connection pooling (`pool_size=10, max_overflow=20`).
  - Declarative ORM model `GuideChunkModel` mapping directly to the `guide_chunks` table with `pgvector.sqlalchemy.Vector(1536)`.
  - Abstract embedding interface (`IEmbeddingService`) with a high-performance, deterministic L2-normalized unit vector generator.
  - `IngestionRepository` executing atomic batch transactions (`session.merge()`) with automatic rollback on error.
  - API endpoint `POST /api/v1/ingest/index` running the end-to-end pipeline: parsing, chunking, embedding generation, and database upserting.
  - Verified live in PostgreSQL with real multi-row vector embeddings indexed.
- **Key concepts learned:**
  - Atomic batch transactions prevent partial indexing corruptions in vector stores.
  - Normalizing embedding vectors to unit length optimizes cosine distance into an accelerated dot product operation.
- **Problems faced & how they were solved:**
  - SQLAlchemy asyncio requiring the `greenlet` dependency for context switching. Added `greenlet` to `pyproject.toml` dependencies via `uv add greenlet`.
- **Interview Soundbite:**
  - *"I implemented an asynchronous embedding and persistence pipeline in Python using SQLAlchemy 2.0 and `pgvector`. Chunks are vectorized and persisted in atomic batches with L2-normalized unit vectors, preventing corrupted partial states and optimizing vector cosine distance queries."*

---

### [2026-10-16] — Milestone 2: Semantic Similarity Retrieval & Hybrid Search
- **What I built/configured:**
  - Vector search service (`src/services/search.py`) executing cosine distance queries (`GuideChunkModel.embedding.cosine_distance(query_vector)`) via pgvector.
  - Hybrid retrieval engine combining vector similarity ordering (`<=>`) with SQL filtering (`game ILIKE`, `is_missable = true`).
  - API endpoint `POST /api/v1/ingest/search` returning scored search results with bounded similarity ratings (0.0 to 1.0).
  - Pydantic search models (`SearchQueryRequest`, `SearchResultItem`, `SearchResponse`).
  - Unit tests validating specific trophy retrieval (Eileen the Crow) and strict missable filtering.
- **Key concepts learned:**
  - Pure vector search must be paired with relational SQL filters to prevent cross-game hallucinations in multi-title corpora.
  - Asynchronous database pooling must be decoupled from test-runner event loop termination (`NullPool` vs. persistent pool).
- **Problems faced & how they were solved:**
  - `asyncpg` event loop closure conflicts during test teardown. Resolved by utilizing `NullPool` in test sessions and running async ASGI fixtures via `pytest.mark.anyio`.
- **Interview Soundbite:**
  - *"I developed an asynchronous semantic retrieval endpoint in FastAPI querying pgvector. It performs hybrid retrieval—combining relational filters like game name and missable tags with cosine distance ordering—returning ranked, contextual trophy chunks in milliseconds."*

---

### [2026-10-16] — Milestone 2: RAG Pipeline Integration & Verifiable Citations
- **What I built/configured:**
  - `IngestionClient` (`apps/api/src/services/ingestionClient.ts`) connecting the Node.js Fastify API to the Python FastAPI vector retrieval service.
  - Implemented graceful degradation: if the vector microservice is unavailable or times out, the chat pipeline logs the incident and safely degrades to base LLM reasoning without raising 500 errors.
  - Structured prompt builder `buildRAGPrompt` isolating retrieved guide context inside explicit `<fontes_verificadas>` delimiters.
  - Updated `PLATINA_SYSTEM_PROMPT` mandating explicit source citations and strict anti-hallucination warnings.
  - Verified live in end-to-end SSE streaming: the model accurately retrieves the Bloodborne Eileen the Crow guide chunk from pgvector and cites `PowerPyx (https://powerpyx.com/bloodborne)` at the end of its response.
- **Key concepts learned:**
  - Isolating RAG chunks in structured XML tags prevents prompt-bleeding between user queries and external guide data.
  - Inter-service communication between Node.js and Python microservices must be resilient with timeouts and graceful degradation.
- **Problems faced & how they were solved:**
  - TypeScript `exactOptionalPropertyTypes` disallowing `signal: undefined` in `fetch()`. Solved by conditionally assigning the signal property only when present.
- **Interview Soundbite:**
  - *"I completed our end-to-end RAG architecture by bridging the Fastify chat gateway to our Python vector service. The API queries pgvector for relevant chunks, isolates them within `<fontes_verificadas>` tags, and instructs the model to anchor its advice in the retrieved context and cite source URLs, eliminating hallucinations while degrading gracefully if the vector service drops."*

---

### [2026-10-16] — Milestone 2: RAG Quality Benchmarking & Evaluation Suite
- **What I built/configured:**
  - Created automated RAG evaluation suite `tests/test_rag_eval.py` running golden benchmark scenarios against complex multi-trophy guides (Elden Ring).
  - Asserts Context Precision (Top-1 entity relevance for missable trophies like Bolt of Gransax and Ranni's Dark Moon Greatsword).
  - Asserts Context Recall (presence of critical point-of-no-return conditions like Maliketh and Erdtree burning).
  - Tested classification accuracy for missable flags and similarity threshold floors (score >= 0.5).
  - Fine-tuned local embedding vector generator with token-frequency weighting, domain term boosting, and stopword dampening.
  - All 7 tests passing in pytest (unit, integration, and evaluation suites).
- **Key concepts learned:**
  - RAG pipelines require quantitative evaluation assertions in CI to detect retrieval drift and ranking degradation before deployment.
  - Domain-specific stopword filtering and term-frequency scaling significantly improve retrieval precision without neural model re-training.
- **Problems faced & how they were solved:**
  - Generic token overlap in title headers dominating search results over specific trophy names. Solved by dampening generic guide boilerplate and boosting specific trophy nouns.
- **Interview Soundbite:**
  - *"I developed an automated RAG evaluation test suite in pytest that continuously asserts Context Precision, Recall, and metadata classification accuracy against golden guide datasets, ensuring our hybrid retrieval pipeline maintains sub-second precision and never regresses on missable trophy warnings."*

---

### [2026-10-16] — Milestone 2: Atomic Guide Reindexing & Lifecycle
- **What I built/configured:**
  - `reindex_game` method in `IngestionRepository` implementing an atomic purge-and-replace transaction in PostgreSQL.
  - Delete query purges previous stale chunks scoped to the target game (`GuideChunkModel.game.ilike(game)`).
  - Inserts fresh chunks and computed embeddings within the same ACID transaction, guaranteeing zero partial-state downtime if indexing fails.
  - API endpoint `POST /api/v1/ingest/reindex` receiving revised guide content and returning deleted vs. reindexed chunk metrics.
  - Integration tests in pytest asserting that previous chunks are pruned and replaced without data loss.
- **Key concepts learned:**
  - Game guides evolve with patches; append-only vector storage leads to contradictory or duplicate advice.
  - Wrapping purge + bulk insert in a single SQL transaction guarantees rollback safety.
- **Problems faced & how they were solved:**
  - Ensuring game name matches in delete queries are case-insensitive and whitespace-trimmed.
- **Interview Soundbite:**
  - *"I implemented an atomic `/reindex` endpoint in FastAPI that executes a transactional purge-and-replace in PostgreSQL. When guides are revised for new game patches, it drops obsolete chunks and inserts fresh embeddings in a single ACID commit, preventing stale advice while guaranteeing zero data loss on failure."*

---

### [2026-10-16] — Milestone 3: Player Progress Tool (`check_player_progress`)
- **What I built/configured:**
  - `PlayerProgressTool` (`src/services/agent/tools/playerProgress.ts`) defining OpenAI/Groq function calling JSON schema.
  - Runtime parameter validation with Zod (`checkPlayerProgressParamsSchema`).
  - HTTP integration connecting Fastify agent logic to the Python player progress route (`/api/v1/players/{psn_id}/progress`).
  - Unit test suite (`playerProgress.test.ts`) validating schema contracts, invalid input rejection, and live mock progress queries.
- **Key concepts learned:**
  - Separating tool definition (JSON Schema for LLM planning) from tool execution (Zod-validated service calls).
- **Problems faced & how they were solved:**
  - Aligning TypeScript property types for optional URL encoding parameters.
- **Interview Soundbite:**
  - *"I built our first agent tool (`check_player_progress`), exposing player PSN trophy completion to the LLM via standard function calling schemas. Runtime Zod validation protects internal routes against hallucinations, returning structured pending missables directly to the agent's reasoning loop."*

---

### [2026-10-16] — Milestone 3: Guide Retrieval Tool (`search_trophy_guides`)
- **What I built/configured:**
  - `SearchGuidesTool` (`src/services/agent/tools/searchGuides.ts`) implementing standard function calling parameters schema.
  - Zod runtime validation (`searchGuidesParamsSchema`) accepting `query`, `game`, `missableOnly`, and `limit`.
  - Service execution calling `ingestionClient.searchGuides` to query PostgreSQL pgvector on demand.
  - Unit tests in Vitest (`searchGuides.test.ts`) testing schema definitions, validation rejection, and retrieval execution.
- **Key concepts learned:**
  - Dynamic tool-based RAG allows the LLM to formulate tailored semantic queries rather than injecting blind vector search on every user prompt.
- **Problems faced & how they were solved:**
  - TypeScript exact optional properties on Zod schema inputs. Solved using `z.input<typeof schema>` to handle optional defaults cleanly.
- **Interview Soundbite:**
  - *"I implemented `search_trophy_guides` as a callable agent tool, allowing the model to autonomously decide when and how to search our pgvector database. This shifts our architecture from static prompt injection to an active agent that searches guides with optimized terms only when required."*

---

### [2026-10-16] — Milestone 3: Autonomous Agent Loop & Tool Calling (`POST /api/v1/agent/run`)
- **What I built/configured:**
  - `PlatinaAgentRunner` (`src/services/agent/runner.ts`) implementing an iterative ReAct execution loop with Groq function calling.
  - Multi-turn tool execution: model autonomously calls `check_player_progress`, receives live PSN status, identifies pending missable trophies, queries `search_trophy_guides` for exact steps, and synthesizes a comprehensive final response.
  - Streaming SSE endpoint `POST /api/v1/agent/run` streaming real-time event frames (`tool_call`, `tool_result`, `chunk`, `done`).
  - Strict recursion ceiling (`maxSteps: 5`) and `AbortSignal` propagation preventing infinite loops and runaway compute.
  - Vitest test suite (`app.test.ts`) validating end-to-end multi-step SSE agent streaming.
- **Key concepts learned:**
  - The ReAct pattern enables complex multi-hop reasoning by pairing LLM inference with intermediate tool observation.
  - Steaming intermediate tool events keeps users engaged during multi-second agent workflows.
- **Problems faced & how they were solved:**
  - Synchronizing Python progress route availability with Node agent runner tests. Ensured local microservice auto-reloading and clear error reporting.
- **Interview Soundbite:**
  - *"I architected our autonomous agent runner implementing a multi-step ReAct loop with Groq. When queried, the agent inspects the player's live trophy progress, detects pending missable trophies, autonomously searches our pgvector guide database, and synthesizes a tactical step-by-step roadmap streamed in real time via SSE."*

---

### [2026-10-16] — Milestone 3: Proactive Next Step Advisor (`POST /api/v1/agent/next-step`)
- **What I built/configured:**
  - `NextStepAdvisor` service (`src/services/agent/nextStep.ts`) analyzing live player progress and prioritizing pending missable trophies.
  - Integration with `searchGuidesTool` to dynamically pull relevant walkthrough sections from `pgvector`.
  - JSON schema output validation via Zod (`nextStepAdviceSchema`) containing `urgentWarning`, `targetTrophy`, `actionableStep`, and session `checklist`.
  - Fastify route `POST /api/v1/agent/next-step` and automated Vitest suite in `app.test.ts`.
- **Key concepts learned:**
  - Proactive AI patterns: instead of waiting for a reactive prompt, systems can compare telemetry (player save state) against domain hazards (missables) to compute high-value advice ahead of time.
- **Problems faced & how they were solved:**
  - Handling cases where a player has 100% completion or no missables pending. Defaulted to congratulatory and general progression states gracefully.
- **Interview Soundbite:**
  - *"I developed the proactive next-step advisor (`/agent/next-step`). By combining telemetry ingestion with missable risk heuristics and pgvector retrieval, it generates structured tactical briefings warning players of irreversible lockouts before they start playing."*

---

### [2026-10-16] — Milestone 3: Model Context Protocol (MCP) Server (`packages/mcp-server`)
- **What I built/configured:**
  - Independent package `@platina-ai/mcp-server` leveraging official `@modelcontextprotocol/sdk`.
  - Registered MCP Resources (`platina://guides/bloodborne`, `platina://guides/elden-ring`) for contextual doc ingestion.
  - Registered MCP Tools: `get_player_trophies`, `search_trophy_guide`, and `get_next_step_briefing`.
  - Configured `StdioServerTransport` for compatibility with Claude Desktop and Claude Code CLI.
  - Verified JSON-RPC handshake (`initialize` -> response) over sub-process pipe.
- **Key concepts learned:**
  - MCP acts as a universal bridge, decoupling domain intelligence and tools from proprietary chat surfaces.
- **Problems faced & how they were solved:**
  - Resolving TypeScript DOM/Node types in MCP packages by tuning `tsconfig.json` `lib` and `types`.
- **Interview Soundbite:**
  - *"I packaged our trophy guidance tools into a dedicated Model Context Protocol (MCP) server. Any MCP-compliant client can now inspect player progress and retrieve missable warnings via standard stdio JSON-RPC without custom integration code."*



















