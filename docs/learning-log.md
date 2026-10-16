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
