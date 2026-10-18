# Technical Design Specification: Tactical Trophy Route Planner & Adaptive Roadmap Agent

**Date:** 2026-10-18  
**Status:** In Review  
**Target Architecture:** `apps/api` (Node.js/Fastify ReAct Agent Loop) + `services/ingest` (Python/pgvector hybrid guide roadmap retrieval)

---

## 1. Context & Business Intent
When players ask: *"Qual a melhor rota pra mim agora no jogo X?"* or *"Quais meus próximos passos?"*, they want an intelligent, tactical routing recommendation based on:
1. Their live PSN trophy progress (what's already unlocked vs what's unearned).
2. The game's official roadmap structure (Campaign Missables, Passive Grinds, Post-Story Cleanup, Online/DLC Grinds).
3. Strategic efficiency: maximizing trophy gains in the shortest time without missing missable content or wasting hours backtracking.

Currently, the agent naively tries to search the user's natural language question into the vector database as a single string (e.g. searching *"qual a melhor rota"*), which returns zero guide chunks and trips the similarity cutoff guardrail, responding with *"Guia oficial não encontrado"*.

---

## 2. Goals, Non-Goals & Anti-Goals

### Goals
- **Telemetry-First Routing:** When a user asks for routes/next steps and supplies a PSN ID, the agent uses `check_player_progress` to fetch all unearned trophies and categorize them.
- **Roadmap Overview Extraction:** Ingest and index high-level roadmap chunks (Phase 1: Story + Natural Grinds; Phase 2: Post-Game Cleanup; Phase 3: Online/DLC) into `guide_chunks` with `category: roadmap`.
- **Natural Grind Identification:** Differentiate between passive grinds that should be accumulated naturally during story gameplay (e.g., weapon execution counts, cumulative kill types, Issen strikes in *Onimusha*, headshots) versus static miscellaneous tasks that waste time if pursued during the campaign.
- **Adaptive Branching for Post-Story Players:** If the main campaign is complete (e.g., player is at 70%+ completion with remaining miscellanea and DLC/Online grinds), the agent outlines two distinct routes:
  - **Option 1 (Fast Clearance):** Quick cleanups (Director Mode, simple standalone challenges) to boost trophy score rapidly.
  - **Option 2 (Heavy Grind First):** Tacking the long, high-coordination tasks first (Doomsday Heists, Masterminds, $8M vehicle investments) so the remainder is trivial.
- **Progressive & Concise Output:** Maintain the strict $\le 120$ word constraint with structured bullet points and a follow-up CTA for the chosen route.

### Non-Goals
- Real-time save file game telemetry (e.g., memory inspection or live mission coordinates); routing relies on PSN trophy sync state and authoritative guide roadmaps.
- Automatic matchmaking with other players for cooperative online trophies.

### Anti-Goals
- Never hallucinate fake trophy requirements or invent fictitious trophies absent from the player's actual PSN profile.
- Never output walls of text with 50-step walkthroughs before the user chooses a preferred route.
- Never trigger the "Guia oficial não encontrado" fallback when valid player telemetry is in hand.

---

## 3. System Architecture & Component Design

### 3.1. Guide & Trophy Ingestion Enhancement (`services/ingest` & `infra/postgres`)
- **Trophy Classification Schema:**
  - Update `player_trophies` or trophy catalog table with column:
    `trophy_category VARCHAR(32) DEFAULT 'standard'` 
    Allowed values:
    - `'missable'`: Blocked by story progression if not done in sequence.
    - `'natural_grind'`: Cumulative tasks best completed passively during story gameplay (e.g. headshots, Issen strikes).
    - `'quick_cleanup'`: Fast, standalone post-story tasks (e.g. Director Mode, simple collectibles, single stunts).
    - `'heavy_grind'`: High-time-investment or complex multi-player tasks (e.g. Masterminds, $8M investments, level 100).
- **Deterministic API Extension:**
  - Update `PlayerProgressService` and `GET /api/v1/players/{psn_id}/progress` to return pre-grouped buckets:
    - `quick_cleanup_trophies: []`
    - `heavy_grind_trophies: []`
    - `natural_grind_trophies: []`
    - `pending_missables: []`

### 3.2. Agent ReAct Routing Strategy (`apps/api/src/services/agent/runner.ts`)
1. **Detection Phase:** Detect routing intents (*"melhor rota"*, *"o que fazer agora"*, *"próximos passos"*).
2. **Telemetry Ingestion:** Call `check_player_progress(psnId, game)` to get pre-classified buckets.
3. **Adaptive Branching for Post-Story Players:**
   - If player has pending missables: Prioritize missable warnings immediately.
   - If campaign is complete / missables cleared: Formulate two distinct paths directly from the structured buckets:
     - **Rota A (Velocidade / Quick Clearance):** Sugere os troféus da lista `quick_cleanup_trophies`.
     - **Rota B (Fundação / Heavy Grind):** Sugere encarar os troféus da lista `heavy_grind_trophies`.
4. **Follow-Up Prompting:** Conclude with the call-to-action asking which route the player prefers to execute first.
5. **Grounding Validator Compatibility:** Structured telemetry buckets feed directly into the grounding verification gate, guaranteeing 100% factual fidelity.

---

## 4. Verification & Evals Plan
1. **Pytest (`services/ingest`):**
   - Ingest and verify retrieval of Roadmap chunks for GTA V, Bloodborne, and Elden Ring.
2. **Vitest (`apps/api`):**
   - Test agent routing prompt with a simulated player profile (71% GTA V progress).
   - Assert the agent outputs the two options (Fast Clearance vs Heavy Grind First) within the concise word limit ($\le 120$ words) without error or "Guia não encontrado" fallback.
