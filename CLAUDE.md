# Platina AI — Project Guidelines

## Overview
**Platina AI** is an assistant for PlayStation trophy hunters, focused on missable trophies and platinum roadmaps, starting with *The Witcher 3: Wild Hunt*.

The system is an application that calls hosted LLM APIs (Groq) without training, fine-tuning, or serving models. It combines structured SQL queries against a canonical relational trophy catalog with semantic retrieval over verified community guide walkthroughs (PowerPyx, PSNProfiles) to deliver accurate, grounded assistance.

---

## Repository Structure
```
platina-ai/
├── apps/api/              # Node.js 22 + TypeScript + Fastify REST & SSE Streaming API
├── services/ingest/       # Python 3.12 + FastAPI catalog ingestion, parsing & embeddings
├── packages/mcp-server/   # Model Context Protocol (MCP) server for Claude Desktop / Cursor
├── infra/
│   ├── postgres/          # PostgreSQL 16 + pgvector migrations and init scripts
│   ├── terraform/         # OpenTofu / Terraform cloud infrastructure manifests
│   └── helm/              # Kubernetes packaging for Kind and AWS cloud deployments
├── docs/
│   └── adr/               # Architectural Decision Records (ADRs)
├── ROADMAP.md             # Engineering roadmap with scoped milestones
└── README.md              # Project overview, architecture, and setup instructions
```

---

## Development & Testing Commands

### Fastify API (`apps/api`)
```bash
cd apps/api
npm install          # Install dependencies
npm run build        # TypeScript typecheck & build (tsc)
npm test             # Run Vitest test suite
```

### Python Ingestion Microservice (`services/ingest`)
```bash
cd services/ingest
uv sync              # Synchronize Python dependencies
uv run pytest tests/ -vv   # Run Pytest suite
```

---

## Engineering Conventions

1. **Strict TypeScript & Zod:**
   - All API endpoints and agent tools enforce strict Zod runtime validation at trust boundaries.
   - Decouple schema definition from tool execution.

2. **Pydantic Artifact Contracts:**
   - Ingestion pipeline v2 utilizes explicit, validated Pydantic models (`services/ingest/src/pipeline/contracts.py`) across all parsing, linking, and chunking stages.

3. **Application Regression Suite:**
   - Maintain 100% green tests across Vitest and Pytest suites.
   - The golden set under `services/ingest/tests/golden/` acts strictly as an application regression test suite to guard against functional regressions.

4. **Small, Atomic Commits:**
   - Make small, focused commits with clear imperative commit messages explaining the rationale.
   - Do not bundle unrelated changes together.

5. **Privacy & Data Security:**
   - The application answers exclusively from verified community trophy guides and the canonical game catalog.
   - Never commit API keys, secrets, credentials, or personal player identifiers.

---

## Architectural Documentation & Roadmap

- **Architectural Decision Records:** Detailed records of technical decisions and trade-offs are documented under `docs/adr/`.
- **Engineering Roadmap:** Planned work, pipeline phases, and effort estimations (71h+ scoped) are tracked in `ROADMAP.md`.
