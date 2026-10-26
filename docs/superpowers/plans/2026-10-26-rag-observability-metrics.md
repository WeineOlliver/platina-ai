# Observabilidade RAG: Latência por Estágio e Sampling de Fidelidade

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar observabilidade completa do pipeline RAG, medindo latências por estágio (`retrieval`, `reranker`, `llm`, `total`), executando amostragem assíncrona de fidelidade (Faithfulness / RAG Triad) em produção com persistência no PostgreSQL, e expondo métricas via endpoint `GET /api/v1/observability/metrics`.

**Architecture:**
- O microserviço Python (`services/ingest`) mede e retorna `retrieval_latency_ms` e `reranker_latency_ms` na resposta do endpoint de busca.
- O Fastify (`apps/api`) mede tempos de inferência/streaming do LLM e tempo total da requisição.
- Um serviço de telemetria grava cada requisição na tabela `rag_metrics_telemetry`.
- Se a requisição for selecionada pelo sampling configurável (`OBSERVABILITY_SAMPLING_RATE`, default 10%), dispara assincronamente em background o `evaluateRagTriad` e persiste as notas de fidelidade sem bloquear o streaming ao usuário.
- O endpoint `GET /api/v1/observability/metrics` retorna agregações analíticas (médias, p95, taxa de amostragem) e as amostras mais recentes.

**Tech Stack:** TypeScript/Fastify, Python/FastAPI, PostgreSQL (`pgvector`), Vitest, Pytest, Groq SDK.

---

## Global Constraints

- Custo zero / sem introduzir dependências pesadas de APM pago.
- Background sampling não pode bloquear o streaming SSE ou degradar o TTFT percebido pelo usuário.
- Migrações SQL adicionadas de forma declarativa e versionada sob `infra/postgres/`.

---

### Task 1: Migration PostgreSQL para Telemetria de Métricas RAG

**Files:**
- Create: `infra/postgres/09_rag_telemetry.sql`

- [ ] **Step 1: Criar arquivo de migração DDL da tabela `rag_metrics_telemetry`**
  Definir tabela com:
  - `id` UUID PRIMARY KEY DEFAULT gen_random_uuid()
  - `session_id` VARCHAR(64) NULL
  - `game` VARCHAR(120) NULL
  - `model_name` VARCHAR(100) NULL
  - `retrieval_latency_ms` FLOAT NOT NULL DEFAULT 0.0
  - `reranker_latency_ms` FLOAT NOT NULL DEFAULT 0.0
  - `llm_latency_ms` FLOAT NOT NULL DEFAULT 0.0
  - `total_latency_ms` FLOAT NOT NULL DEFAULT 0.0
  - `sampled_for_quality` BOOLEAN NOT NULL DEFAULT FALSE
  - `faithfulness_score` FLOAT NULL
  - `context_relevance_score` FLOAT NULL
  - `answer_relevance_score` FLOAT NULL
  - `query_preview` TEXT NULL
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - Índices em `created_at` e `sampled_for_quality`.

- [ ] **Step 2: Commit da migration**
```bash
git add infra/postgres/09_rag_telemetry.sql
git commit -m "feat(db): add rag_metrics_telemetry migration"
```

---

### Task 2: Instrumentar Latência de Busca e Rerank no Microserviço Python

**Files:**
- Modify: `services/ingest/src/schemas/search.py`
- Modify: `services/ingest/src/services/search.py`
- Modify: `services/ingest/src/routes/ingest.py`
- Test: `services/ingest/tests/test_search_latency.py`

- [ ] **Step 1: Adicionar teste unitário de latências na resposta de busca**
  Verificar que `SearchResponse` retorna `retrieval_latency_ms` e `reranker_latency_ms` maiores ou iguais a 0.
- [ ] **Step 2: Rodar teste e validar falha**
- [ ] **Step 3: Implementar medição com `time.perf_counter()` em `search.py` e schemas**
  Atualizar `SearchResponse` para incluir `retrieval_latency_ms: float` e `reranker_latency_ms: float`.
- [ ] **Step 4: Executar testes do pytest**
```bash
pytest services/ingest/tests/test_search_latency.py -v
```
- [ ] **Step 5: Commit**
```bash
git add services/ingest/
git commit -m "feat(ingest): add retrieval and reranker latency metrics to search response"
```

---

### Task 3: Atualizar IngestionClient e Modelagem de Telemetria no Fastify

**Files:**
- Modify: `apps/api/src/services/ingestion/client.ts`
- Create: `apps/api/src/services/observability/telemetry.ts`
- Test: `apps/api/src/services/observability/telemetry.test.ts`

- [ ] **Step 1: Escrever teste unitário para o serviço de telemetria**
  Testar cálculo de percentis p95, inserção e amostragem probabilística.
- [ ] **Step 2: Rodar teste e validar falha**
- [ ] **Step 3: Implementar `TelemetryService` e atualizar `IngestionClient`**
  Permitir que `search` exponha as latências retornadas do backend Python.
- [ ] **Step 4: Rodar teste e validar aprovação**
```bash
npx vitest run apps/api/src/services/observability/telemetry.test.ts
```
- [ ] **Step 5: Commit**
```bash
git add apps/api/src/services/ingestion/client.ts apps/api/src/services/observability/
git commit -m "feat(observability): implement telemetry service and ingestion client latency tracking"
```

---

### Task 4: Instrumentar o Agent Runner e Sampling Assíncrono de Faithfulness

**Files:**
- Modify: `apps/api/src/services/agent/runner.ts`
- Test: `apps/api/src/services/agent/runner.observability.test.ts`

- [x] **Step 1: Escrever teste de runner validando a coleta de latência LLM e disparo do sampling**
- [x] **Step 2: Rodar teste e validar falha**
- [x] **Step 3: Instrumentar `runner.ts` com `performance.now()`**
  - Capturar `llm_latency_ms` e latência total.
  - Ao emitir `done`, despachar registro para `TelemetryService`.
  - Se `Math.random() < samplingRate`, invocar assincronamente `evaluateRagTriad` e persistir scores de fidelidade.
- [x] **Step 4: Rodar testes unitários do runner**
```bash
npx vitest run apps/api/src/services/agent/runner.observability.test.ts
```
- [x] **Step 5: Commit**
```bash
git add apps/api/src/services/agent/
git commit -m "feat(agent): instrument stage latencies and background faithfulness sampling"
```

---

### Task 5: Endpoint `GET /api/v1/observability/metrics` e Verificação E2E

**Files:**
- Create: `apps/api/src/routes/v1/observability.ts`
- Modify: `apps/api/src/routes/v1/index.ts`
- Test: `apps/api/src/routes/v1/observability.test.ts`

- [x] **Step 1: Escrever teste de integração para o endpoint de métricas**
  Validar que `GET /api/v1/observability/metrics` retorna objeto com médias de latência, p95, faithfulness médio e lista de amostras.
- [x] **Step 2: Rodar teste e validar falha**
- [x] **Step 3: Implementar rota `observability.ts` e registrar no plugin v1**
- [x] **Step 4: Rodar testes da rota e suíte geral de regressão**
```bash
npx vitest run apps/api/src/routes/v1/observability.test.ts
```
- [x] **Step 5: Commit**
```bash
git add apps/api/src/routes/v1/
git commit -m "feat(api): expose GET /api/v1/observability/metrics endpoint"
```
