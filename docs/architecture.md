# Platina AI System Architecture

This document describes the high-level system architecture, networking topology, and data flow of **Platina AI**—an autonomous AI assistant for PlayStation trophy hunting and platinum roadmap optimization.

---

## 1. High-Level Architecture Diagram

```mermaid
graph TB
  %% Client Tier
  subgraph Clients [" 🎮 Client Layer "]
    Browser["Web Interface (Browser)<br/>SSE Client"]
    MCPClient["MCP Host Client<br/>(Claude Desktop / Cursor)"]
  end

  %% Ingress Tier
  subgraph Ingress [" 🌐 Ingress & Networking (Multi-AZ VPC) "]
    ALB["AWS Application Load Balancer<br/>(Public Subnets 10.0.0.0/20)"]
    K8sService["Kubernetes Service / NodePort<br/>(30080 / ClusterIP)"]
  end

  %% Compute Tier
  subgraph K8s [" ☸️ Kubernetes Cluster (Kind / k3s on EC2 Graviton) "]
    subgraph API_Pod [" apps/api (Node.js 22 / Fastify / TypeScript) "]
      AgentRunner["ReAct Agent Runner<br/>(Tool Calling Engine)"]
      SSEHandler["SSE Streaming Handler<br/>(/chat & /agent/run)"]
      JWTAuth["JWT Authenticator<br/>(@fastify/jwt)"]
    end

    subgraph MCPServer [" packages/mcp-server "]
      StdioMCP["MCP Server Protocol<br/>(Resources & Tools via stdio)"]
    end

    subgraph Ingest_Pod [" services/ingest (Python 3.12 / FastAPI) "]
      Chunker["Semantic Markdown Chunker<br/>(Hierarchy & Missable Detection)"]
      VectorSearch["VectorSearchService<br/>(Hybrid Filter + Cosine Sim)"]
      CatalogService["CatalogService<br/>(Canonical Game & Trophy Catalog)"]
    end
  end

  %% External AI
  subgraph ExternalAI [" ⚡ External LLM Inference (Zero Cost Dev) "]
    Groq["Groq API Engine<br/>Model: openai/gpt-oss-120b<br/>(Ultra-low latency inference)"]
  end

  %% Storage Tier
  subgraph Storage [" 🗄️ Storage Tier (Isolated Private Subnets) "]
    RDS["PostgreSQL 16 + pgvector<br/>HNSW Cosine Vector Index (1536-dim)<br/>Canonical Trophy Catalog & Guide Vectors"]
    SecretsManager["AWS Secrets Manager<br/>(Rotated Master Credentials)"]
    ECR["Amazon ECR<br/>(Immutable & Scanned Images)"]
  end

  %% Data Flow Connections
  Browser -->|HTTP POST / SSE Stream| ALB
  MCPClient -->|JSON-RPC via stdio| StdioMCP
  StdioMCP -->|Internal HTTP| API_Pod
  ALB --> K8sService
  K8sService --> API_Pod

  API_Pod -->|Tool Call: get_trophy_guide / list_trophies| Ingest_Pod
  API_Pod -->|Tool Call: search_trophy_guides| Ingest_Pod
  API_Pod -->|Chat Completions & Function Calling| Groq

  Ingest_Pod -->|pgvector Cosine Ops <=>| RDS
  Ingest_Pod -->|ORM Queries| RDS
  API_Pod -.->|Read Secrets on Boot| SecretsManager
  K8s -.->|Pull Image| ECR

  classDef clientStyle fill:#3b82f6,stroke:#1d4ed8,stroke-width:2px,color:#fff;
  classDef appStyle fill:#10b981,stroke:#047857,stroke_width:2px,color:#fff;
  classDef aiStyle fill:#f59e0b,stroke:#b45309,stroke_width:2px,color:#fff;
  classDef dataStyle fill:#6366f1,stroke:#4338ca,stroke_width:2px,color:#fff;

  class Browser,MCPClient clientStyle;
  class API_Pod,Ingest_Pod,MCPServer appStyle;
  class Groq aiStyle;
  class RDS,SecretsManager,ECR dataStyle;
```

---

## 2. Multi-Step Agent Execution Flow (ReAct Loop)

> **Privacy & Data Architecture Note**: Platina AI operates strictly without accessing, syncing, or storing third-party PlayStation Network accounts or personal player data. The project answers questions exclusively from verified community trophy guides (PowerPyx, PSNProfiles) and the canonical relational game trophy catalog.

When a player asks: *"How do I get the Hunter's Essence trophy in Bloodborne?"*:

```mermaid
sequenceDiagram
  autonumber
  actor User as 🎮 User / Client
  participant Fastify as ⚡ Fastify API (Node.js)
  participant LLM as 🧠 Groq LLM (120B Model)
  participant Ingest as 🐍 Python Microservice
  participant DB as 🐘 PostgreSQL (pgvector)

  User->>Fastify: POST /api/v1/agent/run (SSE stream requested)
  Fastify->>LLM: Prompt with available Tools [get_trophy_guide, list_trophies, search_trophy_guides]
  LLM-->>Fastify: tool_call: get_trophy_guide(game="Bloodborne", trophy="Hunter's Essence")
  Fastify->>User: SSE data: {"type": "tool_call", "name": "get_trophy_guide"}
  
  Fastify->>Ingest: GET /api/v1/catalog/trophies/guide?game=Bloodborne&trophy=Hunter's%20Essence
  Ingest->>DB: Query canonical trophy metadata and linked guide chunks
  DB-->>Ingest: Return trophy record and verified walkthrough chunks
  Ingest-->>Fastify: Return trophy guide JSON
  Fastify->>User: SSE data: {"type": "tool_result", "data": {...}}

  Fastify->>LLM: Append guide chunks to message history
  LLM-->>Fastify: Final comprehensive answer citing verified guide sources
  Fastify->>User: SSE data: {"type": "chunk", "content": "Attention! Talk to Eileen in Cathedral Ward before the Red Moon..."}
  Fastify->>User: SSE data: {"type": "done"}
```

---

## 3. Defense-in-Depth Networking & Security Architecture

```mermaid
graph LR
  subgraph Internet [" Public Internet "]
    UserRequest["Incoming HTTPS User Request"]
  end

  subgraph VPC [" AWS VPC 10.0.0.0/16 "]
    subgraph PublicSubnet [" Public Subnets (10.0.0.0/20) "]
      ALB["Application Load Balancer<br/>Security Group: platina-sg-alb<br/>Ingress: 80, 443 from 0.0.0.0/0"]
    end

    subgraph AppSubnet [" Private Application Subnets (10.0.32.0/20) "]
      EC2Node["k3s EC2 Graviton Node / Pods<br/>Security Group: platina-sg-app<br/>Ingress: Ports 3000-8000 ONLY from platina-sg-alb"]
    end

    subgraph DBSubnet [" Private Database Subnets (10.0.64.0/20) "]
      RDS["PostgreSQL 16 RDS<br/>Security Group: platina-sg-db<br/>Ingress: Port 5432 ONLY from platina-sg-app"]
    end
  end

  UserRequest --> ALB
  ALB -->|Forward via SG Chaining| EC2Node
  EC2Node -->|Query via SG Chaining| RDS
```

---

## 4. Key Architectural Highlights for Technical Interviews

1. **Polyglot Monorepo Separation:**
   - **Fastify (Node.js/TypeScript):** Chosen for lightweight non-blocking event-loop performance, ultra-fast SSE streaming, and type-safe Zod runtime schema isolation.
   - **FastAPI (Python):** Chosen for native ecosystem compatibility with data ingestion, HTML parsing, and semantic vector operations.
2. **Decoupled Tool Calling (ReAct Loop):**
   - The LLM dynamically selects tools on demand (`get_trophy_guide`, `list_trophies`, `search_trophy_guides`) rather than naively stuffing vector context into every prompt.
3. **Open Model Context Protocol (MCP):**
   - A standalone package (`@platina-ai/mcp-server`) exposes trophy guides as **Resources** and agent workflows as **Tools** over standard `stdio`, allowing zero-code interoperability with Claude Desktop and Cursor.
4. **Declarative Cloud Infrastructure & FinOps:**
   - Unified Terraform and Helm setup supporting local zero-cost development on Kind and cloud staging on Amazon Web Services.
   - Enforces a hard budget ceiling of **$1.00 USD** with proactive alerts, backed by single-command automated teardown (`destroy.sh`).
