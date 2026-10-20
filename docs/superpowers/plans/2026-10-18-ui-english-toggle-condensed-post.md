# UI English/PT Toggle, English Agent Responses, Automated Demo & Punchy LinkedIn Post Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a seamless PT/EN language toggle to the web interface (`test-chat.html`), allow the backend agent to detect and reply in English (system prompt & responses fully in English when English is selected or queried in English), update the automated Playwright demo recorder to run entirely in English, and publish the condensed, high-impact LinkedIn post draft.

**Architecture:**
1. **Frontend i18n Toggle (`test-chat.html`):** Add language toggle button (PT / EN) persisted in `localStorage`. Dictionary of UI strings (headers, tabs, inputs, buttons, chips, initial greeting). Pass `lang: 'en' | 'pt'` in the `/api/v1/agent/run` payload and headers.
2. **Backend Agent Language Awareness (`apps/api/src/services/agent/runner.ts`):** Accept `lang?: 'en' | 'pt'` in `RunAgentOptions`. When `lang === 'en'`, adapt the system prompt persona, tactical progress summaries, table headers, and follow-ups to fluent English.
3. **Automate English Demo Recording (`scripts/generate_demo_assets.py`):** Update Playwright script to toggle to EN, interact in English (*"Which missable trophies should I watch out for in The Witcher 3?"* -> status & table -> *"give me the details for each missable trophy"*), and generate updated `docs/media/platina-ai-demo.mp4` and `platina-ai-demo.gif`.
4. **LinkedIn Post Documentation (`docs/linkedin-post.md`):** Update `docs/linkedin-post.md` with the new punchy, condensed English version.

**Tech Stack:** TypeScript, HTML/CSS/JS (vanilla i18n), Fastify, Playwright, FFmpeg.

---

### Task 1: Add Language Awareness to Agent Runner (English & PT)

**Files:**
- Modify: `apps/api/src/services/agent/runner.ts`
- Modify: `apps/api/src/routes/v1/agent.ts`
- Test: `apps/api/src/services/agent/runner.benchmark.test.ts`
- Test: `apps/api/src/app.test.ts`

**Interfaces:**
- `RunAgentOptions`: add `lang?: 'en' | 'pt'` (default `'pt'`).
- In `runner.ts`: If `lang === 'en'` or query is in English, system prompt adapts to English, and player progress summary table/text formats in English ("Missable Trophies", "Pending", etc.).

- [ ] **Step 1: Write test in `runner.benchmark.test.ts` asserting English responses when `lang: 'en'` is specified**
- [ ] **Step 2: Implement `lang` support in `agent.ts` route and `runner.ts` prompt logic**
- [ ] **Step 3: Run `npm test` in `apps/api` to verify 100% pass**
- [ ] **Step 4: Commit changes**

---

### Task 2: Implement UI Language Toggle (PT/EN) in `test-chat.html`

**Files:**
- Modify: `test-chat.html`

**Interfaces:**
- Header contains clean toggle button: `🌐 EN` / `🌐 PT`.
- Translates dynamic UI text:
  - Header, player status pill, tab buttons, inputs placeholders, send button, logs summary.
  - Initial greeting:
    - PT: *"Olá, Caçador de Troféus! 🏆\nQual jogo você deseja consultar ou platinar hoje?"*
    - EN: *"Hello, Trophy Hunter! 🏆\nWhich game would you like to platinum today?"*
  - Passes `lang: currentLang` in `POST /api/v1/agent/run` body.

- [ ] **Step 1: Implement translation dictionary and toggle button in `test-chat.html`**
- [ ] **Step 2: Verify syntax and behavior**
- [ ] **Step 3: Commit changes**

---

### Task 3: Re-record Automated Demo in English & Generate Assets

**Files:**
- Modify: `scripts/generate_demo_assets.py`
- Output: `docs/media/platina-ai-demo.mp4` & `docs/media/platina-ai-demo.gif`

- [ ] **Step 1: Update Playwright script to select English mode and run the dialogue in English**
- [ ] **Step 2: Run script and verify video/gif generated cleanly under 35s**
- [ ] **Step 3: Commit media assets**

---

### Task 4: Update Condensed LinkedIn Post

**Files:**
- Modify: `docs/linkedin-post.md`

- [ ] **Step 1: Overwrite `docs/linkedin-post.md` with the new punchy, condensed English post and comments**
- [ ] **Step 2: Commit and push**
