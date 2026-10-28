#!/usr/bin/env python3
"""
Script de medição e benchmark da categoria Paráfrase (2x3):
Modos de busca:
1. Densa pura (apenas cosine distance pgvector)
2. Esparsa pura (apenas tsvector @@ plainto_tsquery)
3. Híbrida (Dense + Sparse com RRF)

Provedores:
- local (hash determinístico)
- fastembed (BAAI/bge-small-en-v1.5)
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

SERVICES_INGEST_DIR = Path(__file__).resolve().parents[2]
if str(SERVICES_INGEST_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_INGEST_DIR))

from sqlalchemy import and_, func, select
from src.database import get_db_session
from src.models.chunk import GuideChunkModel
from src.schemas.chunk import IngestGuideRequest
from src.services.chunker import chunker, build_context_prefix
from src.services.embedding import get_embedding_service
from src.services.scraper import scraper

SNAPSHOT_FILE = SERVICES_INGEST_DIR / "tests" / "golden" / "snapshots" / "dicas.html"

PARAPHRASES = [
    ("P01", "Slaughter twenty cattle", "Moo-rderer"),
    ("P02", "Push foes off cliffs using a telekinetic blast", "Humpty Dumpty"),
    ("P03", "Skid down a slope for a long time without stopping", "Rad Steez, Bro!"),
    ("P04", "Defeat archers by sending their projectiles back at them", "Return to Sender"),
    ("P05", "Win a boxing match flawlessly", "Fist of the South Star"),
    ("P06", "Finish first in every equestrian competition", "Fast and Furious"),
    ("P07", "Learn recipes for several kinds of explosives", "Bombardier"),
    ("P08", "Wipe out a group of enemies extremely quickly", "Butcher of Blaviken"),
]


async def reindex_witcher(emb_service):
    html_content = SNAPSHOT_FILE.read_text(encoding="utf-8", errors="ignore")
    markdown = scraper._html_to_markdown(html_content)
    req = IngestGuideRequest(game="The Witcher 3: Wild Hunt", source_url="https://local.snapshots/dicas.html", content=markdown)
    chunks = chunker.chunk_guide(req)

    texts = [
        f"{build_context_prefix(c.game, c.title, c.content, c.metadata.get('source_url', ''))}\n{c.content}"
        for c in chunks
    ]
    embeddings = await emb_service.embed_batch(texts)

    async with get_db_session() as session:
        from sqlalchemy import delete
        await session.execute(delete(GuideChunkModel).where(GuideChunkModel.game.ilike("%Witcher 3%")))
        for c, emb in zip(chunks, embeddings):
            prefix = build_context_prefix(c.game, c.title, c.content, c.metadata.get("source_url", "local"))
            record = GuideChunkModel(
                id=c.chunk_id or c.title,
                game=c.game,
                title=c.title,
                content=c.content,
                context_prefix=prefix,
                is_missable=c.is_missable,
                source_url="local",
                metadata_=c.metadata,
                embedding=emb,
            )
            session.add(record)
        await session.commit()


async def search_mode(query: str, mode: str, emb_service) -> List[str]:
    async with get_db_session() as session:
        game_cond = GuideChunkModel.game.ilike("%Witcher 3%")

        if mode == "dense":
            q_emb = await emb_service.embed_query(query)
            distance_col = GuideChunkModel.embedding.cosine_distance(q_emb).label("distance")
            stmt = select(GuideChunkModel.title).where(game_cond).order_by(distance_col).limit(5)
            rows = (await session.execute(stmt)).scalars().all()
            return list(rows)

        if mode == "sparse":
            ts_query = func.plainto_tsquery("english", query)
            match_cond = GuideChunkModel.tsv.op("@@")(ts_query)
            ts_rank = func.ts_rank(GuideChunkModel.tsv, ts_query).label("ts_rank")
            stmt = select(GuideChunkModel.title).where(and_(game_cond, match_cond)).order_by(ts_rank.desc()).limit(5)
            rows = (await session.execute(stmt)).scalars().all()
            return list(rows)

        if mode == "hybrid":
            # Combined with RRF
            q_emb = await emb_service.embed_query(query)
            distance_col = GuideChunkModel.embedding.cosine_distance(q_emb).label("distance")
            stmt_dense = select(GuideChunkModel, distance_col).where(game_cond).order_by(distance_col).limit(20)
            dense_rows = (await session.execute(stmt_dense)).all()

            ts_query = func.plainto_tsquery("english", query)
            match_cond = GuideChunkModel.tsv.op("@@")(ts_query)
            ts_rank = func.ts_rank(GuideChunkModel.tsv, ts_query).label("ts_rank")
            stmt_sparse = select(GuideChunkModel, ts_rank).where(and_(game_cond, match_cond)).order_by(ts_rank.desc()).limit(20)
            sparse_rows = (await session.execute(stmt_sparse)).all()

            dense_ranks = {model.id: (rank, model) for rank, (model, _) in enumerate(dense_rows, 1)}
            sparse_ranks = {model.id: (rank, model) for rank, (model, _) in enumerate(sparse_rows, 1)}

            all_ids = set(dense_ranks.keys()).union(sparse_ranks.keys())
            scored = []
            k = 60.0
            for cid in all_ids:
                r_d = dense_ranks[cid][0] if cid in dense_ranks else None
                r_s = sparse_ranks[cid][0] if cid in sparse_ranks else None
                model = dense_ranks[cid][1] if cid in dense_ranks else sparse_ranks[cid][1]
                rrf = (1.0 / (k + r_d) if r_d else 0.0) + (1.0 / (k + r_s) if r_s else 0.0)
                scored.append((rrf, model.title))

            scored.sort(key=lambda x: x[0], reverse=True)
            return [t for _, t in scored[:5]]

    return []


async def eval_paraphrases(provider: str) -> Dict[str, float]:
    os.environ["EMBEDDING_PROVIDER"] = provider
    os.environ["EMBEDDING_DIMENSIONS"] = "384" if provider == "fastembed" else "1536"
    emb_service = get_embedding_service()

    await reindex_witcher(emb_service)

    results = {}
    for mode in ["dense", "sparse", "hybrid"]:
        hits = 0
        for pid, query, trophy in PARAPHRASES:
            top_titles = await search_mode(query, mode, emb_service)
            top_norm = " ".join(t.lower() for t in top_titles)
            is_hit = trophy.lower() in top_norm
            if is_hit:
                hits += 1
        results[mode] = hits / len(PARAPHRASES)
    return results


async def main():
    print("Executando benchmark de paráfrases (2x3)...")
    res_local = await eval_paraphrases("local")
    print("Local finalizado:", res_local)

    res_fast = await eval_paraphrases("fastembed")
    print("Fastembed finalizado:", res_fast)

    print("\n" + "=" * 60)
    print("     TABELA 2x3 DE RECALL@5 — CATEGORIA PARÁFRASE")
    print("=" * 60)
    print(f"{'Provider':<15} | {'Densa (Vetor)':<15} | {'Esparsa (TSV)':<15} | {'Híbrida (RRF)':<15}")
    print("-" * 65)
    print(f"{'local (hash)':<15} | {res_local['dense']*100:<14.1f}% | {res_local['sparse']*100:<14.1f}% | {res_local['hybrid']*100:<14.1f}%")
    print(f"{'fastembed (bge)':<15} | {res_fast['dense']*100:<14.1f}% | {res_fast['sparse']*100:<14.1f}% | {res_fast['hybrid']*100:<14.1f}%")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
