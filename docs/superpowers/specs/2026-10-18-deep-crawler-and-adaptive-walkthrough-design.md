# Technical Design Specification: Exhaustive Recursive Subpage Guide Ingestion & Adaptive Walkthrough Mode

**Date:** 2026-10-18  
**Status:** In Review  
**Target Architecture:** `services/ingest` (Recursive Subpage Crawler & Vector Indexer) + `apps/api` (Adaptive Verbosity ReAct Agent)

---

## 1. Intent & Context
Currently:
1. The scraper only indexes the high-level roadmap page or brief fallback summary. Exhaustive subguides (e.g. PowerPyx's *All Gwent Card Locations Guide* with 199 cards, merchant tables, missable tournament requirements) are missing from `guide_chunks`.
2. When players ask for deep step-by-step walkthroughs (*"quero um passo a passo detalhado de como conseguir cada carta"*), the agent is constrained by a rigid $\le 120$ word limit, repeating brief tactical summaries and triggering grounding validator alerts because individual card locations are absent from the vector database.

This specification introduces:
1. **Recursive Subpage Crawling:** When a game guide is ingested, the scraper discovers, crawls, chunks, and vectorizes all linked subguides (collectibles, weapon locations, missable quests, endings).
2. **Adaptive Verbosity Mode (Deep Walkthrough vs. Tactical Brief):**
   - **Default Mode:** Concise tactical summary ($\le 120$ words) with follow-up CTA.
   - **Deep Walkthrough Mode:** When the user requests in-depth instructions (*"detalhado"*, *"passo a passo"*, *"como pegar cada"*, *"todos os itens"*), the 120-word ceiling is lifted. The agent retrieves comprehensive chunks from the subpage index and provides an exhaustive, multi-step walkthrough.

---

## 2. Goals, Non-Goals & Anti-Goals

### Goals
- **Recursive Subpage Discovery:** The scraper scans the main guide page for all related subguide URLs matching canonical patterns (e.g., `/all-*-locations-guide/`, `/*-trophy-guide-*/`, `/collectibles/`, `/gwent/`), fetches each page, extracts clean text, and indexes it under `game` with granular titles.
- **Deep Walkthrough Intent Detection:** The agent runner recognizes deep walkthrough requests and switches its system prompt instructions to allow detailed, formatted steps (tables, checklists, sequential locations).
- **Grounding Support for Granular Facts:** By indexing full subpages into PostgreSQL, granular entities (e.g. *Card: Dandelion*, *Location: Vegelbud Estate Masquerade*, *NPC: Marquise Serenity*) exist in verified sources, passing pre-flight grounding validation without re-prompt failures.
- **Deduplication & Concurrency:** Avoid re-crawling identical subpages or circular redirects.

### Non-Goals
- Crawling external domains outside the author's primary guide site (e.g. no random forum threads or YouTube videos).
- Bypassing heavy paywalls or CAPTCHAs.

### Anti-Goals
- Never truncate detailed walkthroughs back to 120 words when the user explicitly asked for full details.
- Never crash on games with 15+ subpages; ingestion must handle batches reliably with database transaction boundaries.

---

## 3. Architecture & Component Design

### 3.1. Recursive Subpage Scraper Pipeline (`services/ingest/src/services/scraper.py`)
- **Discovery Engine:**
  - `discover_subpages(main_html: str, base_url: str) -> list[str]`:
    - Parses HTML with `BeautifulSoup`.
    - Extracts `<a>` links matching subguide slugs (e.g. `gwent-card-locations`, `all-weapons`, `all-endings`, `collectibles`).
    - Filters out navigation, category pages, tags, and external social links.
- **Recursive Fetch & Parse:**
  - Fetches the main roadmap guide first.
  - Recursively fetches all discovered subpages (concurrency pool of 3-5 concurrent HTTP requests).
  - Normalizes headings and tables into readable Markdown with source URLs.
- **Batch Vector Ingestion (`POST /api/v1/ingest/fetch-and-index`):**
  - Accepts `recursive: bool = True` (default `True`).
  - Chunks all pages semantically, embeds in batches of 20-50, and persists to `guide_chunks` in PostgreSQL.

### 3.2. Adaptive Verbosity ReAct Agent (`apps/api/src/services/agent/runner.ts`)
- **Intent Classifier / Prompt Switch:**
  - Checks if the user message or conversation turn requests detailed walkthroughs:
    `const isDeepWalkthrough = /(detalhad|passo a passo|como pegar cad|todos os|guia complet|rotas complet)/i.test(userMessage);`
  - If `isDeepWalkthrough`:
    - Replaces the $\le 120$ word limit with:
      *"O usuário solicitou um guia detalhado e aprofundado. Apresente um passo a passo completo, estruturado em seções ou tabela, detalhando cada etapa, localização de NPC, missões e cuidados com troféus perdíveis baseando-se estritamente nas fontes verificadas recuperadas."*
    - Retrieves top-8 chunks instead of top-3 to provide comprehensive domain context.
  - If standard tactical turn: retains the concise $\le 120$ words budget.

### 3.3. Grounding Validator Accommodation (`apps/api/src/services/agent/validator.ts`)
- **Coverage-Based Validation Policy (Option 1):**
  - In Deep Walkthrough mode (or answers with $> 150$ words / multiple listed entities):
    - Grounding evaluates the factual coverage ratio:
      $$\text{Coverage} = \frac{\text{Supported Claims}}{\text{Total Extracted Claims}}$$
    - If $\text{Coverage} \ge 0.75$ (75% of extracted cards, NPCs, quest names, and locations match the retrieved guide corpus), the answer is marked valid (`isValid: true`), allowing connective phrasing and fluid explanations without false-positive rejections.
    - If $\text{Coverage} < 0.75$, the validator triggers the standard corrective re-prompt or safe fallback.
  - In short tactical briefs ($\le 120$ words), the strict zero-tolerance validation is maintained.

### 3.4. Multi-Turn Deep Walkthrough Intent & Retrieval Plumbing
- **Intent Recognition:**
  - Evaluates both explicit keywords (*"detalhado"*, *"passo a passo"*, *"como pegar cada"*) and affirmative responses (*"sim"*, *"quero"*, *"manda"*, *"1"*) immediately following an agent CTA (*"Quer os detalhes completos e rotas deste troféu?"*).
- **Retrieval & Tool Limits:**
  - `SearchGuidesTool`: Update Zod schema to allow `limit: z.number().min(1).max(10).default(3)`.
  - In deep walkthrough turns, the runner requests up to 8-10 chunks, providing extensive multi-page context.
  - Expands the output budget up to 800 words for deep walkthroughs.
