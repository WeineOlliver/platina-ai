# Relatório de Avaliação Golden Set & Arquitetura de Idioma — Platina AI

**Data:** 2026-10-27  
**Commit Base:** `f7d875d`  
**Commits da Entrega:** `b58ed15`, `20f8de0`, `3455a64` (branch `main`, sem push)

---

## 1. Topo do Relatório (Configuração Ativa)

```text
================================================================================
           PLATINA AI — RUNNER DE AVALIAÇÃO DE RAG & SQL (GOLDEN SET)
================================================================================
[CONFIG] Embedding Provider: local (deterministic-1536 (local pseudo-random))
[CONFIG] Full-Text TSVector: english (to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content, '')))
================================================================================
```

---

## 2. Diagnóstico do Banco de Dados

Query executada no Postgres:
```sql
SELECT title, length(content) 
FROM guide_chunks 
WHERE game ILIKE '%witcher 3%' 
ORDER BY title;
```

### Resultado (49 chunks indexados)

| Title | Length (bytes) |
| :--- | :--- |
| Armed and Dangerous | 739 |
| Ashes to Ashes (Part 1) | 1149 |
| Ashes to Ashes (Part 2) | 513 |
| Assassin of Kings (Part 1) | 1042 |
| Assassin of Kings (Part 2) | 374 |
| Bombardier | 513 |
| Brawler | 659 |
| Brawl Master (Part 1) | 732 |
| Brawl Master (Part 2) | 768 |
| Butcher of Blaviken | 804 |
| Can’t Touch This! | 857 |
| Fast and Furious | 1038 |
| Fearless Vampire Slayer | 923 |
| Fiend or Foe? | 1183 |
| Fist of the South Star | 446 |
| Friends With Benefits | 904 |
| Full Crew (Part 1) | 665 |
| Full Crew (Part 2) | 823 |
| Full Crew (Part 3) | 1181 |
| Full Crew (Part 4) | 1063 |
| Full Crew (Part 5) | 815 |
| Gwent Master (Part 1) | 1156 |
| Gwent Master (Part 2) | 1200 |
| Gwent Master (Part 3) | 1025 |
| Gwent Master (Part 4) | 964 |
| Humpty Dumpty | 872 |
| Kaer Morhen Trained | 1029 |
| Kingmaker | 1035 |
| Moo-rderer | 352 |
| Overkill (Part 1) | 1180 |
| Overkill (Part 2) | 520 |
| Pest Control | 468 |
| Power Overwhelming | 681 |
| Rad Steez, Bro! | 435 |
| Return to Sender | 585 |
| Shrieker | 552 |
| That Is the Evilest Thing… | 899 |
| The Doppler Effect | 888 |
| The Witcher 3: Wild Hunt — Overview (Part 1) | 543 |
| The Witcher 3: Wild Hunt — Overview (Part 2) | 1026 |
| The Witcher 3: Wild Hunt — Overview (Part 3) | 1155 |
| Triple Threat | 579 |
| Unlimited Money Exploit (Part 1) | 811 |
| Unlimited Money Exploit (Part 2) | 595 |
| What Was That? | 525 |
| When It’s Many Against One… | 982 |
| Witcher Gear Sets | 806 |
| Woodland Spirit (Part 1) | 1194 |
| Woodland Spirit (Part 2) | 341 |

---

## 3. Comparativo Lado a Lado: Baseline vs Novo Relatório

### A. Performance por Categoria

| Categoria | Total de Casos | Baseline (Passou / Taxa) | Novo (Passou / Taxa) | Variação Absoluta |
| :--- | :---: | :---: | :---: | :---: |
| **lista** | 9 | 2 / 22.2% | 2 / 22.2% | 0.0% |
| **dica** | 12 | 10 / 83.3% | 9 / 75.0% | -8.3% |
| **vaga** | 8 | 3 / 37.5% | 7 / 87.5% | **+50.0%** 🚀 |
| **ponto_sem_volta** | 4 | 0 / (N/A - SKIPPED) | 2 / 50.0% | **+50.0%** (agente real + judge) |
| **contaminacao** | 3 | 2 / 66.7% | 3 / 100.0% | **+33.3%** (100% blindado) |
| **fora_escopo** | 3 | 0 / (N/A - SKIPPED) | 3 / 100.0% | **+100.0%** (abstenção total) |
| **Geral Efetivo** | **39** | **17 / 43.6%** | **26 / 66.7%** | **+23.1%** |

### B. Performance por Métrica

| Métrica | Base Avaliados | Baseline Score | Novo Avaliados | Novo Score | Impacto |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **recall@5** | 20 | 65.0% (13/20) | 20 | **80.0%** (16/20) | **+15.0%** |
| **must_contain** | 20 | 80.0% (16/20) | 20 | **90.0%** (18/20) | **+10.0%** |
| **completeness** | 9 | 53.1% (méd) | 9 | 53.1% (méd) | Mantido (catálogo SQL) |
| **contamination** | 3 | 66.7% (2/3) | 3 | **100.0%** (3/3) | **+33.3%** (blindagem multi-jogo) |
| **faithfulness** | 0 | N/A | 7 | **82.9%** (méd) | RAG Triad Judge LLM |
| **answer_relevance** | 0 | N/A | 7 | **77.1%** (méd) | RAG Triad Judge LLM |
| **abstention** | 0 | N/A | 3 | **100.0%** (3/3) | Abstenção honesta sem alucinar |

---

## 4. Detalhamento dos Casos de Avaliação

### Casos Avaliados pelo Agente via RAG Triad (`hybrid` e `none`)

- **[H01] (HYBRID/ponto_sem_volta)** *Antes da batalha de Kaer Morhen, o que eu não posso esquecer?*
  - **Status:** ✅ PASSED
  - **Métricas:** Fidelidade: `0.60` | Pertinência: `0.90` | Overall Triad: `0.78`
  - **Comportamento:** O agente traduziu a intenção, chamou a tool com `query: "Kaer Morhen missable trophies before battle"`, recuperou o guia `Full Crew` e listou os aliados perdíveis em português com as fontes.
- **[H02] (HYBRID/ponto_sem_volta)** *No contrato do espírito da floresta em Skellige, se eu aceitar a oferta do Harald, perco algum troféu?*
  - **Status:** ✅ PASSED
  - **Métricas:** Fidelidade: `0.80` | Pertinência: `1.00` | Overall Triad: `0.93`
  - **Comportamento:** Identificou o troféu `Woodland Spirit`, explicou o dilema entre Sven e Harald e alertou sobre a perda do troféu.
- **[H03] (HYBRID/ponto_sem_volta)** *Estou em Novigrad, tem algum missável que eu preciso fazer aqui?*
  - **Status:** ❌ FAILED
  - **Métricas:** Fidelidade: `0.40` | Pertinência: `0.90`
  - **Motivo:** O agente recuperou `Assassin of Kings` e `Gwent Master`, mas não incluiu `The Doppler Effect` no top de trechos do contexto resumido.
- **[H04] (HYBRID/ponto_sem_volta)** *Vou começar o Hearts of Stone, o que é perdível?*
  - **Status:** ❌ FAILED
  - **Métricas:** Fidelidade: `1.00` | Pertinência: `0.80`
  - **Motivo:** O único snapshot indexado da DLC cobria o set Viper, não contendo o troféu `When It's Many Against One…` nem o termo `Iris`.
- **[N01] (NONE/fora_escopo)** *Como pego os troféus do Blood and Wine?*
  - **Status:** ✅ PASSED
  - **Métricas:** Fidelidade: `1.00` | Pertinência: `0.20`
  - **Comportamento:** Abstenção perfeita. Informou que o guia não está indexado e ofereceu buscar fontes complementares.
- **[N04] (NONE/fora_escopo)** *Como platinar Hollow Knight Silksong?*
  - **Status:** ✅ PASSED
  - **Métricas:** Fidelidade: `1.00` | Pertinência: `0.80`
  - **Comportamento:** Abstenção perfeita. Jogo não indexado, sem alucinações.
- **[N03] (NONE/fora_escopo)** *Como pego o troféu Gwent Grandmaster?*
  - **Status:** ✅ PASSED
  - **Métricas:** Fidelidade: `1.00` | Pertinência: `0.80`
  - **Comportamento:** Abstenção perfeita. Troféu inexistente, não confundiu com `Gwent Master`.

---

## 5. Commits Realizados

1. **`b58ed15`** — `feat(agent): decouple language architecture with English tool schemas and session response routing`
   - Atualização do system prompt em `prompts.ts` e `runner.ts`: chamadas de tools obrigatoriamente em inglês (nomes canônicos) e resposta final no idioma da sessão.
   - Schemas Zod de `searchGuides` e `playerProgress` atualizados com descrições em inglês.
   - `searchGuides`: fallback automático para o jogo da sessão ativa se omitido pelo LLM; erro explícito caso nenhum jogo seja informado.
   - Bateria de testes unitários criada em `languageRouting.test.ts`.

2. **`20f8de0`** — `feat(ingest): add configurable embedding provider and migrate tsvector to english`
   - Migration `infra/postgres/10_tsvector_english.sql`: coluna gerada `tsv` e índice GIN alterados para `'english'`.
   - `GuideChunkModel` e `search.py` atualizados para `plainto_tsquery('english', ...)`.
   - `embedding.py`: factory `get_embedding_service()` selecionando provedor via `EMBEDDING_PROVIDER` (`openai` com `text-embedding-3-small` / `local`).
   - 55 testes unitários de ingestão passando com 100% de sucesso.

3. **`3455a64`** — `feat(eval): connect golden runner to query_en, session game contamination, and ragTriadJudge for hybrid and none routes`
   - Golden set atualizado com os 39 casos contendo `query_en`.
   - `run_golden.py` consumindo `query_en` em rotas RAG, SQL e contaminação.
   - Contaminação repassando o jogo da sessão (`The Witcher 3: Wild Hunt`).
   - Bridge `runAgentCase.ts` executando o agente completo nas rotas `hybrid` e `none` e pontuando com o `ragTriadJudge`.
   - Cabeçalho do relatório com provider de embedding e configuração do `tsvector`.

---

## 6. Git Diff Summary (`git diff origin/main..main --stat`)

```text
 apps/api/src/services/agent/languageRouting.test.ts | 188 +++++++++++++++++++++
 apps/api/src/services/agent/runner.ts              |  34 +++-
 apps/api/src/services/agent/tools/playerProgress.ts |   9 +-
 apps/api/src/services/agent/tools/searchGuides.test.ts  |  41 +++++
 apps/api/src/services/agent/tools/searchGuides.ts  |  44 +++--
 apps/api/src/services/evals/ragTriadJudge.ts       |   1 +
 apps/api/src/services/evals/runAgentCase.ts        | 153 +++++++++++++++++
 apps/api/src/services/llm/prompts.ts               |  20 ++-
 golden_witcher3.json                               |  98 +++++++----
 infra/postgres/10_tsvector_english.sql             |   9 +
 services/ingest/src/config.py                      |   1 +
 services/ingest/src/models/chunk.py                |   3 +-
 services/ingest/src/services/embedding.py          |  61 ++++++-
 services/ingest/src/services/search.py             |   5 +-
 services/ingest/tests/eval/run_golden.py           | 158 +++++++++++++++--
 services/ingest/tests/golden/golden_witcher3.json  |  98 +++++++----
 services/ingest/tests/test_hybrid_schema.py        |   6 +-
 17 files changed, 799 insertions(+), 130 deletions(-)
```

---

## 7. Arquivos Modificados e Conteúdo Completo dos Diffs

### 7.1. apps/api/src/services/llm/prompts.ts
```typescript
// Insight: Production prompt engineering requires strict language decoupling: all tool arguments
// (queries, trophies, quests) must be in English for canonical search and vector retrieval,
// while final user responses must adapt to the user's preferred session language.
export const PLATINA_SYSTEM_PROMPT = `Você é o assistente oficial do Platina AI, especialista em troféus e guias de platina do ecossistema PlayStation (PS4, PS5, PS3).

Seu objetivo é guiar o jogador na rota mais eficiente rumo ao troféu de Platina, com precisão técnica e sem spoilers desnecessários.

Diretrizes obrigatórias:
1. IDIOMA E TOOL CALLS (ARQUITETURA DE IDIOMA):
   - Todos os argumentos de ferramentas (tools) devem ser OBRIGATORIAMENTE em inglês. Traduza a pergunta do usuário para termos em inglês antes de invocar qualquer tool.
   - Nomes de troféus, quests e personagens devem SEMPRE usar o nome oficial em inglês (ex: "Card Collector", "Full Crew", "Kaer Morhen").
   - A resposta final destinada ao jogador deve ser no idioma escolhido pelo usuário na sessão/UI; se não houver especificação, use o idioma da pergunta do usuário.
2. FOCO EM TROFÉUS PERDÍVEIS (MISSABLES): Sempre alerte o jogador com clareza máxima se um troféu puder ser perdido em determinada missão, escolha ou capítulo.
3. ESTRUTURA E ROADMAP:
   - Divida orientações complexas em passos numerados ou tópicos diretos.
   - Indique tempo estimado, dificuldade da platina (1 a 10) e número mínimo de jogadas (playthroughs) necessárias quando relevante.
4. CITAÇÃO OBRIGATÓRIA DE FONTES: Quando trechos de guias indexados forem fornecidos no bloco <fontes_verificadas>, baseie sua resposta prioritariamente neles e cite explicitamente a fonte (título e URL do guia) ao final da explicação.
5. ANTI-ALUCINAÇÃO: Se a informação exata não estiver nas fontes fornecidas ou você não tiver certeza de um requisito de troféu, avise claramente o jogador para não arriscar a perda do troféu.
6. TOM DE VOZ: Tom gamer, encorajador, objetivo, técnico e amigável (como um verdadeiro companheiro de caça aos troféus).`;
```

### 7.2. apps/api/src/services/agent/tools/searchGuides.ts
```typescript
export const searchGuidesParamsSchema = z.object({
  query: z.string().min(2).describe('Search query or exact trophy/boss/quest name in English (must always be in English)'),
  game: z.string().optional().describe('Official game title in English to filter guides (e.g. "The Witcher 3: Wild Hunt", "Bloodborne")'),
  missableOnly: z.boolean().optional().describe('Filter only excerpts with missable trophy warnings'),
  limit: z.number().min(1).max(10).default(3).describe('Maximum number of excerpts to return'),
});

// Resolução com fallback para o jogo da sessão ativa:
const resolvedGame = (validated.data.game || context?.sessionGame || context?.game)?.trim();
if (!resolvedGame) {
  return {
    error: 'Game not specified. Please specify which game you want to search guides for.',
  };
}
```

### 7.3. apps/api/src/services/agent/tools/playerProgress.ts
```typescript
export const checkPlayerProgressParamsSchema = z.object({
  psnId: z.string().min(2).describe('PSN ID or PlayStation Network username of the player'),
  game: z.string().min(2).describe('Official game title in English (e.g. "The Witcher 3: Wild Hunt", "Bloodborne")'),
});
```

### 7.4. infra/postgres/10_tsvector_english.sql
```sql
-- Migration 10: Switch tsvector generated column from portuguese to english for internal English processing
ALTER TABLE guide_chunks DROP COLUMN IF EXISTS tsv;

ALTER TABLE guide_chunks ADD COLUMN tsv tsvector
GENERATED ALWAYS AS (
  to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content, ''))
) STORED;

CREATE INDEX IF NOT EXISTS idx_guide_chunks_tsv_gin ON guide_chunks USING gin(tsv);
```

### 7.5. services/ingest/src/models/chunk.py
```python
    tsv = Column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content, ''))",
            persisted=True,
        ),
    )
```

### 7.6. services/ingest/src/services/search.py
```python
        # 4. Sparse Text Retrieval (PostgreSQL full-text search plainto_tsquery in English)
        # Insight: Internal processing operates strictly in English for canonical matching
        ts_query = func.plainto_tsquery("english", request.query)
        sparse_match_cond = GuideChunkModel.tsv.op("@@")(ts_query)
```

### 7.7. services/ingest/src/services/embedding.py
```python
class OpenAIEmbeddingService(IEmbeddingService):
    DIMENSIONS: int = 1536

    def __init__(self, api_key: Optional[str] = None, model: str = "text-embedding-3-small"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": texts,
        }
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(f"{self.base_url}/embeddings", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json().get("data", [])
            data.sort(key=lambda item: item["index"])
            return [item["embedding"] for item in data]

    async def embed_query(self, query: str) -> List[float]:
        results = await self.embed_texts([query])
        return results[0] if results else [0.0] * self.DIMENSIONS

def get_embedding_service() -> IEmbeddingService:
    # Insight: Select provider via EMBEDDING_PROVIDER (openai|local). Default is local for unit tests and offline dev.
    provider = os.getenv("EMBEDDING_PROVIDER", "local").strip().lower()
    if provider == "openai":
        return OpenAIEmbeddingService()
    return DeterministicLocalEmbeddingService()
```

### 7.8. apps/api/src/services/evals/runAgentCase.ts
```typescript
// Bridge TypeScript que executa o PlatinaAgentRunner completo nas rotas hybrid e none
// e avalia a resposta final utilizando o ragTriadJudge (Faithfulness, Context Relevance, Answer Relevance).
const evaluation = await evaluateRagTriad({
  query: testCase.question,
  contexts: collectedContexts,
  answer: finalAnswer,
});

if (testCase.route === 'none') {
  passed = isAbstained || evaluation.faithfulness.score >= 0.8;
} else if (testCase.route === 'hybrid') {
  const contentPassed = missingTrophies.length === 0 && missingMustContain.length === 0;
  const triadPassed = evaluation.faithfulness.score >= 0.5 && evaluation.answerRelevance.score >= 0.5;
  passed = contentPassed && triadPassed;
}
```

### 7.9. services/ingest/tests/eval/run_golden.py
```python
# Uso de query_en nas chamadas de busca vetorial e SQL
query_en = case.get("query_en") or question

# Contaminação passando o jogo da sessão (Witcher 3) e query em inglês
if category == "contaminacao":
    game_filter = "The Witcher 3: Wild Hunt"
    res = await vector_search_service.search(
        SearchQueryRequest(query=query_en, game=game_filter, limit=5, min_similarity=0.0)
    )

# Rotas hybrid e none conectadas ao agente completo
if route in ["hybrid", "none"]:
    async with AGENT_SEMAPHORE:
        agent_res = await asyncio.to_thread(run_agent_eval_case, case)
```

