from typing import List
from sqlalchemy import select, and_
from src.schemas.search import SearchQueryRequest, SearchResultItem, SearchResponse
from src.models.chunk import GuideChunkModel
from src.services.embedding import embedding_service
from src.database import get_db_session


class VectorSearchService:
    """
    Executes semantic similarity search over trophy guide embeddings in PostgreSQL using pgvector.
    Supports hybrid filtering (game filter, missable flag) combined with cosine distance.
    """

    async def search(self, request: SearchQueryRequest) -> SearchResponse:
        # 1. Embed user query into vector space
        query_vector = await embedding_service.embed_query(request.query)

        # 2. Build SQL conditions for hybrid retrieval
        conditions = []
        if request.game:
            conditions.append(GuideChunkModel.game.ilike(f"%{request.game.strip()}%"))
        if request.missable_only:
            conditions.append(GuideChunkModel.is_missable.is_(True))

        # 3. Query pgvector using cosine distance operator (<=>)
        # Cosine distance ranges from 0.0 (identical) to 2.0 (opposite).
        # We convert to similarity: similarity = 1 - (distance / 2) or max(0, 1 - distance)
        distance_col = GuideChunkModel.embedding.cosine_distance(query_vector).label("distance")

        stmt = select(
            GuideChunkModel,
            distance_col
        )

        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(distance_col).limit(request.limit)

        async with get_db_session() as session:
            result = await session.execute(stmt)
            rows = result.all()

        results: List[SearchResultItem] = []
        for model, distance in rows:
            dist_val = float(distance) if distance is not None else 1.0
            similarity = max(0.0, min(1.0, 1.0 - (dist_val / 2.0)))

            results.append(
                SearchResultItem(
                    id=model.id,
                    game=model.game,
                    title=model.title,
                    content=model.content,
                    is_missable=model.is_missable,
                    source_url=model.source_url,
                    similarity_score=round(similarity, 4),
                    metadata=model.metadata_ or {},
                )
            )

        return SearchResponse(
            query=request.query,
            total_results=len(results),
            results=results,
        )


vector_search_service = VectorSearchService()
