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

