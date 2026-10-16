# Platina AI 🏆

> An intelligent, production-ready AI Assistant for PlayStation Trophy Hunters and Platinum Completionists.

Platina AI is an agentic RAG system that ingests verified trophy guides, indexes contextual walkthroughs into a vector store (`pgvector`), and assists players in real time (e.g., missable trophy alerts, chapter-by-chapter roadmaps, and step-by-step trophy tracking via MCP tools).

---

## Architecture Overview

```
                      +-----------------------------+
                      |   Client / Web App / Chat   |
                      +--------------+--------------+
                                     |
                             (HTTP / SSE Stream)
                                     v
                 +---------------------------------------+
                 |       Node.js / TypeScript API        |
                 |      (Fastify + Structured LLM)       |
                 +-------+-----------------------+-------+
                         |                       |
                  (RPC / Query)            (Tools / MCP)
                         v                       v
      +-----------------------------+   +--------------------+
      |   Python Ingestion / RAG    |   | Custom MCP Server  |
      |     (FastAPI + Embeddings)  |   | (Player Progress)  |
      +--------------+--------------+   +--------------------+
                     |
                     v
           +--------------------+
           |     PostgreSQL     |
           |    + `pgvector`    |
           +--------------------+
```

### Components
- **`apps/api`**: Core Node.js / TypeScript API (Fastify). Handles authentication, streaming responses (SSE), orchestration, and structured outputs.
- **`services/ingest`**: Python & FastAPI ingestion microservice. Extracts text from trophy guides, performs semantically-aware chunking, computes dense embeddings, and queries `pgvector`.
- **`Agent & MCP Server`**: Exposes capabilities such as trophy guide retrieval and player progress checking to LLM agents.
- **`infra/terraform`**: Infrastructure as Code (IaC) provisioning AWS services (EKS, RDS Postgres, ECR, IAM, VPC).
- **`deploy/helm`**: Kubernetes deployment manifests and Helm charts.
- **`.github/workflows`**: Automated CI/CD pipelines for linting, testing, container builds, and deployment.

---

## Tech Stack
- **Languages & Frameworks:** TypeScript (Node.js, Fastify), Python 3.12+ (FastAPI)
- **AI & Retrieval:** Anthropic Claude API / OpenAI API, Dense Embeddings, pgvector, Model Context Protocol (MCP)
- **Database:** PostgreSQL with `pgvector` extension
- **DevOps & Cloud:** Docker, Kubernetes (EKS / k3s), Helm, Terraform, AWS, GitHub Actions

---

## Project Structure

```
platina-ai/
├── CLAUDE.md              # Engineering rules & learning mode instructions
├── apps/api/              # Node.js + TypeScript REST & Streaming API
├── services/ingest/       # Python + FastAPI document ingestion & pgvector RAG
├── infra/terraform/       # AWS Infrastructure as Code
├── deploy/helm/           # Kubernetes Helm charts
├── .github/workflows/     # CI/CD pipelines
└── docs/
    ├── adr/               # Architecture Decision Records
    └── learning-log.md    # Technical learning log & interview preparation notes
```

---

## Development Milestones
- [ ] **Milestone 1:** Node.js API calling LLM with SSE streaming and structured output
- [ ] **Milestone 2:** Python Ingestion service + RAG pipeline with pgvector
- [ ] **Milestone 3:** Agent tool-use and custom MCP server
- [ ] **Milestone 4:** Containerization (Docker) and Kubernetes deployment with Helm
- [ ] **Milestone 5:** Infrastructure as Code with Terraform on AWS
- [ ] **Milestone 6:** CI/CD pipeline, monitoring, and production hardening
