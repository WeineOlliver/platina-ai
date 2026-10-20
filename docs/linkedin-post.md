# Platina AI: High-Impact LinkedIn Post Draft

---

### Option 1: Engineering & Architecture Focus (Recommended for Global Senior Roles)

Ever lost 40+ hours in a game because you missed a single conversation with an NPC before entering a boss room?

In games like Bloodborne and Elden Ring, "missable trophies" permanently lock you out of a Platinum unless you start an entire new playthrough.

To solve this, I built **Platina AI** 🏆—an autonomous AI assistant that synchronizes live PlayStation Network trophy telemetry with verified walkthrough vector embeddings.

Here is the engineering architecture behind it:

🔹 **Polyglot Monorepo:** 
Fastify (Node.js/TypeScript) handles high-throughput Server-Sent Events (SSE) streaming and JWT auth, while a FastAPI (Python 3.12 + Astral uv) microservice manages semantic chunking and dense embeddings.

🔹 **Autonomous ReAct Agent & Latency Engineering (Sub-1.5s TTFT):**
Instead of naive prompt stuffing or sluggish multi-roundtrip ReAct loops, our agent pre-fetches live PSN telemetry and injects synthesized tool turns directly into message history. This slashes Time-to-First-Token (TTFT) by over 50%, streaming instant tactical briefings over Server-Sent Events (SSE) with adaptive validation gating before executing dynamic vector retrieval for unearned missables.

🔹 **PostgreSQL 16 + pgvector (HNSW Index):**
By combining relational metadata with 1536-dimensional L2-normalized embeddings in a single database, we achieve sub-millisecond cosine similarity queries (`<=>`) with full transactional ACID consistency.

🔹 **Open Model Context Protocol (MCP):**
I built a standalone MCP server (`@platina-ai/mcp-server`), allowing developers to connect Platina AI directly to Claude Desktop or Cursor over standard `stdio` JSON-RPC.

🔹 **Enterprise Cloud & FinOps ($1.00 USD Cap):**
Packaged with a unified Helm chart and deployed declaratively via Terraform to AWS (3-tier multi-AZ VPC, RDS, and certified k3s on EC2 Graviton). By running k3s instead of managed EKS, I slashed cloud infrastructure costs by over 90% while enforcing a hard $1.00 USD monthly budget cap with automated teardown automation.

🔹 **Full CI/CD Pipeline:**
GitHub Actions runs three parallel test tracks (Vitest, Pytest, and Helm lint) and publishes multi-architecture Docker images (`linux/amd64` and `linux/arm64`) to Amazon ECR via OpenID Connect (OIDC).

Check out the full repository, 5 Architecture Decision Records (ADRs), and 61 technical interview deep-dives:
🔗 Repository: https://github.com/WeineOlliver/platina-ai
📊 Architecture & Flow: https://github.com/WeineOlliver/platina-ai/blob/main/docs/architecture.md

#SoftwareEngineering #NodeJS #TypeScript #Python #Kubernetes #Terraform #AWS #RAG #AI #MCP #SystemDesign
