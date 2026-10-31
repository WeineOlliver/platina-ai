# 🗺️ Platina AI — Engineering Roadmap

This roadmap outlines planned engineering milestones, architectural improvements, and infrastructure expansions for Platina AI. Each item defines a single concrete objective and estimated effort in hours.

---

## 1. Canonical Ingestion Engine Rebuild & Game Expansion

- **Ingestion Pipeline v2 Core (The Witcher 3):** Rebuild the ingestion pipeline using strict Pydantic artifact contracts, deterministic trophy ID hashing, and staged validation checks. *(6h)*
- **Exhaustive Guide Parsers (PowerPyx & PSNProfiles):** Implement isolated HTML parsers for trophy lists, missable roadmaps, and collectible tables preventing cross-section text bleed. *(4h)*
- **Multi-Game Catalog Expansion:** Ingest and index canonical roadmaps for *Grand Theft Auto V*, *Bloodborne*, and *Elden Ring* with verified entity linking. *(5h)*

---

## 2. Infrastructure as Code & Cloud Modularization (Terraform)

- **Terraform Module Decomposition:** Refactor flat `.tf` scripts into isolated, reusable modules (`modules/vpc`, `modules/rds_pgvector`, `modules/compute`, `modules/ecr`). *(4h)*
- **Multi-Environment Workspaces:** Configure isolated staging and production Terraform workspaces with remote S3 state and DynamoDB state locking. *(2h)*
- **Amazon EKS Managed Cluster Module (ADR-0004):** Author an enterprise EKS module with Managed Node Groups on AWS Graviton and IAM Roles for Service Accounts (IRSA). *(4h)*

---

## 3. Production Kubernetes Packaging (Helm)

- **Production Helm Hardening:** Add Horizontal Pod Autoscalers (HPA), PodDisruptionBudgets, and granular resource limits/requests for API and Ingestion pods. *(3h)*
- **Ingress & TLS Termination:** Configure AWS Load Balancer Controller integration with cert-manager and AWS Certificate Manager (ACM) for automated SSL renewal. *(2h)*

---

## 4. Continuous Integration & Delivery (GitHub Actions)

- **Automated Matrix CI Testing:** Implement matrix testing for Node.js (v22/v24) and Python (3.12/3.14) covering Vitest, Pytest, linting, and type checking on every PR. *(3h)*
- **Container Vulnerability Scanning & Release Automation:** Integrate Trivy container security scans and automated semantic version tagging on merges to main. *(2h)*
- **Automated GitOps CD Pipeline:** Build a continuous deployment workflow triggering rolling Helm upgrades to staging and production Kubernetes environments. *(3h)*

---

## 5. Agent Architecture, Cache & Observability (ADR Follow-ups)

- **Exact Trophy Guide Response Caching:** Implement an in-memory/Redis TTL cache for static `get_trophy_guide` queries to minimize LLM inference cost and latency. *(3h)*
- **SSE Stream Backpressure & Connection Lifecycle:** Implement client disconnect listeners and backpressure handling for long-running Server-Sent Events streams. *(2h)*
- **Automated Benchmark Tracking & Regression Gate:** Integrate golden set evaluation (`run_golden.py`) into the CI pipeline to fail PRs that regress Faithfulness or Recall@5 below 85%. *(3h)*

---

**Total Planned Work:** 44 hours
