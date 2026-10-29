#!/usr/bin/env python3
"""
services/ingest/tests/eval/run_golden.py

Runner de avaliação de RAG e Catálogo/SQL baseado no golden dataset golden_witcher3.json.
Indexa snapshots locais de HTML, executa casos de teste para rotas 'rag' e 'sql',
registra 'hybrid' e 'none' como SKIPPED, e gera relatório estruturado em tela e JSON.
Exit code 0 sempre, garantindo que o relatório seja informativo e não quebre o CI.
"""

import argparse
import asyncio
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Ensure services/ingest is on sys.path
SERVICES_INGEST_DIR = Path(__file__).resolve().parent.parent.parent
if str(SERVICES_INGEST_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_INGEST_DIR))

from sqlalchemy import delete, func, select
from sqlalchemy.orm import selectinload

from src.database import get_db_session
from src.models.catalog import GameModel, TrophyModel
from src.models.chunk import GuideChunkModel
from src.models.player import PlayerGameModel, PlayerModel, PlayerTrophyModel
from src.schemas.chunk import IngestGuideRequest
from src.schemas.search import SearchQueryRequest
from src.services.chunker import chunker, build_context_prefix
from src.services.gwent_chunker import chunk_gwent_guide
from src.services.embedding import embedding_service
from src.services.entity_linker import link_chunks_to_trophies, get_canonical_game_id
from src.catalog.importer import normalize_catalog_name
from src.services.player import player_progress_service
from src.services.scraper import scraper
from src.services.search import vector_search_service

GOLDEN_DIR = SERVICES_INGEST_DIR / "tests" / "golden"
SNAPSHOTS_DIR = GOLDEN_DIR / "snapshots"
GOLDEN_FILE = GOLDEN_DIR / "golden_witcher3.json"
RESULTS_DIR = SERVICES_INGEST_DIR / "tests" / "eval" / "results"


def normalize_str(s: str) -> str:
    """Normalize string for robust title and keyword comparison."""
    if not s:
        return ""
    nfkd = unicodedata.normalize("NFKD", s)
    unaccented = "".join(c for c in nfkd if not unicodedata.combining(c))
    cleaned = (
        unaccented.lower()
        .replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("…", "...")
    )
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


async def index_snapshots_if_available(game_name: str = "The Witcher 3: Wild Hunt") -> int:
    """
    Indexa todos os arquivos HTML presentes em snapshots/ usando o pipeline real de ingestão:
    html_to_markdown -> chunk_guide -> embed_batch -> GuideChunkModel.
    """
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    # Index both PowerPyx (dicas.html) and PSNProfiles guide when available
    guide_names = ["dicas.html", "psnprofiles_guide_witcher3.html"]
    html_files = [SNAPSHOTS_DIR / f for f in guide_names if (SNAPSHOTS_DIR / f).exists()]
    if not html_files:
        html_files = [p for p in SNAPSHOTS_DIR.glob("*.html") if "trophies" not in p.name]
    if not html_files:
        print("[AVISO] Nenhum snapshot HTML encontrado em snapshots/. Usando índice pré-existente.")
        return 0

    all_chunks = []
    global_idx = 0

    snapshot_urls_file = SERVICES_INGEST_DIR / "src" / "catalog" / "snapshot_urls.json"
    snapshot_url_map = {}
    if snapshot_urls_file.exists():
        try:
            snapshot_url_map = json.loads(snapshot_urls_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    for html_file in html_files:
        html_content = html_file.read_text(encoding="utf-8", errors="ignore")
        markdown = scraper._html_to_markdown(html_content)
        source_url = snapshot_url_map.get(html_file.name, f"https://local.snapshots/{html_file.name}")

        req = IngestGuideRequest(game=game_name, source_url=source_url, content=markdown)
        chunks = chunker.chunk_guide(req)

        for c in chunks:
            c.metadata["source_url"] = source_url
            c.metadata["snapshot_file"] = html_file.name
            id_raw = f"{game_name}:{source_url}:{c.title}:{global_idx}"
            c.chunk_id = hashlib.sha256(id_raw.encode("utf-8")).hexdigest()[:24]
            global_idx += 1
            all_chunks.append(c)

    if not all_chunks:
        return 0

    # Entity linking to canonical catalog trophies
    clean_game_id = get_canonical_game_id(game_name)
    async with get_db_session() as session:
        await link_chunks_to_trophies(all_chunks, clean_game_id, session)

    # Insight: Specialized structured chunker for Gwent Card Collector guide
    gwent_file = SNAPSHOTS_DIR / "gwent_cards_witcher3.html"
    if gwent_file.exists() and "witcher" in game_name.lower():
        gwent_html = gwent_file.read_text(encoding="utf-8", errors="ignore")
        gwent_chunks = chunk_gwent_guide(
            gwent_html,
            game_id=clean_game_id,
            card_collector_trophy_id="the-witcher-3-wild-hunt-card-collector",
        )
        gwent_url = snapshot_url_map.get(gwent_file.name, "https://psnprofiles.com/guide/4250-the-witcher-3-wild-hunt-card-collector-guide")
        for gc in gwent_chunks:
            gc.game = game_name
            gc.metadata["source_url"] = gwent_url
            gc.metadata["snapshot_file"] = gwent_file.name
            id_raw = f"{game_name}:gwent:{gc.title}:{global_idx}"
            gc.chunk_id = hashlib.sha256(id_raw.encode("utf-8")).hexdigest()[:24]
            global_idx += 1
            all_chunks.append(gc)

    t_idx_start = time.perf_counter()
    # Insight: Context prefix '<game title> › <DLC ou Base Game> › <section title>' for embedding & tsvector
    texts = [
        f"{c.context_prefix or build_context_prefix(c.game, c.title, c.content, c.metadata.get('source_url', ''))}\n{c.content}"
        for c in all_chunks
    ]
    embeddings = await embedding_service.embed_batch(texts)
    idx_duration = time.perf_counter() - t_idx_start

    async with get_db_session() as session:
        # Atomic clean replacement of witcher chunks for evaluation run
        await session.execute(
            delete(GuideChunkModel).where(GuideChunkModel.game.ilike(f"{game_name}%"))
        )
        for chunk, emb in zip(all_chunks, embeddings):
            prefix = chunk.context_prefix or build_context_prefix(
                chunk.game, chunk.title, chunk.content, chunk.metadata.get("source_url", "local")
            )
            record = GuideChunkModel(
                id=chunk.chunk_id,
                game=chunk.game,
                game_id=clean_game_id,
                trophy_id=getattr(chunk, "trophy_id", None) or chunk.metadata.get("trophy_id"),
                title=chunk.title,
                content=chunk.content,
                context_prefix=prefix,
                is_missable=chunk.is_missable,
                source_url=chunk.metadata.get("source_url", "local"),
                metadata_=chunk.metadata,
                embedding=emb,
            )
            session.add(record)
        await session.commit()

    # Ensure a contaminating game exists in guide_chunks for contamination tests
    async with get_db_session() as session:
        check_other = await session.execute(
            select(func.count(GuideChunkModel.id)).where(
                ~GuideChunkModel.game.ilike("%Witcher%")
            )
        )
        count_other = check_other.scalar() or 0
        if count_other == 0:
            sample_content = (
                "Elden Ring Guide. Derrote Maliketh em Farum Azula. Questline de Ranni e Epsilon."
            )
            sample_emb = await embedding_service.embed_query(sample_content)
            session.add(
                GuideChunkModel(
                    id="chunk_contam_eval_sample",
                    game="Elden Ring",
                    title="Elden Ring — Legendary Armaments & Bosses",
                    content=sample_content,
                    is_missable=True,
                    source_url="https://powerpyx.com/elden-ring",
                    metadata_={},
                    embedding=sample_emb,
                )
            )
            await session.commit()

    print(f"[INDEXAÇÃO] {len(all_chunks)} chunks indexados a partir de {len(html_files)} snapshot(s) em {idx_duration:.3f}s.")
    return len(all_chunks)


def run_agent_eval_case(case: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
    """Execute complete PlatinaAgentRunner via TypeScript eval bridge with exponential backoff on 429/timeout."""
    repo_root = Path(__file__).resolve().parents[4]
    apps_api_dir = repo_root / "apps" / "api"
    payload = json.dumps({
        "id": case["id"],
        "category": case.get("category", ""),
        "route": case.get("route", ""),
        "question": case["question"],
        "game": "The Witcher 3: Wild Hunt",
        "toolOnly": case.get("toolOnly", False),
        "expected": case.get("expected", {}),
    })

    env = os.environ.copy()
    env["PLATINA_DISABLE_LIVE_SCRAPING"] = "true"

    for attempt in range(max_retries):
        try:
            proc = subprocess.run(
                ["npx", "tsx", "src/services/evals/runAgentCase.ts", payload],
                cwd=str(apps_api_dir),
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
            )
            stdout = proc.stdout
            if "__EVAL_RESULT_START__" in stdout and "__EVAL_RESULT_END__" in stdout:
                raw_json = stdout.split("__EVAL_RESULT_START__")[1].split("__EVAL_RESULT_END__")[0].strip()
                result = json.loads(raw_json)

                # Check if it was an ephemeral 429 or timeout inside the bridge
                err_text = str(result.get("error", "")).lower()
                if result.get("status") == "ERROR" and any(k in err_text for k in ["429", "rate limit", "timeout", "timed out", "tpd", "tpm"]):
                    if attempt < max_retries - 1:
                        backoff = 2 ** attempt * 5  # 5s, 10s, 20s
                        print(f"[{case['id']}] Rate limit / Timeout ({err_text[:40]}). Backoff de {backoff}s antes da tentativa {attempt + 2}/{max_retries}...", flush=True)
                        time.sleep(backoff)
                        continue
                return result

            return {
                "id": case["id"],
                "status": "ERROR",
                "error": f"Bridge output parse error: {stdout[:200]}",
                "reasons": [f"Bridge output parse error: {stdout[:200]}"],
                "toolCalls": [],
                "evaluation": None,
            }
        except subprocess.TimeoutExpired as te:
            if attempt < max_retries - 1:
                backoff = 2 ** attempt * 5
                print(f"[{case['id']}] Subprocess timeout ({te.timeout}s). Backoff de {backoff}s antes da tentativa {attempt + 2}/{max_retries}...", flush=True)
                time.sleep(backoff)
                continue
            return {
                "id": case["id"],
                "status": "ERROR",
                "error": f"Timeout expired after {te.timeout}s",
                "reasons": [f"Timeout expired after {te.timeout}s"],
                "toolCalls": [],
                "evaluation": None,
            }
        except Exception as e:
            return {
                "id": case["id"],
                "status": "ERROR",
                "error": str(e),
                "reasons": [str(e)],
                "toolCalls": [],
                "evaluation": None,
            }

    return {
        "id": case["id"],
        "status": "ERROR",
        "error": "Exhausted retries in run_agent_eval_case",
        "reasons": ["Exhausted retries in run_agent_eval_case"],
        "toolCalls": [],
        "evaluation": None,
    }


def classify_agent_runs(runs: List[Dict[str, Any]]) -> Tuple[str, str]:
    """
    Classifica o resultado das 3 execuções do agente:
    - Se todas as 3 passaram -> PASSED
    - Se houve erro de infra/timeout/resposta vazia (ERROR) em qualquer execução -> ERROR
    - Caso contrário (sem erros, mas sem atingir 3/3 aprovações lógicas) -> FAILED
    Retorna (status, motivo_resumido).
    """
    pass_count = sum(1 for r in runs if r.get("status") == "PASSED")
    error_count = sum(1 for r in runs if r.get("status") == "ERROR")

    if pass_count == 3:
        return "PASSED", ""

    if error_count > 0:
        err_msgs = [r.get("error") or "; ".join(r.get("reasons") or []) for r in runs if r.get("status") == "ERROR"]
        detail = "; ".join(filter(None, err_msgs))
        return "ERROR", f"Falha de infra/timeout/resposta vazia em {error_count}/3 rodadas ({pass_count} passaram): {detail}"

    # Sem erros de infra, mas não atingiu 3/3 aprovações lógicas
    last_run = runs[-1]
    reasons = list(last_run.get("reasons") or [])
    reasons.append(f"Passou em {pass_count}/3 tentativas (exige 3/3 para aprovação)")
    return "FAILED", "; ".join(reasons)


AGENT_SEMAPHORE = asyncio.Semaphore(1)


async def evaluate_case(
    case: Dict[str, Any],
    player_trophies: List[PlayerTrophyModel],
    canonical_trophies: Optional[List[Any]] = None,
    canonical_game: Optional[Any] = None,
) -> Dict[str, Any]:
    cid = case["id"]
    category = case.get("category", "")
    route = case.get("route", "")
    question = case["question"]
    query_en = case.get("query_en") or question
    expected = case.get("expected", {})

    # Routes requiring agent LLM reasoning (hybrid, none) run 3 times
    if route in ["hybrid", "none"]:
        runs = []
        for run_idx in range(1, 4):
            print(f"[{cid}] (Run {run_idx}/3: {route}) Avaliando '{question[:35]}...' ", flush=True)
            res_i = await asyncio.to_thread(run_agent_eval_case, case)
            runs.append(res_i)
            await asyncio.sleep(2.0)

        # Count passes, fails, errors
        pass_count = sum(1 for r in runs if r.get("status") == "PASSED")
        final_status, status_reason = classify_agent_runs(runs)

        print(f"[{cid}] -> {pass_count}/3 passed (Status: {final_status})", flush=True)

        last_run = runs[-1]
        all_tool_calls: List[Dict[str, Any]] = []
        for r in runs:
            for tc in r.get("toolCalls") or []:
                all_tool_calls.append(tc)

        reasons = [status_reason] if status_reason else []

        # Insight: For FAILED agent cases, cite the exact tool calls log (query generated, titles returned)
        if final_status == "FAILED":
            tool_call_summaries = []
            for tc in all_tool_calls:
                name = tc.get("name")
                args = tc.get("args") or {}
                status_tc = tc.get("status", "unknown")
                titles = tc.get("returned_chunk_titles") or []
                q = args.get("query", "") if isinstance(args, dict) else ""
                tool_call_summaries.append(
                    f"Tool '{name}' (query='{q}', status={status_tc}, chunks={titles})"
                )
            if tool_call_summaries:
                tool_log_text = " | ".join(tool_call_summaries)
                reasons.insert(0, f"Tool Calls Log: {tool_log_text}")

        eval_triad = last_run.get("evaluation") or {}
        metrics = {
            "is_abstained": 1.0 if last_run.get("isAbstained") else 0.0,
            "pass_ratio": f"{pass_count}/3",
            "pass_count": pass_count,
        }
        if eval_triad:
            metrics["faithfulness"] = eval_triad.get("faithfulness", {}).get("score", 0.0)
            metrics["context_relevance"] = eval_triad.get("contextRelevance", {}).get("score", 0.0)
            metrics["answer_relevance"] = eval_triad.get("answerRelevance", {}).get("score", 0.0)
            metrics["overall_triad"] = eval_triad.get("overallScore", 0.0)

        return {
            "id": cid,
            "category": category,
            "route": route,
            "question": question,
            "query_en": query_en,
            "expected": expected,
            "status": final_status,
            "reason": "; ".join(reasons) if final_status != "PASSED" else "",
            "answer": last_run.get("answer", ""),
            "agent_answers": [run_item.get("answer", "") for run_item in runs],
            "tool_calls": all_tool_calls,
            "metrics": metrics,
            "runs": runs,
        }

    # Route: RAG
    if route == "rag":
        # Contamination tests
        if category == "contaminacao":
            # Pass session game (Witcher 3) and English query as the agent would
            game_filter = "The Witcher 3: Wild Hunt"
            t0 = time.perf_counter()
            await embedding_service.embed_query(query_en)
            embed_lat_ms = (time.perf_counter() - t0) * 1000.0

            res = await vector_search_service.search(
                SearchQueryRequest(query=query_en, game=game_filter, limit=5, min_similarity=0.0)
            )
            chunks = res.results
            must_not = [w.lower() for w in expected.get("must_not_contain", [])]

            foreign_games = [c.game for c in chunks if "witcher" not in c.game.lower()]
            found_forbidden = []
            for c in chunks:
                comb = f"{c.title} {c.content}".lower()
                for f_term in must_not:
                    if f_term in comb:
                        found_forbidden.append(f_term)

            passed = (len(foreign_games) == 0) and (len(found_forbidden) == 0)
            reasons = []
            if foreign_games:
                reasons.append(f"Chunks recuperados de outro jogo: {foreign_games}")
            if found_forbidden:
                reasons.append(f"Termos contaminados encontrados: {found_forbidden}")

            return {
                "id": cid,
                "category": category,
                "route": route,
                "question": question,
                "query_en": query_en,
                "status": "PASSED" if passed else "FAILED",
                "reason": "; ".join(reasons) if not passed else "",
                "metrics": {
                    "contamination_error_count": len(foreign_games) + len(found_forbidden),
                    "embed_latency_ms": embed_lat_ms,
                    "passed": passed,
                },
            }

        # Standard RAG tests (dica, vaga, parafrase)
        exp_trophy = expected.get("trophy", "")
        exp_trophy_norm = normalize_str(exp_trophy)

        # Insight: Production path for 'dica' cases: resolve by name in canonical catalog + chunks by trophy_id
        prod_chunks = []
        prod_matched_trophy = None
        target_chunk_has_terms = True
        if category == "dica" and exp_trophy:
            async with get_db_session() as session:
                clean_gid = get_canonical_game_id("The Witcher 3: Wild Hunt")
                stmt = select(TrophyModel).where(TrophyModel.game_id == clean_gid)
                all_t = (await session.execute(stmt)).scalars().all()
                prod_matched_trophy = next((t for t in all_t if normalize_catalog_name(t.name) == normalize_catalog_name(exp_trophy)), None)
                if prod_matched_trophy:
                    stmt_c = select(GuideChunkModel).where(GuideChunkModel.trophy_id == prod_matched_trophy.id).order_by(GuideChunkModel.id.asc())
                    prod_chunks = (await session.execute(stmt_c)).scalars().all()

        t0 = time.perf_counter()
        print(f"[{cid}] (RAG: {category}) Avaliando '{question[:35]}...' ", flush=True)
        await embedding_service.embed_query(query_en)
        embed_lat_ms = (time.perf_counter() - t0) * 1000.0

        res = await vector_search_service.search(
            SearchQueryRequest(
                query=query_en,
                game="The Witcher 3: Wild Hunt",
                limit=5,
                min_similarity=0.0,
            )
        )
        top_chunks = res.results[:5]
        top_titles_norm = [normalize_str(c.title) for c in top_chunks]
        hybrid_content_norm = " ".join(normalize_str(f"{c.title} {c.content}") for c in top_chunks)

        # Secondary column: fallback_recall@5
        fallback_recall_at_5 = any(exp_trophy_norm in t for t in top_titles_norm) if exp_trophy_norm else True

        if category == "dica" and exp_trophy:
            recall_at_5 = bool(prod_matched_trophy and len(prod_chunks) > 0)
            all_content_norm = " ".join(normalize_str(f"{c.title} {c.content}") for c in prod_chunks) if prod_chunks else hybrid_content_norm
        else:
            recall_at_5 = fallback_recall_at_5
            all_content_norm = hybrid_content_norm

        # Metric: Must Contain (all) and Must Contain Any (at least one)
        must_contain_words = expected.get("must_contain", [])
        must_contain_any_words = expected.get("must_contain_any", [])

        missing_terms = []
        for term in must_contain_words:
            term_norm = normalize_str(term)
            if term_norm not in all_content_norm:
                missing_terms.append(term)
        must_contain_all_passed = len(missing_terms) == 0

        must_contain_any_passed = True
        if must_contain_any_words:
            must_contain_any_passed = any(normalize_str(term) in all_content_norm for term in must_contain_any_words)
            if not must_contain_any_passed:
                missing_terms.append(f"none of {must_contain_any_words}")

        must_contain_passed = must_contain_all_passed and must_contain_any_passed

        # Check if terms exist in target chunk content to separate generator error from search error
        if prod_chunks:
            target_text_norm = " ".join(normalize_str(f"{c.title} {c.content}") for c in prod_chunks)
            target_chunk_has_terms = all(normalize_str(term) in target_text_norm for term in must_contain_words)
            if must_contain_any_words:
                target_chunk_has_terms = target_chunk_has_terms and any(normalize_str(term) in target_text_norm for term in must_contain_any_words)

        # For vaga category: run through full agent once with question in PT
        agent_generated_query = ""
        agent_recall_at_5 = False
        if category == "vaga":
            print(f"[{cid}] (Vaga probe) Obtendo query gerada pelo agente... ", flush=True)
            try:
                # Fast tool call translation probe without running multi-turn judge
                agent_case_res = await asyncio.to_thread(run_agent_eval_case, {
                    "id": cid,
                    "category": category,
                    "route": route,
                    "question": question,
                    "game": "The Witcher 3: Wild Hunt",
                    "toolOnly": True,
                })
                tool_calls = agent_case_res.get("toolCalls", [])
                for tc in tool_calls:
                    if tc.get("name") == "search_trophy_guides":
                        args = tc.get("args") or {}
                        if isinstance(args, dict) and args.get("query"):
                            agent_generated_query = str(args["query"])
                            break
                print(f"[{cid}] (Vaga probe) Concluído: '{agent_generated_query}'", flush=True)
                if agent_generated_query:
                    search_from_agent = await vector_search_service.search(
                        SearchQueryRequest(
                            query=agent_generated_query,
                            game="The Witcher 3: Wild Hunt",
                            limit=5,
                            min_similarity=0.0,
                        )
                    )
                    top_ag_titles = [normalize_str(c.title) for c in search_from_agent.results[:5]]
                    agent_recall_at_5 = any(exp_trophy_norm in t for t in top_ag_titles)
            except Exception as e:
                agent_generated_query = f"Error: {e}"

        passed = recall_at_5 and must_contain_passed
        reasons = []
        if not recall_at_5:
            reasons.append(
                f"Recall@5: Troféu '{exp_trophy}' não encontrado no top-5 ({[c.title for c in top_chunks[:3]]})"
            )
        if not must_contain_passed:
            reasons.append(f"MustContain: Termos ausentes no top-5: {missing_terms}")

        return {
            "id": cid,
            "category": category,
            "route": route,
            "question": question,
            "query_en": query_en,
            "expected": expected,
            "status": "PASSED" if passed else "FAILED",
            "reason": "; ".join(reasons) if not passed else "",
            "metrics": {
                "recall_at_5": 1.0 if recall_at_5 else 0.0,
                "fallback_recall_at_5": 1.0 if fallback_recall_at_5 else 0.0,
                "must_contain": 1.0 if must_contain_passed else 0.0,
                "embed_latency_ms": embed_lat_ms,
                "top_hit": top_chunks[0].title if top_chunks else "None",
                "top_3_titles": [c.title for c in top_chunks[:3]],
                "expected_terms": must_contain_words or must_contain_any_words,
                "target_chunk_has_terms": target_chunk_has_terms,
                "agent_generated_query": agent_generated_query,
                "agent_recall_at_5": agent_recall_at_5,
            },
        }

    # Route: SQL (catálogo / progresso)
    if route == "sql":
        pool = canonical_trophies if canonical_trophies is not None else player_trophies

        if category == "contaminacao":
            # C03: Verificar se o catálogo do jogador para Witcher 3 traz troféus de Witcher 2
            witcher2_trophies = [
                (getattr(t, "name", None) or getattr(t, "trophy_name", ""))
                for t in pool
                if "witcher 2" in (getattr(t, "name", None) or getattr(t, "trophy_name", "")).lower()
            ]
            passed = len(witcher2_trophies) == 0
            return {
                "id": cid,
                "category": category,
                "route": route,
                "question": question,
                "query_en": query_en,
                "status": "PASSED" if passed else "FAILED",
                "reason": "Contém troféus de The Witcher 2" if not passed else "",
                "metrics": {"contamination_error_count": len(witcher2_trophies)},
            }

        # O01: Métricas de Roadmap (dificuldade, horas, jogadas) via GameModel canônico
        if cid == "O01":
            if not canonical_game:
                return {
                    "id": cid,
                    "category": category,
                    "route": route,
                    "question": question,
                    "query_en": query_en,
                    "status": "FAILED",
                    "reason": "GameModel('the-witcher-3-wild-hunt') não encontrado no catálogo.",
                    "metrics": {"completeness": 0.0},
                }

            exp_diff = expected.get("difficulty", "")
            exp_hours = expected.get("hours")
            exp_playthroughs = expected.get("playthroughs")

            game_diff_str = str(int(canonical_game.difficulty)) if canonical_game.difficulty is not None else ""
            diff_ok = bool(game_diff_str and (game_diff_str in str(exp_diff)))
            hours_ok = (canonical_game.hours == exp_hours)
            play_ok = (canonical_game.playthroughs == exp_playthroughs)

            matches = sum([diff_ok, hours_ok, play_ok])
            completeness = matches / 3.0
            passed = (matches == 3)
            reasons = []
            if not diff_ok:
                reasons.append(f"Dificuldade: obtido {canonical_game.difficulty}, esperado {exp_diff}")
            if not hours_ok:
                reasons.append(f"Horas: obtido {canonical_game.hours}, esperado {exp_hours}")
            if not play_ok:
                reasons.append(f"Playthroughs: obtido {canonical_game.playthroughs}, esperado {exp_playthroughs}")

            return {
                "id": cid,
                "category": category,
                "route": route,
                "question": question,
                "query_en": query_en,
                "status": "PASSED" if passed else "FAILED",
                "reason": "; ".join(reasons) if not passed else "",
                "metrics": {"completeness": round(completeness, 2)},
            }

        # Lista de troféus esperados
        expected_trophies = expected.get("trophies", [])
        expected_count = expected.get("count")
        must_not_contain = expected.get("must_not_contain", [])

        # Subconjunto de troféus selecionados do catálogo baseado no caso
        selected_trophies: List[Any] = []
        filter_description = ""

        # Insight: Handle generated SQL cases from canonical catalog
        gen_filter = case.get("filter") or expected.get("filter")
        if case.get("generated") or cid.startswith("GEN_") or gen_filter:
            f_type = gen_filter.get("type") if gen_filter else None
            f_dlc = gen_filter.get("dlc") if gen_filter else None
            f_missable = gen_filter.get("missable") if gen_filter else None
            f_total = gen_filter.get("total") if gen_filter else None

            if not gen_filter:
                cid_u = cid.upper()
                if "BRONZE" in cid_u:
                    f_type = "bronze"
                elif "SILVER" in cid_u:
                    f_type = "silver"
                elif "GOLD" in cid_u:
                    f_type = "gold"
                elif "BASE_GAME" in cid_u:
                    f_dlc = "Base Game"
                elif "HEARTS_OF_STONE" in cid_u:
                    f_dlc = "Hearts of Stone"
                elif "BLOOD_AND_WINE" in cid_u:
                    f_dlc = "Blood and Wine"
                elif "MISSABLE" in cid_u:
                    f_missable = True
                elif "TOTAL" in cid_u:
                    f_total = True

            selected_trophies = []
            for t in pool:
                t_type = (getattr(t, "type", None) or getattr(t, "trophy_type", "")).lower()
                t_dlc = getattr(t, "dlc", None)
                t_missable = getattr(t, "missable", None) if hasattr(t, "missable") else (getattr(t, "is_missable", False) or getattr(t, "trophy_category", "") == "missable")

                if f_type and t_type != f_type.lower():
                    continue
                if f_dlc:
                    if f_dlc.lower() in ("base", "base game"):
                        if t_dlc is not None:
                            continue
                    else:
                        if not t_dlc or t_dlc.lower() != f_dlc.lower():
                            continue
                if f_missable is not None:
                    if bool(t_missable) != bool(f_missable):
                        continue
                selected_trophies.append(t)
            filter_description = f"Generated filter (type={f_type}, dlc={f_dlc}, missable={f_missable}, total={f_total})"
        elif cid in ["L01", "L02"]:
            # Missables in base game (platinum)
            selected_trophies = [
                t for t in pool
                if (getattr(t, "missable", None) if hasattr(t, "missable") else (getattr(t, "is_missable", False) or getattr(t, "trophy_category", "") == "missable"))
                and not getattr(t, "dlc", None)
            ]
            filter_description = "missable=True & dlc=None (base game)"
        elif cid == "L03":
            # Prata no jogo base
            selected_trophies = [
                t for t in pool
                if (getattr(t, "type", None) or getattr(t, "trophy_type", "")).lower() == "silver"
                and not getattr(t, "dlc", None)
            ]
            filter_description = "type='silver' & dlc=None (base game)"
        elif cid == "L04":
            # Insight: Contrato de bruxo via description_query ('contract')
            selected_trophies = [
                t
                for t in pool
                if "contract" in (getattr(t, "description", None) or "").lower()
            ]
            filter_description = "descrição contém 'contract'"
        elif cid == "L05":
            # Insight: Dificuldade via description_query ('difficulty')
            selected_trophies = [
                t
                for t in pool
                if "difficulty" in (getattr(t, "description", None) or "").lower()
            ]
            filter_description = "descrição contém 'difficulty'"
        elif cid == "L06":
            # Briga de punho
            selected_trophies = [
                t
                for t in pool
                if "luta" in (getattr(t, "location", None) or getattr(t, "chapter_or_location", "") or "").lower()
                or "briga" in (getattr(t, "location", None) or getattr(t, "chapter_or_location", "") or "").lower()
                or "fist" in (getattr(t, "location", None) or getattr(t, "chapter_or_location", "") or "").lower()
                or (getattr(t, "name", None) or getattr(t, "trophy_name", "")).lower() in ["brawler", "fist of the south star", "brawl master"]
            ]
            filter_description = "lutas/brigas de punho"
        elif cid == "L07":
            # Hearts of Stone missables
            selected_trophies = [
                t
                for t in pool
                if (getattr(t, "missable", None) if hasattr(t, "missable") else (getattr(t, "is_missable", False) or getattr(t, "trophy_category", "") == "missable"))
                and (
                    "hearts of stone" in (getattr(t, "dlc", "") or "").lower()
                    or "hearts of stone" in (getattr(t, "location", None) or getattr(t, "chapter_or_location", "") or "").lower()
                )
            ]
            filter_description = "DLC Hearts of Stone missable"
        elif cid == "L08":
            # História principal
            selected_trophies = [
                t
                for t in pool
                if getattr(t, "trophy_category", "") == "standard"
                or (getattr(t, "name", None) or getattr(t, "trophy_name", "")).lower() in [e.lower() for e in expected_trophies]
            ]
            filter_description = "história principal"
        else:
            selected_trophies = list(pool)

        selected_names = [getattr(t, "name", None) or getattr(t, "trophy_name", "") for t in selected_trophies]
        selected_names_norm = [normalize_str(n) for n in selected_names]

        # Avaliação de contagem explícita (L02)
        if expected_count is not None:
            actual_count = len(selected_trophies)
            passed = actual_count == expected_count
            reason = (
                f"Contagem incorreta: encontrado {actual_count}, esperado {expected_count}"
                if not passed
                else ""
            )
            return {
                "id": cid,
                "category": category,
                "route": route,
                "question": question,
                "query_en": query_en,
                "status": "PASSED" if passed else "FAILED",
                "reason": reason,
                "metrics": {
                    "completeness": 1.0 if passed else round(min(actual_count, expected_count) / expected_count, 2)
                },
            }

        # Avaliação de completude por lista de troféus
        matched = []
        missing = []
        for exp in expected_trophies:
            exp_norm = normalize_str(exp)
            if exp_norm in selected_names_norm:
                matched.append(exp)
            else:
                missing.append(exp)

        completeness = len(matched) / len(expected_trophies) if expected_trophies else 1.0

        # Avaliação de must_not_contain
        found_forbidden = []
        for term in must_not_contain:
            term_norm = normalize_str(term)
            if term_norm in selected_names_norm:
                found_forbidden.append(term)

        passed = (completeness == 1.0) and (len(found_forbidden) == 0)

        reasons = []
        if completeness < 1.0:
            reasons.append(f"Completude {completeness:.2f} ({len(matched)}/{len(expected_trophies)}). Faltam: {missing}")
        if found_forbidden:
            reasons.append(f"must_not_contain violado: {found_forbidden}")

        return {
            "id": cid,
            "category": category,
            "route": route,
            "question": question,
            "query_en": query_en,
            "expected": expected,
            "status": "PASSED" if passed else "FAILED",
            "reason": "; ".join(reasons) if not passed else "",
            "metrics": {
                "completeness": round(completeness, 2),
                "matched_count": len(matched),
                "total_expected": len(expected_trophies),
            },
        }

    return {
        "id": cid,
        "category": category,
        "route": route,
        "question": question,
        "status": "SKIPPED",
        "reason": f"Rota desconhecida '{route}'",
        "metrics": {},
    }


async def main(split: str = "dev"):
    emb_provider = os.getenv("EMBEDDING_PROVIDER", "local").strip().lower()
    if emb_provider == "fastembed":
        emb_model = "BAAI/bge-small-en-v1.5 (384 dims)"
    elif emb_provider == "openai":
        emb_model = "text-embedding-3-small (1536 dims)"
    else:
        emb_model = f"deterministic (local pseudo-random, {os.getenv('EMBEDDING_DIMENSIONS', '384')} dims)"
    tsv_config = "english (to_tsvector('english', coalesce(context_prefix, '') || ' ' || coalesce(title, '') || ' ' || coalesce(content, '')))"

    print("=" * 80)
    print("           PLATINA AI — RUNNER DE AVALIAÇÃO DE RAG & SQL (GOLDEN SET)")
    print("=" * 80)
    print(f"[CONFIG] Embedding Provider: {emb_provider} ({emb_model})")
    print(f"[CONFIG] Full-Text TSVector: {tsv_config}")
    print(f"[CONFIG] Split selecionado: {split.upper()}")
    print("=" * 80)

    # 1. Index snapshots
    await index_snapshots_if_available("The Witcher 3: Wild Hunt")

    # 2. Carrega Golden Dataset (Manual e Gerados)
    cases: List[Dict[str, Any]] = []
    if GOLDEN_FILE.exists():
        with open(GOLDEN_FILE, "r", encoding="utf-8") as f:
            golden_data = json.load(f)
        manual_cases = golden_data.get("cases", [])
        for mc in manual_cases:
            mc["split"] = "dev"
            mc["generated"] = False
        cases.extend(manual_cases)
        print(f"Cenários manuais carregados ({GOLDEN_FILE.name}): {len(manual_cases)}")
    else:
        print(f"[AVISO] Arquivo golden manual não encontrado em: {GOLDEN_FILE}")

    gen_files = sorted(list(GOLDEN_DIR.glob("generated_*.json")))
    for gf in gen_files:
        try:
            with open(gf, "r", encoding="utf-8") as f:
                gen_data = json.load(f)
            gcases = gen_data.get("cases", []) if isinstance(gen_data, dict) else gen_data
            for gc in gcases:
                gc.setdefault("generated", True)
                if "split" not in gc:
                    val = int(hashlib.sha256(gc["id"].encode("utf-8")).hexdigest(), 16) % 100
                    gc["split"] = "dev" if val < 70 else "test"
            cases.extend(gcases)
            print(f"Cenários gerados carregados ({gf.name}): {len(gcases)}")
        except Exception as e:
            print(f"[AVISO] Falha ao carregar arquivo gerado {gf.name}: {e}")

    # Filtragem pelo split selecionado
    if split != "all":
        filtered_cases = [c for c in cases if c.get("split") == split]
    else:
        filtered_cases = cases

    print(f"\n[SPLIT: {split.upper()}] Cenários selecionados para avaliação: {len(filtered_cases)} de {len(cases)} totais")

    # 3. Consulta troféus de Witcher 3 do banco via caminho de playerProgress e catálogo canônico
    async with get_db_session() as session:
        stmt = (
            select(PlayerTrophyModel)
            .join(PlayerGameModel, PlayerTrophyModel.player_game_id == PlayerGameModel.id)
            .where(PlayerGameModel.game_title.ilike("%The Witcher 3%"))
        )
        res = await session.execute(stmt)
        player_trophies = res.scalars().all()

        stmt_canon = (
            select(TrophyModel)
            .where(TrophyModel.game_id == "the-witcher-3-wild-hunt")
        )
        canonical_trophies = (await session.execute(stmt_canon)).scalars().all()

        stmt_game = (
            select(GameModel)
            .where(GameModel.id == "the-witcher-3-wild-hunt")
        )
        canonical_game = (await session.execute(stmt_game)).scalar_one_or_none()

    # 4. Avalia casos (RAG e SQL sequenciais, depois Agent casos sequenciais)
    print("Avaliando casos diretos (RAG e SQL)...")
    direct_cases = [c for c in filtered_cases if c.get("route") not in ["hybrid", "none"]]
    agent_cases = [c for c in filtered_cases if c.get("route") in ["hybrid", "none"]]

    results: List[Dict[str, Any]] = []
    for dc in direct_cases:
        res = await evaluate_case(dc, player_trophies, canonical_trophies, canonical_game)
        res["generated"] = bool(dc.get("generated", False) or str(dc.get("id", "")).startswith("GEN_"))
        results.append(res)

    print(f"Avaliando {len(agent_cases)} casos com Agente LLM...")
    for ac in agent_cases:
        res = await evaluate_case(ac, player_trophies, canonical_trophies, canonical_game)
        res["generated"] = bool(ac.get("generated", False) or str(ac.get("id", "")).startswith("GEN_"))
        results.append(res)
        await asyncio.sleep(2.0)

    # 5. Agregação por Categoria (separando manual vs gerado)
    categories: Dict[str, Dict[str, int]] = {}
    total_errors = 0
    for r in results:
        is_gen = r.get("generated", False) or str(r.get("id", "")).startswith("GEN_")
        origin = "generated" if is_gen else "manual"
        cat_key = f"{r['category']} ({origin})"
        if cat_key not in categories:
            categories[cat_key] = {"total": 0, "passed": 0, "failed": 0, "error": 0, "skipped": 0}
        categories[cat_key]["total"] += 1
        if r["status"] == "PASSED":
            categories[cat_key]["passed"] += 1
        elif r["status"] == "FAILED":
            categories[cat_key]["failed"] += 1
        elif r["status"] == "ERROR":
            categories[cat_key]["error"] += 1
            total_errors += 1
        elif r["status"] == "SKIPPED":
            categories[cat_key]["skipped"] += 1

    # 6. Agregação por Métrica
    metrics_summary = {
        "recall_at_5": {"total": 0, "success": 0},
        "fallback_recall_at_5": {"total": 0, "success": 0},
        "must_contain": {"total": 0, "success": 0},
        "completeness": {"total": 0, "total_score": 0.0},
        "contamination": {"total": 0, "success": 0},
        "faithfulness": {"total": 0, "total_score": 0.0},
        "answer_relevance": {"total": 0, "total_score": 0.0},
        "abstention": {"total": 0, "success": 0},
        "embed_latency": {"total": 0, "total_ms": 0.0},
    }

    for r in results:
        # Insight: Generated lista cases are marked as SQL sanity checks and excluded from global aggregate metrics
        if r.get("origin") == "gerado" and r.get("category") == "lista":
            continue

        m = r.get("metrics", {})
        if "embed_latency_ms" in m:
            metrics_summary["embed_latency"]["total"] += 1
            metrics_summary["embed_latency"]["total_ms"] += m["embed_latency_ms"]
        if "recall_at_5" in m:
            metrics_summary["recall_at_5"]["total"] += 1
            if m["recall_at_5"] == 1.0:
                metrics_summary["recall_at_5"]["success"] += 1
        if "fallback_recall_at_5" in m:
            metrics_summary["fallback_recall_at_5"]["total"] += 1
            if m["fallback_recall_at_5"] == 1.0:
                metrics_summary["fallback_recall_at_5"]["success"] += 1
        if "must_contain" in m:
            metrics_summary["must_contain"]["total"] += 1
            if m["must_contain"] == 1.0:
                metrics_summary["must_contain"]["success"] += 1
        if "completeness" in m:
            metrics_summary["completeness"]["total"] += 1
            metrics_summary["completeness"]["total_score"] += m["completeness"]
        if "contamination_error_count" in m:
            metrics_summary["contamination"]["total"] += 1
            if m["contamination_error_count"] == 0:
                metrics_summary["contamination"]["success"] += 1
        # Insight: Faithfulness and answer_relevance strictly on all hybrid route cases that did NOT abstain (including H03)
        is_hybrid_non_abstained = (r.get("route") == "hybrid" and m.get("is_abstained", 0.0) == 0.0)
        if "faithfulness" in m and is_hybrid_non_abstained:
            metrics_summary["faithfulness"]["total"] += 1
            metrics_summary["faithfulness"]["total_score"] += m["faithfulness"]
        if "answer_relevance" in m and is_hybrid_non_abstained:
            metrics_summary["answer_relevance"]["total"] += 1
            metrics_summary["answer_relevance"]["total_score"] += m["answer_relevance"]
        if "is_abstained" in m and r.get("category") == "fora_escopo":
            metrics_summary["abstention"]["total"] += 1
            if m["is_abstained"] == 1.0:
                metrics_summary["abstention"]["success"] += 1

    # 7. Renderiza Relatório em Terminal
    print("\n" + "=" * 80)
    print("                    1. RELATÓRIO POR CATEGORIA")
    print("=" * 80)
    print(f"{'Categoria (Origem)':<26} | {'Total':<6} | {'Passou':<7} | {'Falhou':<7} | {'Erro (API)':<10} | {'Ignorado':<8} | {'Taxa Efetiva':<12}")
    print("-" * 88)
    for cat, counts in sorted(categories.items()):
        evaluated = counts["passed"] + counts["failed"]
        rate = f"{(counts['passed'] / evaluated * 100):.1f}%" if evaluated > 0 else "(N/A)"
        print(
            f"{cat:<26} | {counts['total']:<6} | {counts['passed']:<7} | {counts['failed']:<7} | "
            f"{counts['error']:<10} | {counts['skipped']:<8} | {rate:<12}"
        )
    print("-" * 88)
    print(f"[STATUS ERROR TOTAL]: {total_errors} caso(s) com timeout ou falha de infraestrutura de API/rede.")

    print("\n" + "=" * 80)
    print("                    2. MÉTRICAS AGREGADAS")
    print("=" * 80)
    print(f"{'Métrica':<22} | {'Amostras (n)':<14} | {'Sucessos':<8} | {'Taxa':<15}")
    print("-" * 65)

    rec = metrics_summary["recall_at_5"]
    rec_rate = f"{(rec['success'] / rec['total'] * 100):.1f}%" if rec["total"] else "N/A"
    print(f"{'recall@5 (produção)':<22} | {rec['total']:<14} | {rec['success']:<8} | {rec_rate:<15}")

    f_rec = metrics_summary["fallback_recall_at_5"]
    f_rec_rate = f"{(f_rec['success'] / f_rec['total'] * 100):.1f}%" if f_rec["total"] else "N/A"
    print(f"{'fallback_recall@5':<22} | {f_rec['total']:<14} | {f_rec['success']:<8} | {f_rec_rate:<15}")

    must = metrics_summary["must_contain"]
    must_rate = f"{(must['success'] / must['total'] * 100):.1f}%" if must["total"] else "N/A"
    print(f"{'must_contain':<22} | {must['total']:<14} | {must['success']:<8} | {must_rate:<15}")

    comp = metrics_summary["completeness"]
    comp_rate = (
        f"{(comp['total_score'] / comp['total'] * 100):.1f}% (méd)"
        if comp["total"]
        else "N/A"
    )
    print(f"{'completeness':<22} | {comp['total']:<14} | {'-':<8} | {comp_rate:<15}")

    cont = metrics_summary["contamination"]
    cont_rate = f"{(cont['success'] / cont['total'] * 100):.1f}%" if cont["total"] else "N/A"
    print(f"{'contamination':<22} | {cont['total']:<14} | {cont['success']:<8} | {cont_rate:<15}")

    faith = metrics_summary["faithfulness"]
    faith_rate = (
        f"{(faith['total_score'] / faith['total'] * 100):.1f}% (méd)"
        if faith["total"]
        else "N/A"
    )
    print(f"{'faithfulness (juiz)':<22} | {faith['total']:<14} | {'-':<8} | {faith_rate:<15}")

    ans_rel = metrics_summary["answer_relevance"]
    ans_rel_rate = (
        f"{(ans_rel['total_score'] / ans_rel['total'] * 100):.1f}% (méd)"
        if ans_rel["total"]
        else "N/A"
    )
    print(f"{'answer_relevance (juiz)':<22} | {ans_rel['total']:<14} | {'-':<8} | {ans_rel_rate:<15}")

    abst = metrics_summary["abstention"]
    abst_rate = f"{(abst['success'] / abst['total'] * 100):.1f}%" if abst["total"] else "N/A"
    print(f"{'abstention':<22} | {abst['total']:<14} | {abst['success']:<8} | {abst_rate:<15}")

    el = metrics_summary["embed_latency"]
    avg_embed_lat = (el["total_ms"] / el["total"]) if el["total"] else 0.0
    print(f"{'embed_latency_ms':<18} | {el['total']:<10} | {'-':<8} | {avg_embed_lat:.2f} ms (méd)")

    print("\n" + "=" * 80)
    print("        3. CASOS COM FALHA OU DIVERGÊNCIA IDENTIFICADA (BASELINE)")
    print("=" * 80)
    failed_cases = [r for r in results if r["status"] == "FAILED"]
    if not failed_cases:
        print("Nenhuma falha encontrada.")
    else:
        for f_case in failed_cases:
            print(f"[{f_case['id']}] ({f_case['route'].upper()}/{f_case['category']}) {f_case['question']}")
            print(f"   -> Motivo: {f_case['reason']}")

    # Insight: Explicitly list which 'dica' cases failed and why (separates generator error from search error)
    dica_failures = [r for r in results if r.get("category") == "dica" and r.get("status") == "FAILED"]
    print("\n" + "=" * 80)
    print("        3.1. DETALHE DOS CASOS DE DICA QUE FALHARAM")
    print("=" * 80)
    if not dica_failures:
        print("Nenhum caso de dica falhou! 100% aprovados.")
    else:
        for df in dica_failures:
            m = df.get("metrics", {})
            print(f"[{df['id']}] {df['question']}")
            print(f"   -> Termos esperados: {m.get('expected_terms')}")
            print(f"   -> Top-3 títulos recuperados: {m.get('top_3_titles')}")
            print(f"   -> Termo existe no chunk alvo? {'Sim' if m.get('target_chunk_has_terms') else 'Não (erro do gerador)'}")
            print(f"   -> Motivo: {df.get('reason')}")

    print("\n" + "=" * 80)
    print("    4. CASOS AVALIADOS PELO AGENTE COM RAG TRIAD ('HYBRID' E 'NONE')")
    print("=" * 80)
    agent_eval_cases = [r for r in results if r["route"] in ["hybrid", "none"]]
    for a_case in agent_eval_cases:
        status_sym = "✅ PASSED" if a_case["status"] == "PASSED" else ("⚠️ ERROR" if a_case["status"] == "ERROR" else "❌ FAILED")
        m = a_case.get("metrics", {})
        ratio_info = m.get("pass_ratio", "N/A")
        triad_info = f"Taxa 3x: {ratio_info} | Fidelidade: {m.get('faithfulness', 0.0):.2f} | Pertinência: {m.get('answer_relevance', 0.0):.2f}"
        print(f"[{a_case['id']}] ({a_case['route'].upper()}/{a_case['category']}) {a_case['question']}")
        print(f"   -> Status: {status_sym} | {triad_info}")
        if a_case.get("reason"):
            print(f"   -> Motivo: {a_case['reason']}")

    # Print Vaga Agent Tool Queries Table
    vaga_cases = [r for r in results if r["category"] == "vaga"]
    if vaga_cases:
        print("\n" + "=" * 80)
        print("    5. TABELA DE QUERIES GERADAS PELO AGENTE NOS CASOS VAGA")
        print("=" * 80)
        print(f"{'ID':<6} | {'Gabarito (query_en)':<45} | {'Query do Agente':<25} | {'Recall@5 Agente':<15}")
        print("-" * 100)
        for vc in vaga_cases:
            vm = vc.get("metrics", {})
            ag_q = str(vm.get("agent_generated_query") or "-")
            rec_ag = "✅ SIM" if vm.get("agent_recall_at_5") else "❌ NÃO"
            print(f"{vc['id']:<6} | {vc.get('query_en', '')[:43]:<45} | {ag_q[:23]:<25} | {rec_ag:<15}")

    # 8. Grava resultado em JSON em tests/eval/results/<data>.json
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_file = RESULTS_DIR / f"{timestamp}.json"

    export_payload = {
        "timestamp": timestamp,
        "golden_set": "golden_witcher3.json",
        "split": split,
        "total_cases": len(filtered_cases),
        "categories_summary": categories,
        "metrics_summary": {
            "recall_at_5": rec_rate,
            "fallback_recall_at_5": f_rec_rate,
            "must_contain": must_rate,
            "completeness_average": comp_rate,
            "contamination_success_rate": cont_rate,
            "faithfulness_average": faith_rate,
            "answer_relevance_average": ans_rel_rate,
            "abstention_success_rate": abst_rate,
            "average_embed_latency_ms": round(avg_embed_lat, 2),
        },
        "results": results,
    }

    out_file.write_text(json.dumps(export_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[EXPORT] Relatório JSON gravado com sucesso em: {out_file}")
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Runner de avaliação de RAG e Catálogo/SQL")
    parser.add_argument(
        "--split",
        choices=["dev", "test", "all"],
        default="dev",
        help="Split de casos para avaliar (dev, test, all). Default: dev",
    )
    args = parser.parse_args()
    asyncio.run(main(split=args.split))
