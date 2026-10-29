import time
from typing import List, Dict, Any, Optional
from sqlalchemy import select, and_, func
from src.schemas.search import SearchQueryRequest, SearchResultItem, SearchResponse
from src.models.chunk import GuideChunkModel
from src.models.catalog import GameModel
from src.services.entity_linker import get_canonical_game_id
from src.services.embedding import embedding_service
from src.services.reranker import reranker_service
from src.database import get_db_session


class VectorSearchService:
    """
    Executes hybrid retrieval combining dense vector cosine distance and sparse full-text search
    (BM25 via tsvector) with Reciprocal Rank Fusion (RRF) and similarity threshold cutoffs.
    """

    async def search(self, request: SearchQueryRequest) -> SearchResponse:
        t_retrieval_start = time.perf_counter()
        # 1. Embed user query into vector space
        query_vector = await embedding_service.embed_query(request.query)

        # 2. Resolve game to canonical game_id if provided
        resolved_game_id: Optional[str] = None
        if request.game:
            clean_game = request.game.strip()
            slug = get_canonical_game_id(clean_game)
            async with get_db_session() as session:
                stmt_game = (
                    select(GameModel.id)
                    .where(
                        (GameModel.id == clean_game.lower())
                        | (GameModel.id == slug)
                        | (GameModel.title.ilike(clean_game))
                        | (GameModel.aliases.contains([clean_game]))
                    )
                    .limit(1)
                )
                res_game = (await session.execute(stmt_game)).scalars().first()
                if not res_game:
                    stmt_partial = select(GameModel.id).where(GameModel.title.ilike(f"%{clean_game}%")).limit(1)
                    res_game = (await session.execute(stmt_partial)).scalars().first()
                resolved_game_id = res_game

        # 3. Build common filtering conditions
        conditions = []
        if resolved_game_id:
            # Insight: Exact game_id equality filter on guide_chunks rather than ILIKE
            conditions.append(GuideChunkModel.game_id == resolved_game_id)
        elif request.game:
            conditions.append(GuideChunkModel.game.ilike(f"%{request.game.strip()}%"))
        if request.missable_only:
            conditions.append(GuideChunkModel.is_missable.is_(True))

        candidate_limit = max(request.limit * 5, 25)

        # 4. Dense Vector Retrieval (pgvector cosine distance)
        distance_col = GuideChunkModel.embedding.cosine_distance(query_vector).label("distance")
        stmt_dense = select(GuideChunkModel, distance_col)
        if conditions:
            stmt_dense = stmt_dense.where(and_(*conditions))
        stmt_dense = stmt_dense.order_by(distance_col).limit(candidate_limit)

        # 4. Sparse Text Retrieval (PostgreSQL full-text search plainto_tsquery in English)
        # Insight: Internal processing operates strictly in English for canonical matching
        ts_query = func.plainto_tsquery("english", request.query)
        sparse_match_cond = GuideChunkModel.tsv.op("@@")(ts_query)
        ts_rank_col = func.ts_rank(GuideChunkModel.tsv, ts_query).label("ts_rank")

        sparse_conditions = list(conditions) + [sparse_match_cond]
        stmt_sparse = (
            select(GuideChunkModel, ts_rank_col)
            .where(and_(*sparse_conditions))
            .order_by(ts_rank_col.desc())
            .limit(candidate_limit)
        )

        async with get_db_session() as session:
            dense_rows = (await session.execute(stmt_dense)).all()
            sparse_rows = (await session.execute(stmt_sparse)).all()

        # 5. Build rank maps and models for Reciprocal Rank Fusion (RRF)
        dense_rank_map: Dict[str, int] = {}
        dense_sim_map: Dict[str, float] = {}
        chunk_models: Dict[str, GuideChunkModel] = {}

        for rank, (model, distance) in enumerate(dense_rows, start=1):
            dist_val = float(distance) if distance is not None else 1.0
            dense_sim = max(0.0, min(1.0, 1.0 - (dist_val / 2.0)))
            dense_rank_map[model.id] = rank
            dense_sim_map[model.id] = dense_sim
            chunk_models[model.id] = model

        sparse_rank_map: Dict[str, int] = {}
        for rank, (model, _ts_rank) in enumerate(sparse_rows, start=1):
            sparse_rank_map[model.id] = rank
            chunk_models[model.id] = model

        # 6. Reciprocal Rank Fusion (k=60) & Normalized Similarity Scoring
        k = 60.0
        candidates: List[Dict[str, Any]] = []

        for cid, model in chunk_models.items():
            r_dense: Optional[int] = dense_rank_map.get(cid)
            r_sparse: Optional[int] = sparse_rank_map.get(cid)

            dense_rrf = 1.0 / (k + r_dense) if r_dense is not None else 0.0
            sparse_rrf = 1.0 / (k + r_sparse) if r_sparse is not None else 0.0
            rrf_score = dense_rrf + sparse_rrf

            dense_sim = dense_sim_map.get(cid, 0.0)
            if r_sparse is not None:
                sparse_sim = max(0.0, 0.85 - (r_sparse - 1) * 0.05)
            else:
                sparse_sim = 0.0

            # Boost hybrid match when dense vector confirms semantic similarity
            if r_sparse is not None and r_dense is not None:
                normalized_score = min(1.0, max(dense_sim, sparse_sim) + 0.10)
            elif r_dense is not None and dense_sim > 0.5:
                # Strong pure semantic match (e.g. paraphrase) preserves dense similarity
                normalized_score = dense_sim
            else:
                normalized_score = max(dense_sim, sparse_sim)

            # 7. Threshold cutoff filtering
            # In evaluation or broad searches, allow raw RRF score ordering
            if request.min_similarity > 0.0 and normalized_score < request.min_similarity:
                continue

            candidates.append({
                "model": model,
                "rrf_score": rrf_score,
                "similarity_score": round(normalized_score, 4),
            })

        # 8. Sort candidates by RRF rank descending (with similarity as tiebreaker)
        candidates.sort(key=lambda x: (x["rrf_score"], x["similarity_score"]), reverse=True)
        candidate_pool = candidates[:max(request.limit * 3, 15)]

        candidate_items: List[SearchResultItem] = [
            SearchResultItem(
                id=item["model"].id,
                game=item["model"].game,
                title=item["model"].title,
                content=item["model"].content,
                is_missable=item["model"].is_missable,
                source_url=item["model"].source_url,
                similarity_score=item["similarity_score"],
                metadata=item["model"].metadata_ or {},
            )
            for item in candidate_pool
        ]
        retrieval_latency_ms = round((time.perf_counter() - t_retrieval_start) * 1000.0, 2)

        # 9. Cross-Scoring Reranker
        t_rerank_start = time.perf_counter()
        results = reranker_service.rerank(
            query=request.query,
            candidates=candidate_items,
            top_k=request.limit,
        )

        # Enforce minimum similarity cutoff post-reranking
        results = [r for r in results if r.similarity_score >= request.min_similarity]
        reranker_latency_ms = round((time.perf_counter() - t_rerank_start) * 1000.0, 2)

        return SearchResponse(
            query=request.query,
            total_results=len(results),
            results=results,
            retrieval_latency_ms=retrieval_latency_ms,
            reranker_latency_ms=reranker_latency_ms,
        )


vector_search_service = VectorSearchService()
