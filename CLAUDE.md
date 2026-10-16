# Platina AI — Project Guidelines & Learning Rules

## Purpose & Working Agreement
Platina AI is a portfolio and study project designed to master and demonstrate practical AI engineering in production:
- LLMs & RAG (FastAPI, pgvector, embeddings, MCP)
- Senior Backend Architecture (Node.js, TypeScript, Fastify, SSE Streaming)
- Cloud Infrastructure & DevOps (Terraform, AWS, Docker, Kubernetes/Helm, GitHub Actions)

### The Division of Work Rule
> **What is new to me, I write. What I already master, the AI writes and I review.**

1. **Learning Tracks (I Write — AI coaches with `TODO(human)`):**
   - Folders: `services/ingest/` (Python/FastAPI/RAG), `infra/terraform/`, `deploy/helm/`, and Agent/MCP logic.
   - **AI Rule:** Never implement these learning areas unilaterally. Handle routine boilerplate, and for architectural/design choices, insert clear `TODO(human)` markers in code explaining:
     - The context and purpose.
     - The concrete task to complete.
     - Key engineering trade-offs to consider.
   - Always explain the reasoning before editing.

2. **Mastered Tracks (AI Writes — I review):**
   - Folders: `apps/api/` (Node.js & TypeScript).
   - **AI Rule:** Implement the code following modern senior-level practices. Include concise `// Insight:` comment blocks or markdown explanations explaining trade-offs, design patterns, and why alternatives were dismissed.

3. **Interview Preparation Rule (Post-Feature Gate):**
   - At the completion of every feature, ask me **3 technical interview questions in English** covering:
     1. Architecture / System Design decision made.
     2. Failure modes / Edge cases and resilience.
     3. Trade-offs (cost, latency, complexity) vs alternative approaches.
   - I will explain the solution back in English to practice remote technical interview communication.

---

## Feature Development Lifecycle
1. **Study Phase:** Review fundamental concepts before coding.
2. **Plan Mode:** Write the user implementation plan first, then compare with AI suggestions.
3. **Implementation:** Follow Learning style rules with `TODO(human)` steps.
4. **Interview Check:** Explain back the implementation in English based on the 3 questions.
5. **Documentation & Commit:** Document Architecture Decision Records in `docs/adr/` or lessons in `docs/learning-log.md`, then commit.

---

## Repository Structure
```
platina-ai/
├── CLAUDE.md              # Project rules & learning mode instructions
├── apps/api/              # Node.js + TypeScript REST & Streaming API (Explanatory style)
├── services/ingest/       # Python + FastAPI document ingestion, chunking & embeddings (Learning style)
├── infra/terraform/       # AWS Infrastructure as Code (Learning style)
├── deploy/helm/           # Kubernetes charts & manifests (Learning style)
├── .github/workflows/     # CI/CD pipelines
└── docs/
    ├── adr/               # Architecture Decision Records (1 file per decision)
    └── learning-log.md    # Study logs & interview cheat-sheet
```
