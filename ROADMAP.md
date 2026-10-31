# 🗺️ Platina AI — Engineering Roadmap

This roadmap outlines planned engineering milestones, architectural improvements, and infrastructure expansions for **Platina AI**, an application that calls hosted LLM APIs (Groq) to provide structured guidance for PlayStation trophy hunters.

Every item defines a single concrete objective and estimated effort in hours. The golden test suite is used strictly as an application regression test suite to measure system-level functionality.

---

## Done (pipeline v2 foundations)

- **Typed Artifact Contracts:** Pydantic models (`TrophyListParsed`, `GuideParsed`, `LinkedGame`) defining schema boundaries across parsing and entity linking stages in `services/ingest/src/pipeline/contracts.py`.
- **Authoritative Sources Registry:** Versioned registry in `sources.yaml` configuring snapshots, parser kinds, guide roles, and source URLs.
- **Deterministic Identifier Normalization:** Robust slugification and hashing for canonical `game_id` and `trophy_id` normalization in `services/ingest/src/pipeline/normalize.py`.
- **Pipeline CLI Runner & Makefile:** Command-line entry points supporting staged execution (`parse`, `link`, `chunk`, `load`).
- **Snapshot Storage Isolation:** Local guide HTML snapshots located under `data/<game_id>/raw` (gitignored).
- **On-Demand Scraping Disabled:** Live crawling isolated behind the `ON_DEMAND_INGESTION=false` configuration flag.

---

## Phase 1 — Ingestion pipeline (current focus)
*Goal: Finish ingestion for The Witcher 3, then make onboarding a new game a matter of config + snapshots, not new code.*

- **Implement 4 parser stubs:** Implement isolated HTML parsers for `psnprofiles_trophy_list`, `psnprofiles_guide`, `powerpyx_guide`, and `gwent_cards_guide` with strict section isolation preventing cross-section text bleed. *(5h)*
- **Entity linking & stage wiring:** Implement the link stage between catalog and guides, wiring chunk and load stages so `run --stage all` executes end-to-end for The Witcher 3. *(4h)*
- **Per-game config decoupling:** Move all game-specific attributes into `sources.yaml` and configuration files with zero game-specific code paths, and document onboarding steps in `docs/`. *(3h)*
- **Expand golden regression suite:** Grow the regression suite from 116 cases (50 curated + 66 generated) to 200+ covering all app flows (SQL catalog, RAG guide, hybrid, abstention, missables, roadmap order, multi-language), enforcing per-flow pass rates in CI. *(5h)*
- **Multi-game catalog expansion:** Onboard *Grand Theft Auto V*, *Bloodborne*, and *Elden Ring* with configuration, local snapshots, and dedicated regression test cases, proving pipeline reusability. *(6h)*

**Phase 1 Total:** 23h

---

## Phase 2 — Retrieval, tool calling and agent performance (data-driven)
*Goal: Use golden regression test suite results and per-stage metrics to improve answer quality across games.*

- **Failure analysis reporting:** Generate automated failure breakdown reports per regression run detailing failing stages across retrieval, rerank, tool choice, or answer generation. *(3h)*
- **Data-driven retrieval tuning:** Tune semantic chunking per content type, hybrid BM25 and vector weights, reranker settings, similarity thresholds, and query rewriting guided by regression metrics. *(4h)*
- **Tool-calling schema & routing hardening:** Refine tool schemas, descriptions, SQL/RAG/hybrid routing rules, and argument validation retries verified against the regression test suite. *(3h)*
- **Cross-game regression verification gate:** Build automated regression verification ensuring no newly introduced change ships if any onboarded game's pass rate drops. *(3h)*
- **Exact trophy-guide response caching:** Implement an in-memory/Redis TTL cache for static `get_trophy_guide` queries to minimize hosted LLM inference latency. *(3h)*
- **SSE backpressure & connection lifecycle:** Implement client disconnect listeners and backpressure handling for long-running Server-Sent Events streams. *(2h)*

**Phase 2 Total:** 18h

---

## Phase 3 — Bring back removed features in a compliant way
*Goal: Restore progression assistance with zero personal data processing and local-only state.*

- **ADR on compliant player progress options:** Author an Architectural Decision Record evaluating (a) manual progress tracking, (b) export/paste list import, and (c) owner-only sync with local-only storage and zero third-party accounts. *(2h)*
- **Implement local progress tracking & next-step advisor:** Implement the selected local progress option (manual or file import) and restore the proactive next-step advisor on top of it. *(5h)*

**Phase 3 Total:** 7h

---

## Phase 4 — Infrastructure
*Goal: Harden infrastructure as code, container deployments, and continuous deployment.*

- **Terraform module decomposition:** Refactor flat `.tf` files into reusable modules (`modules/vpc`, `modules/rds_pgvector`, `modules/compute`, `modules/ecr`). *(4h)*
- **Multi-environment workspaces:** Configure isolated staging and production Terraform workspaces with remote S3 state and DynamoDB state locking. *(2h)*
- **Amazon EKS managed cluster module (ADR-0004):** Author an enterprise EKS module with Managed Node Groups on AWS Graviton and IAM Roles for Service Accounts (IRSA). *(4h)*
- **Production Helm chart hardening:** Add Horizontal Pod Autoscalers (HPA), PodDisruptionBudgets, and granular resource limits/requests for API and Ingestion pods. *(3h)*
- **Ingress & TLS termination:** Configure AWS Load Balancer Controller integration with cert-manager and AWS Certificate Manager (ACM) for automated SSL renewal. *(2h)*
- **Automated matrix CI testing:** Implement matrix testing for Node.js (v22/v24) and Python (3.12/3.14) covering Vitest, Pytest, linting, and type checking on every PR. *(3h)*
- **Container vulnerability scanning & release automation:** Integrate Trivy container security scans and automated semantic version tagging on merges to main. *(2h)*
- **Automated GitOps CD pipeline:** Build a continuous deployment workflow triggering rolling Helm upgrades to staging and production Kubernetes environments. *(3h)*

**Phase 4 Total:** 23h

---

## Later / under consideration

- Optional integration with the owner's own PSN trophy progress (pending program approval).

---

**Total Planned Work:** 71 hours
*(Phase 1: 23h | Phase 2: 18h | Phase 3: 7h | Phase 4: 23h)*
