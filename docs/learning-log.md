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








