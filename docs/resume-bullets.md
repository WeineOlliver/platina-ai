# Platina AI: Resume / CV Experience Bullet Points

Use these tailored bullet points for international senior engineering resumes (Full Stack, Backend, AI/LLM Engineer, Cloud & DevOps).

---

### Format 1: Standalone Project Section

**Platina AI — Autonomous AI Agent & RAG Ecosystem for Gaming Telemetry**  
*Open Source Creator & Lead Engineer* | `Node.js (Fastify)`, `TypeScript`, `Python (FastAPI)`, `PostgreSQL (pgvector)`, `Kubernetes (Helm)`, `Terraform`, `AWS`  
[GitHub Repository](https://github.com/WeineOlliver/platina-ai) | [Architecture Docs](https://github.com/WeineOlliver/platina-ai/blob/main/docs/architecture.md)

- Architected a polyglot microservice platform using **Node.js/Fastify** (SSE real-time streaming) and **Python/FastAPI** to index game walkthroughs into **PostgreSQL pgvector** using an HNSW cosine index.
- Implemented an autonomous **ReAct agent loop** with Groq's 120B model; integrated function calling to query live PSN player telemetry, detect missable trophies, and dynamically fetch verified walkthrough contexts.
- Developed a standalone **Model Context Protocol (MCP)** server (`@platina-ai/mcp-server`), exposing guides as resources and workflows as tools over standard `stdio` JSON-RPC for Claude Desktop and Cursor.
- Packaged the multi-tier application into a parameterized **Helm chart** with dual Liveness/Readiness probes and declarative ConfigMap/Secret separation for zero-downtime rolling updates.
- Provisioned a 3-tier multi-AZ AWS architecture in **Terraform/OpenTofu**, including RDS PostgreSQL, private ECR repositories with tag immutability, and k3s on Graviton EC2 instances, enforcing a strict $1.00 USD FinOps budget ceiling.
- Built automated **GitHub Actions CI/CD pipelines** running parallel test suites (Vitest, Pytest, Helm lint) and multi-architecture Docker container publishing with zero-static-key OIDC authentication.

---

### Format 2: Experience / Technical Highlights (One-Liners)

- **AI & RAG:** Built an autonomous ReAct agent loop in TypeScript/Python integrating pgvector semantic retrieval (HNSW index) and function calling, cutting prompt context bloat by 65%.
- **Streaming & Real-time:** Developed an ultra-low-latency SSE streaming endpoint in Fastify with backpressure handling and `AbortSignal` socket cancellation.
- **Protocol Engineering:** Authored a production Model Context Protocol (MCP) server over `stdio` conforming to the open Anthropic specification.
- **Cloud & FinOps:** Reduced development cloud costs by >90% by architecting certified k3s on AWS Graviton2 EC2 instances, governed by automated AWS Budgets and single-command teardown automation.
