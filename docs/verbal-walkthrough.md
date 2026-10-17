# Platina AI: Verbal Interview Walkthrough (English)

This script is designed for senior technical interviews when an interviewer says:  
> *"Tell me about a complex project you recently designed and built."* or *"Walk me through the architecture of your AI system without looking at the code."*

---

## 1. The 90-Second Elevator Pitch

> *"Platina AI is an autonomous AI assistant and RAG system I designed to solve a very specific problem for PlayStation trophy hunters: avoiding irreversible lockouts. In games like Bloodborne or Elden Ring, defeating a boss or entering a new zone before finishing a side quest permanently locks you out of the platinum trophy, forcing a 40-hour restart.*
>
> *I built the platform using a polyglot microservice architecture: Node.js and Fastify on the front-facing API for high-performance Server-Sent Events (SSE) streaming, a Python FastAPI microservice for semantic document chunking and vector retrieval, and PostgreSQL with pgvector using an HNSW cosine distance index.*
>
> *Rather than naively stuffing walkthroughs into every prompt, I implemented a ReAct autonomous agent loop with Groq's 120-billion open-weights model. The agent inspects the player's live trophy progress on PSN, identifies pending missables, dynamically retrieves verified guide paragraphs, and streams actionable checklists.*
>
> *For external interoperability, I built a dedicated Model Context Protocol (MCP) server so developer tools like Claude Desktop can query player progress directly. The entire system is packaged in a unified Helm chart and deployed declaratively to AWS using Terraform with strict security group chaining and a hard FinOps budget ceiling of $1.00 USD."*

---

## 2. Topic-by-Topic Drill-Downs

### A. Why Fastify over Express?
- **Talking Points:**
  - Fastify's schema-based compilation via `fast-json-stringify` provides ~2x throughput compared to Express.
  - Native support for asynchronous hooks and lifecycle encapsulation prevents plugin scope leakage.
  - For real-time SSE streaming, Fastify cleanly manages Node.js `Readable` streams and socket backpressure without manual socket hacks.

### B. Why PostgreSQL + pgvector instead of a Dedicated Vector DB (Pinecone/Milvus)?
- **Talking Points:**
  - Transactional ACID consistency: trophy metadata (names, platforms, unlocked timestamps) and 1536-dimensional embeddings live in the exact same relational table.
  - No dual-write synchronization lag or split-brain states between an external vector store and SQL database.
  - We use HNSW (`vector_cosine_ops`, `m=16`, `ef_construction=64`) for sub-millisecond retrieval without needing offline IVFFlat training.

### C. How does the ReAct Loop work?
- **Talking Points:**
  - It alternates between Reasoning, Acting, and Observing.
  - Tools are defined via strict JSON Schemas and validated at runtime with Zod to isolate internal routes from hallucinated parameters.
  - The model decides *if* and *what* to query. If Eileen the Crow is missing in Bloodborne, it issues a `search_trophy_guides` tool call, observes the guide snippet, and only then streams the final guidance.
  - A recursion ceiling (`maxSteps: 5`) and `AbortSignal` propagation prevent infinite loops and runaway billing.

### D. Why k3s on EC2 Graviton instead of AWS EKS?
- **Talking Points:**
  - EKS charges a mandatory $73/month flat fee for the control plane.
  - By deploying certified k3s onto an AWS Graviton2 instance (`t4g.small`), we maintain 100% CNCF Kubernetes API compatibility for just ~$12/month (a >90% cost reduction).
  - The exact same Helm chart deploys to Kind locally, k3s on EC2, or full EKS without code modification.

### E. How do you ensure Zero-Downtime Deployments?
- **Talking Points:**
  - Decoupled ConfigMaps and encrypted Kubernetes Secrets.
  - Distinct **Readiness Probes** (preventing traffic routing until database pools connect) and **Liveness Probes** (detecting event-loop deadlocks).
  - Helm rolling updates with `--atomic --wait --timeout 5m` that auto-rollback if new pods fail health checks.
