# Single-Character Input & Conversational Turn Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow single-character user responses (e.g. "1", "2", "A", "B") in the agent route schema and ensure conversational follow-ups maintain context without HTTP 400 validation errors.

**Architecture:** Update the Zod request validation schema in `apps/api/src/routes/v1/agent.ts` from `.min(2)` to `.min(1)`. Update UI frontend `test-chat.html` to pass along recent conversation history in the request payload so follow-up choices like "2" retain context.

**Tech Stack:** TypeScript, Fastify, Zod, Vitest.

## Global Constraints
- `message` field validation must accept non-empty strings of length $\ge 1$.
- Empty or whitespace-only messages (`""`, `"   "`) must still be rejected.
- All existing agent tests must continue passing.

---

### Task 1: Update Agent Route Schema & Route Test

**Files:**
- Modify: `apps/api/src/routes/v1/agent.ts`
- Test: `apps/api/src/app.test.ts`

**Interfaces:**
- Consumes: `POST /api/v1/agent/run`
- Produces: `200 OK` (SSE stream) for single-character payload `{"message": "2"}`.

- [ ] **Step 1: Write test in `apps/api/src/app.test.ts` asserting `POST /api/v1/agent/run` accepts `{"message": "2"}`**
- [ ] **Step 2: Update Zod schema in `agent.ts` to `z.string().trim().min(1, 'A mensagem não pode ser vazia')`**
- [ ] **Step 3: Update `test-chat.html` so follow-up messages include conversation history or full prompt context**
- [ ] **Step 4: Run `npm test` and `npm run build`**
- [ ] **Step 5: Commit**
