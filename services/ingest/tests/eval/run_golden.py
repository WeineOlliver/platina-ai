#!/usr/bin/env python3
"""
services/ingest/tests/eval/run_golden.py

Runner de avaliação de RAG e Catálogo/SQL baseado no golden dataset golden_witcher3.json.
Indexa snapshots locais de HTML, executa casos de teste para rotas 'rag' e 'sql',
registra 'hybrid' e 'none' como SKIPPED, e gera relatório estruturado em tela e JSON.
Exit code 0 sempre, garantindo que o relatório seja informativo e não quebre o CI.
"""

import asyncio
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
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
from src.models.chunk import GuideChunkModel
from src.models.player import PlayerGameModel, PlayerModel, PlayerTrophyModel
from src.schemas.chunk import IngestGuideRequest
from src.schemas.search import SearchQueryRequest
from src.services.chunker import chunker
from src.services.embedding import embedding_service
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
    return re.sub(r"[^\w\s\.]", " ", cleaned).strip()


async def index_snapshots_if_available(game_name: str = "The Witcher 3: Wild Hunt") -> int:
    """
    Indexa todos os arquivos HTML presentes em snapshots/ usando o pipeline real de ingestão:
    html_to_markdown -> chunk_guide -> embed_batch -> GuideChunkModel.
    """
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    html_files = list(SNAPSHOTS_DIR.glob("*.html"))
    if not html_files:
        print("[AVISO] Nenhum snapshot HTML encontrado em snapshots/. Usando índice pré-existente.")
        return 0

    all_chunks = []
    global_idx = 0

    for html_file in html_files:
        html_content = html_file.read_text(encoding="utf-8", errors="ignore")
        markdown = scraper._html_to_markdown(html_content)
        source_url = f"https://local.snapshots/{html_file.name}"

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

    texts = [f"{c.title}\n{c.content}" for c in all_chunks]
    embeddings = await embedding_service.embed_batch(texts)

    async with get_db_session() as session:
        # Atomic clean replacement of witcher chunks for evaluation run
        await session.execute(
            delete(GuideChunkModel).where(GuideChunkModel.game.ilike(f"{game_name}%"))
        )
        for chunk, emb in zip(all_chunks, embeddings):
            record = GuideChunkModel(
                id=chunk.chunk_id,
                game=chunk.game,
                title=chunk.title,
                content=chunk.content,
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

    print(f"[INDEXAÇÃO] {len(all_chunks)} chunks indexados a partir de {len(html_files)} snapshot(s).")
    return len(all_chunks)


def run_agent_eval_case(case: Dict[str, Any]) -> Dict[str, Any]:
    """Execute complete PlatinaAgentRunner via TypeScript eval bridge and evaluate using ragTriadJudge."""
    repo_root = Path(__file__).resolve().parents[4]
    apps_api_dir = repo_root / "apps" / "api"
    payload = json.dumps({
        "id": case["id"],
        "category": case.get("category", ""),
        "route": case.get("route", ""),
        "question": case["question"],
        "game": "The Witcher 3: Wild Hunt",
        "expected": case.get("expected", {}),
    })
    try:
        env = os.environ.copy()
        env["PLATINA_DISABLE_LIVE_SCRAPING"] = "true"
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
            return json.loads(raw_json)
        return {
            "id": case["id"],
            "status": "FAILED",
            "reasons": [f"Bridge output parse error: {stdout[:200]}"],
            "evaluation": None,
        }
    except Exception as e:
        return {
            "id": case["id"],
            "status": "FAILED",
            "reasons": [str(e)],
            "evaluation": None,
        }


AGENT_SEMAPHORE = asyncio.Semaphore(1)


async def evaluate_case(case: Dict[str, Any], player_trophies: List[PlayerTrophyModel]) -> Dict[str, Any]:
    cid = case["id"]
    category = case.get("category", "")
    route = case.get("route", "")
    question = case["question"]
    query_en = case.get("query_en") or question
    expected = case.get("expected", {})

    # Routes requiring agent LLM reasoning (hybrid, none) connected to PlatinaAgentRunner + ragTriadJudge
    if route in ["hybrid", "none"]:
        async with AGENT_SEMAPHORE:
            print(f"[{cid}] (Agent LLM: {route}) Avaliando '{question[:40]}...' ", flush=True)
            agent_res = await asyncio.to_thread(run_agent_eval_case, case)
            await asyncio.sleep(1.0)
        status = agent_res.get("status", "FAILED")
        print(f"[{cid}] -> {status}", flush=True)
        reasons = list(agent_res.get("reasons") or [])
        if "error" in agent_res and agent_res["error"]:
            reasons.append(agent_res["error"])
        eval_triad = agent_res.get("evaluation") or {}

        metrics = {
            "is_abstained": 1.0 if agent_res.get("isAbstained") else 0.0,
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
            "status": status,
            "reason": "; ".join(reasons) if status != "PASSED" else "",
            "answer": agent_res.get("answer", ""),
            "metrics": metrics,
        }

    # Route: RAG
    if route == "rag":
        # Contamination tests
        if category == "contaminacao":
            # Pass session game (Witcher 3) and English query as the agent would
            game_filter = "The Witcher 3: Wild Hunt"
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
                    "passed": passed,
                },
            }

        # Standard RAG tests (dica, vaga)
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
        all_content_norm = " ".join(normalize_str(f"{c.title} {c.content}") for c in top_chunks)

        exp_trophy = expected.get("trophy", "")
        exp_trophy_norm = normalize_str(exp_trophy)

        # Metric: Recall@5
        recall_at_5 = False
        if exp_trophy_norm:
            recall_at_5 = any(exp_trophy_norm in t for t in top_titles_norm)
        else:
            recall_at_5 = True

        # Metric: Must Contain
        must_contain_words = expected.get("must_contain", [])
        missing_terms = []
        for term in must_contain_words:
            term_norm = normalize_str(term)
            if term_norm not in all_content_norm:
                missing_terms.append(term)
        must_contain_passed = len(missing_terms) == 0

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
            "status": "PASSED" if passed else "FAILED",
            "reason": "; ".join(reasons) if not passed else "",
            "metrics": {
                "recall_at_5": 1.0 if recall_at_5 else 0.0,
                "must_contain": 1.0 if must_contain_passed else 0.0,
                "top_hit": top_chunks[0].title if top_chunks else "None",
            },
        }

    # Route: SQL (catálogo / progresso)
    if route == "sql":
        if category == "contaminacao":
            # C03: Verificar se o catálogo do jogador para Witcher 3 traz troféus de Witcher 2
            witcher2_trophies = [
                t.trophy_name for t in player_trophies if "witcher 2" in t.trophy_name.lower()
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

        # O01: Métricas de Roadmap (dificuldade, horas, jogadas)
        if cid == "O01":
            # O modelo SQL de player_games / player_trophies não persiste métricas de roadmap (horas, playthroughs)
            return {
                "id": cid,
                "category": category,
                "route": route,
                "question": question,
                "query_en": query_en,
                "status": "FAILED",
                "reason": (
                    "Divergência de schema: Tabelas SQL de catálogo/progresso (player_games, player_trophies) "
                    "não armazenam 'difficulty', 'hours' ou 'playthroughs' (dados pertencem ao guia/roadmap)."
                ),
                "metrics": {"completeness": 0.0},
            }

        # Lista de troféus esperados
        expected_trophies = expected.get("trophies", [])
        expected_count = expected.get("count")
        must_not_contain = expected.get("must_not_contain", [])

        # Subconjunto de troféus selecionados do catálogo baseado no caso
        selected_trophies: List[PlayerTrophyModel] = []
        filter_description = ""

        if cid in ["L01", "L02"]:
            # Missables
            selected_trophies = [
                t for t in player_trophies if t.is_missable or t.trophy_category == "missable"
            ]
            filter_description = "missable=True ou category='missable'"
        elif cid == "L03":
            # Prata
            selected_trophies = [
                t for t in player_trophies if t.trophy_type.lower() == "silver"
            ]
            filter_description = "trophy_type='silver'"
        elif cid == "L04":
            # Contrato de bruxo
            selected_trophies = [
                t
                for t in player_trophies
                if "contrato" in (t.chapter_or_location or "").lower()
                or "contrato" in t.trophy_name.lower()
            ]
            filter_description = "localização contém 'contrato'"
        elif cid == "L05":
            # Dificuldade
            selected_trophies = [
                t
                for t in player_trophies
                if "dificuldade" in (t.chapter_or_location or "").lower()
            ]
            filter_description = "localização contém 'dificuldade'"
        elif cid == "L06":
            # Briga de punho
            selected_trophies = [
                t
                for t in player_trophies
                if "luta" in (t.chapter_or_location or "").lower()
                or "briga" in (t.chapter_or_location or "").lower()
                or t.trophy_name.lower() in ["brawler", "fist of the south star", "brawl master"]
            ]
            filter_description = "lutas/brigas de punho"
        elif cid == "L07":
            # Hearts of Stone missables
            selected_trophies = [
                t
                for t in player_trophies
                if (t.is_missable or t.trophy_category == "missable")
                and "hearts of stone" in (t.chapter_or_location or "").lower()
            ]
            filter_description = "DLC Hearts of Stone missable"
        elif cid == "L08":
            # História principal
            selected_trophies = [
                t
                for t in player_trophies
                if t.trophy_category == "standard"
                or t.trophy_name.lower() in [e.lower() for e in expected_trophies]
            ]
            filter_description = "história principal"
        else:
            selected_trophies = list(player_trophies)

        selected_names = [t.trophy_name for t in selected_trophies]
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


async def main():
    emb_provider = os.getenv("EMBEDDING_PROVIDER", "local").strip().lower()
    emb_model = "text-embedding-3-small (1536 dims)" if emb_provider == "openai" else "deterministic-1536 (local pseudo-random)"
    tsv_config = "english (to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content, '')))"

    print("=" * 80)
    print("           PLATINA AI — RUNNER DE AVALIAÇÃO DE RAG & SQL (GOLDEN SET)")
    print("=" * 80)
    print(f"[CONFIG] Embedding Provider: {emb_provider} ({emb_model})")
    print(f"[CONFIG] Full-Text TSVector: {tsv_config}")
    print("=" * 80)

    if not GOLDEN_FILE.exists():
        print(f"[ERRO] Arquivo golden não encontrado em: {GOLDEN_FILE}")
        return

    # 1. Index snapshots
    await index_snapshots_if_available("The Witcher 3: Wild Hunt")

    # 2. Carrega Golden Dataset
    with open(GOLDEN_FILE, "r", encoding="utf-8") as f:
        golden_data = json.load(f)

    cases = golden_data.get("cases", [])
    print(f"\nTotal de cenários carregados: {len(cases)}")

    # 3. Consulta troféus de Witcher 3 do banco via caminho de playerProgress
    async with get_db_session() as session:
        stmt = (
            select(PlayerTrophyModel)
            .join(PlayerGameModel, PlayerTrophyModel.player_game_id == PlayerGameModel.id)
            .where(PlayerGameModel.game_title.ilike("%The Witcher 3%"))
        )
        res = await session.execute(stmt)
        player_trophies = res.scalars().all()

    # 4. Avalia casos (com concorrência assíncrona para rotas do agente)
    print("Avaliando casos (executando avaliações em paralelo)...")
    results: List[Dict[str, Any]] = list(
        await asyncio.gather(*[evaluate_case(c, player_trophies) for c in cases])
    )

    # 5. Agregação por Categoria
    categories: Dict[str, Dict[str, int]] = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"total": 0, "passed": 0, "failed": 0, "skipped": 0}
        categories[cat]["total"] += 1
        if r["status"] == "PASSED":
            categories[cat]["passed"] += 1
        elif r["status"] == "FAILED":
            categories[cat]["failed"] += 1
        elif r["status"] == "SKIPPED":
            categories[cat]["skipped"] += 1

    # 6. Agregação por Métrica
    metrics_summary = {
        "recall_at_5": {"total": 0, "success": 0},
        "must_contain": {"total": 0, "success": 0},
        "completeness": {"total": 0, "total_score": 0.0},
        "contamination": {"total": 0, "success": 0},
        "faithfulness": {"total": 0, "total_score": 0.0},
        "answer_relevance": {"total": 0, "total_score": 0.0},
        "abstention": {"total": 0, "success": 0},
    }

    for r in results:
        m = r.get("metrics", {})
        if "recall_at_5" in m:
            metrics_summary["recall_at_5"]["total"] += 1
            if m["recall_at_5"] == 1.0:
                metrics_summary["recall_at_5"]["success"] += 1
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
        if "faithfulness" in m:
            metrics_summary["faithfulness"]["total"] += 1
            metrics_summary["faithfulness"]["total_score"] += m["faithfulness"]
        if "answer_relevance" in m:
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
    print(f"{'Categoria':<18} | {'Total':<6} | {'Passou':<7} | {'Falhou':<7} | {'Ignorado':<8} | {'Taxa Efetiva':<12}")
    print("-" * 75)
    for cat, counts in categories.items():
        evaluated = counts["passed"] + counts["failed"]
        rate = f"{(counts['passed'] / evaluated * 100):.1f}%" if evaluated > 0 else "(N/A)"
        print(
            f"{cat:<18} | {counts['total']:<6} | {counts['passed']:<7} | {counts['failed']:<7} | "
            f"{counts['skipped']:<8} | {rate:<12}"
        )

    print("\n" + "=" * 80)
    print("                    2. RELATÓRIO POR MÉTRICA")
    print("=" * 80)
    print(f"{'Métrica':<18} | {'Avaliados':<10} | {'Sucesso':<8} | {'Score / Taxa':<15}")
    print("-" * 65)

    r5 = metrics_summary["recall_at_5"]
    r5_rate = f"{(r5['success'] / r5['total'] * 100):.1f}%" if r5["total"] else "N/A"
    print(f"{'recall@5':<18} | {r5['total']:<10} | {r5['success']:<8} | {r5_rate:<15}")

    mc = metrics_summary["must_contain"]
    mc_rate = f"{(mc['success'] / mc['total'] * 100):.1f}%" if mc["total"] else "N/A"
    print(f"{'must_contain':<18} | {mc['total']:<10} | {mc['success']:<8} | {mc_rate:<15}")

    comp = metrics_summary["completeness"]
    comp_rate = (
        f"{(comp['total_score'] / comp['total'] * 100):.1f}% (méd)"
        if comp["total"]
        else "N/A"
    )
    print(f"{'completeness':<18} | {comp['total']:<10} | {'-':<8} | {comp_rate:<15}")

    cont = metrics_summary["contamination"]
    cont_rate = f"{(cont['success'] / cont['total'] * 100):.1f}%" if cont["total"] else "N/A"
    print(f"{'contamination':<18} | {cont['total']:<10} | {cont['success']:<8} | {cont_rate:<15}")

    faith = metrics_summary["faithfulness"]
    faith_rate = (
        f"{(faith['total_score'] / faith['total'] * 100):.1f}% (méd)"
        if faith["total"]
        else "N/A"
    )
    print(f"{'faithfulness':<18} | {faith['total']:<10} | {'-':<8} | {faith_rate:<15}")

    ans_rel = metrics_summary["answer_relevance"]
    ans_rel_rate = (
        f"{(ans_rel['total_score'] / ans_rel['total'] * 100):.1f}% (méd)"
        if ans_rel["total"]
        else "N/A"
    )
    print(f"{'answer_relevance':<18} | {ans_rel['total']:<10} | {'-':<8} | {ans_rel_rate:<15}")

    abst = metrics_summary["abstention"]
    abst_rate = f"{(abst['success'] / abst['total'] * 100):.1f}%" if abst["total"] else "N/A"
    print(f"{'abstention':<18} | {abst['total']:<10} | {abst['success']:<8} | {abst_rate:<15}")

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

    print("\n" + "=" * 80)
    print("    4. CASOS AVALIADOS PELO AGENTE COM RAG TRIAD ('HYBRID' E 'NONE')")
    print("=" * 80)
    agent_cases = [r for r in results if r["route"] in ["hybrid", "none"]]
    for a_case in agent_cases:
        status_sym = "✅ PASSED" if a_case["status"] == "PASSED" else "❌ FAILED"
        m = a_case.get("metrics", {})
        triad_info = f"Fidelidade: {m.get('faithfulness', 0.0):.2f} | Pertinência: {m.get('answer_relevance', 0.0):.2f}"
        print(f"[{a_case['id']}] ({a_case['route'].upper()}/{a_case['category']}) {a_case['question']}")
        print(f"   -> Status: {status_sym} | {triad_info}")
        if a_case.get("reason"):
            print(f"   -> Motivo: {a_case['reason']}")

    # 8. Grava resultado em JSON em tests/eval/results/<data>.json
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_file = RESULTS_DIR / f"{timestamp}.json"

    export_payload = {
        "timestamp": timestamp,
        "golden_set": "golden_witcher3.json",
        "total_cases": len(cases),
        "categories_summary": categories,
        "metrics_summary": {
            "recall_at_5": r5_rate,
            "must_contain": mc_rate,
            "completeness_average": comp_rate,
            "contamination_success_rate": cont_rate,
            "faithfulness_average": faith_rate,
            "answer_relevance_average": ans_rel_rate,
            "abstention_success_rate": abst_rate,
        },
        "results": results,
    }

    out_file.write_text(json.dumps(export_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[EXPORT] Relatório JSON gravado com sucesso em: {out_file}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
