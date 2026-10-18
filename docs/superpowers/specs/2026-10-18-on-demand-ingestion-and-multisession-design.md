# Technical Design Specification: On-Demand Guide Ingestion, Dynamic Game Resolution & Multi-Session Chat UI

**Date:** 2026-10-18  
**Status:** In Review  
**Target Architecture:** `apps/api` (Node.js/Fastify Agent Runner + UI) + `services/ingest` (Python/FastAPI On-Demand Crawler & Chunker)

---

## 1. Intent & Context
Currently:
1. `test-chat.html` sends hardcoded `game: "Grand Theft Auto V"` and retains a single flat `chatHistory` array across all queries. Switching games contaminates context with previous GTA V chat turns.
2. The database contains guide chunks only for pre-seeded games (Bloodborne, Elden Ring, GTA V). Asking about an unindexed game (e.g. *The Witcher 3: Wild Hunt*) causes the agent to either mix up GTA V telemetry or abort with *"Guia oficial não encontrado"*.

This feature delivers:
1. **Dynamic Game Detection:** The frontend and agent resolve the active game dynamically from user intent.
2. **Multi-Session Chat Tabs:** The UI supports persistent tabs/sessions, allowing players to plan multiple platinas simultaneously (e.g. Tab 1: GTA V, Tab 2: The Witcher 3) with isolated message histories.
3. **On-Demand Guide Ingestion Pipeline (Approach A):** When a user asks about a game with 0 guide chunks in PostgreSQL, the agent triggers an on-demand crawl/parse/vectorize workflow, streaming a progress indicator over SSE (*"📥 Jogo inédito detectado: indexando guia oficial..."*) before answering from real ingested knowledge.

---

## 2. Goals, Non-Goals & Anti-Goals

### Goals
- **Multi-Session Tabs in UI:** The frontend supports creating, switching, and deleting chat sessions stored in `localStorage`, each retaining its own `game`, `psnId`, and `history`.
- **Dynamic Game Extraction:** If the user specifies a new game in conversation, the system updates the active session's game title automatically.
- **On-Demand Ingestion Trigger:** `services/ingest` exposes `POST /api/v1/ingest/fetch-and-index` (accepting `game: string, source_url?: string`). If guide chunks for the game do not exist in `guide_chunks`, it automatically fetches/synthesizes authoritative trophy roadmap data (PowerPyx/PSNProfiles schema), chunks, vectorizes, and commits to PostgreSQL.
- **Real-Time Ingestion SSE Feedback:** During agent execution, if on-demand ingestion fires, emit `{ type: "thought", content: "📥 Jogo inédito detectado: indexando guia de [Jogo] no banco de dados..." }` so the user is informed while vectorization completes.

### Non-Goals
- Crawling dynamic behind-login pages or paywalled guides.
- Replacing the primary PostgreSQL vector store with external third-party search APIs.

### Anti-Goals
- Never mix up cross-game telemetry (e.g. applying GTA V heists to The Witcher 3).
- Never fail with HTTP 500 or silent blank screens when an unindexed game is requested.

---

## 3. Architecture & Interfaces

### 3.1. Python Ingestion Service (`services/ingest`)
- **Scraper Pipeline (`src/services/scraper.py`):**
  - Implement real HTTP guide scraper for PowerPyx / PSNProfiles:
    - Queries public trophy guide URLs (e.g. `https://www.powerpyx.com/{slug}-trophy-guide-roadmap/` or PSNProfiles trophy guides).
    - Uses `httpx` with realistic user-agent headers to fetch HTML.
    - Strips navigation, ads, and footers, extracting clean Markdown sections (Roadmap, Overview, Missable Walkthroughs).
  - Falls back gracefully to structured guide parsing if direct HTML requires specific DOM cleanup.
- **Endpoint `POST /api/v1/ingest/fetch-and-index`:**
  - Input: `{"game": "The Witcher 3: Wild Hunt", "source_url": "..."}`
  - Logic:
    1. Checks if `guide_chunks` count for `game` is $> 0$. If already indexed, returns immediately.
    2. Runs `scraper.fetch_game_guide(game)`.
    3. Runs semantic chunker with markdown headings (`# Roadmap`, `## Missable Trophies`).
    4. Generates 1536-dim embeddings and fills `tsv` full-text search column.
    5. Saves chunks to PostgreSQL with transaction safety.
  - Output: `{"status": "indexed", "game": "...", "chunks_indexed": N, "source_url": "..."}`

### 3.2. Node.js Agent Runner & SSE Feedback (`apps/api`)
- In `PlatinaAgentRunner`:
  - When `search_trophy_guides` returns 0 results for a commercial game:
    - Emits SSE event: `{ type: "thought", content: "📥 Jogo inédito detectado: obtendo e indexando guia oficial comunitário (PowerPyx/PSNProfiles) no banco de dados..." }`.
    - Triggers `ingestionClient.fetchAndIndex(game)`.
    - Re-executes vector search over newly indexed chunks and provides grounded response.

### 3.3. Multi-Session Tabbed Chat UI (`test-chat.html`)
- **Session Architecture:**
  - `sessions`: Array stored in `localStorage`:
    ```json
    [
      { "id": "s_gtav", "game": "Grand Theft Auto V", "title": "GTA V (71%)", "history": [...] },
      { "id": "s_witcher", "game": "The Witcher 3: Wild Hunt", "title": "The Witcher 3", "history": [...] }
    ]
    ```
  - Active session ID tracked in `activeSessionId`.
  - Top tab bar displays active tabs with a `[+ Nova Platina]` button.
  - Switching tabs preserves chat bubbles and tool logs of that specific game without contaminating context.
  - Input for changing the active game per session.
