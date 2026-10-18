# Resilient LLM Model Cascade Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a transparent, resilient model fallback cascade (`openai/gpt-oss-120b` -> `llama-3.3-70b-versatile` -> `llama-3.1-8b-instant`) in `apps/api` so that Rate Limits (HTTP 429) or transient provider outages fail over automatically without user disruption.

**Architecture:** Create an `executeWithModelFallback` helper in `apps/api/src/services/llm/fallback.ts` or integrated directly in `runner.ts` and `chatStream.ts`. When an API call throws a 429 or 503 error, it catches the error and retries the exact same prompt and tools with the next available model in the priority list.

**Tech Stack:** TypeScript, Fastify, Groq SDK, Vitest.

## Global Constraints
- Primary model remains configurable via `env.GROQ_MODEL` (default: `openai/gpt-oss-120b`).
- Fallback cascade order: `openai/gpt-oss-120b` -> `llama-3.3-70b-versatile` -> `llama-3.1-8b-instant`.
- Non-429/non-5xx errors (e.g. invalid auth 401, bad request 400) must NOT fail over blindly; they must throw immediately.
- 100% of existing tests must pass.

---

### Task 1: Resilient Model Fallback Helper & Agent Runner Integration

**Files:**
- Create: `apps/api/src/services/llm/fallback.ts`
- Modify: `apps/api/src/services/agent/runner.ts`
- Test: `apps/api/src/services/llm/fallback.test.ts`

**Interfaces:**
- Produces: `executeWithModelCascade<T>(client: Groq, callFn: (model: string) => Promise<T>, models?: string[]): Promise<T>`

- [ ] **Step 1: Write unit tests in `fallback.test.ts` verifying automatic failover on 429 and error preservation on non-transient errors**
- [ ] **Step 2: Implement `executeWithModelCascade` in `fallback.ts`**
- [ ] **Step 3: Integrate cascade into `PlatinaAgentRunner` completion and corrective re-prompt calls**
- [ ] **Step 4: Run `npm test` and `npm run build`**
- [ ] **Step 5: Commit**

---

### Task 2: Documentation & Interview Soundbite

**Files:**
- Modify: `docs/interview-prep.md`
- Modify: `docs/learning-log.md`

- [ ] **Step 1: Add Question Q57 in `docs/interview-prep.md` explaining Multi-Model Resilience and Fallback Cascades**
- [ ] **Step 2: Update `docs/learning-log.md`**
- [ ] **Step 3: Commit and push to main**
