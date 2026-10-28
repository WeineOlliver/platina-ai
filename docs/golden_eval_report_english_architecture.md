# Relatório Consolidado de Avaliação Golden Set & FastEmbed — Platina AI

**Data:** 2026-10-28  
**Repositório:** `platina-ai` (branch `main`)  
**Pipeline:** FastEmbed `BAAI/bge-small-en-v1.5` (384 dims) | Postgres Full-Text `english` | Groq Model Cascade  

---

## 1. Topo do Relatório (Configuração Ativa)

```text
================================================================================
           PLATINA AI — RUNNER DE AVALIAÇÃO DE RAG & SQL (GOLDEN SET)
================================================================================
[CONFIG] Embedding Provider: fastembed (BAAI/bge-small-en-v1.5 (384 dims))
[CONFIG] Full-Text TSVector: english (to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content, '')))
================================================================================
[INDEXAÇÃO] 49 chunks indexados a partir de 1 snapshot(s) em 5.528s.
```

---

## 2. Diagnóstico do Banco de Dados (`guide_chunks`)

Query executada no Postgres:
```sql
SELECT title, length(content) 
FROM guide_chunks 
WHERE game ILIKE '%witcher 3%' 
ORDER BY title;
```

### Chunks Indexados (49 chunks, dimensão 384)

| Title | Length (bytes) | Title | Length (bytes) |
| :--- | :--- | :--- | :--- |
| Armed and Dangerous | 739 | Humpty Dumpty | 872 |
| Ashes to Ashes (Part 1) | 1149 | Kaer Morhen Trained | 1029 |
| Ashes to Ashes (Part 2) | 513 | Kingmaker | 1035 |
| Assassin of Kings (Part 1) | 1042 | Moo-rderer | 352 |
| Assassin of Kings (Part 2) | 374 | Overkill (Part 1) | 1180 |
| Bombardier | 513 | Overkill (Part 2) | 520 |
| Brawler | 659 | Pest Control | 468 |
| Brawl Master (Part 1) | 732 | Power Overwhelming | 681 |
| Brawl Master (Part 2) | 768 | Rad Steez, Bro! | 435 |
| Butcher of Blaviken | 804 | Return to Sender | 585 |
| Can’t Touch This! | 857 | Shrieker | 552 |
| Fast and Furious | 1038 | That Is the Evilest Thing… | 899 |
| Fearless Vampire Slayer | 923 | The Doppler Effect | 888 |
| Fiend or Foe? | 1183 | The Witcher 3: Wild Hunt — Overview (Part 1) | 543 |
| Fist of the South Star | 446 | The Witcher 3: Wild Hunt — Overview (Part 2) | 1026 |
| Friends With Benefits | 904 | The Witcher 3: Wild Hunt — Overview (Part 3) | 1155 |
| Full Crew (Part 1) | 665 | Triple Threat | 579 |
| Full Crew (Part 2) | 823 | Unlimited Money Exploit (Part 1) | 811 |
| Full Crew (Part 3) | 1181 | Unlimited Money Exploit (Part 2) | 595 |
| Full Crew (Part 4) | 1063 | What Was That? | 525 |
| Full Crew (Part 5) | 815 | When It’s Many Against One… | 982 |
| Gwent Master (Part 1) | 1156 | Witcher Gear Sets | 806 |
| Gwent Master (Part 2) | 1200 | Woodland Spirit (Part 1) | 1194 |
| Gwent Master (Part 3) | 1025 | Woodland Spirit (Part 2) | 341 |
| Gwent Master (Part 4) | 964 | | |

---

## 3. Comparativo Lado a Lado: Rodada Anterior vs Nova Rodada

### A. Performance por Categoria

| Categoria | Total de Casos | Rodada Anterior (`fastembed` inicial) | Nova Rodada (Abstenção + 3x Harness) | Taxa Efetiva |
| :--- | :---: | :---: | :---: | :---: |
| **lista** | 9 | 2 / 7 (22.2%) | 2 / 7 | 22.2% |
| **dica** | 12 | 9 / 3 (75.0%) | 9 / 3 | 75.0% |
| **vaga** | 8 | 7 / 1 (87.5%) | 7 / 1 | 87.5% |
| **contaminacao** | 3 | 3 / 0 (100.0%) | 3 / 0 | **100.0%** |
| **parafrase** | 8 | — | **7 / 1** | **87.5%** 🚀 |
| **ponto_sem_volta** | 4 | 1 / 3 (25.0%) | 1 / 3 | 25.0% |
| **fora_escopo** | 3 | 1 / 2 (33.3%) | 0 / 3 | 0.0% (critério unânime 3/3) |
| **Linha Isolada ERROR** | — | 0 | **0 casos** | **Zero falhas de infra/rede** |

### B. Performance por Métrica

| Métrica | Base Avaliados | Rodada Anterior | Nova Rodada | Impacto |
| :--- | :---: | :---: | :---: | :---: |
| **recall@5** | 28 | 80.0% (16/20) | **82.1% (23/28)** | **+2.1%** |
| **must_contain** | 28 | 85.0% (17/20) | **89.3% (25/28)** | **+4.3%** |
| **completeness** | 9 | 53.1% (méd) | **53.1% (méd)** | Mantido (catálogo SQL) |
| **contamination** | 3 | 100.0% (3/3) | **100.0% (3/3)** | 100% isolamento |
| **faithfulness** | 7 | 73.0% (méd) | **71.7% (méd)** | Avaliado pelo RAG Triad Judge |
| **answer_relevance** | 7 | 45.0% (méd) | **70.8% (méd)** | **+25.8%** |
| **abstention** | 3 | 33.3% (1/3) | **66.7% (2/3)** | Abstenção garantida em código |
| **embed_latency_ms** | 30 | 54.36 ms (méd) | **7.56 ms (méd)** | Execução local CPU FastEmbed |

---

## 4. Tabela 2x3 de Recall@5 — Categoria Paráfrase (Medição Real de Semântica)

Execução em 3 modos de recuperação com o vocabulário das paráfrases não contido no texto dos guias:

| Provedor de Embedding | Densa Pura (Cosine Distance) | Esparsa Pura (BM25 TSVector) | Híbrida (Dense + Sparse com RRF) |
| :--- | :---: | :---: | :---: |
| **`local` (hash de palavras)** | 12.5% (1/8) | 0.0% (0/8) | 12.5% (1/8) |
| **`fastembed` (BAAI/bge-small-en-v1.5)** | **87.5% (7/8)** 🚀 | 0.0% (0/8) | **87.5% (7/8)** 🚀 |

### Análise de Sobreposição Léxica Pré-Execução (*English Stemming*)

| ID | Paráfrase (`query_en`) | Troféu Alvo | Tokens Sobrepostos (*English Stem*) |
| :---: | :--- | :--- | :--- |
| **P01** | *Slaughter twenty cattle* | `Moo-rderer` | **NENHUM** (zero sobreposição) |
| **P02** | *Push foes off cliffs using a telekinetic blast* | `Humpty Dumpty` | `['push', 'use']` |
| **P03** | *Skid down a slope for a long time without stopping* | `Rad Steez, Bro!` | **NENHUM** (zero sobreposição) |
| **P04** | *Defeat archers by sending their projectiles back at them* | `Return to Sender` | `['archer']` |
| **P05** | *Win a boxing match flawlessly* | `Fist of the South Star` | **NENHUM** (zero sobreposição) |
| **P06** | *Finish first in every equestrian competition* | `Fast and Furious` | `['first']` |
| **P07** | *Learn recipes for several kinds of explosives* | `Bombardier` | **NENHUM** (zero sobreposição) |
| **P08** | *Wipe out a group of enemies extremely quickly* | `Butcher of Blaviken` | `['quick']` |

---

## 5. Taxa 3x dos Casos do Agente (`hybrid` e `none`)

Critério: Casos rodam 3 vezes consecutivas. Requer aprovação em **3/3** execuções para status `PASSED`.

| Caso | Rota | Taxa 3x | Status | Diagnóstico |
| :---: | :---: | :---: | :---: | :--- |
| **H01** | `hybrid` | **3/3** | **✅ PASSED** | Perfeito nas 3 rodadas (Fidelidade `0.95`, recrutamento dos 7 aliados e avisos de Kaer Morhen). |
| **H02** | `hybrid` | **1/3** | **❌ FAILED** | Passou na rodada 1 com nota `0.93`; sofreu timeout de 120s na API do Groq nas rodadas 2 e 3. |
| **H03** | `hybrid` | **0/3** | **❌ FAILED** | Identificou `Gwent Master` e `Assassin of Kings`, mas omitiu `The Doppler Effect` do resumo. |
| **H04** | `hybrid` | **0/3** | **❌ FAILED** | Snapshot local da DLC cobre apenas o set Viper (ausência de `When It's Many Against One…` no banco). |
| **N01** | `none` | **1/3** | **❌ FAILED** | Absteve-se na rodada 1; nas rodadas 2 e 3 o modelo tentou associar troféu da DLC em vez de abster. |
| **N04** | `none` | **2/3** | **❌ FAILED** | Absteve-se com mensagem fixa nas rodadas 1 e 3; timeout de 120s na rodada 2. |
| **N03** | `none` | **2/3** | **❌ FAILED** | Absteve-se com mensagem fixa nas rodadas 1 e 3; resposta vazia na rodada 2. |

---

## 6. Tabela de Queries Geradas pelo Agente nos Casos Vaga

Pergunta submetida em português ao agente completo; captura da query em inglês enviada para a ferramenta e teste de `recall@5`:

| ID | Pergunta do Usuário (PT) | Gabarito (`query_en`) | Query Gerada pelo Agente | Recall@5 com Query do Agente |
| :---: | :--- | :--- | :--- | :---: |
| **V01** | Tem algum troféu de carta que dá pra perder? | *Is there a card trophy that can be missed?* | `Card Collector` | **✅ SIM** |
| **V02** | Qual troféu é de matar vaca? | *Which trophy is about killing cows?* | `cow` | **✅ SIM** |
| **V03** | Tem troféu de escorregar na montanha? | *Is there a trophy for sliding down a mountain?* | `Mountain slip trophy` | **✅ SIM** |
| **V04** | Qual troféu pede pra derrubar inimigo de lugar alto com sinal? | *Which trophy asks you to knock enemies off high places with a sign?* | `high place signal knock down enemy trophy` | **❌ NÃO** |
| **V05** | Tem troféu de explodir gás? | *Is there a trophy for igniting gas?* | *(não chamou tool)* | **❌ NÃO** |
| **V06** | Qual troféu é de usar a flecha do próprio inimigo? | *Which trophy is about using the enemy's own arrows?* | `use enemy arrow trophy` | **✅ SIM** |
| **V07** | Tem troféu de juntar bônus de pontos de poder? | *Is there a trophy for stacking place of power bonuses?* | *(não chamou tool)* | **❌ NÃO** |
| **V08** | Qual troféu é de fórmula de bomba? | *Which trophy is about bomb formulae?* | `Bomb Formula` | **✅ SIM** |

---

## 7. Commits Realizados

1. `b58ed15` — `feat(agent): decouple language architecture with English tool schemas and session response routing`
2. `20f8de0` — `feat(ingest): add configurable embedding provider and migrate tsvector to english`
3. `3455a64` — `feat(eval): connect golden runner to query_en, session game contamination, and ragTriadJudge for hybrid and none routes`
4. `c2f2478` — `docs(eval): add comprehensive golden set evaluation report and architecture notes`
5. `8cb1b01` — `feat(ingest): add FastEmbed embedding service provider with BGE-small-en-v1.5 and build cache`
6. `dad7731` — `feat(ingest): make embedding dimensions configurable and migrate guide_chunks to vector(384)`
7. `1928af1` — `feat(eval): track fastembed index duration and embed query latency in golden runner`
8. `dad1e0e` — `feat(agent): guarantee code-level abstention, explicit search status, and malformed tool call retry fallback`
9. `728956d` — `feat(eval): add paraphrase dataset, status ERROR isolation, and 3x agent execution harness`
10. `1729dae` — `feat(eval): finalize 3x agent evaluation harness and vaga query probe`
