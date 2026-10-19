# Conversational Onboarding Greeting & Stream Latency Optimization Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform chat onboarding into an interactive conversational flow (greeting prompt -> user names game -> agent auto-identifies game, queries PSN progress in single-roundtrip, and summarizes status before standard chat) while optimizing LLM roundtrip latency and token streaming speed for crisp, snappy video demos.

**Architecture:**
1. **Frontend (`test-chat.html`):** On fresh session/tab creation, display an initial conversational prompt from Platina AI: *"Olá, Caçador de Troféus! Qual jogo você quer platinar hoje?"*. When user types the game name, auto-bind the game input, switch session context, and trigger status summary.
2. **Backend Agent (`apps/api/src/services/agent/runner.ts`):** 
   - Detect game-identification turn: when user specifies a game (or first message names a game), automatically pre-fetch player progress and inject it directly into the prompt context, skipping an extra tool-call turn (reducing latency from 2 roundtrips to 1 roundtrip, ~50% faster TTFT).
   - Real token streaming: stream response tokens as SSE chunks directly, rather than waiting for full-string buffering, keeping validation lightweight.
3. **Demo Automation (`scripts/generate_demo_assets.py`):** Update the Playwright recorder to capture the new onboarding flow (greeting -> user inputs "The Witcher 3: Wild Hunt" -> instant status briefing -> missables question -> detailed follow-up) and generate fresh MP4/GIF assets.
4. **LinkedIn Post & Interview Prep:** Add Q61 in `docs/interview-prep.md` covering TTFT optimization, single-turn context pre-fetching vs multi-turn tool loops, and update the LinkedIn post draft to highlight this specific latency optimization.

**Tech Stack:** TypeScript, Fastify, Server-Sent Events (SSE), Groq SDK, Playwright, FFmpeg, Python.

---

### Task 1: Pre-fetch Tool Injection & TTFT Latency Optimization in Agent Runner

**Files:**
- Modify: `apps/api/src/services/agent/runner.ts`
- Test: `apps/api/src/services/agent/runner.benchmark.test.ts`
- Test: `apps/api/src/app.test.ts`

**Interfaces:**
- `run(userMessage, options)`: If `options.game` or game inferred from `userMessage` and `options.psnId` are present on initial greeting/status turn, runner executes `check_player_progress` synchronously prior to LLM call, appending tool message directly to history.
- LLM executes in 1 roundtrip instead of 2 turns (Tool Call -> Tool Result -> LLM Synthesis).

- [ ] **Step 1: Write Vitest test asserting single-turn synthesis when game and PSN progress are pre-fetched**
- [ ] **Step 2: Implement pre-fetch tool injection and stream acceleration in `runner.ts`**
- [ ] **Step 3: Run `npm test` in `apps/api` to verify 100% pass**
- [ ] **Step 4: Commit changes**

---

### Task 2: Interactive Conversational Onboarding in UI

**Files:**
- Modify: `test-chat.html`

**Interfaces:**
- `renderChatBox()`: If session has empty history, display agent welcome bubble: *"Olá, Caçador de Troféus! 🏆 Qual jogo você quer platinar hoje?"*
- When user submits the first message with a game name (e.g. "The Witcher 3: Wild Hunt" or "GTA V"), UI auto-detects game, updates `#gameInput`, and triggers the status summary flow.

- [ ] **Step 1: Update `test-chat.html` with initial onboarding greeting and auto-game binding**
- [ ] **Step 2: Test manually in browser / verify DOM elements**
- [ ] **Step 3: Commit changes**

---

### Task 3: Automate Crisp Video & GIF Generation with New Fast Flow

**Files:**
- Modify: `scripts/generate_demo_assets.py`
- Output: `docs/media/platina-ai-demo.mp4` & `docs/media/platina-ai-demo.gif`

- [ ] **Step 1: Update `generate_demo_assets.py` to record the onboarding sequence: welcome message -> user types game -> instant tactical summary -> user asks for missables -> deep walkthrough**
- [ ] **Step 2: Run `generate_demo_assets.py` and verify generated MP4 (< 40s) and GIF**
- [ ] **Step 3: Commit updated media and script**

---

### Task 4: Interview Prep Question Q61 & Updated LinkedIn Post

**Files:**
- Modify: `docs/interview-prep.md`
- Modify: `docs/learning-log.md`

- [ ] **Step 1: Add Q61 in `docs/interview-prep.md`: "Optimizing Time-to-First-Token (TTFT) and Reducing Tool-Call Roundtrips in Conversational RAG Agents"**
- [ ] **Step 2: Document Milestone 14 in `docs/learning-log.md`**
- [ ] **Step 3: Commit and push**
